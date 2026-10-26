"""Large valid inputs do not make import resolution or method names slow.

Findings g1ts-5, g1ts-9, and regex-4 of the audit, and the deep package.json file of
the P2 depth finding.

- g1ts-5: before the change, each self-name import examined each `exports` key 8 times.
  `systemap extract` took 32.6 s for 5000 pattern keys and 2000 imports on this host.
  After the change, it took 1.9 s.
- g1ts-9: before the change, `call_sites` examined each import binding for each
  assignment. 4000 star-imported names and 4000 assignments took 5.3 s, and 8000 took
  30.2 s. After the change, 8000 took 0.16 s.
- regex-4: before the change, the method name of one signature with 32000 spaces took
  21.5 s. After the change, it took less than 0.001 s.
- A package.json file with 5000 nested arrays gave RecursionError and a traceback.

The tests count the work. The one time bound is more than ten times the expected time.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract, python_calls, typescript_package_imports
from systemap.config import ConfigError
from systemap.typescript_config import package_json
from systemap.typescript_repo import TYPESCRIPT_REPOSITORY

PATTERN_KEYS = 2000
IMPORTS = 300


def _wide_package() -> dict[str, str]:
    exports = ", ".join(f'"./k{index}/*": "./src/k{index}/*.ts"' for index in range(PATTERN_KEYS))
    lines = "".join(f'import "web/zz{index}";\n' for index in range(IMPORTS))
    return {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "package.json": '{"name": "web", "exports": {' + exports + "}}",
        "tsconfig.json": '{"compilerOptions": {}, "include": ["src/**/*"]}',
        "src/a.ts": lines + 'import { b } from "web/k7/b";\nexport const a = b;\n',
        "src/k7/b.ts": "export const b = 1;\n",
    }


def test_each_self_name_import_matches_the_exports_table_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before the change, the extraction called `_match` 8 times for each import, thus
    # 2408 times for these 301 imports. After the change, it calls `_match` one time.
    pytest.importorskip("tree_sitter_typescript")
    calls = [0]
    match = typescript_package_imports._match

    def counted(*args: Any) -> str | None:
        calls[0] += 1
        return match(*args)

    monkeypatch.setattr(typescript_package_imports, "_match", counted)
    write_tree(tmp_path, _wide_package())
    facts = extract.build(config.load(tmp_path))
    assert calls[0] <= 2 * (IMPORTS + 1)
    assert "web.k7.b" in facts["components"]["web.a"]["imports"]


def test_the_pattern_index_gives_the_order_of_pattern_key_compare() -> None:
    table = {
        "./a/*": "1",
        "./a/b/*": "2",
        "./a/b/*.js": "3",
        "./a/*.js": "4",
        "./c/*/d": "5",
        "./x": "6",
    }
    index = typescript_package_imports._indexed(table)
    pattern = typescript_package_imports._pattern
    # The longest text before `*` has priority, then the longest pattern key.
    assert pattern("./a/b/c.js", index) == "./a/b/*.js"
    assert pattern("./a/b/c.ts", index) == "./a/b/*"
    assert pattern("./a/c.js", index) == "./a/*.js"
    assert pattern("./c/e/d", index) == "./c/*/d"
    # The text that `*` matches must contain one or more characters.
    assert pattern("./a/b/", index) == "./a/*"
    assert pattern("./c/d", index) is None
    assert pattern("./x", index) is None


def _star_module(names: int) -> tuple[str, dict[str, Any]]:
    components = {"pkg.big": {"names": [{"name": f"n{index}"} for index in range(names)]}}
    raw = "from pkg.big import *\n" + "".join(f"v{index} = n{index}\n" for index in range(names))
    return raw, components


def test_call_sites_examine_only_the_import_bindings_of_the_value_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Before the change, each assignment examined each of the 1000 star-imported
    # bindings: 1000000 calls of `_rank`. After the change, the count is about 2000.
    calls = [0]
    rank = python_calls._rank

    def counted(*args: Any) -> int | None:
        calls[0] += 1
        return rank(*args)

    monkeypatch.setattr(python_calls, "_rank", counted)
    raw, components = _star_module(1000)
    sites = python_calls.call_sites(raw, {"pkg"}, {"pkg.big", "pkg.a"}, components, "pkg.a")
    assert sites is not None
    assert calls[0] < 10 * 1000
    values = [site for site in sites if site["bound"] == "value"]
    assert len(values) == 1000
    assert values[0]["local"] == "v0"
    assert values[0]["name"] == "n0"


def test_the_first_import_name_of_a_dotted_value_gives_the_binding() -> None:
    # `import a.b` and `import a` both agree with `a.b.c`. The import that is first in
    # the source gives the binding, as before the change.
    raw = "import pkg.b\nimport pkg\nx = pkg.b.c\ny = pkg.d\n"
    known = {"pkg", "pkg.b", "pkg.m"}
    sites = python_calls.call_sites(raw, {"pkg"}, known, {}, "pkg.m")
    assert sites is not None
    found = {site["local"]: (site["target"], site["name"]) for site in sites}
    assert found["x"] == ("pkg.b", "c")
    assert found["y"] == ("pkg", "d")


def test_a_long_whitespace_sequence_in_a_method_signature_is_not_slow() -> None:
    # Before the change, this test took 88.4 s on this host: the time increased four
    # times for each double length. After the change, the time is less than 0.01 s.
    # The bound is 10 s.
    start = time.monotonic()
    assert TYPESCRIPT_REPOSITORY.method_name("public" + " " * 64000 + "x") == ""
    assert TYPESCRIPT_REPOSITORY.method_name("static" + "\t " * 32000 + "run()") == "run"
    assert time.monotonic() - start < 10


@pytest.mark.parametrize(
    ("signature", "name"),
    [
        ("get (", "get"),
        ("static async *gen<T>(a: T)", "gen"),
        ('"quoted" ()', "quoted"),
        ("get x()", "x"),
        ("public  static\t run ? ()", "run"),
        ("set\n value!(v)", "value"),
        ("public get()", "get"),
        ("declare", ""),
        ("a b(", ""),
        ("public get", ""),
    ],
)
def test_the_method_names_do_not_change(signature: str, name: str) -> None:
    # The values come from the regular expression before the change.
    assert TYPESCRIPT_REPOSITORY.method_name(signature) == name


def test_a_deeply_nested_package_json_gives_a_configuration_error(tmp_path: Path) -> None:
    # Before the change, 5000 nested arrays gave RecursionError, not ConfigError.
    value = "[" * 5000 + '"./a.js"' + "]" * 5000
    (tmp_path / "package.json").write_text('{"name": "web", "exports": ' + value + "}")
    with pytest.raises(ConfigError, match="could not read .*package.json"):
        package_json(tmp_path)
