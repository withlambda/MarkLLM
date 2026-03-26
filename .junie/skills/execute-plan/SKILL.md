---
name: execute-plan
description: Consecutively executes all tasks that belong to a feature plan, validates outcomes, and records implementation results.
---

# Execute Plan

Use this skill when the user requests `/execute-plan <feature-name>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `feature-name`

## Preconditions

- Task files (e.g., `plans/<feature-name>/01-task-name.md`) and `requirements.md` exist.
- Check for `plans/<feature-name>/IMPLEMENTED.md`.

## Procedure

1. If `IMPLEMENTED.md` exists, inform user and abort execution.
2. Execute all tasks belonging to the plan consecutively, in the order of their numbering.
3. For each task, perform implementation and run task-level tests as specified.
4. After the last task is executed:
   - Run the full test suite.
   - Create `IMPLEMENTED.md` with implementation summary, modified file list, and deviations.
   - Update `README.md` when behavior/configuration changed.

## Outputs/Artifacts

- Code/test/doc updates.
- `plans/<feature-name>/IMPLEMENTED.md`.

## Validation

- Full suite passes.
- Success criteria in `requirements.md` are satisfied.
- Final implementation is consistent with design or documented deviations.

## Failure Handling

- On blocker, pause and report root cause, impact, and proposed resolution path.
