#!/usr/bin/env python3
"""
sanitize_n8n_export.py
======================

Strip environment-specific and sensitive values out of an n8n workflow export
so it can be published safely.

This script is deliberately conservative: it *removes* instance-bound metadata
and *replaces* known-sensitive literals with documented placeholders. It does
not attempt to rewrite workflow logic. Node names, node types, connections,
expressions and prompt text are preserved exactly.

Usage
-----
    python3 scripts/sanitize_n8n_export.py raw-export.json sanitized.json
    python3 scripts/sanitize_n8n_export.py raw-export.json --stdout
    python3 scripts/sanitize_n8n_export.py raw-export.json out.json --report

What it does
------------
1.  Drops instance-bound top-level keys:
        id, versionId, meta.instanceId, meta.templateCredsSetupCompleted
2.  Forces ``active`` to ``false`` so an imported copy never starts listening
    on a webhook path before the operator has reviewed it.
3.  Clears ``pinData`` (pinned data is captured from real executions).
4.  Replaces every ``credentials`` block value with a placeholder id/name so
    the importer is forced to re-select a credential in their own instance.
5.  Applies a literal replacement map (RFC 1918 / real public addresses,
    Slack identifiers, internal webhook paths) across all node parameters.
6.  Re-checks the output and fails loudly if a known-bad pattern survives.

Exit codes
----------
    0   sanitized successfully
    1   usage error / unreadable input
    2   sanitization completed but residual sensitive values were detected
"""

from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Replacement map
# --------------------------------------------------------------------------
# The map is deliberately NOT hard-coded in this file.
#
# Its keys are the exact sensitive literals from your environment — internal
# addresses, bot IDs, hostnames, organisation-specific webhook paths. Embedding
# them here would republish, in the sanitizer, precisely the values it exists to
# remove. Instead the map is loaded from a JSON file that is git-ignored.
#
#   scripts/sanitize-map.json           <- yours, never committed
#   scripts/sanitize-map.example.json   <- committed template, generic values
#
# Format: a flat object of {"literal to find": "replacement"}.
#
# Documentation address blocks to use for replacements (RFC 5737):
#   192.0.2.0/24     TEST-NET-1
#   198.51.100.0/24  TEST-NET-2
#   203.0.113.0/24   TEST-NET-3
DEFAULT_MAP_PATH = Path(__file__).with_name("sanitize-map.json")


def load_replacements(path: Path | None) -> dict[str, str]:
    """Load the literal replacement map, or return an empty map."""
    target = path or DEFAULT_MAP_PATH
    if not target.is_file():
        if path is not None:
            raise SystemExit(f"error: replacement map not found: {target}")
        # No map: structural sanitization still runs (credential IDs, instance
        # ID, pinData, active flag) and the residual scan still guards the
        # output, so this is safe — just less thorough.
        print(
            f"note: no replacement map at {target}; running structural "
            "sanitization only. Copy sanitize-map.example.json and fill it in "
            "for literal replacement.",
            file=sys.stderr,
        )
        return {}
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise SystemExit(f"error: {target} must be a flat object of string->string")
    return data


CREDENTIAL_PLACEHOLDERS: dict[str, dict[str, str]] = {
    "slackApi": {"id": "SLACK_CREDENTIAL_ID", "name": "SLACK_API_CREDENTIAL"},
}
DEFAULT_CREDENTIAL_PLACEHOLDER = {
    "id": "REPLACE_WITH_CREDENTIAL_ID",
    "name": "REPLACE_WITH_CREDENTIAL_NAME",
}

DROP_TOP_LEVEL_KEYS = ("id", "versionId")
DROP_META_KEYS = ("instanceId", "templateCredsSetupCompleted")

# --------------------------------------------------------------------------
# Residual-secret detection (post-sanitization self check)
# --------------------------------------------------------------------------
RESIDUAL_PATTERNS: list[tuple[str, str]] = [
    ("slack token", r"xox[abposr]-[A-Za-z0-9-]{10,}"),
    ("slack signing secret", r"\b[0-9a-f]{32}\b"),
    # Slack ids are upper-alphanumeric and effectively always contain a digit.
    # The lookahead stops ALL-CAPS prose ("CONFIDENCE", "DETECTION") matching.
    ("slack user/channel id", r"\b(?=[A-Z0-9]*\d)[UCGDBT][A-Z0-9]{7,10}\b"),
    ("ngrok url", r"[A-Za-z0-9-]+\.ngrok(?:-free)?\.(?:app|io|dev)"),
    ("bearer token", r"[Bb]earer\s+[A-Za-z0-9._\-]{16,}"),
    ("private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("aws access key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("virustotal-style key", r"\b[0-9a-f]{64}\b"),
]

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# Addresses that are fine to keep in a published repository.
ALLOWED_IPS = {
    "0.0.0.0",
    "127.0.0.1",
    "255.255.255.255",
}


def _ip_is_allowed(text: str) -> bool:
    """True if an IPv4 literal is safe to publish."""
    if text in ALLOWED_IPS:
        return True
    try:
        addr = ipaddress.IPv4Address(text)
    except ipaddress.AddressValueError:
        # Not actually an address (e.g. a version string like 1.2.3.4000)
        return True
    # RFC 5737 documentation ranges are the only real addresses we publish.
    for block in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"):
        if addr in ipaddress.IPv4Network(block):
            return True
    return False


# --------------------------------------------------------------------------
# Core transformation
# --------------------------------------------------------------------------
def replace_literals(value: Any, replacements: dict[str, str], hits: dict[str, int]) -> Any:
    """Recursively apply the literal replacement map to strings."""
    if isinstance(value, str):
        out = value
        for needle, placeholder in replacements.items():
            if needle in out:
                hits[needle] = hits.get(needle, 0) + out.count(needle)
                out = out.replace(needle, placeholder)
        return out
    if isinstance(value, list):
        return [replace_literals(item, replacements, hits) for item in value]
    if isinstance(value, dict):
        return {
            replace_literals(k, replacements, hits): replace_literals(v, replacements, hits)
            for k, v in value.items()
        }
    return value


def sanitize_credentials(node: dict[str, Any], removed: list[str]) -> None:
    """Replace credential references with placeholders."""
    creds = node.get("credentials")
    if not isinstance(creds, dict):
        return
    for cred_type, cred_value in creds.items():
        if not isinstance(cred_value, dict):
            continue
        original_id = cred_value.get("id")
        original_name = cred_value.get("name")
        if original_id:
            removed.append(f"credential id ({cred_type}) on node '{node.get('name')}'")
        if original_name:
            removed.append(f"credential name ({cred_type}) on node '{node.get('name')}'")
        placeholder = CREDENTIAL_PLACEHOLDERS.get(cred_type, DEFAULT_CREDENTIAL_PLACEHOLDER)
        cred_value["id"] = placeholder["id"]
        cred_value["name"] = placeholder["name"]


def sanitize(
    workflow: dict[str, Any], replacements: dict[str, str] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (sanitized_workflow, report)."""
    wf = copy.deepcopy(workflow)
    removed: list[str] = []
    hits: dict[str, int] = {}

    for key in DROP_TOP_LEVEL_KEYS:
        if key in wf:
            wf.pop(key)
            removed.append(f"top-level '{key}'")

    meta = wf.get("meta")
    if isinstance(meta, dict):
        for key in DROP_META_KEYS:
            if key in meta:
                meta.pop(key)
                removed.append(f"meta.{key}")
        if not meta:
            wf.pop("meta", None)

    if wf.get("active") is True:
        wf["active"] = False
        removed.append("active=true forced to false")

    if wf.get("pinData"):
        wf["pinData"] = {}
        removed.append("pinData (captured execution data)")

    for node in wf.get("nodes", []):
        sanitize_credentials(node, removed)

    wf = replace_literals(wf, replacements or {}, hits)

    report = {
        "removed": removed,
        "replaced": hits,
        "residual": scan_residual(wf),
    }
    return wf, report


def scan_residual(workflow: dict[str, Any]) -> list[str]:
    """Look for sensitive-looking values that survived sanitization."""
    blob = json.dumps(workflow)
    findings: list[str] = []

    for label, pattern in RESIDUAL_PATTERNS:
        for match in set(re.findall(pattern, blob)):
            findings.append(f"{label}: {match}")

    for match in set(IPV4_RE.findall(blob)):
        if not _ip_is_allowed(match):
            findings.append(f"non-documentation IPv4: {match}")

    for node in workflow.get("nodes", []):
        creds = node.get("credentials") or {}
        for cred_type, cred_value in creds.items():
            if not isinstance(cred_value, dict):
                continue
            cred_id = str(cred_value.get("id", ""))
            expected = CREDENTIAL_PLACEHOLDERS.get(
                cred_type, DEFAULT_CREDENTIAL_PLACEHOLDER
            )["id"]
            if cred_id != expected:
                findings.append(
                    f"unexpected credential id on '{node.get('name')}': {cred_id}"
                )
    return findings


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    parser.add_argument("source", help="raw n8n export (JSON)")
    parser.add_argument("destination", nargs="?", help="output path")
    parser.add_argument("--stdout", action="store_true", help="write to stdout")
    parser.add_argument("--report", action="store_true", help="print a change report")
    parser.add_argument(
        "--map",
        type=Path,
        default=None,
        help="replacement map JSON (default: scripts/sanitize-map.json if present)",
    )
    args = parser.parse_args(argv)

    src = Path(args.source)
    if not src.is_file():
        print(f"error: cannot read {src}", file=sys.stderr)
        return 1

    try:
        workflow = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: {src} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    replacements = load_replacements(args.map)
    sanitized, report = sanitize(workflow, replacements)
    payload = json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n"

    if args.stdout or not args.destination:
        sys.stdout.write(payload)
    else:
        Path(args.destination).write_text(payload, encoding="utf-8")
        print(f"wrote {args.destination}")

    if args.report:
        print("\n--- removed ---", file=sys.stderr)
        for item in report["removed"]:
            print(f"  - {item}", file=sys.stderr)
        print("--- replaced ---", file=sys.stderr)
        for needle, count in sorted(report["replaced"].items()):
            print(f"  - {needle!r} x{count}", file=sys.stderr)

    if report["residual"]:
        print("\nRESIDUAL SENSITIVE VALUES DETECTED:", file=sys.stderr)
        for item in sorted(report["residual"]):
            print(f"  ! {item}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
