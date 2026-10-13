"""The TypeScript project index selects the tsconfig file that compiles each source file.

The nearest tsconfig.json file above a source file gives the project, if its program
contains the file. The program of a project is its input files and the files that they
import. Then the index uses the first project in `references` that has the file in its
input patterns. tsserver uses the same rule (`isDefaultProject` and `isMatchedByConfig`
in TypeScript 5.9.3). Thus a solution file with `"files": []` and the tsconfig.json file
of each monorepo package give their own path aliases.

If no project gives the file by those rules, tsserver uses no configured project. But
`tsc -b` compiles a file that a referenced program imports with the options of that
project. The index then uses the first referenced project whose program contains the file.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace
from pathlib import Path

from systemap.config import ConfigError
from systemap.typescript_config import (
    DECLARATION_SUFFIXES,
    SOURCE_SUFFIXES,
    TypeScriptConfig,
    input_files,
    load_project_config,
    package_json,
)

CONFIG_NAME = "tsconfig.json"
SCRIPT_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")
# An import of a directory reads only these index files, as in tsc.
INDEX_SUFFIXES = (".ts", ".tsx")
# The source suffixes that tsc tries for each JavaScript suffix, in order. Measured
# with tsc 5.9.3 (`bundler` and `node16`): `.mjs` gives only `.mts`, `.cjs` gives only
# `.cts`, and `.jsx` tries `.tsx` before `.ts`. See "File extension substitution" in
# https://www.typescriptlang.org/docs/handbook/modules/reference.html.
SCRIPT_SOURCES = {
    ".js": (".ts", ".tsx"),
    ".jsx": (".tsx", ".ts"),
    ".mjs": (".mts",),
    ".cjs": (".cts",),
}
# An import without a JavaScript or source suffix tries only these suffixes.
PLAIN_SOURCES = (".ts", ".tsx")
# Gives the source files that one file imports, with the options of one project.
DependencyReader = Callable[[Path, TypeScriptConfig], Iterable[Path]]


def without_script_suffix(specifier: str) -> str:
    """This function removes a source, declaration, or JavaScript suffix."""
    for suffix in (*DECLARATION_SUFFIXES, *SOURCE_SUFFIXES, *SCRIPT_SUFFIXES):
        if specifier.endswith(suffix):
            return specifier[: -len(suffix)]
    return specifier


def path_choices(target: Path) -> list[Path]:
    """This function gives the source files that a resolved import path can name.

    The suffix of the import selects the source suffixes, as in tsc. Thus `./mod.mjs`
    names `mod.mts` and not `mod.ts`. A folder import reads its index file.
    """
    if target.suffix in SOURCE_SUFFIXES:
        return [target]
    sources = SCRIPT_SOURCES.get(target.suffix)
    if sources is not None:
        stem = str(target)[: -len(target.suffix)]
        files = [Path(stem + suffix) for suffix in sources]
    else:
        files = [Path(str(target) + suffix) for suffix in PLAIN_SOURCES]
    return files + [target / f"index{suffix}" for suffix in INDEX_SUFFIXES]


def existing_target(targets: Iterable[Path]) -> Path | None:
    """This function gives the first source file that one of the import paths names."""
    return next(
        (
            choice.resolve()
            for target in targets
            for choice in path_choices(target)
            if choice.is_file()
        ),
        None,
    )


class TypeScriptProjects:
    """This index loads each tsconfig file one time and keeps the selected input files."""

    def __init__(
        self, repo: Path, root: TypeScriptConfig, dependencies: DependencyReader | None = None
    ) -> None:
        self.repo = repo.resolve()
        self.root = root
        self._dependencies = dependencies
        self._configs: dict[Path, TypeScriptConfig] = {self.repo / CONFIG_NAME: root}
        self._nearest: dict[Path, Path | None] = {}
        self._inputs: dict[int, frozenset[Path]] = {}
        self._programs: dict[int, frozenset[Path]] = {}
        self._packages: dict[Path, Path | None] = {}
        self._chosen: dict[Path, TypeScriptConfig] = {}

    def config_for(self, path: Path) -> TypeScriptConfig:
        """This function gives the configuration that compiles a source file."""
        if path not in self._chosen:
            self._chosen[path] = self._choose(path.resolve())
        return self._chosen[path]

    def _choose(self, path: Path) -> TypeScriptConfig:
        config = self._nearest_config(path.parent)
        if path in self._selected(config) or path in self.program_files(config):
            return config
        for project in config.projects:
            if path in self._selected(project):
                return project
        for project in config.projects:
            if path in self.program_files(project):
                return project
        return config

    def program_files(self, config: TypeScriptConfig) -> frozenset[Path]:
        """This function gives the input files of a project and the files that they import.

        tsc compiles each imported source file in the same program. Without a dependency
        reader, the result is the input files.
        """
        key = id(config)
        if key not in self._programs:
            self._programs[key] = self._program(config)
        return self._programs[key]

    def lazy_program_files(self, config: TypeScriptConfig) -> Iterator[Path]:
        """This function gives `program_files` only when the caller reads the result.

        `root_candidates` reads the files only if no option gives the output root. Thus
        the other projects do not parse their files for imports.
        """
        yield from self.program_files(config)

    def _program(self, config: TypeScriptConfig) -> frozenset[Path]:
        queue = list(self._selected(config))
        if self._dependencies is None:
            return frozenset(queue)
        seen = set(queue)
        for path in queue:
            for found in self._dependencies(path, config):
                if found not in seen and found.is_relative_to(self.repo):
                    seen.add(found)
                    queue.append(found)
        return frozenset(seen)

    def config_for_directory(self, directory: Path) -> TypeScriptConfig:
        """This function gives the configuration of a package directory.

        A referenced configuration in the same directory has priority over a solution
        file in a parent directory.
        """
        directory = directory.resolve()
        config = self._nearest_config(directory)
        return next(
            (project for project in (config, *config.projects) if project.config_dir == directory),
            config,
        )

    def combined(self) -> TypeScriptConfig:
        """This function gives the top-level configuration with each loaded project.

        The provenance and the configuration issues then include each project.
        """
        projects = dict.fromkeys(self.root.projects)
        issues = dict.fromkeys(self.root.issues)
        for path in sorted(self._configs):
            config = self._configs[path]
            if config is self.root:
                continue
            for project in (config, *config.projects):
                projects.setdefault(replace(project, issues=(), projects=()))
            issues.update(dict.fromkeys(config.issues))
        return replace(self.root, projects=tuple(projects), issues=tuple(issues))

    def package_directory(self, path: Path) -> Path | None:
        """This function gives the nearest directory above a file that has a package.json
        file. The repository root and a directory outside it give None.
        """
        directory = path.resolve().parent
        if directory not in self._packages:
            self._packages[directory] = self._find_package(directory)
        return self._packages[directory]

    def _find_package(self, directory: Path) -> Path | None:
        for candidate in (directory, *directory.parents):
            if candidate == self.repo or not candidate.is_relative_to(self.repo):
                return None
            if (candidate / "package.json").is_file() and package_json(candidate):
                return candidate
        return None

    def _nearest_config(self, directory: Path) -> TypeScriptConfig:
        path = self._nearest_path(directory)
        if path is None:
            return self.root
        if path not in self._configs:
            try:
                self._configs[path] = load_project_config(
                    path, self.repo, self.root.typescript_major
                )
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
        return self._configs[path]

    def _nearest_path(self, directory: Path) -> Path | None:
        if directory in self._nearest:
            return self._nearest[directory]
        found: Path | None = None
        if directory.is_relative_to(self.repo):
            if (directory / CONFIG_NAME).is_file():
                found = directory / CONFIG_NAME
            elif directory != self.repo:
                found = self._nearest_path(directory.parent)
        self._nearest[directory] = found
        return found

    def _selected(self, config: TypeScriptConfig) -> frozenset[Path]:
        key = id(config)
        if key not in self._inputs:
            self._inputs[key] = frozenset(input_files(config, self.repo))
        return self._inputs[key]
