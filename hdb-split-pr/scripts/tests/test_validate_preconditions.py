"""Tests for splitpr_05.executor._validate_preconditions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from splitpr_05.executor import ExecutionError, _validate_preconditions


# ── Helpers ──────────────────────────────────────────────────────────


def _meta(
    source_branch: str = "feature-branch",
    base_branch: str = "main",
    repo_toplevel: str = "/home/user/repo",
    head_rev: str = "abc123def456abc123def456abc123def456abc1",
) -> dict[str, str]:
    """Build a metadata dict with sensible defaults."""
    m: dict[str, str] = {}
    if source_branch:
        m["source_branch"] = source_branch
    if base_branch:
        m["base_branch"] = base_branch
    if repo_toplevel:
        m["repo_toplevel"] = repo_toplevel
    if head_rev:
        m["head_rev"] = head_rev
    return m


GIT_OPS = "splitpr_05.executor.git_ops"


# ── Passing cases ───────────────────────────────────────────────────


@patch(f"{GIT_OPS}.has_uncommitted_changes", return_value=False)
@patch(f"{GIT_OPS}.get_head_rev", return_value="abc123def456abc123def456abc123def456abc1")
@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/home/user/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_matching_repo_and_rev_passes(
    _is_git, _toplevel, _head, _uncommitted
):
    """When repo and HEAD match, no exception is raised."""
    _validate_preconditions("feature-branch", "main", _meta(), dry_run=False)


@patch(f"{GIT_OPS}.has_uncommitted_changes", return_value=False)
@patch(f"{GIT_OPS}.get_head_rev", return_value="abc123def456abc123def456abc123def456abc1")
@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/home/user/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_dry_run_skips_uncommitted_check(
    _is_git, _toplevel, _head, mock_uncommitted
):
    """In dry-run mode, uncommitted changes are not checked."""
    _validate_preconditions("feature-branch", "main", _meta(), dry_run=True)
    mock_uncommitted.assert_not_called()


# ── Not a git repo ──────────────────────────────────────────────────


@patch(f"{GIT_OPS}.is_git_repo", return_value=False)
def test_not_git_repo_raises(_is_git):
    with pytest.raises(ExecutionError, match="Not inside a git repository"):
        _validate_preconditions("feature", "main", _meta(), dry_run=False)


# ── Missing branch metadata ─────────────────────────────────────────


@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_missing_source_branch_raises(_is_git):
    with pytest.raises(ExecutionError, match="No source_branch"):
        _validate_preconditions("", "main", _meta(), dry_run=False)


@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_missing_base_branch_raises(_is_git):
    with pytest.raises(ExecutionError, match="No base_branch"):
        _validate_preconditions("feature", "", _meta(), dry_run=False)


# ── Repository mismatch ─────────────────────────────────────────────


@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/other/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_repo_mismatch_raises(_is_git, _toplevel):
    meta = _meta(repo_toplevel="/home/user/repo")
    with pytest.raises(ExecutionError, match="Repository mismatch"):
        _validate_preconditions("feature", "main", meta, dry_run=False)


# ── Missing repo_toplevel skips check ────────────────────────────────


@patch(f"{GIT_OPS}.has_uncommitted_changes", return_value=False)
@patch(f"{GIT_OPS}.get_head_rev", return_value="abc123def456abc123def456abc123def456abc1")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_missing_repo_toplevel_logs_warning_and_skips(
    _is_git, _head, _uncommitted, caplog
):
    """When repo_toplevel is absent, the check is skipped with a warning."""
    meta = _meta(repo_toplevel="")
    import logging
    with caplog.at_level(logging.WARNING):
        _validate_preconditions("feature", "main", meta, dry_run=False)
    assert "repo_toplevel" in caplog.text


# ── HEAD revision mismatch ──────────────────────────────────────────


@patch(f"{GIT_OPS}.get_head_rev", return_value="different_sha_different_sha_different_sha_d")
@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/home/user/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_head_rev_mismatch_raises(_is_git, _toplevel, _head):
    meta = _meta(head_rev="abc123def456abc123def456abc123def456abc1")
    with pytest.raises(ExecutionError, match="HEAD revision mismatch"):
        _validate_preconditions("feature", "main", meta, dry_run=False)


# ── Missing head_rev skips check ────────────────────────────────────


@patch(f"{GIT_OPS}.has_uncommitted_changes", return_value=False)
@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/home/user/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_missing_head_rev_logs_warning_and_skips(
    _is_git, _toplevel, _uncommitted, caplog
):
    """When head_rev is absent, the check is skipped with a warning."""
    meta = _meta(head_rev="")
    import logging
    with caplog.at_level(logging.WARNING):
        _validate_preconditions("feature", "main", meta, dry_run=False)
    assert "head_rev" in caplog.text


# ── Uncommitted changes ─────────────────────────────────────────────


@patch(f"{GIT_OPS}.has_uncommitted_changes", return_value=True)
@patch(f"{GIT_OPS}.get_head_rev", return_value="abc123def456abc123def456abc123def456abc1")
@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/home/user/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_uncommitted_changes_raises(_is_git, _toplevel, _head, _uncommitted):
    with pytest.raises(ExecutionError, match="uncommitted changes"):
        _validate_preconditions("feature", "main", _meta(), dry_run=False)


@patch(f"{GIT_OPS}.get_head_rev", return_value="abc123def456abc123def456abc123def456abc1")
@patch(f"{GIT_OPS}.get_repo_toplevel", return_value="/home/user/repo")
@patch(f"{GIT_OPS}.is_git_repo", return_value=True)
def test_uncommitted_changes_ignored_in_dry_run(_is_git, _toplevel, _head):
    """dry_run=True should not call has_uncommitted_changes at all."""
    _validate_preconditions("feature", "main", _meta(), dry_run=True)
