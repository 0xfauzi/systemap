"""The nested-map loader has a nesting limit and does linear work for each map.

Finding g1full-5: the loader walked the tree with recursion. A chain of about 1000 nested
model files stopped `systemap check` with RecursionError after 26.4 s (measured on the
base commit 65e5464). Each new map also resolved the path of each loaded map again, so
the work increased with the square of the number of maps.
"""

from __future__ import annotations

import pathlib
from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, nest
from systemap.config import ConfigError

MODEL = """
from systemap import Component, Meaning, Model

MODEL = Model(canvas=(0, 0), containers=(), regions=(), flows=(), flow_kinds=(), components=(
{cards}
))
MEANING = Meaning(plain={{}})
"""


def card(name: str, opens: str | None) -> str:
    where = f', map="{opens}"' if opens else ""
    return f'    Component(id="{name}", does="Keeps values.", implemented_by=("pkg.a",){where}),'


def chain(root: Path, depth: int) -> None:
    """Write map/model.py, which opens map/n1.py, which opens map/n2.py, to map/n<depth>.py."""
    files = {}
    for level in range(depth + 1):
        name = "model.py" if level == 0 else f"n{level}.py"
        opens = f"n{level + 1}.py" if level < depth else None
        files[f"map/{name}"] = MODEL.format(cards=card("C", opens))
    write_tree(root, files)


def count_loads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    loads: list[str] = []
    real = nest.load_model

    def counted(path: Path, label: str = "", root: Path | None = None):  # type: ignore[no-untyped-def]
        loads.append(label)
        return real(path, label, root)

    monkeypatch.setattr(nest, "load_model", counted)
    return loads


def test_a_chain_of_1000_nested_maps_gives_a_config_error_that_names_the_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain(tmp_path, 1000)
    loads = count_loads(monkeypatch)
    with pytest.raises(ConfigError) as caught:
        nest.load(config.load(tmp_path))
    message = str(caught.value)
    assert message.startswith(
        f"map/n{nest.MAX_NESTING}.py: C opens map/n{nest.MAX_NESTING + 1}.py at nesting level "
        f"{nest.MAX_NESTING + 1}. The maximum nesting level is {nest.MAX_NESTING} "
        "(map/model.py -> map/n1.py -> map/n2.py -> "
    )
    assert f"-> map/n{nest.MAX_NESTING + 1}.py)" in message
    assert "Remove the map argument from a component in this chain." in message
    # The loader stops at the limit. It does not read the remaining model files.
    assert len(loads) == nest.MAX_NESTING + 1


def test_a_chain_at_the_limit_loads(tmp_path: Path) -> None:
    chain(tmp_path, nest.MAX_NESTING)
    tree = nest.load(config.load(tmp_path))
    assert len(tree.maps) == nest.MAX_NESTING + 1
    assert tree.maps[-1].id == "/".join(["C"] * nest.MAX_NESTING)


def test_many_nested_maps_resolve_each_path_a_fixed_number_of_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the change, 300 sibling maps resolved 45150 more paths in the duplicate check."""
    count = 300
    files = {
        "map/model.py": MODEL.format(
            cards="\n".join(card(f"C{i}", f"m{i}.py") for i in range(count))
        )
    }
    files |= {f"map/m{i}.py": MODEL.format(cards=card("D", None)) for i in range(count)}
    write_tree(tmp_path, files)
    cfg = config.load(tmp_path)
    calls = [0]
    real = pathlib.Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        calls[0] += 1
        return real(self, strict)

    monkeypatch.setattr(pathlib.Path, "resolve", resolve)
    tree = nest.load(cfg)
    assert [m.id for m in tree.maps[1:4]] == ["C0", "C1", "C2"]
    assert len(tree.maps) == count + 1
    # About 9 for each map after the change, and 45150 more before it.
    assert calls[0] < 20 * count


def test_the_order_of_the_maps_is_depth_first(tmp_path: Path) -> None:
    files = {
        "map/model.py": MODEL.format(cards="\n".join([card("A", "a.py"), card("B", "b.py")])),
        "map/a.py": MODEL.format(cards="\n".join([card("X", "x.py"), card("Y", "y.py")])),
        "map/x.py": MODEL.format(cards=card("Z", "z.py")),
        "map/z.py": MODEL.format(cards=card("Q", None)),
        "map/y.py": MODEL.format(cards=card("Q", None)),
        "map/b.py": MODEL.format(cards=card("Q", None)),
    }
    write_tree(tmp_path, files)
    tree = nest.load(config.load(tmp_path))
    assert tree.ids == ["", "A", "A/X", "A/X/Z", "A/Y", "B"]
    assert [m.parent for m in tree.maps] == [None, "", "A", "A/X", "A", ""]


def test_a_second_component_that_opens_a_loaded_file_names_the_first_map(tmp_path: Path) -> None:
    files = {
        "map/model.py": MODEL.format(cards="\n".join([card("A", "a.py"), card("B", "b.py")])),
        "map/a.py": MODEL.format(cards=card("X", "shared.py")),
        "map/b.py": MODEL.format(cards=card("Y", "shared.py")),
        "map/shared.py": MODEL.format(cards=card("Q", None)),
    }
    write_tree(tmp_path, files)
    with pytest.raises(ConfigError, match=r"^map/b.py: Y opens map/shared.py, but the map A/X "):
        nest.load(config.load(tmp_path))
