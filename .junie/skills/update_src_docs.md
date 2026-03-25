### Skill: `update_src_docs`

- **Guardrail Binding**:
  - This skill MUST follow all Global Guardrails defined in `AGENTS.md`.
- **Trigger**:
  - `/update-src-docs`
- **Inputs**:
  - All relevant source files and existing inline documentation.
- **Preconditions**:
  - Determine where implementation and documentation diverge.
- **Procedure**:
  1. Compare current implementation with existing docs.
  2. Update outdated docstrings/comments to reflect real behavior and signatures.
- **Outputs/Artifacts**:
  - Source files with synchronized documentation.
- **Validation**:
  - No stale or contradictory inline documentation remains in touched areas.
- **Failure Handling**:
  - If undocumented behavior appears unintended, flag it and ask whether code or docs should be authoritative.
