#!/usr/bin/env python3
"""
scan_sensitive_values.py
========================

Scan the repository for values that must never be published: credentials,
tokens, private network addresses, internal hostnames, tunnel URLs, and n8n
instance or credential identifiers.

This runs in CI on every push. It is a safety net, not a substitute for
reviewing an export before committing it — a scanner only catches patterns
somebody thought of in advance.

Usage
-----
    python3 scripts/scan_sensitive_values.py [--root .] [--verbose]

Exit codes
----------
    0   nothing found
    1   at least one finding
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", "dist"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".zip",
                 ".gz", ".tar", ".pdf", ".woff", ".woff2", ".ttf"}

# This file necessarily contains every pattern it looks for, so it is the only
# file exempted from scanning. sanitize_n8n_export.py used to be exempt too,
# because it hard-coded the literals it replaced — which meant the sanitizer
# republished exactly what it existed to remove, and the exemption hid it. The
# map now lives in a git-ignored file and the sanitizer is scanned like anything
# else.
SELF = "scan_sensitive_values.py"

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------
PATTERNS: list[tuple[str, str, str]] = [
    # (id, description, regex)
    ("slack-bot-token", "Slack bot/user/app token", r"xox[abposr]-[A-Za-z0-9-]{10,}"),
    ("slack-webhook", "Slack incoming webhook URL", r"hooks\.slack\.com/services/[A-Za-z0-9/+]+"),
    ("slack-id", "Slack user/channel/team ID",
     r"\b(?=[A-Z0-9]*\d)[UCGDBTWA]0?[A-Z0-9]{7,10}\b"),
    ("aws-access-key", "AWS access key ID", r"\bAKIA[0-9A-Z]{16}\b"),
    ("google-api-key", "Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("github-token", "GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("private-key", "Private key block", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ("jwt", "JSON Web Token", r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ("bearer", "Bearer token literal", r"[Bb]earer\s+[A-Za-z0-9._\-]{20,}"),
    ("basic-auth-url", "Credentials embedded in URL", r"https?://[^\s/:@]+:[^\s/@]+@[^\s/]+"),
    ("ngrok", "ngrok tunnel URL", r"[A-Za-z0-9-]+\.ngrok(?:-free)?\.(?:app|io|dev)"),
    ("tunnel", "Other tunnel URL",
     r"[A-Za-z0-9-]+\.(?:loca\.lt|trycloudflare\.com|serveo\.net|localhost\.run)"),
    ("password-assign", "Hard-coded password assignment",
     r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|apikey|token)\s*[:=]\s*['\"][^'\"$\s{}<>]{8,}['\"]"),
    ("internal-tld", "Internal domain suffix",
     r"\b[a-z0-9][a-z0-9-]{1,62}\.(?:local|internal|intranet|corp|lan|home\.arpa|localdomain)\b(?!\.[a-z])"),
    ("n8n-credential-id", "n8n credential id field",
     r"\"id\"\s*:\s*\"[A-Za-z0-9]{16}\""),
    ("n8n-instance-id", "n8n instanceId", r"\"instanceId\"\s*:\s*\"[0-9a-f]{32,}\""),
]

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# --------------------------------------------------------------------------
# Allowlist
# --------------------------------------------------------------------------
# Documentation and example values that are intentionally published.
ALLOWED_LITERALS = {
    # Placeholders
    "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_CHANNEL_ID", "SLACK_BOT_USER_ID",
    "SLACK_CREDENTIAL_ID", "SLACK_API_CREDENTIAL", "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    "VIRUSTOTAL_API_KEY", "ABUSEIPDB_API_KEY", "THEHIVE_URL", "CORTEX_URL",
    "OPENCTI_URL", "N8N_BASE_URL", "WAZUH_WEBHOOK_PATH",
    # Synthetic identifiers used in examples
    "C0EXAMPLE001", "U0EXAMPLE001", "T0EXAMPLE001", "A0EXAMPLE001",
    "B0EXAMPLE001", "Ev0EXAMPLE001", "FGEXAMPLE0000001",
    # Masked shape shown in configuration.md so readers recognise a Slack
    # member ID without a real one being published.
    "U0XXXXXXXXX",
    # .env.example ships an obviously-invalid token so the shape is visible.
    # Only this exact literal is permitted; any real xoxb- value still fails.
    "xoxb-REPLACE-ME",
}
ALLOWED_LITERAL_RE = re.compile("|".join(re.escape(x) for x in sorted(ALLOWED_LITERALS)))

# Windows event IDs, Kerberos codes and similar values that resemble nothing
# secret but can trip the greedier patterns.
ALLOWED_CONTEXT_SUBSTRINGS = (
    # Standard Docker DNS name for the host, referenced in deployment docs.
    "host.docker.internal",
    # Deliberate fixture in .github/workflows/python-validation.yml: the
    # sanitizer self-test plants this tunnel URL and asserts the sanitizer
    # refuses to exit 0. Removing it would silently disable that test.
    "evil.ngrok-free.app",
    "example.invalid",
    "corp.example",
    "DC-EXAMPLE",
    "WKS-EXAMPLE",
    "FG-EDGE-01",
    "maryamoah",
    "techiesiwaamoah@gmail.com",
    "your-n8n-host",
    "example.com",
)

ALLOWED_IPS = {"0.0.0.0", "127.0.0.1", "255.255.255.255", "8.8.8.8"}
DOC_NETS = [
    ipaddress.IPv4Network("192.0.2.0/24"),
    ipaddress.IPv4Network("198.51.100.0/24"),
    ipaddress.IPv4Network("203.0.113.0/24"),
]


def ip_finding(text: str) -> str | None:
    """Return a description if this IPv4 literal should not be published."""
    if text in ALLOWED_IPS:
        return None
    try:
        addr = ipaddress.IPv4Address(text)
    except ipaddress.AddressValueError:
        return None
    if any(addr in net for net in DOC_NETS):
        return None
    if addr.is_private:
        return "private/RFC1918 address"
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved:
        return None
    return "non-documentation public address"


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path


def value_is_allowed(value: str) -> bool:
    """Allowlist the matched value itself, never the whole line.

    Allowlisting a line would let one permitted placeholder mask a real secret
    sitting beside it, so the check is deliberately narrow: the match must be a
    known placeholder, or a substring of one of the documented example tokens
    (e.g. 'docker.internal' inside 'host.docker.internal').
    """
    if value in ALLOWED_LITERALS:
        return True
    for token in ALLOWED_CONTEXT_SUBSTRINGS:
        if value == token or value in token:
            return True
    return False


def scan_file(path: Path, rel: Path, verbose: bool) -> list[str]:
    findings: list[str] = []
    is_scanner_source = rel.name == SELF

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        if is_scanner_source:
            continue
        stripped = line.strip()
        if not stripped:
            continue

        for _pid, description, pattern in PATTERNS:
            for match in re.finditer(pattern, line):
                value = match.group(0)
                if value_is_allowed(value):
                    continue
                # A match that merely *contains* a placeholder (e.g. a doc line
                # reading `SLACK_BOT_TOKEN=xoxb-...`) is still worth surfacing,
                # so only exact placeholder matches are suppressed above.
                findings.append(f"{rel}:{lineno}: {description}: {value[:80]}")

        for match in IPV4_RE.finditer(line):
            reason = ip_finding(match.group(0))
            if reason:
                findings.append(f"{rel}:{lineno}: {reason}: {match.group(0)}")

    if verbose and not findings:
        print(f"  clean  {rel}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for sensitive values.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--verbose", action="store_true", help="list clean files too")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    all_findings: list[str] = []
    scanned = 0

    for path in iter_files(root):
        scanned += 1
        all_findings.extend(scan_file(path, path.relative_to(root), args.verbose))

    print(f"\nScanned {scanned} file(s).")

    if all_findings:
        print(f"\n{len(all_findings)} finding(s):\n")
        for finding in all_findings:
            print(f"  FAIL  {finding}")
        print(
            "\nIf a finding is a deliberate example, add it to ALLOWED_LITERALS or "
            "ALLOWED_CONTEXT_SUBSTRINGS in this script — with a comment saying why."
        )
        return 1

    print("No sensitive values found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
