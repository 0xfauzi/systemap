#!/usr/bin/env python3
"""Do the plugin manifest check with the Claude Code CLI.

The repository has a root CLAUDE.md for source-development instructions.
The plugin validator warns that this file is not loaded by the plugin.
This warning is not applicable to repository development.
The script lets this warning pass and rejects all other warnings and errors.

    uv run python scripts/check_plugin_manifest.py .claude-plugin/plugin.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# The one warning that does not apply, matched on its file and its opening
# words rather than the whole sentence, which the CLI may reword.
ALLOWED = ("CLAUDE.md", "CLAUDE.md at the plugin root is not loaded")


def allowed(report: dict[str, Any]) -> bool:
    """Is this the root CLAUDE.md warning, and nothing else?"""
    name, opening = ALLOWED
    return Path(report.get("file", "")).name == name and all(
        str(w.get("message", "")).startswith(opening) for w in report.get("warnings", [])
    )


def problems(data: dict[str, Any]) -> list[str]:
    """Everything the validator said that this repository has not accounted for."""
    out: list[str] = []
    reports = [data.get("manifest") or {}, *(data.get("contents") or [])]
    for report in reports:
        where = Path(str(report.get("file", "?"))).name
        out += [f"{where}: {e.get('message', e)}" for e in report.get("errors", [])]
        if allowed(report):
            continue
        out += [f"{where}: {w.get('message', w)}" for w in report.get("warnings", [])]
    return out


def main(argv: list[str]) -> int:
    target = argv[1] if len(argv) > 1 else ".claude-plugin/plugin.json"
    done = subprocess.run(
        ["claude", "plugin", "validate", target, "--strict", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(done.stdout)
    except ValueError:
        print(done.stdout or done.stderr, file=sys.stderr)
        print(
            f"The validator report could not be read for {target}. "
            "Use a Claude Code CLI with `plugin validate --json`. Version "
            "2.1.246 lacks this option. Version 2.1.278 has it.",
            file=sys.stderr,
        )
        return 1
    found = problems(data)
    excused = any(allowed(r) and r.get("warnings") for r in (data.get("contents") or []))
    if found:
        print(f"{target} is not valid:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    note = ". The root CLAUDE.md warning is not applicable here" if excused else ""
    print(f"{target}: valid{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
