"""Shared Markdown parsing for the review scripts — a real parser, not regexes.

Every script that needs to know where prose is (as opposed to code fences,
display math, admonish wrappers, headings) goes through here. The document is
parsed with markdown-it-py (CommonMark + tables) plus the dollarmath plugin so
`$...$` and `$$...$$` are tokens rather than text. Admonish fences are re-parsed
recursively because their bodies are prose. Phrase matching on the resulting
*natural-language* text may still use regexes; the markup never is.

Dependencies (declare in each caller's PEP-723 header):
    markdown-it-py>=3, mdit-py-plugins>=0.4
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.dollarmath import dollarmath_plugin

_MD = MarkdownIt("commonmark").enable("table").use(dollarmath_plugin, allow_space=True, allow_digits=True)

PROSE_KINDS = ("paragraph", "list_item", "blockquote", "table_cell", "heading")


@dataclass
class Block:
    kind: str              # paragraph | heading | list_item | table_cell
    line: int              # 1-based first source line
    end: int               # 1-based last source line (inclusive)
    text: str              # prose with inline math/code replaced by a space
    plain: str             # prose with inline math/code kept verbatim (for citations)
    source: str            # the exact source lines
    had_math: bool = False
    level: int = 0         # heading level
    list_index: int | None = None   # ordered-list item number
    in_blockquote: bool = False
    admonish: str | None = None     # admonish kind when inside one
    heading_path: tuple[str, ...] = ()   # enclosing headings' text, outermost first


@dataclass
class Admonish:
    kind: str
    title: str
    line: int
    end: int


@dataclass
class Figure:
    line: int
    alt: str
    src: str


@dataclass
class Doc:
    path: Path
    lines: list[str]
    blocks: list[Block] = field(default_factory=list)
    admonish: list[Admonish] = field(default_factory=list)
    code_fences: int = 0
    math_blocks: int = 0
    figures: list[Figure] = field(default_factory=list)

    @property
    def headings(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "heading"]

    def under_heading(self, predicate) -> list[Block]:
        """Blocks whose nearest enclosing heading satisfies predicate(text)."""
        return [b for b in self.blocks if b.heading_path and predicate(b.heading_path[-1]) and b.kind != "heading"]

    def prose_words(self) -> int:
        return sum(len(b.text.split()) for b in self.blocks)


def _admonish_info(info: str) -> tuple[str, str]:
    """'admonish warning title="Getting 0/0"' -> ('warning', 'Getting 0/0')."""
    try:
        parts = shlex.split(info)
    except ValueError:
        parts = info.split()
    kind = parts[1] if len(parts) > 1 and "=" not in parts[1] else "note"
    title = ""
    for p in parts[1:]:
        if p.startswith("title="):
            title = p[len("title="):]
    return kind, title


def _inline_text(tok: Token, doc: Doc, line: int) -> tuple[str, str, bool]:
    """Returns (text, plain, had_math): text drops math/code, plain keeps them."""
    out, plain, had_math = [], [], False
    for c in tok.children or []:
        if c.type == "text":
            out.append(c.content); plain.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" "); plain.append(" ")
        elif c.type == "math_inline":
            out.append(" "); plain.append(f"${c.content}$"); had_math = True
        elif c.type == "code_inline":
            out.append(" "); plain.append(f"`{c.content}`")
        elif c.type == "image":
            alt = "".join(g.content for g in (c.children or []) if g.type == "text")
            doc.figures.append(Figure(line, alt, c.attrGet("src") or ""))
        # strong/em/link open+close and html_inline carry no prose of their own
    return "".join(out), "".join(plain), had_math


def _walk(tokens: list[Token], doc: Doc, offset: int, admonish: str | None, heading_path: list[str]) -> None:
    """offset: 0-based source line the token stream starts at (for nested parses)."""
    kind_stack: list[tuple[str, int | None]] = []   # (block kind, ordered index)
    ordered: list[int] = []                          # running counters per ordered list
    blockquote = 0
    pending_heading_level = 0
    for i, t in enumerate(tokens):
        line = (t.map[0] + offset + 1) if t.map else None
        end = (t.map[1] + offset) if t.map else None
        if t.type == "heading_open":
            pending_heading_level = int(t.tag[1])
            kind_stack.append(("heading", None))
        elif t.type == "paragraph_open":
            kind_stack.append(("paragraph", None))
        elif t.type == "ordered_list_open":
            ordered.append(int(t.attrGet("start") or 1) - 1)
        elif t.type == "ordered_list_close":
            ordered.pop()
        elif t.type == "list_item_open":
            idx = None
            if ordered and t.markup.endswith((".", ")")):
                ordered[-1] += 1; idx = ordered[-1]
            kind_stack.append(("list_item", idx))
        elif t.type in ("heading_close", "paragraph_close", "list_item_close"):
            if kind_stack:
                kind_stack.pop()
        elif t.type == "blockquote_open":
            blockquote += 1
        elif t.type == "blockquote_close":
            blockquote -= 1
        elif t.type in ("th_open", "td_open"):
            kind_stack.append(("table_cell", None))
        elif t.type in ("th_close", "td_close"):
            kind_stack.pop()
        elif t.type == "math_block":
            doc.math_blocks += 1
        elif t.type == "fence":
            if t.info.strip().startswith("admonish"):
                kind, title = _admonish_info(t.info)
                doc.admonish.append(Admonish(kind, title, line, end))
                inner = _MD.parse(t.content)
                _walk(inner, doc, t.map[0] + offset + 1, kind, list(heading_path))
            else:
                doc.code_fences += 1
        elif t.type == "inline":
            # the enclosing block is the innermost open kind; list_item wraps a paragraph
            kind, idx = ("paragraph", None)
            for k, ix in reversed(kind_stack):
                if k in ("heading", "table_cell"):
                    kind, idx = k, None; break
                if k == "list_item":
                    kind, idx = k, ix; break
            # a paragraph directly inside a list item is the item's text
            if kind == "paragraph":
                for k, ix in reversed(kind_stack):
                    if k == "list_item":
                        kind, idx = "list_item", ix; break
            pline = line if line else (tokens[i - 1].map[0] + offset + 1 if tokens[i - 1].map else offset + 1)
            pend = end if end else pline
            text, plain, had_math = _inline_text(t, doc, pline)
            src = "\n".join(doc.lines[pline - 1:pend])
            if kind == "heading":
                lvl = pending_heading_level
                while heading_path and len(heading_path) >= lvl:
                    heading_path.pop()
                doc.blocks.append(Block("heading", pline, pend, text.strip(), plain.strip(), src,
                                        had_math, level=lvl, heading_path=tuple(heading_path)))
                heading_path.append(text.strip())
            else:
                doc.blocks.append(Block(kind, pline, pend, text.strip(), plain.strip(), src, had_math,
                                        list_index=idx, in_blockquote=blockquote > 0, admonish=admonish,
                                        heading_path=tuple(heading_path)))


def parse(path: str | Path) -> Doc:
    p = Path(path)
    text = p.read_text(errors="replace")
    doc = Doc(p, text.splitlines())
    _walk(_MD.parse(text), doc, 0, None, [])
    return doc


def prose_blocks(doc: Doc, include_headings: bool = False) -> list[Block]:
    return [b for b in doc.blocks if include_headings or b.kind != "heading"]


def locate(doc: Doc, block: Block, needle: str) -> int:
    """Best source line for a phrase found in block.text (prose search, not markup)."""
    head = needle.strip().lower()[:16]
    for n in range(block.line, block.end + 1):
        if head and head in doc.lines[n - 1].lower():
            return n
    return block.line
