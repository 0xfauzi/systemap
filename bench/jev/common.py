"""Shared loading for the Jev experiments: the benchmark repos, their maps and facts."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from systemap import config, extract, nest
from systemap.extract import is_empty_marker
from systemap.model import Meaning, Model, claimed

HERE = Path(__file__).parent
DATA = HERE / "data"
SYSTEMAP = HERE.parents[1]
SCRATCH = SYSTEMAP / "bench/scratch"

REPOS = {
    "kstrl": SCRATCH / "kstrl-first-map-20260826T114300Z/repo",
    "mealie": SCRATCH / "mealie-first-map-20260826T142022Z/repo",
    "paperless": SCRATCH / "paperless-ngx-first-map-20260826T125316Z/repo",
    "poetry": SCRATCH / "poetry-first-map-20260826T121716Z/repo",
    "rich": SCRATCH / "rich-first-map-20260826T132926Z/repo",
}


@dataclass
class Repo:
    name: str
    root: Path
    cfg: Any
    model: Model
    meaning: Meaning
    facts: dict[str, Any]
    owner: dict[str, str]  # module -> component id (top map)

    @property
    def records(self) -> dict[str, Any]:
        return self.facts["components"]

    def comp(self, cid: str):
        return next(c for c in self.model.components if c.id == cid)

    def modules_of(self, cid: str) -> list[str]:
        return sorted(m for m, c in self.owner.items() if c == cid)

    def placeable(self) -> list:
        """Components a module can belong to: every non-actor card."""
        return [c for c in self.model.components if c.kind != "actor"]


@cache
def load(name: str) -> Repo:
    root = REPOS[name] if name in REPOS else SYSTEMAP
    cfg = config.load(root)
    tree = nest.load(cfg)
    cache_file = DATA / f"facts-{name}.json"
    if cache_file.exists():
        facts = json.loads(cache_file.read_text())
    else:
        facts = extract.build(cfg)
        cache_file.write_text(json.dumps(facts))
    model, meaning = tree.top.model, tree.top.meaning
    mods = [m for m, r in facts["components"].items() if not is_empty_marker(r)]
    owner: dict[str, str] = {}
    for c in model.components:
        for m in claimed(c, mods):
            owner.setdefault(m, c.id)
    return Repo(name, root, cfg, model, meaning, facts, owner)


def first_sentence(text: str, cap: int = 300) -> str:
    text = " ".join((text or "").split())
    for end in (". ", ".\n"):
        i = text.find(end)
        if i != -1:
            text = text[: i + 1]
            break
    return text[:cap]


def module_state(repo: Repo, m: str, *, doc_cap: int = 600, names_cap: int = 40) -> dict[str, Any]:
    """What a reader of the facts knows about one module, compact."""
    r = repo.records[m]
    doc = " ".join((r.get("docstring") or "").split())[:doc_cap]
    names = [f"{n['name']} ({n['kind']})" for n in r.get("names", [])][:names_cap]
    return {
        "module": m,
        "docstring": doc or None,
        "public_names": names,
        "imports": sorted(r.get("imports", []))[:20],
        "imported_by": sorted(r.get("imported_by", []))[:20],
    }


def component_brief(repo: Repo, cid: str) -> str:
    c = repo.comp(cid)
    plain = repo.meaning.plain.get(cid, "")
    parts = [f"{plain}." if plain else "", c.does]
    if c.interface:
        parts.append(f"Interface: {c.interface}")
    return " ".join(p for p in parts if p)


def write(exp: str, rows: list[dict[str, Any]]) -> None:
    path = DATA / f"{exp}.jsonl"
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"{exp}: {len(rows)} items -> {path.name}")


def rng(seed: str) -> random.Random:
    return random.Random(seed)


NONE = "none of these"


def owner_criteria(repo: Repo) -> dict[str, str]:
    """Every card a module could belong to, described, and a way to say none fits."""
    crit = {c.id: component_brief(repo, c.id) for c in repo.placeable()}
    crit[NONE] = "No component on this map carries out what this module does."
    return crit


def row(exp: str, repo: str, id_: str, state: Any, questions: dict, label: dict) -> dict[str, Any]:
    return {
        "exp": exp,
        "repo": repo,
        "id": id_,
        "state": state,
        "questions": questions,
        "label": label,
    }


def noul(instructions: str) -> dict[str, str]:
    return {"type": "noul", "instructions": instructions}


def choice(instructions: str, criteria: dict[str, str]) -> dict[str, Any]:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}
