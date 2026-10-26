"""The cost of the tsconfig reader is linear in its input, and its results do not change.

Before this change, three tsconfig inputs had a very large cost:

- An unclosed string or block comment made the JSONC regular expressions quadratic. A
  text of 80 KB with an unclosed string of escaped quotes took 51.9 s.
- An include pattern with many stars became a regular expression that went back to try
  each split of the path. The pattern `src/` + 20 stars + `z` took 2.1 s for one path,
  and each two more stars made the time about 4 times longer.
- A chain of files that each extend two files that extend the same next file was read
  again for each route through the chain. Depth 16 took 38.8 s, and the cost became
  two times larger for each level.

Acceptance, written before the change: a 1 MB text with an unclosed string parses or
fails in less than 1 s with the same error, the pattern with many stars costs less than
10 ms for each path, and a chain of depth 30 loads in less than 1 s. The bounds in
these tests are 10 s, and the earlier code took much longer than 100 s at these sizes.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Any

import pytest

from systemap import typescript_config
from systemap.jsonc_text import strip_jsonc
from systemap.tsconfig_glob import compile_glob

# The earlier regular expressions. The tests compare the new reader with them on short
# texts, where their cost is small.
_OLD_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/')
_OLD_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')


def _old_strip(text: str) -> str:
    def blank(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith('"'):
            return token
        return "".join(char if char in "\r\n" else " " for char in token)

    def comma(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0).startswith('"') else ""

    return _OLD_COMMA.sub(comma, _OLD_TOKEN.sub(blank, text.lstrip("\ufeff")))


def _old_glob(pattern: str, folder: bool) -> re.Pattern[str]:
    regex = (
        re.escape(pattern)
        .replace(r"\*\*/", "(?:[^/]+/)*")
        .replace(r"\*\*", ".*")
        .replace(r"\*", "[^/]*")
        .replace(r"\?", "[^/]")
    )
    return re.compile(regex + ("(?:/.*)?" if folder else ""))


@pytest.mark.parametrize(
    "text",
    [
        '{"a": "x // y',
        '{"a": "x /* y */ z',
        '{"a": "x\\\n", "b": "/* c */", }',
        '{"a": 1 /* open, "b": [1, 2,] // line\n}',
        '{"a": "\\"\\"\\", ]',
        '\ufeff{"a": [1, /* c */ ], }',
        '{"a": "\\\\", "b": "//",\r\n}',
    ],
)
def test_the_reader_gives_the_text_of_the_earlier_expressions(text: str) -> None:
    assert strip_jsonc(text) == _old_strip(text)


def test_random_texts_give_the_text_of_the_earlier_expressions() -> None:
    rng = random.Random(11)
    alphabet = ['"', "\\", "/", "*", ",", "}", "]", " ", "\n", "\r", "a"]
    for _ in range(20000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 20)))
        assert strip_jsonc(text) == _old_strip(text), repr(text)


@pytest.mark.parametrize("unit", ['\\"', "/* "])
def test_an_unclosed_string_of_one_megabyte_fails_quickly(tmp_path: Path, unit: str) -> None:
    # The earlier code took 51.9 s at 80 KB with escaped quotes, and the cost was
    # quadratic. At 1 MB, it took more than 100 s.
    text = '{"compilerOptions": {"a": "' + unit * ((1 << 20) // len(unit))
    (tmp_path / "tsconfig.json").write_text(text)
    start = time.perf_counter()
    with pytest.raises(ValueError, match="Unterminated string starting at: line 1 column 27"):
        typescript_config.load_typescript_config(tmp_path)
    assert time.perf_counter() - start < 10


def test_random_patterns_give_the_matches_of_the_earlier_expression() -> None:
    rng = random.Random(5)
    pattern_chars = ["*", "*", "?", "/", "a", "b", ".", "\n"]
    path_chars = ["a", "b", "/", ".", "\n"]
    for _ in range(3000):
        pattern = "".join(rng.choice(pattern_chars) for _ in range(rng.randint(0, 8)))
        pattern = pattern.strip("/")
        folder = rng.random() < 0.2
        old, new = _old_glob(pattern, folder), compile_glob(pattern, folder)
        for _ in range(20):
            path = "".join(rng.choice(path_chars) for _ in range(rng.randint(0, 9)))
            assert new.fullmatch(path) == bool(old.fullmatch(path)), (pattern, path)


def test_a_pattern_with_many_stars_costs_little(tmp_path: Path) -> None:
    # The earlier code took 2.1 s for one path with 20 stars, about 4 times longer for
    # each two more stars. With 40 stars, it took much more than 100 s.
    matcher = typescript_config._glob_pattern("src/" + "*" * 40 + "z", tmp_path)
    start = time.perf_counter()
    assert not matcher.fullmatch("src/aaaaaaaaaaaaaaaaaaaaaaaa.ts")
    assert matcher.fullmatch("src/aaaaz")
    assert time.perf_counter() - start < 10


def test_a_long_pattern_of_mixed_repeats_costs_little() -> None:
    # The tokens of "***/" are `*` and `**/`, and the two are not merged. The earlier
    # matcher kept a list of all later positions for each token. With 4000 repeats, it
    # took 4.4 s to make and 2.1 s for each path, with 1246 MB of memory. Time and memory
    # grew 4 times when the repeats doubled, thus 16000 repeats took more than 100 s.
    start = time.perf_counter()
    matcher = compile_glob("***/" * 16000 + "z", False)
    assert not matcher.fullmatch("src/aaaaaaaaaaaaaaaaaaaaaaaa.ts")
    assert matcher.fullmatch("src/a/b/c/z")
    assert time.perf_counter() - start < 10


def test_long_random_patterns_give_the_matches_of_the_earlier_expression() -> None:
    rng = random.Random(9)
    pattern_chars = ["*", "*", "*", "?", "/", "a", "/"]
    for _ in range(300):
        pattern = "".join(rng.choice(pattern_chars) for _ in range(rng.randint(8, 13)))
        pattern = pattern.strip("/")
        folder = rng.random() < 0.2
        old, new = _old_glob(pattern, folder), compile_glob(pattern, folder)
        for _ in range(20):
            path = "".join(rng.choice("a/a") for _ in range(rng.randint(0, 12)))
            assert new.fullmatch(path) == bool(old.fullmatch(path)), (pattern, path)


def _diamond(root: Path, depth: int) -> None:
    """Make a chain: each file extends two files, and the two files extend one file."""
    for level in range(depth):
        top = f"a{level}.json" if level else "tsconfig.json"
        both = {"extends": [f"./a{level + 1}.json", f"./b{level + 1}.json"]}
        (root / top).write_text(json.dumps(both))
        (root / f"b{level + 1}.json").write_text(json.dumps({"extends": f"./a{level + 1}.json"}))
    last = {"extends": "@missing/base", "compilerOptions": {"outDir": "out"}, "include": ["s"]}
    (root / f"a{depth}.json").write_text(json.dumps(last))


def test_a_diamond_chain_reads_each_file_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The earlier code read the files of depth 12 more than 8000 times.
    _diamond(tmp_path, 12)
    reads: list[Path] = []
    read = typescript_config._read_config

    def counted(path: Path, repo: Path) -> dict[str, Any]:
        reads.append(path)
        return read(path, repo)

    monkeypatch.setattr(typescript_config, "_read_config", counted)
    config = typescript_config.load_typescript_config(tmp_path)
    assert len(reads) == len(set(reads)) == 25
    assert config.out_dir == (tmp_path / "out").resolve()
    assert config.issues == (("a12.json", "@missing/base"),)


def test_a_deep_diamond_chain_loads_quickly(tmp_path: Path) -> None:
    # The earlier code took 38.8 s at depth 16, and two times longer for each level.
    _diamond(tmp_path, 40)
    start = time.perf_counter()
    config = typescript_config.load_typescript_config(tmp_path)
    assert time.perf_counter() - start < 10
    assert config.out_dir == (tmp_path / "out").resolve()
    assert config.inputs is not None and config.inputs.include == ("s",)


def test_a_cycle_in_a_diamond_chain_is_still_an_error(tmp_path: Path) -> None:
    _diamond(tmp_path, 6)
    (tmp_path / "a6.json").write_text(json.dumps({"extends": "./b3.json"}))
    with pytest.raises(ValueError, match="circular tsconfig extends relation"):
        typescript_config.load_typescript_config(tmp_path)


def test_a_file_that_extends_and_references_name_is_read_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "base.json").write_text('{"compilerOptions": {"strict": true}}')
    (tmp_path / "one").mkdir()
    (tmp_path / "one" / "tsconfig.json").write_text('{"extends": "../base.json"}')
    (tmp_path / "tsconfig.json").write_text(
        '{"extends": "./base.json", "references": [{"path": "./one"}, {"path": "./base.json"}]}'
    )
    reads: list[Path] = []
    read = typescript_config._read_config

    def counted(path: Path, repo: Path) -> dict[str, Any]:
        reads.append(path)
        return read(path, repo)

    monkeypatch.setattr(typescript_config, "_read_config", counted)
    config = typescript_config.load_typescript_config(tmp_path)
    assert sorted(path.name for path in reads) == ["base.json", "tsconfig.json", "tsconfig.json"]
    assert [project.config_dir for project in config.projects] == [
        (tmp_path / "one").resolve(),
        tmp_path.resolve(),
    ]
