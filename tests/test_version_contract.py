"""Focused contracts for the 2.1 release-version boundary."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tetris_ballistic.run_artifacts import software_identity

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "2.1.0"


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(
        r"(?ms)^\[project\]\s*$\n(?P<body>.*?)(?=^\[|\Z)",
        text,
    )
    assert project is not None, "pyproject.toml must contain [project] metadata"
    matches = re.findall(
        r'(?m)^version\s*=\s*"([^"]+)"\s*$',
        project.group("body"),
    )
    assert len(matches) == 1, "[project] must declare exactly one static version"
    return matches[0]


def test_pep621_declares_the_2_1_boundary() -> None:
    assert _project_version() == EXPECTED_VERSION


def test_pep621_uses_current_spdx_license_metadata() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'license = "MIT"' in text
    assert 'license-files = ["LICENSE"]' in text
    assert "License :: OSI Approved :: MIT License" not in text


def test_source_distribution_declares_release_notes_and_docs() -> None:
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()

    assert "include CHANGELOG.md" in manifest
    assert "recursive-include docs *.md" in manifest


def test_setup_py_is_a_metadata_free_compatibility_shim() -> None:
    tree = ast.parse((ROOT / "setup.py").read_text(encoding="utf-8"))
    setup_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setup"
    ]

    assert len(setup_calls) == 1
    assert setup_calls[0].args == []
    assert setup_calls[0].keywords == []


def test_changelog_leads_with_the_source_version_as_unreleased() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"(?m)^## \[([^]]+)] — (.+)$", text)

    assert headings
    assert headings[0] == (EXPECTED_VERSION, "Unreleased")
    assert len({version for version, _status in headings}) == len(headings)


def test_managed_source_identity_uses_the_pep621_version() -> None:
    identity = software_identity(ROOT / "tetris_ballistic")

    assert identity["record"]["source_declared_version"] == EXPECTED_VERSION


def test_tag_workflow_builds_only_after_version_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "workflow.yml").read_text(
        encoding="utf-8"
    )

    assert 'tags:\n      - "v*"' in workflow
    assert "does not match project version" in workflow
    assert "python -m build" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "gh-action-pypi-publish" not in workflow
    assert "PYPI_API_TOKEN" not in workflow
