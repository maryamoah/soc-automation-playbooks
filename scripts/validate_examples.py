#!/usr/bin/env python3
"""
validate_examples.py
====================

Validate the files in ``examples/`` against the schemas in ``schemas/``.

Uses ``jsonschema`` when it is installed. When it is not, falls back to a small
bundled validator that supports the subset of JSON Schema actually used by this
repository: ``type``, ``enum``, ``const``, ``required``, ``properties``,
``additionalProperties``, ``items``, ``minItems``, ``minLength``, ``minimum``,
``maximum``, ``pattern``, ``anyOf``, ``oneOf``, ``allOf``, ``$defs``/``$ref``
(local pointers and sibling-file references).

The fallback exists so CI and a fresh clone both work with no install step. It
is not a complete JSON Schema implementation and is not intended to be.

Usage
-----
    python3 scripts/validate_examples.py [--root .]

Exit codes
----------
    0   all examples valid
    1   at least one example failed validation
    2   a mapped example or schema file is missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# What gets validated against what.
#   (example path, schema name, json-pointer-ish subkey or None for whole doc)
# --------------------------------------------------------------------------
VALIDATION_MAP: list[tuple[str, str, str | None]] = [
    ("examples/outputs/informational-triage.json", "ai-triage-result.schema.json", None),
    ("examples/outputs/suspicious-triage.json", "ai-triage-result.schema.json", None),
    ("examples/outputs/malicious-triage.json", "ai-triage-result.schema.json", None),
    ("examples/outputs/insufficient-evidence.json", "ai-triage-result.schema.json", None),
    ("examples/enrichment/virustotal-response.json", "enrichment-result.schema.json", "normalized"),
    ("examples/enrichment/abuseipdb-response.json", "enrichment-result.schema.json", "normalized"),
]

# Slack-shaped inputs: the embedded event text is validated as a Wazuh alert
# where it parses as JSON.
SLACK_INPUTS: list[tuple[str, bool]] = [
    ("examples/inputs/wazuh-firewall-alert.json", True),
    ("examples/inputs/wazuh-windows-alert.json", True),
    ("examples/inputs/wazuh-rule-id-only-alert.json", True),
    ("examples/inputs/slack-event.json", False),
]

WAZUH_SCHEMA = "wazuh-alert.schema.json"


# --------------------------------------------------------------------------
# Minimal fallback validator
# --------------------------------------------------------------------------
class MiniValidationError(Exception):
    pass


TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _check_type(value: Any, expected: str, path: str) -> None:
    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise MiniValidationError(f"{path}: expected integer, got {type(value).__name__}")
        return
    if expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MiniValidationError(f"{path}: expected number, got {type(value).__name__}")
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            raise MiniValidationError(f"{path}: expected boolean, got {type(value).__name__}")
        return
    python_type = TYPE_MAP.get(expected)
    if python_type is None:
        return  # unknown type keyword: ignore rather than false-fail
    if not isinstance(value, python_type):
        raise MiniValidationError(f"{path}: expected {expected}, got {type(value).__name__}")


def _resolve_ref(ref: str, root: dict, schema_dir: Path) -> dict:
    if ref.startswith("#/"):
        node: Any = root
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or token not in node:
                raise MiniValidationError(f"unresolvable $ref {ref}")
            node = node[token]
        if not isinstance(node, dict):
            raise MiniValidationError(f"$ref {ref} does not point at a schema")
        return node
    # Sibling file reference, e.g. "enrichment-result.schema.json"
    candidate = schema_dir / ref.split("#")[0]
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    raise MiniValidationError(f"unresolvable $ref {ref}")


def mini_validate(
    value: Any,
    schema: dict,
    root: dict,
    schema_dir: Path,
    path: str = "$",
) -> None:
    if not isinstance(schema, dict):
        return

    if "$ref" in schema:
        target = _resolve_ref(schema["$ref"], root, schema_dir)
        mini_validate(value, target, target if "$ref" not in schema else root, schema_dir, path)
        return

    if "const" in schema and value != schema["const"]:
        raise MiniValidationError(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise MiniValidationError(f"{path}: {value!r} not in enum {schema['enum']}")

    declared = schema.get("type")
    if isinstance(declared, str):
        _check_type(value, declared, path)
    elif isinstance(declared, list):
        for candidate in declared:
            try:
                _check_type(value, candidate, path)
                break
            except MiniValidationError:
                continue
        else:
            raise MiniValidationError(f"{path}: expected one of {declared}")

    for keyword in ("allOf",):
        for sub in schema.get(keyword, []):
            mini_validate(value, sub, root, schema_dir, path)

    for keyword in ("anyOf", "oneOf"):
        options = schema.get(keyword)
        if options:
            for option in options:
                try:
                    mini_validate(value, option, root, schema_dir, path)
                    break
                except MiniValidationError:
                    continue
            else:
                raise MiniValidationError(f"{path}: no {keyword} branch matched")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise MiniValidationError(f"{path}: shorter than minLength {schema['minLength']}")
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, value):
            raise MiniValidationError(f"{path}: {value!r} does not match {pattern}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise MiniValidationError(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise MiniValidationError(f"{path}: above maximum {schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise MiniValidationError(f"{path}: fewer than minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                mini_validate(item, item_schema, root, schema_dir, f"{path}[{index}]")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise MiniValidationError(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, sub_value in value.items():
            if key in properties:
                mini_validate(sub_value, properties[key], root, schema_dir, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                raise MiniValidationError(f"{path}: unexpected property {key!r}")


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance: Any, schema: dict, schema_dir: Path) -> list[str]:
    """Return a list of error strings (empty means valid)."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        try:
            mini_validate(instance, schema, schema, schema_dir)
            return []
        except MiniValidationError as exc:
            return [str(exc)]

    resolver_store = {}
    for sibling in schema_dir.glob("*.schema.json"):
        doc = load_json(sibling)
        resolver_store[sibling.name] = doc
        if "$id" in doc:
            resolver_store[doc["$id"]] = doc

    try:
        validator_cls = jsonschema.validators.validator_for(schema)
        resolver = jsonschema.RefResolver(
            base_uri=schema_dir.as_uri() + "/", referrer=schema, store=resolver_store
        )
        validator = validator_cls(schema, resolver=resolver)
        return [
            f"{'.'.join(str(p) for p in err.absolute_path) or '$'}: {err.message}"
            for err in validator.iter_errors(instance)
        ]
    except Exception as exc:  # noqa: BLE001 - surface tool problems, don't mask them
        return [f"validator error: {exc}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate examples against schemas.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    schema_dir = root / "schemas"

    if not schema_dir.is_dir():
        print(f"error: {schema_dir} not found", file=sys.stderr)
        return 2

    try:
        import jsonschema  # type: ignore  # noqa: F401

        print("Validator: jsonschema")
    except ImportError:
        print("Validator: bundled fallback (install 'jsonschema' for full coverage)")
    print()

    failures = 0
    missing = 0

    # ---- mapped examples -------------------------------------------------
    for example_rel, schema_name, subkey in VALIDATION_MAP:
        example_path = root / example_rel
        schema_path = schema_dir / schema_name
        if not example_path.is_file():
            print(f"  MISSING  {example_rel}")
            missing += 1
            continue
        if not schema_path.is_file():
            print(f"  MISSING  schemas/{schema_name}")
            missing += 1
            continue

        instance = load_json(example_path)
        if subkey is not None:
            if subkey not in instance:
                print(f"  FAIL  {example_rel}: no '{subkey}' key to validate")
                failures += 1
                continue
            instance = instance[subkey]

        errors = validate(instance, load_json(schema_path), schema_dir)
        label = f"{example_rel}" + (f" [{subkey}]" if subkey else "")
        if errors:
            failures += 1
            print(f"  FAIL  {label}  ->  {schema_name}")
            for error in errors:
                print(f"          {error}")
        else:
            print(f"  ok    {label}  ->  {schema_name}")

    # ---- Slack-shaped inputs --------------------------------------------
    print()
    wazuh_schema_path = schema_dir / WAZUH_SCHEMA
    for example_rel, expect_wazuh in SLACK_INPUTS:
        example_path = root / example_rel
        if not example_path.is_file():
            print(f"  MISSING  {example_rel}")
            missing += 1
            continue

        doc = load_json(example_path)
        event = doc.get("body", {}).get("event")
        if not isinstance(event, dict):
            print(f"  FAIL  {example_rel}: no body.event object")
            failures += 1
            continue
        for field in ("type", "text", "channel", "user", "ts"):
            if field not in event:
                print(f"  FAIL  {example_rel}: body.event missing {field!r}")
                failures += 1
                break
        else:
            if not expect_wazuh:
                print(f"  ok    {example_rel}  ->  Slack event envelope")
                continue
            try:
                embedded = json.loads(event["text"])
            except json.JSONDecodeError as exc:
                print(f"  FAIL  {example_rel}: body.event.text is not JSON: {exc}")
                failures += 1
                continue
            errors = validate(embedded, load_json(wazuh_schema_path), schema_dir)
            if errors:
                failures += 1
                print(f"  FAIL  {example_rel} [embedded alert]  ->  {WAZUH_SCHEMA}")
                for error in errors:
                    print(f"          {error}")
            else:
                print(f"  ok    {example_rel} [embedded alert]  ->  {WAZUH_SCHEMA}")

    print()
    if missing:
        print(f"{missing} file(s) missing.")
        return 2
    if failures:
        print(f"{failures} example(s) failed validation.")
        return 1
    print("All examples valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
