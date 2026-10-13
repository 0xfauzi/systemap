"""The live map writes only in its directory, and the servers read only in their directory.

Acceptance (Codex results cli-1, cli-9, cli-10, cli-11, cli-13):
- cli-1: a rendered page name outside the served directory gives `state: error`, and no
  file outside the directory. A component that opens a map with the ID `../Escape` gives
  ConfigError from `render_tree`.
- cli-10: a page write that raises OSError gives `state: error`. The next request
  renders again, and its good result gives `state: ready`.
- cli-11: a request for a symbolic link to a file or a directory outside the served
  directory gives 404. A symbolic link to a file in the directory gives 200.
- cli-13: after a good version without a nested page, that page is not on disk, and its
  empty directory is not on disk.
- cli-9: the watched files include each language configuration file (the names in
  `config_files` of the adapter) in the folders between a package root and the
  repository root, and below a package root. Python and TypeScript fixtures.
"""

from __future__ import annotations

import http.client
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import write_tree
from test_live import Events, render
from test_nested import edit, nested  # noqa: F401 - a fixture

from systemap import live_watch, serve
from systemap.config import ConfigError

PAGE = "<html><body>map</body></html>"


def _live(out: Path, *versions: dict[str, str]) -> serve.LiveMap:
    """Give a live map whose renders give the versions in order. The last one repeats."""
    pending = list(versions)

    def rendered() -> serve.Rendered:
        files = pending.pop(0) if len(pending) > 1 else pending[0]
        return serve.Rendered(files=dict(files))

    return serve.LiveMap(out, rendered, Events())


# ---- cli-1: writes stay in the served directory ----------------------------------------


def test_a_page_name_outside_the_served_directory_is_refused(tmp_path: Path) -> None:
    out = tmp_path / "served" / "out"
    live = _live(out, {"index.html": PAGE, "../../escape.html": PAGE})
    state = render(live)
    assert state["state"] == "error"
    assert "not in the output directory" in state["error"]
    assert not (tmp_path / "escape.html").exists()


def test_a_nested_map_id_with_dot_segments_is_refused(nested: Path) -> None:  # noqa: F811
    edit(nested, "map/model.py", 'id="Gateway"', 'id="../Escape"')
    edit(nested, "map/model.py", '"Gateway"', '"../Escape"')
    with pytest.raises(ConfigError, match="opens a map"):
        serve.render_tree(nested, "")


# ---- cli-10: a failed write does not stop the versions ---------------------------------


def test_a_failed_page_write_gives_an_error_and_the_next_version_renders(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    live = _live(out, {"index.html": PAGE, "sub/index.html": PAGE}, {"index.html": PAGE})
    (out / "sub").write_text("a file, not a directory", encoding="utf-8")
    state = render(live)
    assert state["state"] == "error" and state["version"] == 1
    state = render(live)
    assert state["state"] == "ready" and state["version"] == 2


# ---- cli-13: the pages of removed maps go -----------------------------------------------


def test_a_good_version_removes_the_pages_of_removed_maps(tmp_path: Path) -> None:
    out = tmp_path / "out"
    child = {"index.html": PAGE, "Child/index.html": PAGE, "Child/Inner/index.html": PAGE}
    live = _live(out, child, {"index.html": PAGE})
    assert render(live)["state"] == "ready"
    assert (out / "Child/Inner/index.html").is_file()
    assert render(live)["state"] == "ready"
    assert (out / "index.html").is_file()
    assert not (out / "Child").exists()


# ---- cli-11: the server reads only in its directory --------------------------------------


@pytest.fixture
def linked(tmp_path: Path) -> Iterator[int]:
    served, outside = tmp_path / "served", tmp_path / "outside"
    write_tree(served, {"index.html": PAGE, "page.html": PAGE})
    write_tree(outside, {"secret.txt": "secret", "index.html": "secret"})
    (served / "private").symlink_to(outside, target_is_directory=True)
    (served / "secret.txt").symlink_to(outside / "secret.txt")
    (served / "inner").mkdir()
    (served / "inner" / "index.html").symlink_to(outside / "index.html")
    (served / "same.html").symlink_to(served / "page.html")
    httpd = serve.make_server(served, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()


def _status(port: int, path: str) -> tuple[int, str]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    answer = connection.getresponse()
    body = answer.read().decode("utf-8", "replace")
    connection.close()
    return answer.status, body


def test_the_server_refuses_links_outside_its_directory(linked: int) -> None:
    for path in ("/private/secret.txt", "/private/", "/secret.txt", "/inner/", "/inner/index.html"):
        status, body = _status(linked, path)
        assert status == 404, path
        assert "secret" not in body, path
    assert _status(linked, "/same.html") == (200, PAGE)
    assert _status(linked, "/") == (200, PAGE)


# ---- cli-9: the watcher scans nested configuration files ---------------------------------


def _watched(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in live_watch.watched(root) if p.exists()}


def test_the_watcher_scans_nested_typescript_configuration(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"packages/web/src" = "web"\n',
            "packages/web/src/app.ts": "export const app = 1;\n",
            "packages/web/src/lib/package.json": '{"name": "lib"}\n',
            "packages/web/tsconfig.json": '{"compilerOptions": {"paths": {}}}\n',
            "packages/web/package.json": '{"name": "web"}\n',
            "packages/package.json": '{"name": "all"}\n',
            "other/tsconfig.json": "{}\n",
        },
    )
    found = _watched(tmp_path)
    assert {
        "packages/web/tsconfig.json",
        "packages/web/package.json",
        "packages/package.json",
        "packages/web/src/lib/package.json",
        "packages/web/src/app.ts",
    } <= found
    assert "other/tsconfig.json" not in found


def test_the_watcher_scans_nested_python_configuration(tmp_path: Path) -> None:
    write_tree(
        tmp_path,
        {
            "systemap.toml": 'language = "python"\n[package_roots]\n"libs/core/src/core" = "core"\n',
            "libs/core/src/core/__init__.py": "",
            "libs/core/pyproject.toml": '[project]\nname = "core"\n',
            "other/pyproject.toml": '[project]\nname = "other"\n',
        },
    )
    found = _watched(tmp_path)
    assert {"libs/core/pyproject.toml", "libs/core/src/core/__init__.py"} <= found
    assert "other/pyproject.toml" not in found
