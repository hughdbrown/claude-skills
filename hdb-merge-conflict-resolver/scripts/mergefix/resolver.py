"""Core resolution engine.

Coordinates conflict parsing, AI calls, and resolution application.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

import anthropic

from mergefix import ai as ai_module
from mergefix import db
from mergefix import git_ops
from mergefix.models import (
    ConflictBlock,
    ConflictFile,
    MergeContext,
    OperationType,
    Resolution,
    Strategy,
)

logger = logging.getLogger(__name__)

# Conflict marker patterns
_OURS_RE = re.compile(r"^<{7}\s*(.*)")
_BASE_RE = re.compile(r"^\|{7}\s*(.*)")
_DIVIDER_RE = re.compile(r"^={7}$")
_THEIRS_RE = re.compile(r"^>{7}\s*(.*)")

CONTEXT_LINES = 15  # lines of context before/after each conflict block

# Lock files and generated files that should not be content-merged
SKIP_PATTERNS = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "Gemfile.lock",
    "poetry.lock",
    "composer.lock",
    "go.sum",
}

# Confidence thresholds
HIGH_CONFIDENCE = 0.9
MEDIUM_CONFIDENCE = 0.7


def resolve_all(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic | None,
    model: str,
    dry_run: bool,
    verbose: bool,
) -> dict[str, list[Resolution]]:
    """Resolve all conflicts in the repository.

    Returns a mapping of file_path -> list of Resolutions.
    """
    # Discover conflicts
    conflicted_paths = git_ops.get_conflicted_files()
    if not conflicted_paths:
        logger.info("No conflicted files found.")
        return {}

    context = git_ops.get_merge_context()
    _log_context(context, conflicted_paths)

    # Store context metadata
    db.set_metadata(conn, "operation", context.operation.value)
    db.set_metadata(conn, "current_branch", context.current_branch)
    db.set_metadata(conn, "incoming_ref", context.incoming_ref)
    db.set_metadata(conn, "total_conflicted_files", str(len(conflicted_paths)))

    all_resolutions: dict[str, list[Resolution]] = {}

    for file_path in conflicted_paths:
        resolutions = _resolve_file(
            conn=conn,
            client=client,
            model=model,
            file_path=file_path,
            context=context,
            dry_run=dry_run,
            verbose=verbose,
        )
        if resolutions is not None:
            all_resolutions[file_path] = resolutions

    return all_resolutions


def _resolve_file(
    conn: sqlite3.Connection,
    client: anthropic.Anthropic | None,
    model: str,
    file_path: str,
    context: MergeContext,
    dry_run: bool,
    verbose: bool,
) -> list[Resolution] | None:
    """Resolve all conflicts in a single file.

    Returns the list of resolutions, or None if the file was skipped.
    """
    # Check for skip conditions
    basename = Path(file_path).name
    if basename in SKIP_PATTERNS:
        logger.info(
            "Skipping lock file '%s' — regenerate after merge.", file_path
        )
        db.insert_skipped_file(conn, file_path, "lock file")
        return None

    status = git_ops.get_conflict_status(file_path)
    if status in ("DD",):
        logger.info(
            "Both sides deleted '%s'. Removing.", file_path
        )
        git_ops.rm_file(file_path, dry_run)
        db.insert_skipped_file(conn, file_path, "both deleted")
        return None

    if status in ("AU", "UA", "DU", "UD"):
        logger.warning(
            "Delete/modify conflict on '%s' (status=%s). "
            "Requires manual resolution.",
            file_path,
            status,
        )
        db.insert_skipped_file(
            conn, file_path, f"delete/modify conflict ({status})"
        )
        return None

    if git_ops.is_binary_file(file_path):
        logger.warning(
            "Binary file '%s'. Requires manual resolution.", file_path
        )
        db.insert_skipped_file(conn, file_path, "binary file")
        return None

    # Parse the file
    try:
        conflict_file = parse_conflict_file(file_path)
    except OSError as e:
        logger.error("Could not read '%s': %s", file_path, e)
        db.insert_skipped_file(conn, file_path, f"read error: {e}")
        return None

    if not conflict_file.blocks:
        logger.warning(
            "No conflict markers found in '%s'. Skipping.", file_path
        )
        db.insert_skipped_file(conn, file_path, "no conflict markers")
        return None

    logger.info(
        "Resolving '%s' (%d conflict block%s)...",
        file_path,
        conflict_file.block_count,
        "s" if conflict_file.block_count != 1 else "",
    )

    # Resolve each block
    resolutions: list[Resolution] = []
    for block in conflict_file.blocks:
        if client is not None:
            try:
                resolution = ai_module.resolve_conflict(
                    client=client,
                    model=model,
                    block=block,
                    context=context,
                )
            except (ai_module.AIError, Exception) as e:
                logger.warning(
                    "AI resolution failed for '%s' block %d: %s. "
                    "Falling back to take_theirs.",
                    file_path,
                    block.block_index + 1,
                    e,
                )
                resolution = Resolution(
                    strategy=Strategy.TAKE_THEIRS,
                    resolved_content=block.theirs,
                    confidence=0.3,
                    reasoning=f"AI fallback due to error: {e}",
                )
        else:
            # No AI client — default to take_theirs
            resolution = Resolution(
                strategy=Strategy.TAKE_THEIRS,
                resolved_content=block.theirs,
                confidence=0.3,
                reasoning="No AI client available. Defaulting to incoming changes.",
            )

        flagged = resolution.confidence < HIGH_CONFIDENCE
        applied = not dry_run and resolution.confidence >= MEDIUM_CONFIDENCE

        db.insert_resolution(
            conn=conn,
            file_path=file_path,
            block_index=block.block_index,
            total_blocks=block.total_blocks,
            resolution=resolution,
            ours_content=block.ours,
            theirs_content=block.theirs,
            base_content=block.base,
            ours_label=block.ours_label,
            theirs_label=block.theirs_label,
            applied=applied,
            flagged=flagged,
        )

        if verbose:
            _log_resolution(block, resolution, flagged)

        resolutions.append(resolution)

    # Apply resolutions to the file
    if not dry_run:
        low_confidence = any(
            r.confidence < MEDIUM_CONFIDENCE for r in resolutions
        )
        if low_confidence:
            logger.warning(
                "Low-confidence resolution in '%s'. "
                "Skipping auto-apply — resolve manually.",
                file_path,
            )
        else:
            _apply_resolutions(conflict_file, resolutions, dry_run)
    else:
        logger.info("[DRY RUN] Would apply %d resolutions to '%s'.",
                     len(resolutions), file_path)

    return resolutions


def parse_conflict_file(file_path: str) -> ConflictFile:
    """Parse a file with conflict markers into a ConflictFile.

    Handles both standard (2-way) and diff3 (3-way) conflict markers.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    blocks: list[ConflictBlock] = []

    i = 0
    while i < len(lines):
        line_stripped = lines[i].rstrip("\n\r")
        ours_match = _OURS_RE.match(line_stripped)
        if ours_match:
            block = _parse_single_block(
                lines, i, file_path, len(blocks)
            )
            if block is not None:
                blocks.append(block)
                i = block.end_line  # skip past the >>>>>>> line
                continue
        i += 1

    # Set total_blocks on all blocks
    total = len(blocks)
    for b in blocks:
        b.total_blocks = total

    # Extract context for each block
    for b in blocks:
        b.context_before = _extract_context_before(lines, b.start_line - 1)
        b.context_after = _extract_context_after(lines, b.end_line - 1)

    return ConflictFile(
        path=file_path,
        blocks=blocks,
        original_content=content,
    )


def _parse_single_block(
    lines: list[str],
    start: int,
    file_path: str,
    block_index: int,
) -> ConflictBlock | None:
    """Parse a single conflict block starting at line index `start`.

    Returns None if the block is malformed.
    """
    ours_label_match = _OURS_RE.match(lines[start].rstrip("\n\r"))
    ours_label = ours_label_match.group(1).strip() if ours_label_match else "HEAD"

    ours_lines: list[str] = []
    base_lines: list[str] | None = None
    theirs_lines: list[str] = []
    theirs_label = ""

    # State machine: ours -> (base ->) theirs
    state = "ours"
    i = start + 1

    while i < len(lines):
        line_stripped = lines[i].rstrip("\n\r")

        if state == "ours":
            base_match = _BASE_RE.match(line_stripped)
            divider_match = _DIVIDER_RE.match(line_stripped)

            if base_match:
                # Entering base section (diff3 mode)
                base_lines = []
                state = "base"
            elif divider_match:
                # No base, going straight to theirs
                state = "theirs"
            else:
                ours_lines.append(lines[i])

        elif state == "base":
            divider_match = _DIVIDER_RE.match(line_stripped)
            if divider_match:
                state = "theirs"
            else:
                base_lines.append(lines[i])

        elif state == "theirs":
            theirs_match = _THEIRS_RE.match(line_stripped)
            if theirs_match:
                theirs_label = theirs_match.group(1).strip()
                return ConflictBlock(
                    file_path=file_path,
                    block_index=block_index,
                    total_blocks=0,  # set later
                    ours=_join_lines(ours_lines),
                    theirs=_join_lines(theirs_lines),
                    base=_join_lines(base_lines) if base_lines is not None else None,
                    ours_label=ours_label,
                    theirs_label=theirs_label,
                    start_line=start + 1,  # 1-based
                    end_line=i + 1,  # 1-based, inclusive
                )
            else:
                theirs_lines.append(lines[i])

        i += 1

    # Malformed block — never found >>>>>>>
    logger.warning(
        "Malformed conflict block in '%s' starting at line %d.",
        file_path,
        start + 1,
    )
    return None


def _join_lines(lines: list[str]) -> str:
    """Join lines, stripping trailing newline from the last line."""
    text = "".join(lines)
    if text.endswith("\n"):
        text = text[:-1]
    return text


def _extract_context_before(lines: list[str], marker_index: int) -> str:
    """Extract CONTEXT_LINES lines before the conflict marker."""
    start = max(0, marker_index - CONTEXT_LINES)
    context_lines = lines[start:marker_index]
    return "".join(context_lines).rstrip("\n")


def _extract_context_after(lines: list[str], marker_index: int) -> str:
    """Extract CONTEXT_LINES lines after the conflict marker."""
    start = marker_index + 1
    end = min(len(lines), start + CONTEXT_LINES)
    context_lines = lines[start:end]
    return "".join(context_lines).rstrip("\n")


def _apply_resolutions(
    conflict_file: ConflictFile,
    resolutions: list[Resolution],
    dry_run: bool,
) -> None:
    """Replace conflict blocks in the file with resolved content and stage it.

    Processes blocks in reverse order so line numbers remain stable.
    """
    lines = conflict_file.original_content.splitlines(keepends=True)
    blocks = conflict_file.blocks

    # Pair blocks with resolutions, process in reverse order
    pairs = list(zip(blocks, resolutions))
    for block, resolution in reversed(pairs):
        start_idx = block.start_line - 1  # 0-based
        end_idx = block.end_line  # end_line is 1-based inclusive, so this is exclusive

        # Build the replacement
        resolved = resolution.resolved_content
        if not resolved.endswith("\n"):
            resolved += "\n"

        # Replace the lines
        lines[start_idx:end_idx] = [resolved]

    # Write the file
    resolved_content = "".join(lines)
    with open(conflict_file.path, "w", encoding="utf-8") as f:
        f.write(resolved_content)

    # Stage the resolved file
    git_ops.stage_file(conflict_file.path, dry_run)
    logger.info("Resolved and staged '%s'.", conflict_file.path)


def _log_context(
    context: MergeContext,
    conflicted_paths: list[str],
) -> None:
    """Log the merge context and conflicted file list."""
    logger.info("=" * 60)
    logger.info("MERGE CONFLICT RESOLUTION")
    logger.info("=" * 60)
    logger.info("Operation:      %s", context.operation.value)
    logger.info("Current branch: %s", context.current_branch)
    if context.incoming_ref:
        logger.info("Incoming:       %s", context.incoming_ref)
    logger.info("Conflicted files: %d", len(conflicted_paths))
    for i, path in enumerate(conflicted_paths, 1):
        logger.info("  %d. %s", i, path)
    logger.info("")


def _log_resolution(
    block: ConflictBlock,
    resolution: Resolution,
    flagged: bool,
) -> None:
    """Log a single resolution in verbose mode."""
    flag_str = " [FLAGGED]" if flagged else ""
    logger.info(
        "  Block %d/%d: %s (confidence=%.2f)%s",
        block.block_index + 1,
        block.total_blocks,
        resolution.strategy.value,
        resolution.confidence,
        flag_str,
    )
    logger.info("    Reasoning: %s", resolution.reasoning)
