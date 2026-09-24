---
name: hdb:rust-dev
description: Develop Rust code efficiently by minimizing compile cycles and batching work
---

# hdb:rust-dev

Develop Rust code with practices that minimize compile-wait time and maximize throughput in AI-assisted workflows.

## Usage

```
/hdb:rust-dev <task description>
```

## Description

Implements Rust code using a batch-first workflow optimized for AI-assisted development. Instead of the naive write-one-file-compile-fix loop, this skill writes internally consistent code across multiple files before triggering a single compile pass, then fixes all errors in one batch. This approach eliminates the dominant time cost in AI-assisted Rust development: waiting for the compiler.

## Instructions

When the user invokes `/hdb:rust-dev <task description>`:

### Phase 1: Understand the task

1. **Read relevant existing code.** Before writing anything, read every file that will be modified or that the new code depends on. Understand the types, traits, module structure, and error handling patterns already in use.

2. **Identify the full scope.** List all files that need to be created or modified. Group them by dependency order:
   - **Leaf modules** — types, models, data structures (no internal dependencies)
   - **Core logic** — algorithms, business logic (depends on leaf modules)
   - **Integration points** — handlers, CLI wiring, tests (depends on core logic)

3. **Verify third-party crate APIs before writing code that uses them.** For any crate you haven't used recently or any unfamiliar feature (template filters, integration crates, macro attributes):
   - Check the docs for your **exact version combination** — e.g., a template engine, a web framework and the crate that bridges them must all agree on versions
   - If an integration crate bridges two dependencies, verify all three versions are compatible before writing any handlers or templates
   - When in doubt, write a minimal standalone example (`examples/smoke.rs`) and `cargo check` it before building on the API

4. **Identify domain-specific constraints and edge cases.** Before writing core logic, document the domain invariants that the compiler cannot check:
   - Sign conventions and ordering of operands in domain formulas
   - Numerical edge cases (division by zero, trig inputs outside valid ranges, limits as values approach zero or infinity)
   - Unit conversions and coordinate systems
   - Business rules or domain constraints that produce **wrong answers** (not compiler errors) when violated

   These domain bugs are invisible to the compiler and typically cost more debugging time than type errors.

### Phase 2: Batch write

5. **Write all code before compiling.** Generate all files in dependency order (leaves first, integration last). Ensure internal consistency across files:
   - Type names, field names, and method signatures match at every call site
   - Imports reference the correct module paths
   - Trait implementations satisfy all required methods
   - Error types propagate consistently through `?` chains
   - Lifetimes and ownership are correct at API boundaries

   **Do not run `cargo check` or `cargo build` between files.** The goal is zero intermediate compilations.

6. **Self-review before compiling.** Before triggering the first compile, scan the generated code for these common issues:

   **Rust-specific:**
   - Missing `use` imports
   - Mismatched `&str` vs `String` at function boundaries
   - `move` closures that should borrow, or borrows that need `clone()`
   - Missing `derive` attributes (Debug, Clone, Serialize, etc.)
   - `async` functions that need `.await` or missing `Send` bounds
   - Public vs private visibility (`pub`, `pub(crate)`)

   **Domain-specific:**
   - Do formulas match the reference specification? (sign conventions, operand order, edge cases)
   - Are trig/math inputs clamped to valid ranges? (e.g., `acos` argument within `[-1, 1]`)
   - Are division-by-zero and degenerate cases handled? (e.g., guard against zero denominators)
   - Do string format specifiers match the template engine's actual syntax? (e.g., Askama filter syntax vs `format!` syntax)

### Phase 3: Compile and fix

7. **Use `cargo check` for the first pass, not `cargo build`.** `cargo check` skips codegen and linking, running 2-3x faster. It catches all type errors, borrow errors, and lifetime issues.

   ```bash
   cargo check 2>&1
   ```

8. **Fix all errors in a single batch.** Read the full compiler output, identify every error, and fix them all before recompiling. Do not fix one error and recompile — that wastes a full compile cycle on partial progress.

   Common batch-fix patterns:
   - If multiple files have the same import error, fix them all at once with parallel edits
   - If a type rename caused errors across 5 files, fix all 5 before recompiling
   - If the borrow checker rejects a pattern, fix the API design (not just the one call site) to prevent cascading errors

9. **Iterate until clean.** Repeat the check-fix cycle. Each cycle should resolve multiple errors. If a cycle fixes only one error, you are being too incremental — look for the root cause.

10. **Run `cargo build` only when `cargo check` is clean** and you need to execute the binary or run tests.

11. **Run `cargo test` to verify correctness.** If tests fail, fix the failures and re-run. Use `cargo test -- --nocapture` when you need to see output from failing tests.

### Phase 4: Validate

12. **Run clippy over every target, with warnings as errors.**

    ```bash
    cargo clippy --all-targets -- -D warnings 2>&1
    ```

    `--all-targets` includes tests, benches and examples, which plain `cargo clippy` skips. `-D warnings` makes a warning block completion instead of scrolling past. Fix the cause; add `#[allow(clippy::...)]` only with a comment saying why the lint is wrong *here*.

13. **Run `cargo fmt --check`** to verify formatting. Apply `cargo fmt` if needed.

## Build Optimization Reference

Apply these project-level optimizations when setting up a new Rust project or when build times become painful:

### Fast linker (macOS Apple Silicon)

Add to `.cargo/config.toml`:

```toml
[target.aarch64-apple-darwin]
rustflags = ["-C", "link-arg=-fuse-ld=/opt/homebrew/bin/ld64.lld"]
```

Requires: `brew install lld`. On macOS the linker must be invoked as `ld64.lld` (not `lld`), which is the Mach-O compatible driver. Using plain `lld` will fail with "Invoke ld64.lld (macOS) instead". Cuts link time 50-80% on incremental builds.

**Keep `lld` in step with Xcode.** `ld64.lld` reads the SDK's `.tbd` library stubs, and a new SDK can use a format an older `lld` rejects. Seen with Xcode 27: LLD 22 failed on every project with `could not load TAPI file … libSystem.tbd: malformed file … unknown architecture arm64e.x1-macos`, followed by hundreds of `undefined symbol` errors (`__error`, `_Unwind_GetIP`) — all consequences of `libSystem` not loading. `brew upgrade lld` (to 23) fixed it. When link errors appear after an Xcode or macOS update:

1. `ld64.lld --version` and `xcrun --show-sdk-version` — suspect the pairing first.
2. `RUSTFLAGS="" cargo build` confirms it: an empty `RUSTFLAGS` overrides the target rustflags, so Apple's `ld` links instead. (It changes the flags, so everything rebuilds.)
3. `brew upgrade lld`, or remove the override until `lld` catches up.

### Compilation caching

```bash
cargo install sccache --locked
```

Then either `export RUSTC_WRAPPER=sccache`, or persist it in `~/.cargo/config.toml` (or a project's `.cargo/config.toml`):

```toml
[build]
rustc-wrapper = "sccache"
```

Once configured, every `rustc` call goes through it — keep it updated with the same `cargo install` command.

Caches compiled crates across builds. Saves time when switching branches, after `cargo clean`, or across projects sharing dependencies.

### Workspace splitting

For projects with independent subsystems, split into a Cargo workspace:

```toml
[workspace]
members = ["core", "web", "cli"]
```

Benefits:
- Independent crates compile in parallel across CPU cores
- Only the changed crate recompiles on incremental builds
- Enforces clean API boundaries between subsystems

Split when: the project has 3+ modules with no circular dependencies and build times exceed 30 seconds.

### Check tests without running them

```bash
cargo check --tests
```

Validates that test code compiles without building the test harness or running tests. Useful during the write phase when you want to verify test code is structurally correct.

### Continuous checking during manual development

```bash
cargo watch -x check
```

Reruns `cargo check` on every file save. Useful when the developer is editing code manually between AI-assisted sessions.

## Release Profile

For production binaries, add this to `Cargo.toml` to produce fast, stripped binaries:

```toml
[profile.release]
codegen-units = 1      # Better optimization, slower compile
debug = false
lto = true
opt-level = 3          # Optimize for speed (the release default)
panic = "abort"        # Don't include unwinding code
strip = true           # Strip symbols from binary
```

**What each setting does:**
- `codegen-units = 1` — Allows LLVM to optimize across the entire crate as one unit. Produces faster/smaller code at the cost of slower release builds. Only affects `cargo build --release`.
- `lto = true` — Link-Time Optimization across all crates. Eliminates dead code and inlines across crate boundaries: faster and smaller. `lto = "thin"` gets most of the speed for much less link time.
- `opt-level = 3` — Optimize for speed. Switch to `"z"` (or `"s"`) **only** when size is the constraint: WASM downloads, embedded targets. `"z"` disables loop vectorization and trims inlining, so CPU-bound code is usually slower — never pick it by default for a CLI or server.
- `panic = "abort"` — Removes unwinding machinery (~10-20% size reduction). Panics terminate immediately. Incompatible with `catch_unwind()` — only use in applications, not libraries.
- `strip = true` — Strips debug symbols and symbol tables from the final binary.

**When to use:** CLI tools, web servers, deployable binaries. Do not apply `panic = "abort"` to library crates that may be used by others.

**Measure, don't assume.** Profile-level choices, `rayon`, and data-structure changes are all performance claims. Time the release binary before and after (`hyperfine`), use `criterion` for hot functions (see `resources/crates.md`), and `cargo flamegraph` (or Instruments on macOS) to find where the time goes before optimizing anything.

## Rust-Specific Patterns

### Error handling

- Use `anyhow::Result` for application code and CLI tools
- Use `thiserror` for library crates that expose typed errors
- Propagate with `?` rather than `.unwrap()` in non-test code
- In tests, `.unwrap()` is acceptable — it produces clear panic messages with line numbers

```toml
anyhow = "1.0"
thiserror = "2"
```

### API design

- **Use enums instead of boolean flags or boolean tuples.** Replace `(bool, bool)` parameter pairs with a named enum. `ScrapeTargets::Both` is self-documenting; `(true, false)` is not.
- **Use `StatusCode` with error responses in web handlers.** Don't return error HTML without a corresponding HTTP status code.

### Ownership at API boundaries

Design function signatures to minimize ownership friction:

- Accept `&str` not `String` when the function doesn't need to store the value
- Accept `impl Into<String>` when the function stores the value and callers might have either `&str` or `String`
- Return owned types (`String`, `Vec<T>`) from functions — let the caller decide to borrow
- Use `Cow<'_, str>` only when profiling shows the clone matters

### Module organization

- **Use `lib.rs` + `main.rs` split for all non-trivial projects.** Put all logic in `lib.rs` (and its submodules); `main.rs` only parses args and calls into the library. This is the single most impactful structural decision: it enables integration tests in `tests/`, which cannot import from a binary crate.
- One `mod.rs` (or `module_name.rs`) per logical subsystem
- Re-export the public API from `mod.rs` so callers use short paths (e.g., `use crate::bemt::design_propeller` not `use crate::bemt::optimizer::design_propeller`)
- Keep `mod.rs` files thin — orchestration and re-exports, not implementation
- Unit tests go in the same file as the code they test (`#[cfg(test)] mod tests`)
- **Integration tests go in `tests/`.** These test the public API through `use your_crate::...`. Use test fixtures (files in `tests/fixtures/`) for data-driven tests. This is only possible with the `lib.rs` split.

### Dependency management

- Pin major versions in `Cargo.toml` (e.g., `serde = "1"` not `serde = "*"`)
- Use `features` sparingly — only enable what you need (e.g., `tokio = { version = "1", features = ["rt-multi-thread", "macros"] }` not `features = ["full"]`)
- Prefer `bundled` feature for C library bindings (e.g., `rusqlite = { features = ["bundled"] }`) to avoid system dependency issues
- Run `cargo update` periodically to pick up patch releases

## Preferred Crates by Domain

When the project has no existing precedent for a dependency, read `resources/crates.md` (in this skill's directory). It lists preferred crates by domain — CLI, web, async, hashing/parallelism, WASM, serialization, TUI, git, benchmarking — with versions checked on a stated date and the traps each one has (e.g. reqwest 0.13 has no `rustls-tls` feature; `serde_yaml` is deprecated; ratatui re-exports `crossterm`). Re-check any version with `cargo search <crate> --limit 1` before adding it.

## Crate Compatibility

When using multiple crates that integrate with each other, verify version compatibility **before** writing application code:

- **Integration crates** (e.g., `tower-http`, `sqlx` with runtime features, template/web-framework glue crates) bridge two or more dependencies. All bridged versions must be compatible. Check the integration crate's `Cargo.toml` for its dependency version requirements.
- **Test compatibility early.** After adding a new integration crate, run `cargo check` on a minimal use before writing handlers or business logic. Discovering incompatibility after writing 500 lines of handler code wastes the entire batch.
- **When an integration crate lags behind its dependencies**, drop it and implement the glue manually. For example, if a template integration crate doesn't support the latest version of your web framework, render templates manually and wrap the output. A few lines of manual glue is better than pinning to an old framework version.
- **Pin integration crate versions explicitly** (e.g., `some_glue = "=0.4.0"`) when you need a specific compatible combination, to prevent `cargo update` from breaking it.

## Testing Strategies

### Golden-value tests for numerical and domain code

For code that computes numerical results (solvers, financial calculations, data transformations), compile-time correctness is necessary but not sufficient — the code can compile and produce wrong answers. Use golden-value tests:

1. **Obtain reference values** from a known-good source (published tables, reference implementation, manual calculation)
2. **Create test fixtures** with input data and expected outputs
3. **Assert with tolerances** — use approximate comparison for floating-point results:
   ```rust
   assert!((result - expected).abs() < 1e-6, "expected {expected}, got {result}");
   ```
4. **Test edge cases explicitly** — zero inputs, boundary values, degenerate cases that are valid but extreme

### Integration tests with fixtures

For code that processes external data (HTML, files, API responses):

1. **Store representative fixtures** in `tests/fixtures/` — real-world examples, not hand-crafted minimal inputs
2. **Test the public API end-to-end** — parse, transform, and verify the output in a single test
3. **Include malformed inputs** — test that bad data produces clear errors, not panics

### Web application state

Prefer simpler state patterns that avoid ownership complexity:

- **Pass configuration (not connections) in web state.** For example, store a database path as a `String` and open a connection per request, rather than sharing `Arc<Mutex<Connection>>` across handlers. This eliminates lock contention and simplifies ownership.
- Use `Arc<T>` for truly shared read-only state (config, compiled templates, static data)
- Use per-request resources for anything with mutable state or cleanup requirements

## Guidelines

- **Batch over incremental.** The single most impactful practice is writing more code before compiling. Each compile cycle costs 10-30 seconds; eliminating 10 unnecessary cycles saves 2-5 minutes per task.
- **Read before writing.** Never modify a file you haven't read. The compiler errors from misunderstanding existing types cost more time than reading the file would have.
- **Fix root causes, not symptoms.** If the borrow checker rejects a pattern in 3 places, the API design is wrong — fix the signature, not the call sites.
- **Keep the dependency tree shallow.** Every new crate dependency adds compile time. Check if the standard library or an existing dependency already provides the functionality.
- **Use the type system, don't fight it.** If you're writing a lot of `.clone()`, `Rc`, or `unsafe`, step back and reconsider the data ownership model.
- **Verify crate APIs before committing to them.** The cost of discovering an API mismatch after writing 10 handlers is far higher than testing one minimal example first. This applies especially to template engines, integration crates, and anything with macro-based DSLs.
- **Domain bugs cost more than type bugs.** The compiler catches type errors, borrow errors, and lifetime issues. It cannot catch wrong formulas, incorrect sign conventions, or numerical edge cases. Invest verification effort proportional to the risk: domain-critical code needs golden-value tests, not just `cargo check`.
- **Split `lib.rs` from `main.rs` by default.** This is a one-time structural decision that enables integration testing, benchmarking, and reuse. Do it at project creation, not as a refactor later.
- **Respect the user's CLAUDE.md.** The user's global instructions override defaults. Check for project-specific conventions before applying generic Rust patterns.

## Other
- Some AI LLMs suggest changing the Rust edition in Cargo.toml to 2021 from 2024. Their reasoning is mistaken: they are not up to date.The latest Rust edition is 2024 and Cargo.toml files with this should not be changed.
