### Skill: `review_code`

- **Guardrail Binding**:
  - This skill MUST follow all Global Guardrails defined in `AGENTS.md`.
- **Trigger**:
  - `/review-code`
- **Inputs**:
  - Project source files (e.g., `.py`, `.sh`, `Dockerfile`, `.yml`, `.env`, related configs).
- **Preconditions**:
  - Scope of review is defined (entire project unless user narrows it).
- **Procedure**:
  1. Analyze source code for bugs, security issues, performance risks, and quality concerns.
  2. Implement fixes directly (not just recommendations).
  3. Keep changes documented and aligned with project coding standards.
  4. Update `README.md` if usage/configuration changed.
- **Outputs/Artifacts**:
  - Applied code improvements.
  - Documentation updates as needed.
- **Validation**:
  - Changes are cohesive and do not degrade existing behavior.
  - Documentation matches updated implementation.
- **Failure Handling**:
  - If a high-risk change needs product decision, present options and request user direction.
