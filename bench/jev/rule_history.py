"""Count the steps of the history where a change brought an import against a rule.

`systemap claims` gives the import rules of a component before a change. This script
measures how frequently such a rule applied to a change in the history of this
repository. It uses the import rules and the component claims of the map at HEAD. For
each commit on the first-parent line of HEAD, it extracts the facts at that commit and
gets the result of each rule (`import_rules.evaluate`). A module that no component claim
at HEAD selects has no component, as in `systemap history`.

A step brings a failure of a rule when the rule has the result `fail` at the commit and
a different result at its first parent. The script also gives, for each such step, the
imports against the rule that the parent did not have.

Acceptance value, written on 2026-11-24 before the first run: if fewer than 3 steps
bring a failure, the rules did not apply to the changes of this history. Then paired
agent runs with and without `systemap claims` are not worth their cost here, because the
part of the output that a check can score did not apply. With 3 or more steps, a pilot
with agent runs has cases to use.

The rules are from 2026-11-24. Each rule passes at HEAD, and the repair of that day
removed the imports against `commands-above-all`. Thus a failure in the history shows an
import that was removed later. It does not show that a maintainer wanted the rule then.

Run from the repository root, with the full history:

    uv run python bench/jev/rule_history.py
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

from systemap import config, history, import_rules, nest
from systemap.model import Model


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def results(
    cfg: config.Config, model: Model, sha: str
) -> dict[str, tuple[str, frozenset[tuple[str, str]]]]:
    """Give the result and the imports against each rule at a commit."""
    facts = history.facts_at(cfg, sha)
    return {
        outcome.rule.id: (outcome.result, frozenset(outcome.imports))
        for outcome in import_rules.evaluate(model, facts)
    }


Result = dict[str, tuple[str, frozenset[tuple[str, str]]]]


def report(
    brought: list[tuple[str, str, list[tuple[str, str]]]],
    failing: Counter[str],
    unknown: Counter[str],
    step_count: int,
) -> None:
    head = git("rev-parse", "--short", "HEAD").strip()
    print(f"HEAD {head}: {step_count} steps, {len(failing)} rules")
    for rule in sorted(failing):
        print(f"  {rule:26} fail at {failing[rule]:3} steps, unknown at {unknown[rule]:3} steps")
    with_failure = {commit for commit, _rule, _imports in brought}
    print(f"steps that bring a failure: {len(with_failure)} ({len(brought)} rule failures)")
    for commit, rule, imports in brought:
        subject = git("log", "-1", "--format=%ad %s", "--date=short", commit).strip()[:70]
        print(f"  {commit[:7]} {rule}: {subject}")
        for src, dst in imports[:4]:
            print(f"      {src} -> {dst}")


def main() -> int:
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        print("The history is not complete. Do `git fetch --unshallow` first.", file=sys.stderr)
        return 1
    cfg = config.load(Path.cwd().resolve())
    model = nest.load(cfg, None).top.model
    lines = git("rev-list", "--first-parent", "--parents", "HEAD").splitlines()
    steps = [line.split()[:2] for line in lines if len(line.split()) > 1]
    held: dict[str, Result] = {}
    brought: list[tuple[str, str, list[tuple[str, str]]]] = []
    failing: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    for commit, parent in steps:
        for sha in (commit, parent):
            if sha not in held:
                held[sha] = results(cfg, model, sha)
        was = held[parent]
        for rule, (result, imports) in held[commit].items():
            failing[rule] += result == import_rules.FAIL
            unknown[rule] += result == import_rules.UNKNOWN
            if result == import_rules.FAIL and was[rule][0] != import_rules.FAIL:
                brought.append((commit, rule, sorted(imports - was[rule][1])))
    report(brought, failing, unknown, len(steps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
