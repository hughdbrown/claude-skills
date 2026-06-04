#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["sympy>=1.12", "pyyaml>=6.0"]
# ///
"""Substitute every claimed answer back through a CAS. The correctness gate.

For a problems/solutions book, prose review is NOT enough: a solution can read
fluently, pass check-refs, and build clean while being mathematically wrong
(wrong sign, wrong coefficient, a system declared inconsistent that isn't).
This script is the primary correctness gate — it machine-verifies claimed
answers with sympy. Build it in Phase 0 and make writing each entry part of the
drafting task; back-filling hundreds of entries after the fact is the expensive
path.

Drive it from a YAML file (default scripts/answers/answers.yaml) — a list of
entries, each with `id`, `type`, and type-specific keys. EXACT key names matter;
aliases raise KeyError at run time. Supported types and their keys:

  arithmetic         expression, claimed_value, [tolerance]
  equation_solutions var, lhs, rhs, claimed_solutions (list)
  comparison         lhs, rhs, relation   ('<','<=','>','>=','==')
  set_equality       lhs (list), rhs (list)
  system             vars (list), equations (list of "lhs = rhs"), claimed_solution (dict)
  matrix_solution    matrix (list of rows), rhs (list), claimed_solution (list)

Per-entry escape hatches:
  skip: true                        # not machine-checkable (proof/sketch/prose) — counted, not run
  known_defect: true                # known-wrong; expected to fail. Reports "fix detected" if it starts passing.

Sympy will not symbolically simplify every true identity (e.g.
atan(1/2)+atan(1/3)-pi/4); give such entries a `tolerance` to fall through to a
numeric check.

Usage:
    answer-audit.py [--file answers.yaml] [--only chNN]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from sympy import Eq, Matrix, simplify, sympify
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# implicit_multiplication: "2x"/"4px" -> 2*x / 4*p*x.  convert_xor: "x^2" -> x**2
# (math authors write ^ for powers). Extend the locals for a trig/calculus book
# (sin, cos, asin, limit, Sum, LambertW, ...).
TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
PARSE_LOCALS: dict = {}


def P(expr) -> "object":
    return parse_expr(str(expr), transformations=TRANSFORMS, local_dict=PARSE_LOCALS)


def is_zero(expr, tol: float | None) -> bool:
    s = simplify(expr)
    if s == 0:
        return True
    if tol is not None:
        try:
            return abs(complex(s.evalf())) <= tol
        except (TypeError, ValueError):
            return False
    return False


def check(entry: dict) -> tuple[bool, str]:
    t = entry["type"]
    tol = entry.get("tolerance")
    if t == "arithmetic":
        return is_zero(P(entry["expression"]) - P(entry["claimed_value"]), tol), "value mismatch"
    if t == "equation_solutions":
        var = P(entry["var"])
        diff = P(entry["lhs"]) - P(entry["rhs"])
        bad = [s for s in entry["claimed_solutions"]
               if not is_zero(diff.subs(var, P(s)), tol)]
        return (not bad), f"these are not roots: {bad}"
    if t == "comparison":
        rel = {"<": "<", "<=": "<=", ">": ">", ">=": ">=", "==": "=="}[entry["relation"]]
        ok = bool(sympify(f"({entry['lhs']}) {rel} ({entry['rhs']})",
                          locals=PARSE_LOCALS))
        return ok, "comparison is false"
    if t == "set_equality":
        lhs = {simplify(P(x)) for x in entry["lhs"]}
        rhs = {simplify(P(x)) for x in entry["rhs"]}
        return (lhs == rhs), f"sets differ: {lhs} vs {rhs}"
    if t == "system":
        sol = {P(k): P(v) for k, v in entry["claimed_solution"].items()}
        for eq in entry["equations"]:
            l, r = eq.split("=", 1)
            if not is_zero((P(l) - P(r)).subs(sol), tol):
                return False, f"solution fails: {eq}"
        return True, ""
    if t == "matrix_solution":
        A = Matrix([[P(c) for c in row] for row in entry["matrix"]])
        b = Matrix([P(x) for x in entry["rhs"]])
        x = Matrix([P(x) for x in entry["claimed_solution"]])
        return (simplify(A * x - b) == Matrix.zeros(*b.shape)), "A x != b"
    raise ValueError(f"unknown type '{t}' in entry {entry.get('id', '?')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default="scripts/answers/answers.yaml")
    ap.add_argument("--only", help="only entries whose id starts with this (e.g. ch04)")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        sys.exit(f"answer-audit: {path} not found — scaffold it in Phase 0")
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if args.only:
        entries = [e for e in entries if str(e.get("id", "")).startswith(args.only)]

    failed, skipped, fixed, checked, defects = [], 0, [], 0, 0
    for e in entries:
        eid = e.get("id", "?")
        if e.get("skip"):
            skipped += 1
            continue
        try:
            ok, why = check(e)
        except Exception as exc:  # malformed entry, bad parse
            ok, why = False, f"{type(exc).__name__}: {exc}"
        if e.get("known_defect"):
            defects += 1
            if ok:
                fixed.append(eid)  # defect silently fixed — clear the flag
            continue
        checked += 1
        if not ok:
            failed.append(f"  {eid}: {why}")

    print(f"answer-audit: {checked} checked, {len(failed)} failed, "
          f"{skipped} skipped, {defects} known-defect")
    for f in fixed:
        print(f"  NOTE: known_defect '{f}' now passes — remove the flag.")
    if failed:
        print("\n".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
