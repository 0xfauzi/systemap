"""The test comparison of a source change: the added and removed tests of each module.

Each side of the comparison resolves the imports of its own test files. The side is the
merge base, the head commit, or the working tree. The configuration files, the module
paths, and the known modules of that side give the import targets of its test files.
For a commit, a copy of the committed tree in a temporary folder gives these inputs, as
for the facts of a commit (`delta_git.facts_at`). The `systemap.toml` of the working
tree applies to each side, as for those facts.

For each target module, the comparison compares the tests of the base, if the base
imports the module, with the tests of the head, if the head imports the module.

A side that cannot read or parse a test file gives a problem for the file. A side whose
configuration or module paths give an error gives a problem for each of its test files.
Then the test changes of the file are not known. The comparison does not use an empty
test list for such a file. The language adapter gives the parser state: `parse_surface`
gives None for a text that does not parse.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Mapping
from pathlib import Path

from systemap import change_text, delta_git, extraction
from systemap.config import Config, ConfigError
from systemap.language import LanguageAdapter

NOT_PARSED = "the {} text could not be parsed"
BAD_SIDE = "the {} configuration or module paths give an error: {}"


@dataclasses.dataclass(frozen=True)
class Tests:
    """The test identities of one test file at one side, and the modules that it imports."""

    names: frozenset[str] = frozenset()
    targets: frozenset[str] = frozenset()


# A test file at one side: its tests, or the problem that makes its tests not known.
Found = Tests | str


def compare(
    cfg: Config,
    language: LanguageAdapter,
    texts: tuple[Mapping[str, change_text.Text], Mapping[str, change_text.Text]],
    revisions: tuple[str, str | None],
) -> tuple[dict[str, set[str]], dict[str, set[str]], list[str]]:
    """Give the added tests and the removed tests of each target module, and the problems.

    `texts` gives the text of each changed test file at the base and at the head.
    `revisions` gives the base commit and the head commit. A head of None is the working
    tree. A test file with a problem is in the third list, as `path: problem`.
    """
    before = _side(cfg, language, texts[0], revisions[0], "base")
    after = _side(cfg, language, texts[1], revisions[1], "head")
    added: dict[str, set[str]] = {}
    removed: dict[str, set[str]] = {}
    problems: list[str] = []
    for path in texts[0]:
        old, new = before[path], after[path]
        if isinstance(old, str) or isinstance(new, str):
            problems.append(f"{path}: {old if isinstance(old, str) else new}")
            continue
        _add_changes(old, new, added, removed)
    return added, removed, problems


def _add_changes(
    old: Tests, new: Tests, added: dict[str, set[str]], removed: dict[str, set[str]]
) -> None:
    """Add the test changes of one file for each module that a side imports."""
    for target in old.targets | new.targets:
        was = old.names if target in old.targets else frozenset()
        now = new.names if target in new.targets else frozenset()
        if now - was:
            added.setdefault(target, set()).update(now - was)
        if was - now:
            removed.setdefault(target, set()).update(was - now)


def _side(
    cfg: Config,
    language: LanguageAdapter,
    texts: Mapping[str, change_text.Text],
    revision: str | None,
    side: str,
) -> dict[str, Found]:
    """Give the tests of each test file at one side, or its problem.

    A file that the side does not have has no tests. The function copies a committed tree
    only if a test file at that commit has text.
    """
    found: dict[str, Found] = {
        path: text.problem if text.problem else Tests() for path, text in texts.items()
    }
    wanted = {path: text.raw for path, text in texts.items() if text.raw and not text.problem}
    if not wanted:
        return found
    if revision is None:
        found.update(_resolved(cfg, language, wanted, side))
        return found
    with tempfile.TemporaryDirectory(prefix="systemap-tests-") as folder:
        into = Path(folder).resolve()
        delta_git.write_tree(cfg.root, revision, into)
        found.update(_resolved(dataclasses.replace(cfg, root=into), language, wanted, side))
    return found


def _resolved(
    cfg: Config, language: LanguageAdapter, texts: dict[str, str], side: str
) -> dict[str, Found]:
    """Give the tests and the import targets of each test text, with the files at cfg.root."""
    try:
        # The same module paths and resolution context as the extraction of these files.
        paths = extraction._source_paths(cfg, language)
        context = language.context(cfg.root, paths, cfg.test_dirs, cfg.test_patterns)
    except ConfigError as exc:
        return dict.fromkeys(texts, BAD_SIDE.format(side, exc))
    prefixes = {name for _, name in cfg.roots}
    out: dict[str, Found] = {}
    for path, raw in texts.items():
        names = frozenset(f"{path}::{name}" for name in language.test_names(raw, path))
        # A text without tests can be a text that does not parse. Only then is the parser
        # state necessary.
        if not names and language.parse_surface(raw, path) is None:
            out[path] = NOT_PARSED.format(side)
            continue
        importer = f"__test__:{path}"
        targets = language.internal_uses(
            raw,
            prefixes,
            set(paths),
            module=importer,
            repo=cfg.root,
            paths={**paths, importer: cfg.root / path},
            context=context,
        )
        out[path] = Tests(names, frozenset(targets))
    return out
