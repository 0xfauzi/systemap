"""The TypeScript import resolver finds the source file that an import names.

Project discovery and the module facts use this one resolver, with these rules:

- A relative import or a `paths` alias names the first existing source file of its
  targets, in the tsc order. If no module has that file, the import does not resolve.
  A later target does not replace it.
- If no relative or alias target exists, a self-name import or a subpath import (`#name`)
  resolves through package.json (`typescript_package_imports`).
- An import path with a NUL character names no file. It does not resolve.
- The module facts also resolve an import of a different workspace package: a package
  that a package.json file of the repository names. The module name that the package
  root gives must then be in the folder of that package.json file. A name of a package
  root is not an import name for other imports. Project discovery does not add a file of
  a different workspace package to a program: tsc reads the declaration output of that
  package, and that output is not source.

Project discovery runs before the programs are complete. Thus, when tsc infers the
output root of a package from its program files, discovery uses the input files of
the project for a program that it has not completed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from systemap import repo_files, typescript_package_imports
from systemap.config import ConfigError
from systemap.typescript_config import (
    DECLARATION_SUFFIXES,
    TypeScriptConfig,
    alias_targets,
    package_json,
)
from systemap.typescript_projects import existing_target, without_script_suffix
from systemap.typescript_syntax import syntax_tree

if TYPE_CHECKING:
    from systemap.typescript import TypeScriptContext

# A file path cannot contain this character.
NUL = "\0"
# Gives (import source text, imported names) for each import of a parsed module.
ImportReader = Callable[[Any], Iterable[tuple[str, set[str]]]]


def relative_targets(specifier: str, importer: Path, root_dirs: tuple[Path, ...]) -> list[Path]:
    """Give the import paths of a relative specifier. The suffix stays, because it selects
    the source suffixes (see `path_choices`)."""
    relative = (importer.parent / specifier).resolve()
    targets = [relative]
    containing = [root for root in root_dirs if relative.is_relative_to(root)]
    if containing:
        source_root = max(containing, key=lambda root: len(root.parts))
        tail = relative.relative_to(source_root)
        targets.extend(root / tail for root in root_dirs if root != source_root)
    return targets


def target_file(
    specifier: str, importer: Path, compiler: TypeScriptConfig, repo: Path
) -> Path | None:
    """Give the first existing source file that a relative import or an alias names."""
    if NUL in specifier:
        return None
    targets = (
        relative_targets(specifier, importer, compiler.root_dirs)
        if specifier.startswith(".")
        else alias_targets(specifier, compiler, repo)
    )
    return existing_target(targets)


def target_module(
    specifier: str, importer: Path, compiler: TypeScriptConfig, context: TypeScriptContext
) -> str | None:
    """Give the module that an import names, or None."""
    found = target_file(specifier, importer, compiler, context.repo)
    if found is not None:
        return context.modules_by_path.get(found)
    return package_module(specifier, importer, context)


def package_module(specifier: str, importer: Path, context: TypeScriptContext) -> str | None:
    """Give the module of a self-name import or a subpath import, or None."""
    if specifier.startswith(".") or NUL in specifier:
        return None
    package = typescript_package_imports.resolve(specifier, importer, context)
    return package.module if package is not None else None


def module_name(name: str) -> str:
    """Give the module name that an npm import name gives under the package root names."""
    return name.removeprefix("@").replace("/", ".").replace("-", "_")


def workspace_module(
    specifier: str, importer: Path, paths: dict[str, Path], context: TypeScriptContext
) -> str | None:
    """Give the module of an import of a different workspace package, or None."""
    directory = workspace(specifier, importer, context)
    if directory is None:
        return None
    normalized = module_name(without_script_suffix(specifier))
    return next(
        (
            name
            for name in (normalized, f"{normalized}.index")
            if name in paths and paths[name].resolve().is_relative_to(directory)
        ),
        None,
    )


def workspace(specifier: str, importer: Path, context: TypeScriptContext) -> Path | None:
    """Give the folder of the different workspace package that an import names, or None.

    The package of the importing file is not a different package: a self-name import
    uses `exports` (`typescript_package_imports`).
    """
    if specifier.startswith((".", "/", "#")) or NUL in specifier:
        return None
    parts = specifier.split("/")
    name = "/".join(parts[:2] if specifier.startswith("@") else parts[:1])
    directory = _workspace_packages(context).get(name)
    projects = context.projects
    own = projects.package_directory(importer) if projects is not None else None
    if directory is None or directory == (own or context.repo.resolve()):
        return None
    return directory


def _workspace_packages(context: TypeScriptContext) -> dict[str, Path]:
    """Give the folder of each package name: the repository root and each folder with a
    package.json file above a module. A name that two folders give is not included."""
    if context.workspaces is None:
        named: dict[str, Path | None] = {}
        for folder in sorted(_package_folders(context)):
            name = _package_name(folder, context.repo.resolve())
            if name:
                named[name] = None if name in named else folder
        context.workspaces = {name: folder for name, folder in named.items() if folder}
    return context.workspaces


def _package_folders(context: TypeScriptContext) -> set[Path]:
    projects = context.projects
    folders = {context.repo.resolve()}
    if projects is not None:
        found = (projects.package_directory(path) for path in context.modules_by_path)
        folders.update(folder for folder in found if folder is not None)
    return folders


def _package_name(folder: Path, repo: Path) -> str:
    """Give the `name` of the package.json file in a folder. A file that the reader cannot
    read gives no name, as in `typescript_package_imports`."""
    try:
        name = package_json(folder, repo).get("name")
    except ConfigError:
        return ""
    return name if isinstance(name, str) else ""


def program_dependencies(
    path: Path,
    compiler: TypeScriptConfig,
    context: TypeScriptContext,
    paths: dict[str, Path],
    read_imports: ImportReader,
) -> Iterator[Path]:
    """Give the source files that one program file imports. The project index adds them to
    the program, as tsc does, before it selects a project or an output root."""
    repo = context.repo
    try:
        text = repo_files.read_text(repo, repo_files.relative(repo, path))
        root = syntax_tree(text, path.as_posix())
    except (OSError, UnicodeError):
        return
    for specifier, _ in read_imports(root):
        found = target_file(specifier, path, compiler, repo)
        if found is None:
            module = package_module(specifier, path, context)
            found = paths[module].resolve() if module in paths else None
        if found is not None and not found.name.endswith(DECLARATION_SUFFIXES):
            yield found
