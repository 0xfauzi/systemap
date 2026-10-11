"""The TypeScript project index selects the tsconfig file that compiles each source file.

The nearest tsconfig.json file above a source file gives the project. If that project
does not select the file, the index uses a project in its `references` that selects the
file. tsserver uses the same rule. Thus a solution file with `"files": []` and the
tsconfig.json file of each monorepo package give their own path aliases.
"""

from __future__ import annotations

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


def without_script_suffix(specifier: str) -> str:
    """This function removes a source, declaration, or JavaScript suffix."""
    for suffix in (*DECLARATION_SUFFIXES, *SOURCE_SUFFIXES, *SCRIPT_SUFFIXES):
        if specifier.endswith(suffix):
            return specifier[: -len(suffix)]
    return specifier


def path_choices(target: Path) -> list[Path]:
    """This function gives the source files that a resolved import path can name."""
    if target.suffix in SOURCE_SUFFIXES:
        return [target]
    if target.suffix in SCRIPT_SUFFIXES:
        target = Path(without_script_suffix(str(target)))
    return [Path(str(target) + suffix) for suffix in SOURCE_SUFFIXES] + [
        target / f"index{suffix}" for suffix in INDEX_SUFFIXES
    ]


class TypeScriptProjects:
    """This index loads each tsconfig file one time and keeps the selected input files."""

    def __init__(self, repo: Path, root: TypeScriptConfig) -> None:
        self.repo = repo.resolve()
        self.root = root
        self._configs: dict[Path, TypeScriptConfig] = {self.repo / CONFIG_NAME: root}
        self._nearest: dict[Path, Path | None] = {}
        self._inputs: dict[int, frozenset[Path]] = {}
        self._packages: dict[Path, Path | None] = {}
        self._chosen: dict[Path, TypeScriptConfig] = {}

    def config_for(self, path: Path) -> TypeScriptConfig:
        """This function gives the configuration that compiles a source file."""
        if path not in self._chosen:
            self._chosen[path] = self._choose(path.resolve())
        return self._chosen[path]

    def _choose(self, path: Path) -> TypeScriptConfig:
        config = self._nearest_config(path.parent)
        return next(
            (project for project in (config, *config.projects) if path in self._selected(project)),
            config,
        )

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
            self._inputs[key] = frozenset(input_files(config))
        return self._inputs[key]
