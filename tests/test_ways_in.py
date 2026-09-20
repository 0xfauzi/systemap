"""The ways into a system, and the journeys that should walk from them.

`systemap.ways_in` reads a module's syntax tree for the ways in a framework
registers: routes, commands, tasks and plugin hooks. `judgement` then asks
for a journey from each, in one line per card once a card takes more than a
few of one kind, and says when a journey jumps or starts at nothing.
"""

from __future__ import annotations

from typing import Any

from systemap import judgement, ways_in
from systemap.model import Journey, Meaning

# ---- what the source registers -----------------------------------------------------


def found(source: str, module: str = "pkg.mod") -> list[tuple[str, str, str]]:
    return [(p["kind"], p["name"], p["target"]) for p in ways_in.in_source(module, source)]


def test_web_routes_are_read_with_their_method_and_path() -> None:
    source = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/recipes/{slug}")
def read_recipe(slug): ...

@router.post("/recipes")
async def make_recipe(): ...

@app.route("/health", methods=["GET", "HEAD"])
def health(): ...
"""
    assert found(source) == [
        ("route", "GET /recipes/{slug}", "read_recipe"),
        ("route", "POST /recipes", "make_recipe"),
        ("route", "GET /health", "health"),
        ("route", "HEAD /health", "health"),
    ]


def test_django_routes_come_from_the_urlpatterns_table() -> None:
    source = """
from django.urls import path, re_path
urlpatterns = [
    path("documents/", views.documents, name="documents"),
    re_path(r"^fetch/doc/(?P<pk>\\d+)$", views.fetch),
] + extra
"""
    assert found(source) == [
        ("route", "/documents/", "views.documents"),
        ("route", "/^fetch/doc/(?P<pk>\\d+)$", "views.fetch"),
    ]


def test_commands_are_read_from_click_typer_cleo_and_django() -> None:
    click = """
@cli.group(name="config")
def config_group(): ...

@config_group.command("show")
def show(): ...

@app.command()
def serve(): ...
"""
    assert found(click) == [
        ("command", "config", "config_group"),
        ("command", "show", "show"),
        ("command", "serve", "serve"),
    ]
    cleo = """
class AddCommand(Command):
    name = "add"
    description = "add a package"
"""
    assert found(cleo) == [("command", "add", "AddCommand")]
    managed = "class Command(BaseCommand):\n    help = 'reindex'\n"
    assert found(managed, "app.management.commands.reindex") == [
        ("command", "manage.py reindex", "Command")
    ]


def test_a_decorator_that_is_not_a_way_in_is_not_one() -> None:
    # rich's @group() groups renderables; nobody types it
    assert found("@group()\ndef _render_stack(self): ...") == []
    assert found("@property\ndef name(self): ...") == []
    # a cache read is not a route, because its argument is not a path
    assert found('@cache.get("key")\ndef value(): ...') == []


def test_background_tasks_are_ways_in_too() -> None:
    source = """
@shared_task
def train_classifier(): ...

@app.task(bind=True)
def empty_trash(self): ...
"""
    assert found(source) == [
        ("task", "train_classifier", "train_classifier"),
        ("task", "empty_trash", "empty_trash"),
    ]


def test_poetry_scripts_and_plugin_hooks_are_read_from_pyproject() -> None:
    data = {
        "tool": {"poetry": {"scripts": {"poetry": "poetry.console.application:main"}}},
        "project": {"entry-points": {"pytest11": {"cov": "pkg.plugin:setup"}}},
    }
    components = {"poetry.console.application": {}, "pkg.plugin": {}}
    assert ways_in.in_pyproject(data, components) == [
        {
            "kind": "console_script",
            "name": "poetry",
            "module": "poetry.console.application",
            "target": "main",
        },
        {"kind": "plugin", "name": "pytest11: cov", "module": "pkg.plugin", "target": "setup"},
    ]
    # a script pointing outside this system is not one of its ways in
    assert ways_in.in_pyproject(data, {"pkg.plugin": {}})[0]["kind"] == "plugin"


def test_each_way_in_is_named_the_way_a_person_would_name_it() -> None:
    assert ways_in.label({"kind": "route", "name": "GET /x", "module": "m"}) == "GET /x (route)"
    assert ways_in.label({"kind": "command", "name": "add", "module": "m"}) == "add (command)"
    assert "background task" in ways_in.label({"kind": "task", "name": "t", "module": "m"})
    assert ways_in.label({"kind": "console_script", "name": "x", "module": "m"}) == ""


# ---- what judgement asks about them ------------------------------------------------


def facts_with(points: list[dict[str, str]], modules: list[str]) -> dict[str, Any]:
    return {
        "entry_points": points,
        "components": {m: {"uses": {}, "names": [], "functions": []} for m in modules},
    }


def route(name: str, module: str) -> dict[str, str]:
    return {"kind": "route", "name": name, "module": module, "target": "view"}


def test_a_card_that_takes_a_crowd_of_routes_is_asked_once(sample: Any) -> None:
    modules = ["pkg.reader"]
    points = [route(f"GET /r{n}", "pkg.reader") for n in range(6)]
    facts = facts_with(points, modules)
    lines = judgement.entry_points_without_journey(sample.model, Meaning(plain={}), facts)
    assert lines == ["entry point 6 routes into Reader have no journey (component Reader)"]
    # a few are still asked about one by one, so the map can be fixed one at a time
    facts = facts_with(points[:3], modules)
    lines = judgement.entry_points_without_journey(sample.model, Meaning(plain={}), facts)
    assert lines == [
        "entry point GET /r0 (route) has no journey (component Reader)",
        "entry point GET /r1 (route) has no journey (component Reader)",
        "entry point GET /r2 (route) has no journey (component Reader)",
    ]


def test_a_journey_covers_the_way_in_it_names_in_starts(sample: Any) -> None:
    facts = facts_with([route("GET /r", "pkg.reader")], ["pkg.reader"])
    walk = Journey(id="read", label="read one", steps=(), starts="GET /r")
    meaning = Meaning(plain={}, journeys=(walk,))
    assert judgement.entry_points_without_journey(sample.model, meaning, facts) == []
    assert judgement.journey_problems(meaning, facts) == []


def test_a_journey_that_starts_nowhere_says_so(sample: Any) -> None:
    facts = facts_with([route("GET /r", "pkg.reader")], ["pkg.reader"])
    walk = Journey(id="read", label="read one", steps=(), starts="GET /gone")
    lines = judgement.journey_problems(Meaning(plain={}, journeys=(walk,)), facts)
    assert lines == ["journey start: read starts at GET /gone, which the facts have no way in for"]
