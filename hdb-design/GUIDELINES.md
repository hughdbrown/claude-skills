## Guidelines
      
- **Ground decisions in the codebase.** Match the project's existing patterns, tools, and conventions. Do not
introduce new frameworks, languages, or paradigms without strong justification.
- **Keep stages small and incremental.** Each stage should touch no more than ~5 files, add clear demonstrable
value, and leave the system in a working state.
- **Be specific in tasks.** "Add error handling" is too vague. "Add an error return to `ProcessFile()` in
`internal/worker/process.go` and propagate it through `RunJob()` to the caller" is actionable.
- **Flag risks and open questions.** If a decision has meaningful trade-offs, present the options with pros and cons
and let the developer choose.
- **Do not over-scope.** The feature description is the scope. Do not introduce tangential improvements, refactors,
or "nice to haves" unless the developer asks for them.
- **Respect the project's complexity budget.** A simple feature gets a simple design. Do not add abstractions,
extension points, or configurability beyond what is needed now.
- **Spike when uncertain.** If a technical decision depends on behavior you can't determine from reading code (e.g.,
 "will SQLite handle 1000 concurrent webhook deliveries?"), recommend a time-boxed spike before finalizing the
design. The spike is a task in a preliminary stage, and the PRD notes which decisions depend on its results.
- **Tests are the specification, code is the implementation.** During implementation, treat tests as the authority
on what the code should do. If a test and the PRD disagree, the test is wrong — fix the test first, then fix the
code. Never make a test pass by weakening its assertions.

