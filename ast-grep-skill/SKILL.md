---
name: ast-grep
description: Search and rewrite code structurally with ast-grep instead of grep — AST pattern matching with metavariables, YAML rules, and safe codemods. Use when searching code for syntactic constructs (calls, declarations, imports, loops), when grep/regex gives false positives from strings, comments, or formatting differences, or when doing find-and-replace refactors across a codebase.
---

# ast-grep: structural code search

ast-grep parses code into a syntax tree (via tree-sitter) and matches **patterns that are themselves code**, not text. Use it instead of grep whenever the thing you're looking for is a syntactic construct rather than a string.

## When to use ast-grep instead of grep

- Formatting varies: `f(x)`, `f( x )`, and multi-line `f(\n  x\n)` are one pattern: `f($X)`.
- grep false-positives on strings/comments: `ast-grep -p 'console.log($$$)'` matches only real calls, never `"console.log"` or `// console.log`.
- The match has structure regex can't express: nested calls, argument lists, "X inside a loop", "function that calls itself".
- You want to **rewrite** what you find, safely and idempotently.

Keep using grep/ripgrep for plain strings, log output, non-code files, and "where does this word appear at all".

## Quick start

```bash
brew install ast-grep        # or: npm i -g @ast-grep/cli, cargo install ast-grep

ast-grep -p 'console.log($MSG)' src/                  # search a directory
ast-grep -p 'await $P' -l ts src/                     # force language
ast-grep -p 'var $N = $V' --rewrite 'let $N = $V' -l js src/   # show diff
#   add --interactive (-i) to confirm each change, --update-all (-U) to apply all
ast-grep scan --rule rules/no-eval.yml src/           # run a YAML rule
```

**Always single-quote patterns** — double quotes make the shell expand `$MSG` to empty.

## Pattern essentials

- A pattern must be **valid code** for the target language; it's parsed, then matched structurally at any nesting depth.
- `$VAR` matches exactly one node (any expression, however complex). Names must be UPPERCASE: `$MSG`, `$META_VAR`. `$msg` is invalid.
- `$$$` / `$$$ARGS` matches zero or more nodes (argument lists, parameters, statement bodies): `function $F($$$ARGS) { $$$BODY }`.
- Repeating a metavariable forces equality: `$A == $A` matches `x == x` but not `x == y`. Use `$_` / `$_NAME` for "don't care, don't unify".
- Pattern matches a whole node. `console.log($MSG)` finds the call wherever it sits; you do not anchor with `.*`.

## When a pattern won't match (the #1 debugging loop)

1. Check what your pattern parsed as: `ast-grep -p '$KEY: $VAL' -l js --debug-query=ast`
2. Check what the target code parses as: paste it into the playground (https://ast-grep.github.io/playground.html), or `--debug-query=cst` on a minimal sample.
3. If the pattern parses as the wrong construct (e.g. `a: 1` becomes a labeled statement, class fields parse as assignments), give it **context** and select the node you mean — see "Pattern objects" in [REFERENCE.md](REFERENCE.md).
4. If quoting style / trailing commas / `async` modifiers block the match, relax strictness: `--strictness ast` (see strictness table in REFERENCE.md).
5. Build complex rules incrementally: start from the atomic pattern, add one constraint at a time, re-run after each.

## YAML rules in one minute

When a one-line pattern isn't enough (context, exclusions, alternatives), write a rule file and run `ast-grep scan`:

```yaml
id: no-console-in-prod
language: JavaScript
severity: warning
message: console.log in production code
rule:
  pattern: console.log($$$ARGS)
  inside:                      # relational: only inside functions…
    kind: function_declaration
    stopBy: end
  not:                         # …excluding test functions
    inside:
      kind: function_declaration
      has: {kind: identifier, regex: "^test"}
      stopBy: end
fix: logger.debug($$$ARGS)     # optional rewrite — name the $$$ or it won't substitute
```

Key vocabulary (full semantics in REFERENCE.md):
- **Atomic**: `pattern` (code shape), `kind` (node type, e.g. `function_declaration`), `regex` (text — always pair with `kind`/`pattern`).
- **Relational**: `inside`, `has`, `follows`, `precedes` — add `stopBy: end` to search beyond immediate neighbors (you almost always want this).
- **Composite**: `all`, `any`, `not`, `matches` (reusable utils). Sibling keys AND together implicitly.
- **`constraints:`** filters what a metavariable may be (`kind`, `regex`, `pattern`).

## Scripting and piping

```bash
ast-grep -p 'TODO' --json | jq 'length'                       # count matches
ast-grep -p 'function $N($$$) { $$$ }' src/ --json \
  | jq -r '.[].metaVariables.single.N.text'                   # extract captures
echo 'eval(x)' | ast-grep -p 'eval($$$)' --stdin -l js        # pipe code in
```

Exit codes: `run` returns 0 if matched, 1 if not; `scan` returns 1 if any error-severity rule fired — both ready for CI gates and pre-commit hooks (examples in REFERENCE.md).

## Going deeper

See [REFERENCE.md](REFERENCE.md) for: full rule schema, relational/composite rule semantics and pitfalls, pattern objects (`context`/`selector`), strictness levels, metavariable constraints, reusable utility rules, project setup (`sgconfig.yml`, `ast-grep new`, `ast-grep test`), rewrite mechanics, and JSON/jq/CI recipes.
