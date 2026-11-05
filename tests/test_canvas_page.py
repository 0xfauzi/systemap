"""The canvas page behind the setting `[render] canvas` (`canvas_page`, `config_render`).

Acceptance values:

1. Without the setting, or with `canvas = false`, `render` writes the linked pages with
   no change: each page is the text of `page.build`.
2. With `canvas = true`, `render` writes the canvas page at the top page, and a small
   page at the page of each nested map. The small page goes to the top page with the
   map ID in the hash. `render --check` and `check` then agree with the files.
3. The canvas page holds the canvas data one time, in one JSON element, and the data is
   the object of `canvas_data.build`. No "<" of the data is in the page text.
4. The CSP of the canvas page has the digest of each script element and each style
   element of the page, and no other script digest.
5. A value of `[render]` that is not correct gives a configuration error.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_nest_join import CONFIG, NESTED, SOURCE, TOP

from systemap import canvas_data, canvas_page, config, facts_file, nest, page, page_csp
from systemap.cli import main

DATA = re.compile(r'<script type="application/json" id="canvas-data">(.*?)</script>', re.S)


def _made(root: Path, setting: str) -> Path:
    files = {
        "systemap.toml": CONFIG + setting,
        "map/model.py": TOP,
        "map/gateway.py": NESTED,
        **SOURCE,
    }
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    return root


def _read(root: Path, rel: str) -> str:
    return (root / "docs" / "map" / rel).read_text(encoding="utf-8")


def _loaded(root: Path) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    cfg = config.load(root)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


@pytest.mark.parametrize("setting", ["", "[render]\ncanvas = false\n"])
def test_without_the_setting_render_writes_the_linked_pages(tmp_path: Path, setting: str) -> None:
    """Acceptance 1."""
    root = _made(tmp_path, setting)
    cfg, tree, facts = _loaded(root)
    assert not cfg.render_canvas
    for m in tree.maps:
        built = page.build(
            cfg,
            m.model,
            m.meaning,
            m.theme,
            facts,
            {"has_change": False},
            nesting=page.nesting_of(cfg, tree, m, facts),
        )
        assert m.page_path(cfg).read_text(encoding="utf-8") == built
        assert 'id="canvas-data"' not in built


@pytest.fixture(scope="module")
def canvas_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _made(tmp_path_factory.mktemp("canvas"), "[render]\ncanvas = true\n")


def test_with_the_setting_render_writes_the_canvas_page(canvas_root: Path) -> None:
    """Acceptance 2."""
    top = _read(canvas_root, "index.html")
    assert '<canvas id="canvas"' in top
    assert "window.systemapCanvas" in top
    nested = _read(canvas_root, "Gateway/index.html")
    assert '<meta http-equiv="refresh" content="0;url=../index.html#Gateway">' in nested
    assert '<a href="../index.html#Gateway">' in nested
    assert "<canvas" not in nested
    assert main(["--root", str(canvas_root), "render", "--check"]) == 0
    assert main(["--root", str(canvas_root), "check"]) == 0


def test_a_deep_map_goes_to_the_top_page_with_its_path() -> None:
    """Acceptance 2: the URL of the small page of a map on level 2."""
    m = nest.Map(id="Gateway/Routes", path=Path("x"), rel="x", model=None, meaning=None, theme={})  # type: ignore[arg-type]
    assert canvas_page.target(m) == "../../index.html#Gateway/Routes"
    spaced = nest.Map(id="A b", path=Path("x"), rel="x", model=None, meaning=None, theme={})  # type: ignore[arg-type]
    assert canvas_page.target(spaced) == "../index.html#A%20b"


def test_the_canvas_page_holds_the_data_one_time(canvas_root: Path) -> None:
    """Acceptance 3."""
    top = _read(canvas_root, "index.html")
    found = DATA.findall(top)
    assert len(found) == 1
    cfg, tree, facts = _loaded(canvas_root)
    assert json.loads(found[0]) == json.loads(canvas_data.text(canvas_data.build(cfg, tree, facts)))
    assert top.count("Takes the requests.") == 1


def test_the_data_cannot_end_its_element() -> None:
    """Acceptance 3: a "<" in a text of the data becomes an escape."""
    data = {"v": 1, "name": "</script><script>alert(1)</script>", "maps": []}
    built = canvas_page.build({"scheme": "dark", "schemes": {}, **_theme()}, data)
    (text,) = DATA.findall(built)
    assert "<" not in text
    assert json.loads(text)["name"] == data["name"]


def _theme() -> dict[str, Any]:
    cfg = config.load(Path(__file__).resolve().parent.parent)
    return dict(nest.load(cfg).top.theme)


def _digest(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def test_the_policy_has_the_digest_of_each_script_and_style(canvas_root: Path) -> None:
    """Acceptance 4."""
    top = _read(canvas_root, "index.html")
    policy = page_csp.of_page(top)
    scripts = re.findall(r"<script>(.*?)</script>", top, re.S)
    styles = re.findall(r"<style>(.*?)</style>", top, re.S)
    assert len(scripts) == 2 and len(styles) == 1
    directives = dict(part.split(" ", 1) for part in policy.split("; "))
    assert sorted(directives["script-src"].split()) == sorted(_digest(s) for s in scripts)
    assert directives["style-src-elem"] == _digest(styles[0])
    assert "connect-src" not in directives


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('render = "yes"\n', "render must be a table"),
        ("[render]\ncanvas = 1\n", "render.canvas must be true or false"),
        ("[render]\nlinked = true\n", "render has an unknown key: linked"),
    ],
)
def test_a_wrong_render_value_is_a_configuration_error(
    tmp_path: Path, text: str, error: str
) -> None:
    """Acceptance 5."""
    # A key of the top table must come before the first table of the file.
    write_tree(
        tmp_path, {"systemap.toml": (text + CONFIG) if "[" not in text else CONFIG + text, **SOURCE}
    )
    with pytest.raises(config.ConfigError, match=re.escape(error)):
        config.load(tmp_path)
