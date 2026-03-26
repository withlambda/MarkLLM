---
name: execute-task
description: Executes a single task from a feature plan, validates outcomes, and creates IMPLEMENTED.md if it's the last task.
---

# Execute Task

Use this skill when the user requests `/execute-task <task-file-name>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `task-file-name`: The file name of the task (e.g., `01-task-name.md`). It is assumed to be located in the current or relevant plan directory.

## Preconditions

- The task file exists.
- `requirements.md` in the same plan directory exists.
- Dependencies listed in the task file have been executed (if applicable).

## Procedure

1. Read the task file to understand the task description, ordering, dependencies, and test requirements.
2. Verify that dependencies are already implemented (e.g., by checking codebase or previous `IMPLEMENTED.md` if any).
3. Execute the implementation steps defined in the task file.
4. Implement and run task-level tests as specified.
5. If the task is the last one in the plan (based on ordering numbers of all task files in the plan directory):
   - Run the full test suite after implementation.
   - Create `IMPLEMENTED.md` in the plan directory with:
     - Implementation summary
     - New/modified file list
     - Deviations and rationale
   - Update `README.md` when behavior/configuration changed.
6. Report the task execution results.

## Outputs/Artifacts

- Code/test/doc updates.
- `plans/<feature-name>/IMPLEMENTED.md` (only if the last task).

## Validation

- Task-level tests pass.
- If it's the last task, the full suite passes.
- Success criteria in `requirements.md` for this task are satisfied.

## Failure Handling

- On blocker, pause and report root cause, impact, and proposed resolution path.
- If dependencies are not met, notify the user.
