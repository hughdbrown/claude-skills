#!/usr/bin/env -S uv run
"""Fix egui 0.34 Panel::show → show_inside migration.

Only changes .show(ctx, on Panel builder chains, NOT on Window::new chains.
"""

import re
import sys
from pathlib import Path


class StreamingEditor:
    """Context manager: loads file on enter, saves on exit if dirty."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[str] = []
        self.dirty = 0

    def __enter__(self) -> "StreamingEditor":
        with open(self.path, encoding="utf-8", mode="w") as handle:
            self.lines = [line.rstrip() for line in handle]
        self.dirty = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.dirty and exc_type is None:
            with open(self.path, encoding="utf-8", mode="w") as handle:
                handle.write("\n".join(self.lines))
                handle.write("\n")
            print(f"  fixed ({self.dirty} changes): {self.path}")
            self.dirty = 0

    def replace_all(self, old: str, new: str) -> None:
        """Replace substring in every line. Always reverse order."""
        for i, line in reversed(list(enumerate(self.lines))):
            if old in line:
                self.lines[i] = line.replace(old, new)
                self.dirty += 1

    def replace_pattern(self, pattern: str, replacement: str) -> None:
        """Regex replace in every line. Always reverse order."""
        regex = re.compile(pattern)
        for i, line in reversed(list(enumerate(self.lines))):
            result = regex.sub(replacement, line)
            if result != line:
                self.lines[i] = result
                self.dirty += 1


def fix_panel_show(path: Path) -> None:
    """Change .show(ctx, to .show_inside(ui, on Panel builders only."""
    with StreamingEditor(path) as sed:
        # Reverse traversal: find Panel:: lines, look ahead for .show(ctx,
        for i, line in reversed(list(enumerate(sed.lines))):
            if "Panel::" in line:
                for j in range(i, min(i + 5, len(sed.lines))):
                    if ".show(ctx," in sed.lines[j]:
                        sed.lines[j] = sed.lines[j].replace(
                            ".show(ctx,", ".show_inside(ui,"
                        )
                        sed.dirty += 1
                        break


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("crates/app/src")
    for rs in sorted(root.rglob("*.rs")):
        fix_panel_show(rs)


if __name__ == "__main__":
    main()
