"""The facts cache of `systemap history` gets the shape check of the stored facts.

`history.facts_at` reads cached facts from `.systemap/facts`. Before the change, it
examined only that the value was a table with a `components` table. A record of an
incorrect type stopped `systemap history` with AttributeError, and a deeply nested value
stopped it with RecursionError in the JSON parser. Now the cache reader uses
`facts_shape.problem`, the check of `facts_file.read_facts`. A cache file with an
incorrect shape is not usable: `facts_at` extracts the facts again and replaces the file.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, facts_shape, history
from systemap.cli import main

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
TREE = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/tools.py": "def run() -> None:\n    pass\n",
}


def first(facts: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = next(iter(facts["components"].values()))
    return record


def _set(key: str, value: Any) -> Callable[[dict[str, Any]], str]:
    def change(facts: dict[str, Any]) -> str:
        first(facts)[key] = value
        return json.dumps(facts)

    return change


def _not_a_record(facts: dict[str, Any]) -> str:
    facts["components"][next(iter(facts["components"]))] = "x"
    return json.dumps(facts)


CHANGES: dict[str, Callable[[dict[str, Any]], str]] = {
    "a record that is not a table": _not_a_record,
    "a file that is a number": _set("file", 3),
    "an absolute file path": _set("file", "/etc/tools.py"),
    "uses that is a list": _set("uses", ["pkg"]),
    "a value with 100000 levels": lambda facts: "[" * 100000 + "]" * 100000,
}


@pytest.fixture
def committed(tmp_path: Path) -> tuple[Path, str]:
    write_tree(tmp_path, TREE)
    subprocess.run([*GIT, "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run([*GIT, "commit", "-qm", "base"], cwd=tmp_path, check=True)
    sha = subprocess.run(
        [*GIT, "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()
    return tmp_path, sha


@pytest.mark.parametrize("name", list(CHANGES))
def test_a_cache_file_with_an_incorrect_shape_is_extracted_again(
    committed: tuple[Path, str], name: str
) -> None:
    root, sha = committed
    cfg = config.load(root)
    clean = history.facts_at(cfg, sha)
    assert facts_shape.problem(clean) is None
    (cached,) = list(history.cache_dir(cfg).glob(f"{sha}-*.json"))
    cached.write_text(CHANGES[name](json.loads(json.dumps(clean))), encoding="utf-8")
    assert history.facts_at(cfg, sha) == clean
    assert json.loads(cached.read_text(encoding="utf-8")) == clean


def test_history_gives_the_same_report_after_a_change_to_the_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    subprocess.run([*GIT, "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-qm", "base"], cwd=root, check=True)
    (root / "pkg/more.py").write_text("def more() -> None:\n    pass\n", encoding="utf-8")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-qm", "head"], cwd=root, check=True)
    argv = ["--root", str(root), "history", "--every", "0", "--since", "30 years ago"]
    capsys.readouterr()
    assert main(argv) == 0
    report = capsys.readouterr().out
    for cached in history.cache_dir(config.load(root)).glob("*.json"):
        cached.write_text(_not_a_record(json.loads(cached.read_text(encoding="utf-8"))))
    assert main(argv) == 0
    assert capsys.readouterr().out == report
