"""Create and verify a source input that excludes reference map artefacts.

Acceptance before execution: every extracted source file is retained; reference
maps, facts, rendered output, and case packets are absent. Any added, removed,
or changed input file must fail workflow validation. This checks supplied input
bytes, not the agent's access to other directories during an external run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from systemap import config, extract, nest


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def excluded_paths(cfg: config.Config) -> set[Path]:
    maps = {Path(item.rel) for item in nest.load(cfg).maps}
    parents = {path.parent for path in maps if path.parent != Path(".")}
    return maps | parents | {Path(cfg.out_dir)}


def require_allowed_path(tree: Path, rel: str, excluded: set[Path]) -> None:
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"workflow input path leaves snapshot: {rel}")
    resolved = (tree / path).resolve()
    if not resolved.is_relative_to(tree.resolve()):
        raise ValueError(f"workflow input target leaves snapshot: {rel}")
    target = resolved.relative_to(tree.resolve())
    if any(path.is_relative_to(item) or target.is_relative_to(item) for item in excluded):
        raise ValueError(f"workflow input names reference artefacts: {rel}")


def test_sources(cfg: config.Config) -> set[str]:
    language = extract.language_for(cfg)
    suffixes = {".py"} if cfg.language == "python" else {".ts", ".tsx", ".mts", ".cts"}
    files = set()
    for path in cfg.root.rglob("*"):
        rel = path.relative_to(cfg.root).as_posix()
        if not path.is_file() or path.suffix not in suffixes:
            continue
        in_test_dir = any(
            directory and Path(rel).is_relative_to(Path(directory)) for directory in cfg.test_dirs
        )
        if in_test_dir or language.is_test_file(rel, cfg.test_dirs, cfg.test_patterns):
            files.add(rel)
    return files


def allowed_sources(snapshot: Path, facts: dict[str, Any]) -> list[str]:
    """Only extracted source and configured test source enter the input."""
    cfg = config.load(snapshot / "tree")
    paths = sorted({record["file"] for record in facts["components"].values()} | test_sources(cfg))
    excluded = excluded_paths(cfg)
    for rel in paths:
        require_allowed_path(cfg.root, rel, excluded)
    return paths


def configuration(snapshot: Path) -> bytes:
    """Expose source locations and Python package settings without map answers."""
    cfg = config.load(snapshot / "tree")
    settings: dict[str, Any] = {
        "name": cfg.name,
        "language": cfg.language,
        "package_roots": dict(cfg.package_roots),
        "tests_dirs": cfg.test_dirs,
        "test_patterns": cfg.test_patterns,
    }
    pyproject = snapshot / "tree" / "pyproject.toml"
    if pyproject.is_file():
        project = tomllib.loads(pyproject.read_text())
        public = project.get("project", {})
        settings["python_project"] = {
            key: public[key]
            for key in (
                "name",
                "requires-python",
                "dependencies",
                "optional-dependencies",
                "scripts",
                "entry-points",
            )
            if key in public
        }
    return canonical(settings) + b"\n"


def expected_files(snapshot: Path, facts: dict[str, Any], configs: list[str]) -> dict[str, bytes]:
    paths = allowed_sources(snapshot, facts)
    cfg = config.load(snapshot / "tree")
    excluded = excluded_paths(cfg)
    for rel in configs:
        path = Path(rel)
        require_allowed_path(cfg.root, rel, excluded)
        if path.name != "package.json" and not (
            path.name.startswith("tsconfig") and path.suffix == ".json"
        ):
            raise ValueError(f"workflow config must be package.json or tsconfig*.json: {rel}")
    files = {rel: (snapshot / "tree" / rel).read_bytes() for rel in sorted(set(paths + configs))}
    if "source-config.json" in files:
        raise ValueError("source-config.json conflicts with generated configuration")
    files["source-config.json"] = configuration(snapshot)
    return files


def prepare(
    snapshot: Path,
    destination: Path,
    reference: dict[str, Any],
    facts: dict[str, Any],
    configs: list[str],
) -> str:
    destination = destination.resolve()
    if destination.is_relative_to(snapshot.resolve()) or snapshot.resolve().is_relative_to(
        destination
    ):
        raise ValueError("workflow input must be separate from the reference snapshot")
    if destination.exists():
        raise ValueError(f"workflow input already exists: {destination}")
    files = expected_files(snapshot, facts, configs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        for rel, raw in files.items():
            target = staging / "tree" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        manifest = {
            "format": 1,
            "snapshot_id": reference["snapshot_id"],
            "configs": sorted(set(configs)),
            "files": {rel: digest(raw) for rel, raw in files.items()},
        }
        identity = digest(canonical(manifest))
        (staging / "manifest.json").write_bytes(canonical(manifest) + b"\n")
        os.replace(staging, destination)
        return identity
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify(
    snapshot: Path,
    reference: dict[str, Any],
    facts: dict[str, Any],
    result: dict[str, Any],
    result_file: Path,
) -> None:
    rel = result.get("workflow_input")
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("workflow result requires a relative workflow_input directory")
    supplied = result_file.parent / rel
    manifest = json.loads((supplied / "manifest.json").read_text())
    if result.get("workflow_input_sha256") != digest(canonical(manifest)):
        raise ValueError("workflow input differs from its recorded hash")
    if manifest.get("format") != 1 or manifest.get("snapshot_id") != reference["snapshot_id"]:
        raise ValueError("workflow input uses a different source snapshot")
    configs = manifest.get("configs")
    if not isinstance(configs, list) or any(not isinstance(item, str) for item in configs):
        raise ValueError("workflow input has an invalid configuration whitelist")
    expected = {rel: digest(raw) for rel, raw in expected_files(snapshot, facts, configs).items()}
    expected_manifest = {
        "format": 1,
        "snapshot_id": reference["snapshot_id"],
        "configs": sorted(set(configs)),
        "files": expected,
    }
    if manifest != expected_manifest:
        raise ValueError("workflow input whitelist differs from frozen source")
    verify_files(supplied, expected)


def verify_files(supplied: Path, expected: dict[str, str]) -> None:
    if supplied.is_symlink() or (supplied / "tree").is_symlink():
        raise ValueError("workflow input directories must not be symlinks")
    paths = list((supplied / "tree").rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("workflow input must not contain symlinks")
    actual = {
        path.relative_to(supplied / "tree").as_posix(): digest(path.read_bytes())
        for path in paths
        if path.is_file()
    }
    if actual != expected:
        raise ValueError("workflow input files changed, appeared, or disappeared")
    if {path.name for path in supplied.iterdir()} != {"tree", "manifest.json"}:
        raise ValueError("workflow input contains extra reference artefacts")
