#!/usr/bin/env python3
"""Validate the plugin manifest in strict mode, with one warning allowed.

This repository is two things at once: a project a coding agent works in, and
a Claude Code plugin that ships the systemap skill. `claude plugin validate
--strict` is the right gate for the manifest, because an unrecognised field or
a missing description should fail CI rather than be tolerated at runtime.

It emits one warning that does not apply here:

    CLAUDE.md at the plugin root is not loaded as project context.

That is advice for a repository that is only a plugin. This one has a root
`AGENTS.md` for every coding agent and a `CLAUDE.md` holding `@AGENTS.md` so
Claude Code loads it, and a pre-commit hook holds the two to the same section
structure. Neither file ships as plugin context, and neither is meant to.

So this allows exactly that warning, on exactly that file, and fails on
everything else: any error anywhere, and any other warning. If the CLI stops
emitting it, nothing here changes; if it emits a different one, this fails and
someone reads it.

    python3 scripts/check_plugin_manifest.py .claude-plugin/plugin.json
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
        print(f"could not read the validator's report for {target}", file=sys.stderr)
        return 1
    found = problems(data)
    excused = any(allowed(r) and r.get("warnings") for r in (data.get("contents") or []))
    if found:
        print(f"{target} is not valid:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    note = "; the root CLAUDE.md warning does not apply here" if excused else ""
    print(f"{target}: valid{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
