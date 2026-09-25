# ${task_id}: ${title}

## Goal

${goal}

## Assigned Model

${model_name}

## Depends On

${depends_on}

## Scope

Allowed files:

${allowed}

Do not modify:

${forbidden}

## Contract

<!-- Paste or link the exact types, routes, schemas, and error behavior this task must honor.
     Workers follow this verbatim; they do not design it. -->

## Requirements

- <!-- behavior the change must have -->

## Acceptance Criteria

- <!-- observable, testable outcomes -->

## Verification

Run:

```bash
${verify}
```

## Handoff Format

Write the handoff to `${handoff_path}` using `templates/HANDOFF.md`. Return:

- Summary of implementation
- Files changed
- Commands run and results
- Tests added or changed
- Known limitations or questions
- Commit SHA
