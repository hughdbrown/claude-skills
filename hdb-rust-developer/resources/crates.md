# Preferred Crates by Domain

Load this only when a project needs a dependency it has no precedent for. An
existing project's `Cargo.toml` always wins over this list.

Versions were checked against crates.io on 2026-09-23. Before adding one, run
`cargo search <crate> --limit 1` — this file goes stale, and a minor-version
bump on a 0.x crate is a breaking change.

Every crate added costs compile time and is one more thing to upgrade. Check
the standard library and the existing dependency tree first.

## Command-line utilities

```toml
clap = { version = "4.6", features = ["derive"] }    # Argument parsing with derive macros
dirs = "7"                                            # Platform-standard directories (~/.config, etc.)
glob = "0.3"                                          # File path glob matching
regex = "1.13"                                        # Regular expressions
```

- `clap` with `derive` for declarative argument definitions. Avoid hand-parsing `std::env::args`. Use `value_enum` for closed sets of choices so clap rejects bad input and the code gets an enum, not a string.
- `dirs` for config/data/cache directories. Never hardcode `~/.config` — it differs on macOS and Windows.
- `glob` for file pattern matching (e.g., `"src/**/*.rs"`).
- `regex` compiles patterns to automata. Compile once (`std::sync::LazyLock<Regex>`), never inside a loop. Use `RegexSet` for many patterns. Reach for it only when `str` methods (`split_once`, `strip_prefix`, `find`) cannot do the job.

## Web applications

```toml
axum = "0.8"                                              # Web framework (async, tower-based)
tokio = { version = "1.53", features = ["rt-multi-thread", "macros", "net"] }
tower-http = { version = "0.7", features = ["fs"] }       # HTTP middleware (static files, CORS, etc.)
reqwest = "0.13"                                          # HTTP client; rustls is the default TLS
askama = "0.16"                                           # Compile-time HTML templates
```

- **reqwest 0.13 has no `rustls-tls` feature.** rustls is now the default (`default-tls = [rustls]`). Copying `features = ["rustls-tls"]` from older code fails to resolve. Use `native-tls` only when the platform trust store is required.
- **Avoid template/framework integration crates that lag behind framework releases.** Render the template yourself and wrap the output:
  ```rust
  let html = template.render().context("rendering index")?;
  Ok(Html(html))
  ```
  This avoids version coupling between the template engine and the web framework.

## Asynchronous operation

```toml
tokio = { version = "1.53", features = ["rt-multi-thread", "macros"] }
```

- Enable only the features used (`time`, `sync`, `fs`, `net`, `process`, `signal` as needed). `features = ["full"]` is acceptable for a throwaway binary, never for a library.
- `tokio::spawn` for concurrent tasks, `tokio::select!` for racing futures, `JoinSet` to await a group.
- Prefer `std::sync::Mutex` for short critical sections. Use `tokio::sync::Mutex` only when the guard must be held across an `.await`.
- CPU-bound work does not belong on the async runtime. Move it to `tokio::task::spawn_blocking`; for data-parallel work, run rayon inside `spawn_blocking` (or send the result back over a `tokio::sync::oneshot`). Never call rayon's blocking APIs directly from an async task.

## System code with hashing and parallel execution

```toml
blake3 = { version = "1.8", features = ["rayon"] }    # Fast cryptographic hashing (SIMD-accelerated)
rayon = "1.12"                                         # Data parallelism (parallel iterators)
memmap2 = "0.9"                                        # Memory-mapped file I/O
```

- `blake3` with `rayon` hashes large inputs on multiple threads (`Hasher::update_rayon`). Only worth it above roughly 128 KiB; below that, single-threaded `update` is faster.
- `rayon` turns `.iter()` into `.par_iter()` for CPU-bound work over collections. Measure first — for small collections the scheduling cost exceeds the gain.
- `memmap2` gives zero-copy access to large files, but **`Mmap::map` is `unsafe`**: if another process truncates or rewrites the file while it is mapped, reads are undefined behaviour (typically `SIGBUS`). Confine it to one function with a `// SAFETY:` comment stating the assumption. For files that fit in memory, `std::fs::read` is simpler and safe.

## WASM (WebAssembly)

```toml
yew = { version = "0.23", features = ["csr"] }        # Component framework (React-like)
patternfly-yew = "0.8"                                 # PatternFly 5 UI components for Yew
```

- `yew` with `csr` (client-side rendering) for browser-targeted WASM applications.
- `patternfly-yew` provides pre-built UI components (tables, forms, navigation) following the PatternFly design system. Check its required `yew` version before upgrading either.
- Build with `trunk serve` for development, `trunk build --release` for production. For WASM, `opt-level = "z"` in the release profile *is* the right choice — download size dominates.

## Serialization and deserialization

```toml
serde = { version = "1", features = ["derive"] }       # Serialization framework
serde_json = "1"                                        # JSON
toml = "1"                                              # TOML (config files)
csv = "1.4"                                             # CSV reading/writing
chrono = { version = "0.4", features = ["serde"] }      # DateTime with serde support
```

- Always enable `serde`'s `derive` feature.
- Deserialize straight into typed structs and enums, not `serde_json::Value`. Use `#[serde(rename_all = "...")]`, `#[serde(default)]` and `#[serde(deny_unknown_fields)]` for config files so a typo is an error, not a silently ignored key.
- Borrow on deserialize where the input outlives the value: `#[serde(borrow)] name: &'a str` or `Cow<'a, str>` avoids an allocation per field.
- **YAML: `serde_yaml` is deprecated** (published as `0.9.34+deprecated`). For new code use `serde_yaml_ng` (0.10) or `serde_norway` (0.9); prefer TOML or JSON when the format is yours to choose.
- `chrono::DateTime<Utc>` as the standard timestamp type; convert to local time only for display.

## Terminal / TUI applications

```toml
ratatui = "0.30"                                        # TUI framework (widgets, layout, rendering)
```

- Do not add `crossterm` as a separate dependency. ratatui re-exports it as `ratatui::crossterm`, which guarantees the versions match; a second, different `crossterm` in the tree compiles but its events and types do not interoperate.
- Start with `let terminal = ratatui::init();` and end with `ratatui::restore();`. `init` enables raw mode and the alternate screen **and installs a panic hook that restores the terminal** — no hand-written `std::panic::set_hook` needed.

## Git operations

```toml
git2 = "0.21"                                           # libgit2 bindings
```

- `git2` provides full git operations (clone, commit, diff, log, blame) without shelling out to `git`.
- Bundles `libgit2` via `libgit2-sys` unless a matching system library is found through `pkg-config`.
- For simple operations (status, add, commit), shelling out to `git` via `std::process::Command` is simpler and avoids the compile-time cost of `git2`.

## Benchmarking

```toml
[dev-dependencies]
criterion = "0.8"                                       # Statistics-driven micro-benchmarks
```

- Put benchmarks in `benches/`, with `[[bench]] name = "..." harness = false` in `Cargo.toml`. Requires the `lib.rs` split — benches, like integration tests, cannot import from a binary crate.
- For whole-program timing, `hyperfine 'target/release/app args'` needs no code at all.
