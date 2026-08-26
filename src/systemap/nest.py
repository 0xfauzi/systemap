"""Nested maps: a card that opens a map of its own, and the tree they form.

One canvas cannot hold a large repository legibly, and past forty cards
the readings stop being readings. A component may carry `map`, a path
relative to its model file naming a sub-model module that exports `MODEL`
and `MEANING` like any model. The sub-map draws the inside of that one
card: its cards claim exactly the modules the card claims (symbol claims
allowed, empty package markers left out as the coverage rule leaves them
out), no more and no fewer, and its actors are cards of the map it is
inside, so its edges to the outside have somewhere to land. The parent
claims the modules once for coverage; the nesting rule of `systemap
check` holds the sub-map to them.

Every command that reads the model walks the tree this module loads:
the top map first, then each sub-map depth first in the order the parent
lists its cards. A map is named by the cards that open it, joined by
`/` (`Gateway`, `Gateway/Routes`); the top map's id is empty. A sub-map's
page is written under the output directory at `<id>/index.html`, and the
lines a command prints for a sub-map carry `<id>: ` in front.
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
    """One map in the tree: the top map, or the map inside one card.

    `id` is empty for the top map and the opening cards' ids joined by
    `/` below it; `card` is the parent card that opens this map and
    `parent` the parent map's id. `rel` is the model file relative to
    the root, the name messages call it by.
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
        """What a line printed for this map carries in front: nothing for the top."""
        return f"{self.id}: " if self.id else ""

    @property
    def inside(self) -> int:
        """How many cards the map holds of its own: every card but the actors."""
        return sum(1 for c in self.model.components if c.kind != "actor")

    def page_path(self, cfg: Config) -> Path:
        """Where the map's page is written: `index.html` under the map's directory."""
        return cfg.out_path / self.id / "index.html" if self.id else cfg.page_path


@dataclass(frozen=True)
class Tree:
    """Every map, the top first, then depth first in the parents' card order."""

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
        """The parent's card that opens `m`; None for the top map."""
        parent = self.parent_of(m)
        return None if parent is None else parent.model.component(m.card)


def _child_id(parent: Map, card: str) -> str:
    return f"{parent.id}/{card}" if parent.id else card


def load(cfg: Config) -> Tree:
    """The tree of maps under the configured model, every module loaded.

    A sub-model that does not import, or names no MODEL and MEANING, is
    refused the way the top model is; a sub-map that names a model file
    already on the path above it is a cycle and refused too. An actor's
    `map` is not followed: the placement rule reports it.
    """
    model, meaning = load_model(cfg.model_path, cfg.model)
    top = Map("", cfg.model_path, cfg.model, model, meaning, _theme(cfg, model, meaning), None, "")
    maps = [top]
    _walk(cfg, top, [cfg.model_path.resolve()], maps)
    return Tree(tuple(maps))


def _theme(cfg: Config, model: Model, meaning: Meaning) -> dict[str, Any]:
    return theme_mod.resolve(cfg.theme, all_layers(model, meaning))


def _walk(cfg: Config, parent: Map, above: list[Path], maps: list[Map]) -> None:
    for c in parent.model.opening:
        if c.kind == "actor" or c.map is None:
            continue
        path = (parent.path.parent / c.map).resolve()
        rel = cfg.rel(path)
        if path in above:
            chain = " -> ".join(cfg.rel(p) for p in above)
            raise ConfigError(
                f"{parent.rel}: {c.id} opens {rel}, which is already a map above it "
                f"({chain}); a map cannot open itself"
            )
        if not path.is_file():
            raise ConfigError(
                f"{parent.rel}: {c.id} opens {rel}, which does not exist; write the "
                f"sub-model module there, or remove map from the card"
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
    """What each opening card of `m` opens, for the panel: name, link, cards, preview.

    The link is relative to the map's own page (`<card>/index.html`); a
    figure, which may be embedded anywhere, is given none. `preview` is
    the drawing the page fills in (`page.nesting_of`, the sub-map's
    Structure reading as a small SVG); empty here and in a figure.
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
    """The refusal for a map id the tree does not have, with the ids it does."""
    known = ", ".join(m.id for m in tree.maps if m.id) or "none"
    return ConfigError(
        f"unknown map id: {map_id}; the maps inside a card are {known} (the top map needs no --map)"
    )
