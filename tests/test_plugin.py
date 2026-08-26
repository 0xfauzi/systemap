"""The Claude Code plugin at the repository root ships the same skill the
package installs, and its manifest carries the package's version.

The package directory `src/systemap/skill/` is the source of truth.
`skills/systemap/` is what the plugin loads; it is a copy of the whole
tree, kept identical by this test, so a plugin install and `systemap
skill` cannot hand an agent two different procedures. The plugin
manifest's version is the package version, so a release cannot ship them
apart.
"""

from __future__ import annotations

import json
from pathlib import Path

import systemap
from systemap import skill

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SKILL = ROOT / "skills" / "systemap"
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

REFERENCES = (
    "schema.md",
    "example.md",
    "layout.md",
    "layers.md",
    "journeys-and-invariants.md",
    "second-pass.md",
    "pitfalls.md",
)


def tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_plugin_skill_tree_is_identical_to_the_package_skill_tree() -> None:
    shipped = {rel: content.encode("utf-8") for rel, content in skill.files().items()}
    assert tree(PLUGIN_SKILL) == shipped, (
        "skills/systemap/ differs from src/systemap/skill/; mirror the package directory: "
        "rm -rf skills/systemap && cp -R src/systemap/skill skills/systemap"
    )


def test_skill_is_a_directory_of_named_references() -> None:
    shipped = skill.files()
    assert list(shipped)[0] == "SKILL.md"
    assert sorted(shipped) == sorted(["SKILL.md", *(f"references/{r}" for r in REFERENCES)])
    # SKILL.md stays short and names every reference and when to read it.
    lines = shipped["SKILL.md"].splitlines()
    assert len(lines) <= 200, f"SKILL.md is {len(lines)} lines; the ceiling is 200"
    for ref in REFERENCES:
        assert f"references/{ref}" in shipped["SKILL.md"], ref


def test_plugin_manifest_version_is_the_package_version() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["name"] == "systemap"
    assert manifest["version"] == systemap.__version__, (
        f".claude-plugin/plugin.json says {manifest['version']}, the package says "
        f"{systemap.__version__}; bump both together"
    )


def test_marketplace_points_at_the_repository_root() -> None:
    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert market["name"] == "systemap"
    (entry,) = market["plugins"]
    assert entry["name"] == "systemap"
    assert entry["source"] == "./"


def test_skill_front_matter_fits_the_plugin_limits() -> None:
    text = skill.text()
    head = text.split("---", 2)[1]
    fields = dict(line.split(": ", 1) for line in head.strip().splitlines())
    assert fields["name"] == "systemap"
    assert len(fields["description"]) <= 1024
    for phrase in ("map this repository", "draw the system map", "update the map"):
        assert phrase in fields["description"], phrase
    assert fields["license"] == "MIT"
    assert fields["compatibility"].startswith("Requires Python 3.11+")
