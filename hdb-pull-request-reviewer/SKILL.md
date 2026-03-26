# /roborev:pull-request-reviewer

Pre-review a pull request to anticipate problems and shorten the review cycle.

## Usage

```
/roborev:pull-request-reviewer [pr_number_or_branch]
```

## Description

Analyzes a pull request (or the current branch's diff against main) before formal review. Runs automated checks, inspects the diff for common problem areas derived from historical review patterns, and generates a structured pre-review report with blocking issues, likely findings, and suggestions.

The goal is to catch problems that would fail review _before_ submitting, reducing round-trips.

## Instructions

When the user invokes `/roborev:pull-request-reviewer [pr_number_or_branch]`:

1. **Determine the target**: PR number via `gh pr view`, or current branch diff against `main`

2. **Gather the diff**: Full diff, changed file list, and commit log

3. **Run automated checks**: `go build`, `go vet`, `go test`, `gofmt`

4. **Analyze for common problem areas**:
   - **Security**: Prompt injection in agentic prompts, auth/authz gaps on new endpoints, command injection, unbounded input
   - **Concurrency**: Data races, file descriptor races, context/channel misuse
   - **Error handling**: Unchecked return values, partial failure corruption, missing error context
   - **Test quality**: Coverage gaps, flaky patterns, test isolation
   - **Scope**: Unrelated changes mixed in, large files not split, commit hygiene
   - **Go idioms**: Format/vet compliance, deprecated patterns, style consistency
   - **Dependencies**: Unjustified external deps, version consistency, build tags

5. **Check the PR description**: Verify Summary, Test Plan, and issue references

6. **Present the report**: Blocking issues, likely findings, suggestions, check results

7. **Offer to fix**: If blocking issues found, offer to fix them and re-run tests

## Example

User: `/roborev:pull-request-reviewer`

Agent:
1. Detects current branch, computes diff against `main`
2. Runs `go build`, `go vet`, `go test` -- all pass
3. Finds 2 issues: missing error-path test (medium), unformatted file (low)
4. Reports: "Pre-review found 2 items. Would you like me to fix them before you submit the PR?"
