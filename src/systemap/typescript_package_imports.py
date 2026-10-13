"""The TypeScript package import reader resolves the imports that name a file of the same
package through package.json.

Two kinds of import do this:

- A self-name import names the package itself, as `import ky from "ky"` in the ky
  package. The nearest package.json above the importing file must have this `name` and
  an `exports` field. The `exports` field then gives the file.
- A subpath import starts with `#`. The `imports` field of the nearest package.json
  gives the file, or an npm package.

The rules are the Node.js rules: "Self-referencing a package using its name" and
"Subpath imports" in https://nodejs.org/api/packages.html, and PACKAGE_SELF_RESOLVE,
PACKAGE_IMPORTS_RESOLVE, PACKAGE_IMPORTS_EXPORTS_RESOLVE, PATTERN_KEY_COMPARE, and
PACKAGE_TARGET_RESOLVE in https://nodejs.org/api/esm.html. TypeScript uses the same
rules ("package.json "imports" and self-name imports" in
https://www.typescriptlang.org/docs/handbook/modules/reference.html). For a package of
the local project, TypeScript then maps an output path in outDir to its input source
file. The entry reader does the same step for package entry points.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from systemap.config import ConfigError
from systemap.typescript_config import config_present, package_json
from systemap.typescript_entry import Package, entry_module, package_at

if TYPE_CHECKING:
    from systemap.typescript import TypeScriptContext

# TypeScript always matches `types` and `default`. tsc with `node16` or `nodenext`
# also matches `node`. The format of the importing file selects `import` or `require`.
# The adapter does not read `moduleResolution` or `customConditions`. Thus it uses
# `import`, except in a `.cts` file, which is always CommonJS.
BASE_CONDITIONS = frozenset({"types", "node", "default"})
# TypeScript replaces each output suffix with its input suffix (handbook step 8).
DECLARATION_TO_SCRIPT = ((".d.ts", ".js"), (".d.mts", ".mjs"), (".d.cts", ".cjs"))
# A JSON null in a condition object stops the search (PACKAGE_TARGET_RESOLVE).
_BLOCKED = object()
# A URL scheme, such as `node:` or `file:`.
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class PackageImport:
    """This record gives the result of a self-name import or a subpath import.

    `module` is the source module of the target file, or None if no module has the
    file. `package` is the npm package that a subpath import names, or an empty string.
    An import with this record is a local import, unless `package` is not empty.
    """

    module: str | None
    package: str = ""


def resolve(specifier: str, importer: Path, context: TypeScriptContext) -> PackageImport | None:
    """This function resolves a self-name import or a subpath import.

    The result is None for each other import. Then the import names an npm package, or
    a different rule resolves it.
    """
    scope = _scope(importer, context)
    if scope is None:
        # Node.js stops with an error for a subpath import without package.json.
        return PackageImport(None) if specifier.startswith("#") else None
    conditions = _conditions(importer)
    if specifier.startswith("#"):
        return _subpath_import(specifier, scope, conditions, context)
    return _self_import(specifier, scope, conditions, context)


def is_local(specifier: str, importer: Path, context: TypeScriptContext) -> bool:
    """This function tells if package.json makes an import a local import."""
    found = resolve(specifier, importer, context)
    return found is not None and not found.package


def npm_package(specifier: str, importer: Path | None, context: TypeScriptContext) -> str:
    """This function gives the npm package that a subpath import names, or an empty
    string."""
    if importer is None or not specifier.startswith("#"):
        return ""
    found = resolve(specifier, importer, context)
    return found.package if found is not None else ""


def _subpath_import(
    specifier: str, scope: Package, conditions: frozenset[str], context: TypeScriptContext
) -> PackageImport:
    imports = scope.data.get("imports")
    target = _match(specifier, imports, conditions) if isinstance(imports, dict) else None
    if target is None:
        return PackageImport(None)
    if target.startswith("./"):
        return PackageImport(_module(target, scope, context))
    if target.startswith(("../", "/")) or URL.match(target):
        # Node.js refuses such a target (PACKAGE_TARGET_RESOLVE), also `node:fs`.
        # A bare name such as `fs` is correct.
        return PackageImport(None)
    # A bare target names a package. It can also be a self-name import.
    found = _self_import(target, scope, conditions, context)
    return found if found is not None else PackageImport(None, target)


def _self_import(
    specifier: str, scope: Package, conditions: frozenset[str], context: TypeScriptContext
) -> PackageImport | None:
    name = scope.data.get("name")
    exports = scope.data.get("exports")
    if not isinstance(name, str) or exports is None:
        return None
    if specifier != name and not specifier.startswith(name + "/"):
        return None
    subpath = "." + specifier[len(name) :]
    target = _match(subpath, _subpaths(exports), conditions)
    if target is None or not target.startswith("./"):
        return PackageImport(None)
    return PackageImport(_module(target, scope, context))


def _subpaths(exports: Any) -> dict[str, Any] | None:
    """This function gives the subpath table of `exports`.

    A string, a list, or a condition object is the value of the subpath ".". A table
    with keys that start with "." and keys that do not is not valid.
    """
    if not isinstance(exports, dict):
        return {".": exports}
    dotted = [key.startswith(".") for key in exports]
    if all(dotted):
        return exports
    return None if any(dotted) else {".": exports}


def _match(key: str, table: Mapping[str, Any] | None, conditions: frozenset[str]) -> str | None:
    """This function gives the target of a key, with PACKAGE_IMPORTS_EXPORTS_RESOLVE.

    An exact key has priority. Otherwise, the pattern key with the longest text before
    `*` matches, then the longest pattern key. The text that `*` matches replaces each
    `*` in the target.
    """
    if table is None:
        return None
    if key in table and "*" not in key and not key.endswith("/"):
        return _target(table[key], "", conditions)
    patterns = sorted(
        (pattern for pattern in table if pattern.count("*") == 1 and _matches(key, pattern)),
        key=lambda pattern: (pattern.index("*"), len(pattern)),
        reverse=True,
    )
    if not patterns:
        return None
    before, _star, after = patterns[0].partition("*")
    matched = key[len(before) : len(key) - len(after)]
    return _target(table[patterns[0]], matched, conditions)


def _matches(key: str, pattern: str) -> bool:
    before, _star, after = pattern.partition("*")
    return (
        key.startswith(before)
        and key != before
        and key.endswith(after)
        and len(key) >= len(pattern)
    )


def _target(value: Any, matched: str, conditions: frozenset[str]) -> str | None:
    found = _target_value(value, matched, conditions)
    return found if isinstance(found, str) else None


def _target_value(value: Any, matched: str, conditions: frozenset[str]) -> object:
    """This function gives a target string, None for no target, or _BLOCKED for null."""
    if value is None:
        return _BLOCKED
    if isinstance(value, str):
        return value.replace("*", matched)
    if isinstance(value, list):
        return _first_string(value, matched, conditions)
    if isinstance(value, dict):
        return _first_condition(value, matched, conditions)
    return None


def _first_string(values: list[Any], matched: str, conditions: frozenset[str]) -> str | None:
    """A list gives its first entry that gives a target."""
    found = (_target_value(item, matched, conditions) for item in values)
    return next((item for item in found if isinstance(item, str)), None)


def _first_condition(table: dict[str, Any], matched: str, conditions: frozenset[str]) -> object:
    """The first matched condition with a target, or with null, gives the result. The
    order is the order of the keys in the file."""
    for condition, nested in table.items():
        found = (
            _target_value(nested, matched, conditions)
            if condition == "default" or condition in conditions
            else None
        )
        if found is not None:
            return found
    return None


def _module(target: str, scope: Package, context: TypeScriptContext) -> str | None:
    """This function gives the source module of a target file of the package.

    A declaration target uses the script suffix that tsc emits with it. Then the entry
    reader maps the output path to the source file.
    """
    for declaration, script in DECLARATION_TO_SCRIPT:
        if target.endswith(declaration):
            target = target[: -len(declaration)] + script
            break
    return entry_module(target, scope, context)


def _conditions(importer: Path) -> frozenset[str]:
    return BASE_CONDITIONS | {"require" if importer.suffix == ".cts" else "import"}


def _scope(importer: Path, context: TypeScriptContext) -> Package | None:
    """This function gives the nearest package.json above the importing file.

    A package.json file that the reader cannot read gives no package. The extraction then
    keeps the import as it was before, and Node.js also stops at such a file.
    """
    directory = importer.resolve().parent
    scopes: dict[Path, Package | None] = context.package_scopes
    if directory not in scopes:
        scopes[directory] = _find_scope(directory, context)
    return scopes[directory]


def _find_scope(directory: Path, context: TypeScriptContext) -> Package | None:
    repo = context.repo.resolve()
    folders = (folder for folder in (directory, *directory.parents) if folder.is_relative_to(repo))
    found = next((folder for folder in folders if config_present(folder / "package.json")), None)
    if found is None:
        return None
    try:
        return package_at(found, context, package_json(found, repo))
    except ConfigError:
        return None
