"""
validate_json.py
================

Parse every ``.json`` file in the repository and run structural sanity checks on
the ones we know the shape of.

Checks performed
----------------
1.  Every ``.json`` file parses as JSON.
2.  Every file in ``schemas/`` looks like a JSON Schema (has ``$schema``,
     ``title``, ``type`` or ``$defs``).
3.  Every ``*.sanitized.json`` under ``workflows/n8n/`` is a plausible n8n
     export: has ``nodes`` and ``connections``, every connection target exists,
     every node has ``name``/``type``/``parameters``, and node names are unique.
4.  Sanitized exports are inactive and carry no instance-bound identifiers.

Usage
-----
    python3 scripts/validate_json.py [--root .] [--quiet]

Exit codes
----------
    0   all checks passed
    1   one or more checks failed
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache"}

# n8n keys that must not survive sanitization.
FORBIDDEN_EXPORT_KEYS = ("id", "versionId")
FORBIDDEN_META_KEYS = ("instanceId",)


class Results:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checked = 0

    def error(self, path: Path, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warn(self, path: Path, message: str) -> None:
        self.warnings.append(f"{path}: {message}")


def iter_json_files(root: Path):
    for path in sorted(root.rglob("*.json")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def check_schema_file(path: Path, doc: object, results: Results) -> None:
    if not isinstance(doc, dict):
        results.error(path, "schema file is not a JSON object")
        return
    if "$schema" not in doc:
        results.warn(path, "no $schema declared")
    if "title" not in doc:
        results.warn(path, "no title")
    if not any(key in doc for key in ("type", "$defs", "properties", "anyOf", "oneOf")):
        results.error(path, "does not look like a schema (no type/properties/$defs)")


def check_n8n_export(path: Path, doc: object, results: Results) -> None:
    if not isinstance(doc, dict):
        results.error(path, "n8n export is not a JSON object")
        return

    nodes = doc.get("nodes")
    connections = doc.get("connections")

    if not isinstance(nodes, list) or not nodes:
        results.error(path, "missing or empty 'nodes'")
        return
    if not isinstance(connections, dict):
        results.error(path, "missing 'connections'")
        return

    names: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            results.error(path, f"node[{index}] is not an object")
            continue
        name = node.get("name")
        if not name:
            results.error(path, f"node[{index}] has no name")
            continue
        if name in names:
            results.error(path, f"duplicate node name: {name!r}")
        names.add(name)
        if "type" not in node:
            results.error(path, f"node {name!r} has no type")
        if "parameters" not in node:
            results.error(path, f"node {name!r} has no parameters")

    # Every connection endpoint must resolve to a real node.
    for source, outputs in connections.items():
        if source not in names:
            results.error(path, f"connection from unknown node {source!r}")
        if not isinstance(outputs, dict):
            results.error(path, f"connections[{source!r}] is not an object")
            continue
        for output_list in outputs.values():
            if not isinstance(output_list, list):
                continue
            for output in output_list:
                if not isinstance(output, list):
                    continue
                for target in output:
                    if not isinstance(target, dict):
                        continue
                    node_name = target.get("node")
                    if node_name not in names:
                        results.error(
                            path, f"connection {source!r} -> unknown node {node_name!r}"
                        )

    # Sanitization invariants.
    if path.name.endswith(".sanitized.json"):
        if doc.get("active") is True:
            results.error(path, "sanitized export must have active: false")
        for key in FORBIDDEN_EXPORT_KEYS:
            if key in doc:
                results.error(path, f"sanitized export still contains top-level {key!r}")
        meta = doc.get("meta")
        if isinstance(meta, dict):
            for key in FORBIDDEN_META_KEYS:
                if key in meta:
                    results.error(path, f"sanitized export still contains meta.{key}")
        if doc.get("pinData"):
            results.error(path, "sanitized export still contains pinData")

        # Report unreachable nodes: useful signal, not an error, because the
        # AI SOC Assistant genuinely has unwired Switch outputs.
        reachable: set[str] = set()
        for source, outputs in connections.items():
            reachable.add(source)
            for output_list in outputs.values():
                if not isinstance(output_list, list):
                    continue
                for output in output_list:
                    if not isinstance(output, list):
                        continue
                    for target in output:
                        if isinstance(target, dict) and target.get("node"):
                            reachable.add(target["node"])
        orphans = sorted(names - reachable)
        if orphans:
            results.warn(path, f"nodes not referenced by any connection: {orphans}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate every JSON file in the repo.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    results = Results()

    for path in iter_json_files(root):
        results.checked += 1
        rel = path.relative_to(root)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            results.error(rel, f"invalid JSON: {exc}")
            continue
        except UnicodeDecodeError as exc:
            results.error(rel, f"not UTF-8: {exc}")
            continue

        parts = rel.parts
        if parts and parts[0] == "schemas":
            check_schema_file(rel, doc, results)
        elif rel.name.endswith(".sanitized.json") or (
            len(parts) > 1 and parts[0] == "workflows" and parts[1] == "n8n"
            and isinstance(doc, dict) and "nodes" in doc
        ):
            check_n8n_export(rel, doc, results)

        if not args.quiet:
            print(f"  ok  {rel}")

    print()
    print(f"Checked {results.checked} JSON file(s).")

    for warning in results.warnings:
        print(f"  warn  {warning}")
    for error in results.errors:
        print(f"  FAIL  {error}")

    if results.errors:
        print(f"\n{len(results.errors)} error(s).")
        return 1
    print("All JSON valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
