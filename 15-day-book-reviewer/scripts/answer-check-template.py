#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["sympy>=1.12"]
# ///
"""Mechanical answer check — the correctness reviewer's required companion.

Copy this file to docs/reviews/round-<N>/checks/<chunk>.py, fill CHECKS with one
entry per worked example and exercise in your chunk, run it, and paste the
summary line into your report. The controller re-runs the file; a report whose
numbers cannot be reproduced by its check file is treated as unverified.

Rules (from the series' lessons-learned):
- Derive each check from the PROBLEM's own constants, never from the key. A
  check that asserts the key equals itself proves nothing.
- Solve by hand first, write the check second, read the key third.
- If the check disagrees with the key, verify the checker before blaming the
  author (population vs sample variance once produced a false positive).
- Prose/proof/"argue it" exercises are `skip` entries: counted, not run, and
  named in the report as checked by hand.

Entry kinds (all expressions are sympy strings; `x, h, n, t, k` are symbols):
  {"id": "ex3",  "kind": "limit",  "expr": "(x**2+x-6)/(x-2)", "var": "x", "to": "2",  "claimed": "5"}
  {"id": "ex5",  "kind": "limit",  "expr": "((4+h)**2-16)/h",  "var": "h", "to": "0",  "claimed": "8", "dir": "+-"}
  {"id": "we2",  "kind": "value",  "expr": "sqrt(2*101325/1.225)", "claimed": "406.7", "tol": 0.5}
  {"id": "ex7",  "kind": "solve",  "eq": "x**2-5*x+6", "var": "x", "claimed": ["2", "3"]}
  {"id": "ex8",  "kind": "simplify", "lhs": "(x**3-1)/(x-1)", "rhs": "x**2+x+1"}
  {"id": "ex1",  "kind": "series",  "expr": "1/2**n", "var": "n", "lo": "1", "hi": "oo", "claimed": "1"}
  {"id": "ex4",  "kind": "skip",   "why": "prose: explain why the limit fails"}
  {"id": "ex9",  "kind": "limit",  "expr": "1/x**2", "var": "x", "to": "0", "claimed": "oo"}
  {"id": "ex10", "kind": "limit",  "expr": "1/x", "var": "x", "to": "0", "dir": "-", "claimed": "-oo"}
  {"id": "ex2",  "kind": "matrix", "expr": "Matrix([[1,2],[3,4]])*Matrix([[1],[1]])", "claimed": "Matrix([[3],[7]])"}

When a fix changes a number or expression, the FIXER adds or updates the entry for
every case the finding names and re-runs this file; a check that covers one of
two cases is how a slip in the second case ships.
"""
from __future__ import annotations

import sys

import sympy as sp
from sympy import oo, pi, E, I, sqrt, sin, cos, tan, exp, log, ln, Matrix, Rational, factorial  # noqa: F401

x, h, n, t, k, y = sp.symbols("x h n t k y")
LOCALS = {s.name: s for s in (x, h, n, t, k, y)} | {
    "oo": oo, "pi": pi, "E": E, "e": E, "I": I, "sqrt": sqrt, "sin": sin, "cos": cos, "tan": tan,
    "exp": exp, "log": log, "ln": ln, "Matrix": Matrix, "Rational": Rational, "factorial": factorial,
}

CHECKS: list[dict] = [
    # Fill me in. One entry per worked example ("weN") and exercise ("exN").
]


def S(s: str):
    return sp.sympify(s, locals=LOCALS)


def close(a, b, tol: float | None) -> bool:
    if a in (oo, -oo, sp.zoo) or b in (oo, -oo, sp.zoo):
        return a == b            # oo - oo is nan, so compare infinities directly
    if tol is None:
        return sp.simplify(a - b) == 0
    return abs(float(sp.N(a)) - float(sp.N(b))) <= tol


def run(c: dict) -> tuple[bool | None, str]:
    kind = c["kind"]
    if kind == "skip":
        return None, c.get("why", "not mechanically checkable")
    if kind == "limit":
        v = LOCALS[c["var"]]
        dirs = ["+", "-"] if c.get("dir", "+-") == "+-" else [c["dir"]]
        got = [sp.limit(S(c["expr"]), v, S(c["to"]), dir=d) for d in dirs]
        if len(got) == 2 and not close(got[0], got[1], None):
            return False, f"one-sided limits differ: {got[0]} vs {got[1]}"
        return close(got[0], S(c["claimed"]), c.get("tol")), f"computed {got[0]}"
    if kind == "value":
        got = S(c["expr"])
        return close(got, S(c["claimed"]), c.get("tol")), f"computed {sp.N(got, 8)}"
    if kind == "solve":
        v = LOCALS[c["var"]]
        got = set(sp.solve(S(c["eq"]), v))
        want = {S(s) for s in c["claimed"]}
        return got == want, f"computed {sorted(got, key=str)}"
    if kind == "simplify":
        return sp.simplify(S(c["lhs"]) - S(c["rhs"])) == 0, "lhs - rhs simplifies to 0"
    if kind == "series":
        v = LOCALS[c["var"]]
        got = sp.summation(S(c["expr"]), (v, S(c["lo"]), S(c["hi"])))
        return close(got, S(c["claimed"]), c.get("tol")), f"computed {got}"
    if kind == "matrix":
        got = S(c["expr"])
        return sp.simplify(got - S(c["claimed"])) == sp.zeros(*got.shape), f"computed {got}"
    return False, f"unknown kind {kind!r}"


def main() -> int:
    if not CHECKS:
        print("CHECKS is empty — fill it in before running.", file=sys.stderr)
        return 2
    passed = failed = skipped = 0
    for c in CHECKS:
        try:
            ok, note = run(c)
        except Exception as e:  # a broken entry is a failure, not a pass
            ok, note = False, f"error: {e}"
        if ok is None:
            skipped += 1; print(f"SKIP  {c['id']}: {note}")
        elif ok:
            passed += 1; print(f"PASS  {c['id']}: {note}")
        else:
            failed += 1; print(f"FAIL  {c['id']}: {note}  (claimed {c.get('claimed')})")
    print(f"answer-check: {passed} passed, {failed} failed, {skipped} skipped by hand")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
