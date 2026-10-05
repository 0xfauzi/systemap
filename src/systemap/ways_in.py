"""The entry point reader finds routes, commands, background tasks, and plugin hooks in
source code.

An entry point lets a person or another system start an operation. The reader records
literal registrations for supported frameworks. An unknown framework binding gives a
diagnostic rather than assumed coverage.
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
    """This function reads the dotted name of an expression, such as app.router.get."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else node.attr
    return ""


def _methods(call: ast.Call) -> list[str]:
    """This function reads HTTP methods from a Flask-style route, with GET as the default."""
    for kw in call.keywords:
        if kw.arg != "methods" or not isinstance(kw.value, ast.List | ast.Tuple):
            continue
        found = [_literal(e).upper() for e in kw.value.elts if _literal(e)]
        if found:
            return found
    return ["GET"]


def _from_decorator(call: ast.Call, func: str, bindings: dict[str, str]) -> list[dict[str, str]]:
    """This function reads entry point registrations from supported decorator forms.

    Command decorators must have a receiver, such as @app.command() or @cli.group().
    """
    name = _dotted(call.func)
    last = name.rsplit(".", 1)[-1]
    receiver = bindings.get(name.rsplit(".", 1)[0], "") if "." in name else ""
    direct = bindings.get(name, "")
    if not direct and receiver in {"click", "celery"}:
        direct = f"{receiver}.{last}"
    first = _literal(call.args[0]) if call.args else ""
    given = next((_literal(kw.value) for kw in call.keywords if kw.arg == "name"), "")
    if receiver == "route" and last in HTTP_METHODS and first.startswith("/"):
        return [{"kind": "route", "name": f"{last.upper()} {first}", "target": func}]
    if receiver == "route" and last == "route" and first.startswith("/"):
        return [
            {"kind": "route", "name": f"{method} {first}", "target": func}
            for method in _methods(call)
        ]
    if _is_command_decorator(last, receiver, direct):
        return [{"kind": "command", "name": first or given or func, "target": func}]
    if _is_task_decorator(last, receiver, direct):
        return [{"kind": "task", "name": func, "target": func}]
    return []


def _is_command_decorator(last: str, receiver: str, direct: str) -> bool:
    return (last in COMMAND_DECORATORS and receiver == "command") or direct in {
        "click.command",
        "click.group",
    }


def _is_task_decorator(last: str, receiver: str, direct: str) -> bool:
    return (last in TASK_DECORATORS and receiver == "task") or direct == "celery.shared_task"


def _decorated(tree: ast.AST, bindings: dict[str, str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                found = _from_decorator(dec, node.name, bindings)
                out += found
                decorator = _dotted(dec.func)
                if any(p["kind"] == "command" for p in found) and (
                    decorator.endswith("group") or bindings.get(decorator) == "click.group"
                ):
                    bindings[node.name] = "command"
            elif bindings.get(_dotted(dec)) == "celery.shared_task":
                out.append({"kind": "task", "name": node.name, "target": node.name})
    return out


def _route_call(call: ast.AST) -> dict[str, str] | None:
    """This function reads one Django path registration in a urlpatterns list."""
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
    """This function reads Django urlpatterns, including concatenated lists."""
    found = [
        _route_call(call)
        for node in ast.walk(tree)
        if _is_urlpatterns(node)
        for call in ast.walk(node.value)  # type: ignore[attr-defined]
    ]
    return [x for x in found if x is not None]


def _class_name(node: ast.ClassDef) -> str:
    """This function reads a literal class name attribute, if available."""
    named = ""
    for body in node.body:
        if not isinstance(body, ast.Assign | ast.AnnAssign):
            continue
        targets = body.targets if isinstance(body, ast.Assign) else [body.target]
        if any(t.id == "name" for t in targets if isinstance(t, ast.Name)):
            named = _literal(body.value)
    return named


def _class_command(node: ast.ClassDef, module: str) -> dict[str, str] | None:
    """This function reads a Django Command class or a named cleo command."""
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
    """This function gives entry points registered by the module source."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    bindings = _bindings(tree)
    found = _decorated(tree, bindings) + _url_patterns(tree) + _class_commands(tree, module)
    return [{**point, "module": module} for point in found]


def registration_candidates(module: str, source: str) -> list[dict[str, str]]:
    """This function gives possible decorator registrations that must have a known
    framework binding.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    bindings = _bindings(tree)
    _decorated(tree, bindings)
    return [
        candidate
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        for dec in node.decorator_list
        if isinstance(dec, ast.Call)
        if (candidate := _registration_candidate(module, node, dec, bindings)) is not None
    ]


def _registration_candidate(
    module: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    dec: ast.Call,
    bindings: dict[str, str],
) -> dict[str, str] | None:
    if _from_decorator(dec, node.name, bindings):
        return None
    name = _dotted(dec.func)
    receiver, _, method = name.rpartition(".")
    route = (
        method in (*HTTP_METHODS, "route")
        and bool(dec.args)
        and _literal(dec.args[0]).startswith("/")
    )
    command_or_task = method in (*COMMAND_DECORATORS, *TASK_DECORATORS)
    if not (route or command_or_task) or bindings.get(receiver) == "local":
        return None
    return {
        "kind": "decorator",
        "name": f"{module}.{node.name}",
        "target": name,
        "reason": "The framework binding is unknown. Examine the registration source.",
    }


def _bindings(tree: ast.AST) -> dict[str, str]:
    """This function identifies framework imports and receiver objects at module scope."""
    body = getattr(tree, "body", [])
    imported = _import_bindings(body)
    return {**imported, **_receiver_bindings(body, imported)}


def _import_bindings(body: list[ast.stmt]) -> dict[str, str]:
    imported: dict[str, str] = {}
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported[alias.asname or alias.name] = alias.name
    return imported


def _receiver_bindings(body: list[ast.stmt], imported: dict[str, str]) -> dict[str, str]:
    receivers: dict[str, str] = {}
    for node in body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        constructed = imported.get(_dotted(node.value.func), _dotted(node.value.func))
        kind = _receiver_kind(constructed)
        for target in node.targets:
            if isinstance(target, ast.Name):
                receivers[target.id] = kind or "local"
    return receivers


def _receiver_kind(constructed: str) -> str:
    if constructed in {"fastapi.FastAPI", "fastapi.APIRouter", "flask.Flask"}:
        return "route"
    if constructed in {"typer.Typer", "click.Group"}:
        return "command"
    if constructed == "celery.Celery":
        return "task"
    return ""


def _table(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    out: Any = data
    for key in keys:
        out = out.get(key, {}) if isinstance(out, dict) else {}
    return out if isinstance(out, dict) else {}


def in_pyproject(data: dict[str, Any], components: dict[str, Any]) -> list[dict[str, str]]:
    """This function reads package scripts and plugin hooks from pyproject.toml.

    It includes Poetry scripts and project entry points in addition to project scripts.
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
    """This function reads an entry point group for modules in the system."""
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
    """This function gives a display name for an entry point."""
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
