"""The Claude Code plugin at the repository root ships the same skill the
package installs, and its manifest carries the package's version.

The package file `src/systemap/skill/SKILL.md` is the source of truth.
`skills/systemap/SKILL.md` is what the plugin loads; it is a copy, kept
identical by this test, so a plugin install and `systemap skill` cannot
hand an agent two different procedures. The plugin manifest's version is
the package version, so a release cannot ship them apart.
"""

from __future__ import annotations

import json
from pathlib import Path

import systemap
from systemap import skill

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SKILL = ROOT / "skills" / "systemap" / "SKILL.md"
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def test_plugin_skill_is_byte_identical_to_the_package_skill() -> None:
    assert PLUGIN_SKILL.read_bytes() == skill.text().encode("utf-8"), (
        "skills/systemap/SKILL.md differs from src/systemap/skill/SKILL.md; "
        "copy the package file over it: cp src/systemap/skill/SKILL.md skills/systemap/SKILL.md"
    )


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
