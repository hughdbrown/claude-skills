# ast-grep Reference

Detailed reference distilled from *Mastering ast-grep*. Companion to [SKILL.md](SKILL.md).

## CLI cheat sheet

```bash
ast-grep -p 'PATTERN' [PATHS]          # alias for: ast-grep run --pattern
ast-grep -p 'PATTERN' -l js            # --lang: js, ts, tsx, python, rust, go, java, c, …
ast-grep -p 'PATTERN' --globs '*.ts'   # restrict files
ast-grep -p 'OLD' --rewrite 'NEW'      # show diffs (dry run by default)
ast-grep -p 'OLD' --rewrite 'NEW' -i   # --interactive: accept/reject each match
ast-grep -p 'OLD' --rewrite 'NEW' -U   # --update-all: apply everything
ast-grep scan                          # run all rules via sgconfig.yml discovery
ast-grep scan --rule file.yml [PATHS]  # run one rule file
ast-grep scan --inline-rules 'id: t…'  # rule YAML as a CLI string
ast-grep test                          # run rule tests; --update-all refreshes snapshots
ast-grep new                           # scaffold project / rule / test / util
ast-grep lsp                           # language server for editor integration
ast-grep -p 'X' --debug-query=ast      # show how the PATTERN parses (ast|cst|pattern|sexp)
```

Exit codes — `run`: 0 match found, 1 no match, 2 error. `scan`: 0 clean, 1 any error-severity match.

## Metavariables

| Form | Matches | Notes |
|------|---------|-------|
| `$NAME` | exactly one AST node | UPPERCASE letters/digits/underscore only; `$msg`, `$123`, `$KEBAB-CASE` invalid |
| `$$$` / `$$$NAME` | zero or more consecutive nodes | argument/parameter lists, statement sequences |
| `$_` / `$_NAME` | one node, non-capturing | repeated occurrences do NOT need to be equal |
| repeated `$A … $A` | unification | all occurrences must be structurally identical |

Edge cases:
- A metavariable must be a **complete AST node**. `obj.on$EVENT` and `"Hello $WORLD"` are literal text, not captures. For partial-identifier matching use `constraints: {NAME: {regex: …}}` or a `regex` rule.
- Multi-metavariables are non-greedy and never backtrack: `f($$$A, $$$B)` on `f(a, b, c)` binds `$$$A=[a]`, `$$$B=[b, c]`.
- Multi-metavariables **cannot be constrained** via `constraints:` (silently ignored).
- Unification is structural, not textual: `1 + 1` ≡ `1+1`, but `(1 + 1)` differs (extra parenthesized node).

## Rule file schema

```yaml
id: kebab-case-unique-id        # required
language: JavaScript            # required
rule: {...}                     # required — the matching predicate
message: What was found         # diagnostic
severity: error|warning|info|hint|off   # default hint; error fails `scan`
note: |
  Longer markdown remediation guidance.
fix: replacement with $CAPTURES # optional rewrite
constraints: {NAME: {...}}      # optional metavariable filters
utils: {name: {...}}            # optional local reusable sub-rules
transform: {...}                # optional string ops on captures (substring/replace/convert)
labels: {...}                   # optional highlight customization
```

Multiple rules in one file separated by `---` apply in a single atomic pass (e.g. rename a definition and all its call sites together).

## Atomic rules

**`pattern`** — structural code shape (see metavariables above).

**`kind`** — match by tree-sitter node type, bypassing pattern parsing:
```yaml
rule:
  kind: function_declaration
```
Use when patterns are ambiguous (`{}` block vs object literal) or would require enumerating modifier combinations (async/export/decorators). Discover kind names in the playground (hover a node) or with `--debug-query=ast`.

Caution: `kind` does **not** change how a sibling `pattern` is parsed. `pattern: $N = $V` parses as `assignment_expression`; adding `kind: field_definition` yields zero matches. To reparse in context, use a pattern object (below).

Structural selectors (v0.39.1+): `kind: call_expression>identifier` (child), `+` (adjacent sibling), `~` (any following sibling), space (descendant).

**`regex`** — Rust regex over the node's text. Automata-based: no backreferences, no lookahead/lookbehind; `(?i)` case-insensitivity, classes, anchors, alternation all fine. **Always pair with `kind` or `pattern`** so it doesn't run against every node:
```yaml
rule:
  kind: identifier
  regex: "^MAX_"
```

## Relational rules: inside, has, follows, precedes

```yaml
rule:
  pattern: await $P
  inside:                 # target is a descendant of…
    kind: for_in_statement
    stopBy: end
```

- `inside` — target is within a node matching the sub-rule.
- `has` — target contains a node matching the sub-rule.
- `follows` / `precedes` — target appears after / before a **sibling** (same parent) matching the sub-rule.

**`stopBy`** controls traversal depth:
- `neighbor` (default) — immediate parent/child/adjacent sibling only. Most "why doesn't this match?" cases are a missing `stopBy: end`.
- `end` — exhaustive traversal to the tree boundary.
- a rule object — traverse until a node matches it (boundary is inclusive). E.g. stop an `inside` search at the enclosing function so you don't match across scope boundaries:
```yaml
inside:
  pattern: this.$PROP
  stopBy: {kind: function_declaration}
```

**`field`** constrains the structural role (tree-sitter field) of an immediate child/parent; only valid with `has`/`inside` and default `stopBy: neighbor`:
```yaml
rule:
  kind: pair
  has: {field: key, pattern: prototype}   # 'prototype' as a key, not a value
```
Common fields: `key`/`value`, `name`/`body`, `condition`/`consequence`/`alternative`, `left`/`right`.

Pitfalls:
- Sibling rules operate at statement level. `console.log('x')` matches a `call_expression`, but its siblings are `expression_statement`s — include the trailing `;` in the pattern (`console.log('x');`) so it matches the statement.
- Siblings must share the same parent block.

Metavariables captured in the outer pattern are visible in nested rules — e.g. recursive functions:
```yaml
rule:
  pattern: function $F($$$) { $$$ }
  has: {pattern: $F($$$), stopBy: end}
```

## Composite rules: all, any, not, matches

All conditions in a composite apply to the **same node**.

```yaml
rule:
  any:                              # OR
    - pattern: var $N = $V
    - pattern: let $N = $V
    - pattern: const $N = $V
```

- Sibling keys at the same level AND together implicitly (`pattern:` + `inside:` + `not:` in one rule object).
- Use explicit `all:` when (a) YAML would need duplicate keys (two `pattern`s), or (b) **metavariable capture order matters** — `all` evaluates first-to-last, so capture `$F` in the first entry before referencing it in a later `has`.
- `not` vs `has`+`not` (classic trap):
```yaml
# A: blocks containing NO return statement (absence)
rule: {kind: statement_block, not: {has: {kind: return_statement, stopBy: end}}}
# B: blocks containing anything that isn't a return (almost everything!)
rule: {kind: statement_block, has: {not: {kind: return_statement}, stopBy: end}}
```
For "does not contain X", always wrap: `not: {has: X}`.

## Pattern objects: context, selector, strictness

Some constructs can't parse standalone — class fields, JSON pairs, Go/C call ambiguity. Embed the pattern in compilable context and select the node you want:

```yaml
rule:
  pattern:
    context: class A { $FIELD = $INIT }   # full parseable snippet
    selector: field_definition            # node kind to extract as the real pattern
    strictness: smart                     # optional
```

CLI equivalent: `ast-grep -p 'class A { $F = $I }' --selector field_definition -l js`.

Known cases needing context:
| Construct | Naive parse | Fix |
|---|---|---|
| JS class field `$F = $I` | assignment expression | `context: class A { $F = $I }`, `selector: field_definition` |
| JSON/object pair `"k": $V` | invalid / labeled statement | `context: '{"k": $V}'`, `selector: pair` |
| Go call `fmt.Println($A)` | type conversion | `context: func main() { fmt.Println($A) }`, `selector: call_expression` |
| C call `$F($A)` | macro type specifier | `context: $F($$$);`, `selector: call_expression` |

### Strictness levels

| Level | Ignores | Use for |
|---|---|---|
| `cst` | nothing — every token must match | style/format enforcement |
| `smart` (default) | extra unnamed nodes in target | everyday matching |
| `ast` | all unnamed nodes (punctuation, keywords) both sides | quote-style/trailing-comma/modifier-agnostic matching |
| `relaxed` | unnamed nodes + comments | comment-tolerant matching |
| `signature` | text content entirely | shape-only matching (`foo(bar)` ≡ `baz(qux)`) |
| `template` | node kinds (keeps text + topology) | text across differing syntactic classifications |

CLI: `--strictness ast`. YAML: `strictness:` inside a pattern object.

## Constraints on metavariables

Two-stage model: pattern matches and binds first, then constraints filter bindings.

```yaml
rule:
  pattern: const $NAME = $VALUE
constraints:
  NAME:  {regex: "^[A-Z][A-Z0-9_]*$"}    # key has no $ prefix
  VALUE: {any: [{kind: string}, {kind: number}]}
```

Constraint values are full rule objects (`kind`, `regex`, `pattern`, `all`, `any`, `not`). Example — hardcoded credentials:
```yaml
rule: {pattern: apiKey = $VALUE}
constraints: {VALUE: {kind: string}}
```

## Utility rules (reusable predicates)

Local (same file) via `utils:` + `matches:`:
```yaml
utils:
  is-literal:
    any: [{kind: number}, {kind: string}, {kind: 'true'}, {kind: 'false'}, {kind: 'null'}]
rule:
  kind: array
  has: {matches: is-literal}
```

Global: one rule-shaped file per util in a `utilDirs` directory (see sgconfig below); referenced the same way with `matches:`. Utils may be recursive (a util whose body `matches` itself) — e.g. matching arbitrarily parenthesized numbers.

## Rewriting (fix)

```yaml
rule: {pattern: console.log($$$ARGS)}
fix: logger.log($$$ARGS)
```

- Captures substitute their exact source text; internal formatting is preserved.
- **Name multi-metavariables used in a fix.** `pattern: console.log($$$)` + `fix: logger.log($$$)` emits the literal text `$$$`; use `$$$ARGS` in both (verified on 0.42.2).
- Indentation in multi-line `fix:` templates is relative; ast-grep re-indents to the match site:
```yaml
rule: {pattern: '$B = lambda: $R'}
fix: |
  def $B():
      return $R
```
- ast-grep does string-template substitution — it does not re-validate the result. You are responsible for the replacement being syntactically valid; test with `ast-grep test`.
- Apply via `scan --rule r.yml -i` (interactive) or `-U` (all). For value-rewriting beyond substitution, see `transform:` (substring/replace/convert case) and `rewriters:` in the book — e.g. converting captured names between camelCase/snake_case.

## Project setup: sgconfig.yml

```bash
ast-grep new project     # scaffolds sgconfig.yml, rules/, rule-tests/, utils/
ast-grep new rule NAME   # scaffold a rule + test
```

```yaml
# sgconfig.yml
ruleDirs:    [rules]               # required; recursive .yml discovery
testConfigs: [{testDir: rule-tests}]
utilDirs:    [utils]
languageGlobs: {html: ['*.vue', '*.svelte']}   # map extra extensions to a parser
```

`ast-grep scan` auto-discovers sgconfig.yml upward from cwd; override with `--config path`. Diagnose discovery problems with `ast-grep scan --inspect entity`.

## Testing rules

`rule-tests/<id>-test.yml`:
```yaml
id: no-console        # must match the rule id
valid:                # must NOT match (false positives reported as "Noisy")
  - logger.info('m')
invalid:              # MUST match (misses reported as "Missing")
  - console.log('m')
  - |
    function f() {
      console.log('multi-line case');
    }
```
Run `ast-grep test`. Snapshots (`__snapshots__/`) additionally lock in messages/fixes/highlight ranges; refresh intentionally with `ast-grep test --update-all`. Write the test first, then the rule — cheap TDD for rules.

## JSON output, jq, CI

```bash
ast-grep -p 'PAT' src/ --json            # pretty (also --json=stream | compact)
echo 'code' | ast-grep -p 'PAT' --stdin -l js --json
```

Match object fields: `text`, `range` (line/column + UTF-8 `byteOffset`), `file`, `metaVariables`, and for scan: `ruleId`, `severity`, `message`, `replacement`.

```bash
ast-grep scan --json | jq 'length'                                      # count
ast-grep -p 'console.log($MSG)' src/ --json | jq -r '.[].text'          # matched text
… --json | jq -r '.[].metaVariables.single.NAME.text'                   # captures
ast-grep scan --json | jq 'group_by(.file) | map({file: .[0].file, count: length})'
ast-grep scan --json | jq '[.[] | select(.severity == "error")]'
ast-grep scan --json | jq -r '.[] | [.file, .range.start.line, .ruleId] | @csv'
```

CI gate:
```bash
RESULT=$(ast-grep scan --json=compact)
ERRORS=$(echo "$RESULT" | jq '[.[] | select(.severity == "error")] | length')
[ "$ERRORS" -gt 0 ] && exit 1
```

Pre-commit:
```bash
for FILE in $(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(js|ts)$'); do
  [ "$(ast-grep -p 'debugger' "$FILE" --json | jq 'length')" -gt 0 ] && \
    { echo "debugger statement in $FILE"; exit 1; }
done
```

Non-UTF-8 sources: transcode first — `iconv -f ISO-8859-1 -t utf-8 legacy.js | ast-grep --stdin -l js -p 'PAT'`.

## Debugging quick table

| Symptom | Likely cause | Fix |
|---|---|---|
| Zero matches, pattern looks right | pattern parsed as a different construct | `--debug-query=ast`; add `context`+`selector` |
| Matches in playground, not in CLI | shell double-quoting ate `$VARS` | single-quote the pattern |
| Misses formatting variants | strictness too tight | try `--strictness ast` / `relaxed` |
| Relational rule never fires | default `stopBy: neighbor` | add `stopBy: end` |
| `follows`/`precedes` never fires | matching expression, not statement | include `;` so pattern is statement-level |
| `kind` + `pattern` = zero matches | pattern parses to a different kind | pattern object with `context`/`selector` |
| Too many matches | missing exclusion | add `not:` / `constraints:`; remember `not: {has: …}` for absence |

Playground: https://ast-grep.github.io/playground.html — live AST view of both pattern and target code; the fastest way to learn a language's node kinds and field names.
