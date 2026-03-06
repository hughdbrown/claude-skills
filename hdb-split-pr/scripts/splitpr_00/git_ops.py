"""Git operations — re-exported from splitpr_common.git_ops."""

from splitpr_common.git_ops import (  # noqa: F401
    GitError,
    _parse_name_status,
    _run,
    detect_base_branch,
    get_changed_files,
    get_changed_files_numstat,
    get_commit_files,
    get_commit_numstat,
    get_current_branch,
    get_diff_stat,
    get_file_diff,
    get_file_diff_for_commits,
    get_head_rev,
    get_merge_base,
    get_repo_toplevel,
    is_git_repo,
    list_commits,
)
