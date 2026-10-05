"""The nested-map loader makes a tree of maps from component map paths.

The top map contains components that can open their own internal maps. Each nested map
has an ID from the parent component path. A nested map cannot open itself or another
ancestor model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import theme as theme_mod
from systemap.config import Config, ConfigError, load_model
from systemap.model import Component, Meaning, Model, all_layers

# Past this many cards a single map stops working; `systemap suggest`
# says so and names the cards to open.
CARDS_PER_MAP = 40
# A card whose modules exceed this many is a candidate to open, whatever
# the map's size; the skill's target is three to ten modules per card.
MODULES_PER_CARD = 10


@dataclass(frozen=True)
class Map:
    """This record contains the top map or one nested map.

    The top map has an empty ID. Nested IDs use component IDs separated by slashes. The
    card field identifies the parent component. The parent field identifies the parent
    map.
    """

    id: str
    path: Path
    rel: str
    model: Model
    meaning: Meaning
    theme: dict[str, Any]
    parent: str | None = None
    card: str = ""

    @property
    def top(self) -> bool:
        return self.parent is None

    @property
    def prefix(self) -> str:
        """This property gives the diagnostic prefix for a nested map, or an empty string
        for the top map.
        """
        return f"{self.id}: " if self.id else ""

    @property
    def inside(self) -> int:
        """This property counts internal components without actors."""
        return sum(1 for c in self.model.components if c.kind != "actor")

    def page_path(self, cfg: Config) -> Path:
        """This method gives index.html in the map output directory."""
        return cfg.out_path / self.id / "index.html" if self.id else cfg.page_path


@dataclass(frozen=True)
class Tree:
    """This record lists the top map first, then nested maps in component depth-first
    order.
    """

    maps: tuple[Map, ...]

    @property
    def top(self) -> Map:
        return self.maps[0]

    @property
    def nested(self) -> bool:
        return len(self.maps) > 1

    @property
    def ids(self) -> list[str]:
        return [m.id for m in self.maps]

    def get(self, map_id: str) -> Map:
        for m in self.maps:
            if m.id == map_id:
                return m
        raise KeyError(map_id)

    def has(self, map_id: str) -> bool:
        return any(m.id == map_id for m in self.maps)

    def children(self, m: Map) -> list[Map]:
        return [child for child in self.maps if child.parent == m.id]

    def parent_of(self, m: Map) -> Map | None:
        return None if m.parent is None else self.get(m.parent)

    def opening_card(self, m: Map) -> Component | None:
        """This function gives the parent component that opens the map, or None for the top
        map.
        """
        parent = self.parent_of(m)
        return None if parent is None else parent.model.component(m.card)


def _child_id(parent: Map, card: str) -> str:
    return f"{parent.id}/{card}" if parent.id else card


def load(cfg: Config) -> Tree:
    """This function loads all model modules in the map tree.

    An import error, missing MODEL or MEANING, missing file, or model cycle gives a
    configuration error.
    """
    model, meaning = load_model(cfg.model_path, cfg.model)
    top = Map("", cfg.model_path, cfg.model, model, meaning, _theme(cfg, model, meaning), None, "")
    maps = [top]
    _walk(cfg, top, [cfg.model_path.resolve()], maps)
    return Tree(tuple(maps))


def _theme(cfg: Config, model: Model, meaning: Meaning) -> dict[str, Any]:
    try:
        return theme_mod.resolve(cfg.theme, all_layers(model, meaning))
    except ValueError as exc:
        raise ConfigError(f"{cfg.source or 'theme'}: {exc}") from exc


def _walk(cfg: Config, parent: Map, above: list[Path], maps: list[Map]) -> None:
    for c in parent.model.opening:
        if c.kind == "actor" or c.map is None:
            continue
        path = (parent.path.parent / c.map).resolve()
        rel = cfg.rel(path)
        if path in above:
            chain = " -> ".join(cfg.rel(p) for p in above)
            raise ConfigError(
                f"{parent.rel}: {c.id} opens {rel}, which is already a parent map ({chain}). A "
                f"map cannot open itself."
            )
        if not path.is_file():
            raise ConfigError(
                f"{parent.rel}: {c.id} opens {rel}, which is missing. Write the nested model "
                f"module at this path, or remove map from the component."
            )
        model, meaning = load_model(path, rel)
        child = Map(
            _child_id(parent, c.id),
            path,
            rel,
            model,
            meaning,
            _theme(cfg, model, meaning),
            parent.id,
            c.id,
        )
        maps.append(child)
        _walk(cfg, child, [*above, path], maps)


def opens(tree: Tree, m: Map, links: bool = True) -> dict[str, dict[str, Any]]:
    """This function gives nested-map names, links, component counts, and preview data for
    the panel.

    Page links are relative to the selected map. Figures omit these links because their
    location can differ.
    """
    return {
        child.card: {
            "name": child.card,
            "href": f"{child.card}/index.html" if links else "",
            "cards": child.inside,
            "preview": "",
        }
        for child in tree.children(m)
    }


def unknown_map(tree: Tree, map_id: str) -> ConfigError:
    """This function gives an unknown-map diagnostic with the available map IDs."""
    known = ", ".join(m.id for m in tree.maps if m.id) or "none"
    return ConfigError(
        f"unknown map id: {map_id}. The nested map IDs are {known} (the top map uses no --map)."
    )
