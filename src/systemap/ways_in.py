"""The ways into a system: routes, commands, tasks and plugin hooks, read from the source.

An entry point is where somebody outside meets the system: a person typing
a command, a browser asking for a URL, a queue handing over a job. Each one
is a walk a reader may need, so `systemap judgement` asks for a journey from
each, and `systemap journeys` can draft one.

`systemap.extract` finds the plain ones itself: console scripts, `__main__`
modules, `main` functions, argparse subcommands, and the public functions of
a package root. This module finds the ones that a framework registers, where
the way in is a decorator or a table rather than a function anybody calls:

    routes ..... FastAPI and its routers, Flask, and Django's urlpatterns
                 (the path as written: a router mounted under a prefix is
                 read without it, since the prefix is set where it is mounted)
    commands ... click, typer, cleo, and Django's management commands
    tasks ...... Celery, and anything whose decorator reads as a task
    plugins .... the entry-point groups a package publishes

Everything here is read from the syntax tree; nothing is imported and
nothing is run. A way in that only exists at runtime (a route built from a
variable, a command registered in a loop) cannot be seen, and the map says
what the tree states.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

# A decorator of these names, on a function, registers a way in.
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
COMMAND_DECORATORS = ("command", "group")
TASK_DECORATORS = ("task", "shared_task", "periodic_task")
# Django and its relatives register routes in a list of calls.
ROUTE_CALLS = ("path", "re_path", "url")


def _literal(node: ast.expr | None) -> str:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ""


def _dotted(node: ast.expr) -> str:
    """The dotted name of an expression, as far as it is one: `app.router.get`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else node.attr
    return ""


def _methods(call: ast.Call) -> list[str]:
    """The HTTP methods a Flask-style route names, upper case; GET when it names none."""
    for kw in call.keywords:
        if kw.arg != "methods" or not isinstance(kw.value, ast.List | ast.Tuple):
            continue
        found = [_literal(e).upper() for e in kw.value.elts if _literal(e)]
        if found:
            return found
    return ["GET"]


def _from_decorator(call: ast.Call, func: str) -> list[dict[str, str]]:
    """The ways in one decorator registers, if it is one of the shapes above.

    A command decorator has to be called on something (`@app.command()`,
    `@cli.group()`): that something is the command line the function joins.
    A bare `@group()` is a decorator of another kind, and rich's, which
    groups renderables, is why this is checked.
    """
    name = _dotted(call.func)
    last = name.rsplit(".", 1)[-1]
    on_something = "." in name
    first = _literal(call.args[0]) if call.args else ""
    given = next((_literal(kw.value) for kw in call.keywords if kw.arg == "name"), "")
    if last in HTTP_METHODS and first.startswith("/"):
        return [{"kind": "route", "name": f"{last.upper()} {first}", "target": func}]
    if last == "route" and first.startswith("/"):
        return [
            {"kind": "route", "name": f"{method} {first}", "target": func}
            for method in _methods(call)
        ]
    if last in COMMAND_DECORATORS and on_something:
        return [{"kind": "command", "name": first or given or func, "target": func}]
    if last in TASK_DECORATORS:
        return [{"kind": "task", "name": func, "target": func}]
    return []


def _decorated(tree: ast.AST) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                out += _from_decorator(dec, node.name)
            elif _dotted(dec).rsplit(".", 1)[-1] in TASK_DECORATORS:
                out.append({"kind": "task", "name": node.name, "target": node.name})
    return out


def _route_call(call: ast.AST) -> dict[str, str] | None:
    """One `path("x/", view)` of a urlpatterns list."""
    if not isinstance(call, ast.Call) or _dotted(call.func) not in ROUTE_CALLS:
        return None
    route = _literal(call.args[0]) if call.args else ""
    view = _dotted(call.args[1]) if len(call.args) > 1 else ""
    if not route and not view:
        return None
    return {"kind": "route", "name": f"/{route.lstrip('/')}", "target": view}


def _is_urlpatterns(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign):
        return False
    return any(t.id == "urlpatterns" for t in node.targets if isinstance(t, ast.Name))


def _url_patterns(tree: ast.AST) -> list[dict[str, str]]:
    """Django's `urlpatterns = [path("x/", view), ...]`, including `+ [...]` forms."""
    found = [
        _route_call(call)
        for node in ast.walk(tree)
        if _is_urlpatterns(node)
        for call in ast.walk(node.value)  # type: ignore[attr-defined]
    ]
    return [x for x in found if x is not None]


def _class_name(node: ast.ClassDef) -> str:
    """The literal `name = "..."` a class sets on itself, if it sets one."""
    named = ""
    for body in node.body:
        if not isinstance(body, ast.Assign | ast.AnnAssign):
            continue
        targets = body.targets if isinstance(body, ast.Assign) else [body.target]
        if any(t.id == "name" for t in targets if isinstance(t, ast.Name)):
            named = _literal(body.value)
    return named


def _class_command(node: ast.ClassDef, module: str) -> dict[str, str] | None:
    """A command written as a class: Django's `Command`, or a cleo command with a name."""
    parts = module.split(".")
    managed = len(parts) >= 3 and parts[-3:-1] == ["management", "commands"]
    bases = {_dotted(b).rsplit(".", 1)[-1] for b in node.bases}
    if managed and any(b.endswith("Command") for b in bases):
        return {"kind": "command", "name": f"manage.py {parts[-1]}", "target": node.name}
    named = _class_name(node)
    if named and any(b.endswith("Command") for b in bases):
        return {"kind": "command", "name": named, "target": node.name}
    return None


def _class_commands(tree: ast.AST, module: str) -> list[dict[str, str]]:
    found = [
        _class_command(node, module) for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]
    return [x for x in found if x is not None]


def in_source(module: str, source: str) -> list[dict[str, str]]:
    """Every way into the system this module's source registers."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    found = _decorated(tree) + _url_patterns(tree) + _class_commands(tree, module)
    return [{**point, "module": module} for point in found]


def _table(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    out: Any = data
    for key in keys:
        out = out.get(key, {}) if isinstance(out, dict) else {}
    return out if isinstance(out, dict) else {}


def in_pyproject(data: dict[str, Any], components: dict[str, Any]) -> list[dict[str, str]]:
    """The scripts and plugin hooks a package publishes, beyond `[project.scripts]`.

    Poetry writes its scripts under `[tool.poetry.scripts]`, and a package
    that extends another publishes `[project.entry-points."<group>"]`. Both
    are ways in: somebody outside calls them by name.
    """
    out: list[dict[str, str]] = []
    for name, target in sorted(_table(data, "tool", "poetry", "scripts").items()):
        text = target if isinstance(target, str) else str(target.get("callable", ""))
        module, _, func = text.partition(":")
        if module.strip() in components:
            out.append(
                {
                    "kind": "console_script",
                    "name": str(name),
                    "module": module.strip(),
                    "target": func.strip(),
                }
            )
    groups = _table(data, "project", "entry-points")
    for group, entries in sorted(groups.items()):
        out += _hooks(group, entries, components)
    return out


def _hooks(group: str, entries: Any, components: dict[str, Any]) -> list[dict[str, str]]:
    """One entry-point group's hooks, for the modules this system holds."""
    if not isinstance(entries, dict):
        return []
    out = []
    for name, target in sorted(entries.items()):
        module, _, func = str(target).partition(":")
        if module.strip() in components:
            hook = f"{group}: {name}"
            out.append(
                {"kind": "plugin", "name": hook, "module": module.strip(), "target": func.strip()}
            )
    return out


def label(point: dict[str, str]) -> str:
    """One of these ways in, the way a person would name it."""
    kind, name, module = point["kind"], point["name"], point["module"]
    if kind == "route":
        return f"{name} (route)"
    if kind == "command":
        return f"{name} (command)"
    if kind == "task":
        return f"{name}() (background task in {module})"
    if kind == "plugin":
        return f"{name} (plugin hook)"
    return ""


def read_pyproject(repo: Path) -> dict[str, Any]:
    import tomllib

    path = repo / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
