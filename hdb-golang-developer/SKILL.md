---
name: hdb:go-dev
description: Develop Go code rapidly and correctly using proven patterns from production projects
---

# hdb:go-dev

Develop Go code that compiles and passes tests on the first attempt, using patterns proven in production Go projects.

## Usage

```
/hdb:go-dev <task description>
```

## Description

Implements Go code using a workflow optimized for correctness-on-first-compile. Go's fast compiler makes the edit-compile-test cycle cheap, but avoidable failures still waste time. This skill front-loads the decisions that cause first-attempt failures: interface satisfaction, nil handling, error propagation, concurrency safety, and test isolation. The goal is green on the first `go test`.

## Instructions

When the user invokes `/hdb:go-dev <task description>`:

### Phase 1: Understand the task and codebase

1. **Read the project's CLAUDE.md** if it exists. It contains project-specific rules that override all defaults in this skill.

2. **Identify the project's conventions** by reading:
   - `go.mod` — Go version, module path, existing dependencies
   - `Makefile` — build targets, build tags, LDFLAGS
   - One representative test file — test style (table-driven, subtests, helpers)
   - One representative handler/command — error handling, logging, context usage

3. **Map the change.** List:
   - Files to create or modify
   - Interfaces that must be satisfied
   - Functions that will be called from existing code
   - Test files to create or modify

### Phase 2: Write code

4. **Write types and interfaces first.** Define all structs, interfaces, and type aliases before writing any logic. This prevents cascading signature mismatches.

5. **Write implementation second.** Follow these rules to get it right the first time:

   **Error handling — always wrap with context:**
   ```go
   return fmt.Errorf("load config: %w", err)
   ```
   Never use bare `return err`. Every error site must add context describing what operation failed. This makes debugging possible without a stack trace.

   **Resource cleanup — defer immediately after acquisition:**
   ```go
   f, err := os.Open(path)
   if err != nil {
       return fmt.Errorf("open %s: %w", path, err)
   }
   defer f.Close()
   ```
   Never separate acquisition from defer. If there's logic between them, a future edit will introduce a leak.

   **Nil safety — check interfaces and pointers at boundaries:**
   ```go
   func (s *Server) Start() error {
       if s.db == nil {
           return errors.New("server: database not initialized")
       }
       // ...
   }
   ```
   Check nil at public API boundaries (exported methods, constructors). Trust nil-safety within a package's private methods.

   **Context propagation — accept and pass context everywhere:**
   ```go
   func (s *Store) GetUser(ctx context.Context, id int64) (*User, error) {
       row := s.db.QueryRowContext(ctx, "SELECT ...", id)
       // ...
   }
   ```
   Every function that does I/O, calls an external service, or could block must accept `context.Context` as its first parameter.

   **Concurrency — protect shared state with the narrowest tool:**
   - `sync.Mutex` for simple shared state
   - `sync.RWMutex` when reads far outnumber writes
   - `atomic.Value` / `atomic.Int64` for single values
   - Channels for coordination between goroutines
   - Never hold a mutex across I/O or blocking calls

   **Goroutine lifecycle — always ensure goroutines can exit:**
   ```go
   go func() {
       for {
           select {
           case <-ctx.Done():
               return
           case job := <-ch:
               process(job)
           }
       }
   }()
   ```
   Every goroutine must have a termination path via context cancellation or channel close. Goroutine leaks are silent and cumulative.

6. **Write tests third.** Follow the project's existing test style. When no precedent exists, use these patterns:

   **Table-driven tests with subtests:**
   ```go
   func TestParseQuery(t *testing.T) {
       tests := []struct {
           name  string
           input string
           want  Query
       }{
           {name: "empty", input: "", want: Query{}},
           {name: "from operator", input: "from:alice", want: Query{From: "alice"}},
       }
       for _, tt := range tests {
           t.Run(tt.name, func(t *testing.T) {
               got := ParseQuery(tt.input)
               if diff := cmp.Diff(tt.want, got); diff != "" {
                   t.Errorf("ParseQuery(%q) mismatch (-want +got):\n%s", tt.input, diff)
               }
           })
       }
   }
   ```

   **Test isolation with `t.TempDir()`:**
   ```go
   func TestStoreOpen(t *testing.T) {
       dbPath := filepath.Join(t.TempDir(), "test.db")
       s, err := store.Open(dbPath)
       if err != nil {
           t.Fatalf("Open: %v", err)
       }
       defer s.Close()
       // ...
   }
   ```
   Never use fixed paths or shared temp directories. Every test gets its own `t.TempDir()`.

   **HTTP tests with `httptest`:**
   ```go
   func TestHealthEndpoint(t *testing.T) {
       srv := httptest.NewServer(handler)
       defer srv.Close()

       resp, err := http.Get(srv.URL + "/api/health")
       if err != nil {
           t.Fatalf("GET /api/health: %v", err)
       }
       defer resp.Body.Close()

       if resp.StatusCode != http.StatusOK {
           t.Errorf("status = %d, want 200", resp.StatusCode)
       }
   }
   ```

   **Mock external binaries for CLI tests:**
   ```go
   func TestAgentInvocation(t *testing.T) {
       testutil.MockBinaryInPath(t, "claude", `#!/bin/sh
   echo '{"result": "ok"}'`)
       // test code that shells out to "claude"
   }
   ```

   **Test helpers get `t.Helper()`:**
   ```go
   func openTestDB(t *testing.T) *Store {
       t.Helper()
       dbPath := filepath.Join(t.TempDir(), "test.db")
       s, err := Open(dbPath)
       if err != nil {
           t.Fatalf("openTestDB: %v", err)
       }
       t.Cleanup(func() { s.Close() })
       return s
   }
   ```
   Always call `t.Helper()` first. Always use `t.Cleanup()` instead of relying on the caller to defer.

### Phase 3: Verify

7. **Run the verification sequence.** Execute these in order, fixing issues between each step:

   ```bash
   go build ./...          # Catch compilation errors
   go vet ./...            # Catch common mistakes (printf args, unreachable code, etc.)
   go test ./...           # Run all tests
   ```

   If the project uses build tags (e.g., `fts5`), include them:
   ```bash
   go test -tags fts5 ./...
   ```

8. **Run the formatter.** Format is non-negotiable in Go:
   ```bash
   go fmt ./...
   ```
   Stage any formatting changes. Formatting-only changes are still changes.

9. **Run the linter** if `golangci-lint` is available:
   ```bash
   golangci-lint run ./...
   ```

## Project Infrastructure Setup

When starting a new Go project or adding infrastructure to an existing one, apply these patterns:

### Module initialization

```bash
go mod init github.com/user/project
```

Use the full GitHub path even for private projects. It prevents import conflicts if the module is ever referenced externally.

### Directory layout

```
project/
├── cmd/projectname/       # CLI entry point
│   ├── main.go            # Cobra root command, signal handling
│   └── cmd/               # Subcommands (one file per command)
├── internal/              # All application packages
│   ├── config/            # TOML config loading
│   ├── store/             # Database access (SQLite, Postgres)
│   ├── testutil/          # Shared test helpers, builders, fixtures
│   └── ...                # Domain packages
├── Makefile               # Build, test, lint, install targets
├── go.mod
├── CLAUDE.md              # Project-specific AI development rules
└── .githooks/pre-commit   # Format + lint check
```

**Rules:**
- Everything except `cmd/` and `main.go` goes in `internal/`. This prevents external imports of unstable code.
- One primary type per file. `broadcaster.go` contains `EventBroadcaster` and its helpers, not unrelated types.
- Test files live next to the code they test (`store.go` + `store_test.go`).
- `testutil/` is a shared package for test helpers, builders, and fixtures used across multiple packages.

### Makefile

```makefile
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT  ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE    ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
LDFLAGS  = -ldflags "-X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.date=$(DATE)"

.PHONY: build install test lint fmt vet clean

build:
	go build $(LDFLAGS) -o bin/projectname ./cmd/projectname

install:
	go install $(LDFLAGS) ./cmd/projectname

test:
	go test ./...

lint:
	golangci-lint run ./...

fmt:
	go fmt ./...

vet:
	go vet ./...

clean:
	rm -rf bin/
```

### Pre-commit hook

```bash
#!/bin/sh
# .githooks/pre-commit

# Check formatting
UNFORMATTED=$(gofmt -l .)
if [ -n "$UNFORMATTED" ]; then
    echo "Files need formatting:"
    echo "$UNFORMATTED"
    exit 1
fi

# Run vet
go vet ./...
```

Enable with:
```bash
git config core.hooksPath .githooks
```

### Database schema embedding

```go
import "embed"

//go:embed schema.sql
var schemaSQL string

func (s *Store) initSchema() error {
    _, err := s.db.Exec(schemaSQL)
    return err
}
```

Embed SQL schemas in the binary. Never load schema files from the filesystem at runtime — it breaks when the binary runs from a different directory.

### Configuration pattern

```go
type Config struct {
    DataDir    string `toml:"data_dir"`
    ServerAddr string `toml:"server_addr"`
    MaxWorkers int    `toml:"max_workers"`
}

func DefaultConfig() *Config {
    return &Config{
        ServerAddr: "127.0.0.1:8080",
        MaxWorkers: 4,
    }
}

func Load(path string) (*Config, error) {
    cfg := DefaultConfig()
    if _, err := toml.DecodeFile(path, cfg); err != nil {
        return nil, fmt.Errorf("load config %s: %w", path, err)
    }
    return cfg, nil
}
```

Always provide `DefaultConfig()` so the application works without a config file. Load overlays the file on top of defaults.

### CLI entry point

```go
func main() {
    ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer cancel()

    if err := rootCmd.ExecuteContext(ctx); err != nil {
        os.Exit(1)
    }
}
```

Trap signals at the top. Pass context through Cobra into all subcommands. Never call `os.Exit()` from inside a subcommand — return an error and let `main()` exit.

## Go Problem Areas to Avoid

These are the patterns that most frequently cause first-attempt failures or production bugs:

### 1. Interface pollution

**Wrong:** Define an interface with 10 methods that mirrors the concrete type.
**Right:** Define the smallest interface the caller needs.

```go
// Wrong: mirrors the concrete Store
type Database interface {
    Open() error
    Close() error
    GetUser(ctx context.Context, id int64) (*User, error)
    ListUsers(ctx context.Context) ([]User, error)
    InsertUser(ctx context.Context, u *User) error
    DeleteUser(ctx context.Context, id int64) error
    // ... 15 more methods
}

// Right: the handler only needs two methods
type UserGetter interface {
    GetUser(ctx context.Context, id int64) (*User, error)
}
```

Define interfaces where they're consumed (in the caller's package), not where they're implemented. This prevents import cycles and keeps interfaces small.

### 2. Goroutine leaks

**Wrong:**
```go
go func() {
    for msg := range ch {
        process(msg)
    }
}()
// ch is never closed, goroutine lives forever
```

**Right:**
```go
go func() {
    for {
        select {
        case <-ctx.Done():
            return
        case msg, ok := <-ch:
            if !ok {
                return
            }
            process(msg)
        }
    }
}()
```

Every goroutine must exit when its parent context cancels. Test this by calling `cancel()` in tests and verifying the goroutine returns.

### 3. Race conditions in tests

**Wrong:** Tests mutate package-level variables without synchronization.
**Right:**
- Use `t.Setenv()` for environment variables (automatically marks test as non-parallel)
- Use `t.TempDir()` for file-based isolation
- Avoid `t.Parallel()` when tests share mutable state
- Run CI with `-race` to catch data races: `go test -race ./...`

### 4. Nil map/slice panics

**Wrong:**
```go
type Config struct {
    Labels map[string]string
}
// c.Labels["key"] = "value"  // panic if Labels is nil
```

**Right:**
```go
func NewConfig() *Config {
    return &Config{
        Labels: make(map[string]string),
    }
}
```

Always initialize maps in constructors. Nil slices are safe to append to, but nil maps panic on write.

### 5. Forgetting to check `rows.Err()`

**Wrong:**
```go
rows, _ := db.Query("SELECT ...")
for rows.Next() {
    // ...
}
// Missing: rows.Err() check
```

**Right:**
```go
rows, err := db.Query("SELECT ...")
if err != nil {
    return fmt.Errorf("query users: %w", err)
}
defer rows.Close()
for rows.Next() {
    if err := rows.Scan(&u.ID, &u.Name); err != nil {
        return fmt.Errorf("scan user: %w", err)
    }
    users = append(users, u)
}
if err := rows.Err(); err != nil {
    return fmt.Errorf("iterate users: %w", err)
}
```

`rows.Next()` can stop due to an error, not just end of results. Always check `rows.Err()` after the loop.

### 6. Import cycles

Go forbids circular imports. When package A needs a type from package B and vice versa:
- Extract the shared type into a third package (often `internal/types` or the consuming package defines an interface)
- Define an interface in the consuming package that the other package's concrete type satisfies
- Never restructure to use `interface{}` or `any` to dodge the cycle

### 7. Closing HTTP response bodies

**Wrong:**
```go
resp, err := http.Get(url)
if err != nil {
    return err
}
// forgot resp.Body.Close()
```

**Right:**
```go
resp, err := http.Get(url)
if err != nil {
    return fmt.Errorf("GET %s: %w", url, err)
}
defer resp.Body.Close()
```

Always `defer resp.Body.Close()` immediately after checking the error. Leaking HTTP response bodies exhausts connection pools.

### 8. SQL `NULL` handling

**Wrong:**
```go
var name string
row.Scan(&name)  // panics or empty string if NULL
```

**Right:**
```go
var name sql.NullString
row.Scan(&name)
if name.Valid {
    user.Name = name.String
}
```

Use `sql.NullString`, `sql.NullInt64`, etc. for nullable columns. Or use pointer types (`*string`) with appropriate scan targets.

## Dependency Preferences

When the project has no precedent for a choice, prefer these well-tested libraries:

| Need | Library | Why |
|------|---------|-----|
| CLI framework | `spf13/cobra` | Standard, subcommand support, flag binding |
| Config files | `BurntSushi/toml` | Simple, Go-native, no tags required for basic use |
| HTTP router | `go-chi/chi/v5` | stdlib-compatible, middleware, lightweight |
| Logging | `log/slog` (stdlib) | Structured, zero dependencies, sufficient for most apps |
| Test comparisons | `google/go-cmp` | Deep equality with diff output, handles unexported fields |
| UUIDs | `google/uuid` | Standard, well-maintained |
| SQLite | `mattn/go-sqlite3` (CGO) or `modernc.org/sqlite` (pure Go) | Both mature; pure Go avoids CGO pain on cross-compile |
| TUI | `charmbracelet/bubbletea` | Elm architecture, composable, well-maintained |

**Avoid adding dependencies for:**
- HTTP clients (use `net/http`)
- JSON handling (use `encoding/json`)
- String manipulation (use `strings`, `strconv`)
- File I/O (use `os`, `io`, `path/filepath`)
- Regex (use `regexp`)
- Time (use `time`)

The Go stdlib is unusually capable. Every external dependency adds compile time, supply chain risk, and upgrade burden.

## Guidelines

- **Green on first `go test`.** Front-load type correctness and interface satisfaction. The Go compiler is fast — use it as a feedback tool, not a crutch.
- **Read before writing.** Read every file that will be modified and every interface that must be satisfied. Misunderstanding an existing signature wastes a full edit-compile-fix cycle.
- **Error messages are for humans.** `"query users: %w"` tells you what failed. `"%w"` alone tells you nothing. Every `fmt.Errorf` must add context.
- **Tests are isolated.** `t.TempDir()`, `t.Setenv()`, `t.Cleanup()`. No shared state between tests. No test depends on another test running first.
- **Interfaces are small.** 1-3 methods. Defined where consumed, not where implemented. If an interface has more than 5 methods, it's probably a concrete type in disguise.
- **Concurrency is explicit.** Every goroutine has a cancellation path. Every shared variable has a documented synchronization mechanism. Prefer channels for coordination, mutexes for protection.
- **Dependencies are earned.** Check if the stdlib solves the problem before adding a dependency. `net/http`, `encoding/json`, `log/slog`, `database/sql` cover most needs.
- **Format before commit.** `go fmt ./...` then `go vet ./...`. Always. Stage formatting changes alongside logic changes.
- **Respect CLAUDE.md.** The project's instructions override everything in this skill. Read it first.
