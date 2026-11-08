"""The canvas page, the default output, and the setting `[render] canvas` (`canvas_page`,
`canvas_redirect`, `config_render`).

Acceptance values (acceptance 1, 2 and 7 to 10 are for step 5 of
docs/design/nested-canvas.md, written before the first run):

1. Without a `[render]` table, or with `canvas = true`, `render` writes the canvas page at
   the top page, and a small page at the page of each nested map. The small page goes to
   the top page with the map ID in the hash. `render --check` and `check` then agree with
   the files.
2. With `canvas = false`, `render` writes the linked pages with no change: each page is
   the text of `page.build`. `render` and `refresh` give the notice line
   `config_render.NOTICE` one time, and their exit codes are the exit codes of the run
   without the setting. Without the setting, the commands give no notice line.
3. The canvas page holds the canvas data one time, in one JSON element, and the data is
   the object of `canvas_data.build`. No "<" of the data is in the page text.
4. The CSP of the canvas page has the digest of each script element and each style
   element of the page, and no other script digest.
5. A value of `[render]` that is not correct gives a configuration error.
6. The canvas page has the parts for a screen reader: the canvas has the role img, a
   label with the name of the map, and a description of the inputs. After the canvas, the
   page has one empty `nav` element for the list of the tree and one polite live region.
   The canvas, the help text, the list and the live region are in one `main` element. The
   script writes the list from the canvas data (`buildTree`) and does not give the card
   texts a second time. A link of the list with the focus has a box of 44 pixels high
   or more. The tree part adds 12,000 bytes or less to the page.
7. The small page (`canvas_redirect`): a viewport meta element, one script element in the
   head, and the SHA-256 digest of that script is the only source of script-src. The
   script goes to the address of the top page and adds the incoming hash after the map
   ID. A refresh meta element and a visible link go to `index.html#<map ID>`. The policy
   has default-src 'none', no connect-src and frame-src 'none'. The page has 2,048 bytes
   or less for a map ID of 40 characters. A map ID with a space or with a "<" character
   is quoted in each address.
8. The policy of the canvas page has frame-src 'none'. The linked pages of
   `canvas = false` keep frame-src 'self'.
9. `check` and `render --check` exit 1 after one changed byte in the canvas page, after
   one changed byte in a small page, and after a change of a `does` text of the model
   without `refresh`. Each line of a changed page names the file.
10. The caption of a figure of a nested map names the top page with the map ID in the
    hash (`docs/map/index.html#Gateway`). With `canvas = false`, it names the linked page.
    `check` finds a figure with the caption of the linked page as stale.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_nest_join import CONFIG, NESTED, SOURCE, TOP

from systemap import (
    canvas_data,
    canvas_page,
    canvas_redirect,
    config,
    config_render,
    facts_file,
    judgement_json,
    nest,
    page,
    page_canvas_tree,
    page_csp,
)
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


LINKED = "[render]\ncanvas = false\n"


def test_without_the_setting_render_writes_the_canvas_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1 and 2: the default is the canvas page, with no notice line."""
    root = _made(tmp_path, "")
    assert config_render.NOTICE not in capsys.readouterr().err
    cfg, tree, facts = _loaded(root)
    assert cfg.render_canvas
    for m, text in canvas_page.pages(cfg, tree, facts):
        assert m.page_path(cfg).read_text(encoding="utf-8") == text
    assert '<canvas id="canvas"' in _read(root, "index.html")
    assert "<canvas" not in _read(root, "Gateway/index.html")


def test_with_canvas_false_render_writes_the_linked_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 2 and 8."""
    root = _made(tmp_path, LINKED)
    assert capsys.readouterr().err.count(config_render.NOTICE) == 1
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
        assert "frame-src 'self'" in page_csp.of_page(built).split("; ")


@pytest.mark.parametrize("command", [["render"], ["render", "--check"], ["refresh"]])
def test_the_notice_line_keeps_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    """Acceptance 2: the same exit code with and without the notice line."""
    codes = {}
    for name, setting in (("canvas", ""), ("linked", LINKED)):
        root = _made(tmp_path / name, setting)
        capsys.readouterr()
        codes[name] = main(["--root", str(root), *command])
        err = capsys.readouterr().err
        assert err.count(config_render.NOTICE) == (1 if setting else 0), err
    assert codes["canvas"] == codes["linked"]


@pytest.fixture(scope="module")
def canvas_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _made(tmp_path_factory.mktemp("canvas"), "[render]\ncanvas = true\n")


def test_with_the_setting_render_writes_the_canvas_page(canvas_root: Path) -> None:
    """Acceptance 1."""
    top = _read(canvas_root, "index.html")
    assert '<canvas id="canvas"' in top
    assert "window.systemapCanvas" in top
    nested = _read(canvas_root, "Gateway/index.html")
    assert '<meta http-equiv="refresh" content="0;url=../index.html#Gateway">' in nested
    assert '<a href="../index.html#Gateway">' in nested
    assert "<canvas" not in nested
    assert main(["--root", str(canvas_root), "render", "--check"]) == 0
    assert main(["--root", str(canvas_root), "check"]) == 0


def _map(map_id: str) -> nest.Map:
    return nest.Map(id=map_id, path=Path("x"), rel="x", model=None, meaning=None, theme={})  # type: ignore[arg-type]


def test_a_deep_map_goes_to_the_top_page_with_its_path() -> None:
    """Acceptance 7: the URL of the small page of a map on level 2."""
    assert canvas_redirect.target(_map("Gateway/Routes")) == "../../index.html#Gateway/Routes"
    assert canvas_redirect.target(_map("A b")) == "../index.html#A%20b"
    assert canvas_redirect.target(_map("")) == "index.html"


def _head_script(text: str) -> str:
    head = text[: text.index("</head>")]
    (script,) = re.findall(r"<script>(.*?)</script>", head, re.S)
    assert text.count("<script") == 1
    return str(script)


@pytest.mark.parametrize("map_id", ["Gateway", "Gateway/Routes", "A b/<i>" + "x" * 33])
def test_the_small_page_goes_to_the_top_page_with_the_hash(map_id: str) -> None:
    """Acceptance 7."""
    m = _map(map_id)
    text = canvas_redirect.page(m)
    url = canvas_redirect.target(m)
    assert '<meta name="viewport" content="width=device-width,initial-scale=1">' in text
    script = _head_script(text)
    directives = dict(part.split(" ", 1) for part in page_csp.of_page(text).split("; "))
    assert directives["script-src"] == _digest(script)
    assert directives["default-src"] == "'none'"
    assert directives["frame-src"] == "'none'"
    assert directives["style-src-elem"] == "'none'"
    assert "connect-src" not in directives
    # The script has the fixed address, and it adds only the hash after its "#".
    assert json.dumps(url) in script
    assert 'location.replace(t+(h?"/"+h:""))' in script
    assert "<" not in url and " " not in url
    assert f'<meta http-equiv="refresh" content="0;url={url}">' in text
    assert f'<a href="{url}">canvas page</a>' in text
    assert "<i>" not in text
    assert len(text.encode("utf-8")) <= 2048


def test_the_small_page_script_adds_the_hash() -> None:
    """Acceptance 7: the script in Node, with a hash for a card, no hash, and hashes that
    name a different site. The address stays relative to the small page, and the hash
    stays after its "#"."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("the test needs the node command")
    script = _head_script(canvas_redirect.page(_map("Gateway")))
    probe = (
        "const out=[];for(const hash of process.argv.slice(1)){"
        "const location={hash,replace:(u)=>out.push(u)};"
        + script
        + "}process.stdout.write(JSON.stringify(out));"
    )
    hashes = ["#Routes", "", "#//example.com/x", "#javascript:alert(1)"]
    proc = subprocess.run(
        [node, "-e", probe, "--", *hashes], capture_output=True, text=True, timeout=60, check=True
    )
    assert json.loads(proc.stdout) == [
        "../index.html#Gateway/Routes",
        "../index.html#Gateway",
        "../index.html#Gateway///example.com/x",
        "../index.html#Gateway/javascript:alert(1)",
    ]


def test_the_canvas_page_permits_no_frame(canvas_root: Path) -> None:
    """Acceptance 8."""
    for rel in ("index.html", "Gateway/index.html"):
        policy = page_csp.of_page(_read(canvas_root, rel)).split("; ")
        assert "frame-src 'none'" in policy, rel
        assert "frame-src 'self'" not in policy, rel


def _differs(out: str) -> list[str]:
    """Give the file of each line that tells of a file that differs from the output."""
    return [line.split()[0] for line in out.splitlines() if "differs from the" in line]


def test_check_finds_a_changed_page(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Acceptance 9."""
    root = _made(tmp_path, "")
    for rel in ("index.html", "Gateway/index.html"):
        path = root / "docs" / "map" / rel
        good = path.read_bytes()
        at = good.index(b"</body>") - 1
        path.write_bytes(good[:at] + (b"?" if good[at : at + 1] == b"!" else b"!") + good[at + 1 :])
        for command in (["check"], ["render", "--check"]):
            capsys.readouterr()
            assert main(["--root", str(root), *command]) == 1, (rel, command)
            assert _differs(capsys.readouterr().out) == [f"docs/map/{rel}"], (rel, command)
        path.write_bytes(good)
    assert main(["--root", str(root), "check"]) == 0
    model = root / "map" / "gateway.py"
    model.write_text(
        model.read_text(encoding="utf-8").replace("Takes the routes.", "Takes each route."),
        encoding="utf-8",
    )
    for command in (["check"], ["render", "--check"]):
        capsys.readouterr()
        assert main(["--root", str(root), *command]) == 1, command
        assert _differs(capsys.readouterr().out) == ["docs/map/index.html"], command


FIGURE = (
    '[[figures]]\nout = "gateway.html"\nmap = "Gateway"\nmode = "reach"\ncomponents = ["Routes"]\n'
)


@pytest.mark.parametrize(
    ("setting", "named"),
    [("", "docs/map/index.html#Gateway"), (LINKED, "docs/map/Gateway/index.html")],
)
def test_a_figure_of_a_nested_map_names_its_page(tmp_path: Path, setting: str, named: str) -> None:
    """Acceptance 10."""
    root = _made(tmp_path, setting + FIGURE)
    assert main(["--root", str(root), "refresh"]) == 0
    path = root / "docs" / "map" / "gateway.html"
    text = path.read_text(encoding="utf-8")
    assert f"the map at <code>{named}</code>." in text
    if setting:
        return
    path.write_text(text.replace(named, "docs/map/Gateway/index.html"), encoding="utf-8")
    assert main(["--root", str(root), "check"]) == 1


def test_the_canvas_page_holds_the_data_one_time(canvas_root: Path) -> None:
    """Acceptance 3."""
    top = _read(canvas_root, "index.html")
    found = DATA.findall(top)
    assert len(found) == 1
    cfg, tree, facts = _loaded(canvas_root)
    still = judgement_json.open_boundary(tree, facts, cfg)
    data = canvas_data.build(cfg, tree, facts, open_lines=still)
    assert json.loads(found[0]) == json.loads(canvas_data.text(data))
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
    scripts = re.findall(r"<script>(.*?)</script>", top, re.S | re.I)
    styles = re.findall(r"<style>(.*?)</style>", top, re.S | re.I)
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


def test_the_page_has_the_parts_for_a_screen_reader(canvas_root: Path) -> None:
    """Acceptance 6."""
    top = _read(canvas_root, "index.html")
    canvas = re.search(r"<canvas [^>]*>", top)
    assert canvas is not None
    assert 'role="img"' in canvas.group(0)
    assert 'aria-label="System map: join"' in canvas.group(0)
    assert 'aria-describedby="canvas-help"' in canvas.group(0)
    assert '<p id="canvas-help" class="sr-only">' in top
    after = top[top.index("</canvas>") :]
    assert after.count('<nav id="canvas-tree" class="tree" aria-label="Map tree"></nav>') == 1
    assert after.count('<p id="canvas-said" class="sr-only" aria-live="polite"></p>') == 1
    assert "setTimeout(buildTree, 0)" in top
    assert re.search(
        r"<body><header class=\"cbar\" [^>]*>.*</header><main><canvas .*</nav>"
        r"<p id=\"canvas-said\"[^>]*></p></main>",
        top,
    )
    assert top.count("Takes the requests.") == 1
    assert re.search(r"\.tree a:focus\{[^}]*min-height:44px", top)
    added = (page_canvas_tree.CSS + page_canvas_tree.HTML + page_canvas_tree.TREE).encode()
    assert len(added) <= 12_000
