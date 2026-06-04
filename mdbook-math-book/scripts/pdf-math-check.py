#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Fail if raw TeX math leaked into the rendered PDF instead of typesetting.

`mdbook build` exits 0 even when math is broken: a too-old mdbook-pandoc, or a
missing `[output.pandoc.markdown.extensions] math = true`, silently passes the
literal `$$ \\frac{a}{b} $$` through to the page. This script is the canonical
"did the math actually render?" gate. It extracts text with pdftotext and fails
if any raw-TeX control sequence survived.

Run it in `just check` / `just test`. A green `mdbook build` is NOT proof the
PDF is correct — this is.

Usage:
    pdf-math-check.py [PDF ...]          # default: every PDF under book/pandoc/pdf/
    pdf-math-check.py --text-file t.txt  # check pre-extracted text (for tests)
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Control sequences that should NEVER appear in rendered output. If pdftotext
# sees these, MathJax/pandoc never converted the source — the math is broken.
RAW_TEX_PATTERNS = (
    r"\$\$",
    r"\\frac",
    r"\\dfrac",
    r"\\tfrac",
    r"\\sqrt",
    r"\\mathbb",
    r"\\mathbf",
    r"\\left",
    r"\\right",
    r"\\begin\{",
    r"\\end\{",
    r"\\sum",
    r"\\int",
)


def extract_text(pdf: Path) -> str:
    if shutil.which("pdftotext") is None:
        sys.exit("pdf-math-check: pdftotext not found (install poppler-utils)")
    proc = subprocess.run(
        ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        sys.exit(proc.stderr.strip() or f"pdf-math-check: pdftotext failed on {pdf}")
    return proc.stdout


def check_text(text: str, label: str) -> list[str]:
    hits = []
    for pattern in RAW_TEX_PATTERNS:
        if re.search(pattern, text):
            hits.append(f"{label}: raw TeX '{pattern}' survived into the PDF")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdfs", nargs="*", help="PDF files (default: book/pandoc/pdf/*.pdf)")
    ap.add_argument("--text-file", help="check this extracted-text file instead of a PDF")
    args = ap.parse_args()

    failures: list[str] = []
    if args.text_file:
        failures += check_text(Path(args.text_file).read_text(encoding="utf-8"),
                               args.text_file)
    else:
        pdfs = [Path(p) for p in args.pdfs] or sorted(Path("book/pandoc/pdf").glob("*.pdf"))
        if not pdfs:
            sys.exit("pdf-math-check: no PDF found under book/pandoc/pdf/ — run `mdbook build` first")
        for pdf in pdfs:
            failures += check_text(extract_text(pdf), pdf.name)

    if failures:
        print("\n".join(failures))
        print(f"pdf-math-check: FAIL ({len(failures)} issue(s)). Math is not rendering — "
              "check mdbook-pandoc>=0.10.6 and `math = true` in book.toml.")
        return 1
    print("pdf-math-check: OK — no raw TeX leaked into the PDF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
