"""CI and release use fixed tool versions, and a fork page is rendered with base code.

ci-4: before the change, each setup-uv step used `version: latest` or no version, the
build backend was `hatchling` without a version, and the release `uv run` could lock again.
ci-7: before the change, only the renderer of the pull request examined the committed page.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from systemap import language as languages
from systemap import scaffold

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CONSTRAINTS = ROOT / ".github" / "build-constraints.txt"
EXACT = re.compile(r'^\s*version: "\d+\.\d+\.\d+"$', re.M)


def setup_uv_blocks(text: str) -> list[str]:
    """Give the lines after each setup-uv line, to the next step or run line."""
    lines = text.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        if "astral-sh/setup-uv@" not in line:
            continue
        block = []
        for nxt in lines[i + 1 :]:
            if nxt.lstrip().startswith(("- ", "run:")):
                break
            block.append(nxt)
        blocks.append("\n".join(block))
    return blocks


def workflow_texts() -> dict[str, str]:
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(WORKFLOWS.glob("*.yml"))}
    init = scaffold.files("demo", "pkg", [("pkg", "pkg")], language=languages.repository("python"))
    texts["init"] = init[".github/workflows/systemap.yml"]
    return texts


def test_each_setup_uv_step_has_one_exact_uv_version() -> None:
    versions = set()
    for name, text in workflow_texts().items():
        blocks = setup_uv_blocks(text)
        assert blocks, name
        for block in blocks:
            found = EXACT.findall(block)
            assert len(found) == 1, (name, block)
            versions.add(found[0].strip())
    assert len(versions) == 1
    assert "version: latest" not in "".join(workflow_texts().values())


def test_each_action_has_a_commit_sha() -> None:
    for name, text in workflow_texts().items():
        for line in text.splitlines():
            if "uses:" in line:
                assert re.search(r"@[0-9a-f]{40} # v", line), (name, line)


def test_the_build_backend_and_its_dependencies_are_fixed() -> None:
    requires = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pins = requires["build-system"]["requires"]
    assert pins and all("==" in pin for pin in pins)
    constraints = CONSTRAINTS.read_text(encoding="utf-8")
    for pin in pins:
        assert f"{pin} \\\n" in constraints, pin
    packages = re.findall(r"^([A-Za-z0-9_.-]+)==\S+ \\$", constraints, re.M)
    assert len(packages) >= 2
    for package in packages:
        block = constraints.split(f"\n{package}==", 1)[1]
        assert "--hash=sha256:" in block.split("\n", 2)[1], package


def test_release_and_install_make_the_package_with_hashed_build_dependencies() -> None:
    release = (WORKFLOWS / "workflow.yml").read_text(encoding="utf-8")
    ci = (WORKFLOWS / "systemap.yml").read_text(encoding="utf-8")
    install = ci.split("\n  install:\n", 1)[1].split("\n  plugin:\n", 1)[0]
    # The release job sets the values for each step: `uv run` also builds the package.
    release_env = release.split("\n    env:\n", 1)[1].split("\n    steps:\n", 1)[0]
    build_step = install.split("run: uv build\n", 1)[0].rsplit("- name:", 1)[1]
    for block in (release_env, build_step):
        assert "UV_BUILD_CONSTRAINT: .github/build-constraints.txt" in block
        assert 'UV_REQUIRE_HASHES: "1"' in block
    assert re.findall(r"uv run(?! --locked)", release) == []


def test_a_fork_pull_request_page_is_rendered_with_the_base_code() -> None:
    text = (WORKFLOWS / "systemap.yml").read_text(encoding="utf-8")
    job = text.split("\n  base-render:\n", 1)[1].split("\n  delta:\n", 1)[0]
    assert "github.event.pull_request.head.repo.full_name != github.repository" in job
    assert "ref: ${{ github.event.pull_request.base.sha }}" in job
    assert "path: base" in job and "path: pr" in job
    assert job.count("persist-credentials: false") == 2
    assert "permissions" not in job
    assert "base/.venv/bin/systemap --root pr render --check" in job
