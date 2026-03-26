# Plan Review: language-aware-image-descriptions

**Reviewed**: 2026-03-26
**Artifacts reviewed**: requirements.md, design.md, tasks.md
**Cross-referenced against**: handler.py, vllm_worker.py, settings.py, existing tests

---

## Overall Assessment

The plan is well-structured with clear functional/non-functional requirements, a sound high-level design, and logically ordered tasks with traceability. However, several gaps, ambiguities, and feasibility risks need to be addressed before implementation can proceed smoothly.

---

## Critical Issues

### C1 — Language detection approach is uncommitted (design.md §3, tasks.md T1)

The design mentions two options — a dedicated library vs. heuristic/stdlib-only inference — but does not commit to either. This is a blocker for T1 because:
- A library choice (e.g., `langdetect`, `lingua-language-detector`) requires a `requirements.txt` update and adds a dependency with its own determinism characteristics.
- A heuristic/stdlib approach requires defining what heuristic is used and its limitations.

**Recommendation**: Commit to a specific approach in design.md. A lightweight library like `langdetect` (with seeded determinism) is pragmatic. Add an explicit sub-task to T1 for updating `requirements.txt` if a library is chosen.

### C2 — `GlobalConfig` wrapper fields are frozen (design.md §3, tasks.md T3)

The wrapper labels (`image_description_heading`, `image_description_end`, `image_description_section_heading`) in `GlobalConfig` are declared with `frozen=True`. The current design says to "extend the insertion function interface to accept localized labels" but T3 does not acknowledge the frozen constraint. If the implementation attempts to mutate config fields, it will raise a Pydantic `ValidationError`.

**Recommendation**: T3 and design.md §1/§3 must explicitly state that localized labels are passed as function parameters (not config mutation). The `insert_image_descriptions_to_text_file` signature should accept optional label overrides that default to `app_config` values when not provided.

### C3 — Custom prompt template vs. language instruction composition is unspecified (design.md §2, tasks.md T2)

Edge case #4 in requirements.md correctly identifies that custom user prompts might conflict with language instructions, but neither design nor tasks specify the resolution. Currently (`vllm_worker.py` line 656), a custom `prompt_template` fully replaces the system prompt. If a language instruction is simply appended/prepended, the composition order and precedence are ambiguous.

**Recommendation**: Define explicit composition rules in design.md:
- When `prompt_template` is provided: append a language directive sentence (e.g., `"Respond in {language}."`) to the end of the custom prompt.
- When no template is provided: append the same directive to the default system prompt.
- Document that the language directive is always the final sentence in the system prompt to ensure it is not overridden by earlier instructions.

---

## High-Priority Issues

### H1 — Localization map scope and content are underspecified (requirements.md FR-4, design.md §3)

FR-4 requires localized wrappers but the plan never specifies:
- Which languages are supported (just the top 5–10? all ISO 639-1?).
- What the localized strings look like (e.g., German: `**[BEGINN BILDBESCHREIBUNG]**`).
- Fallback behavior when a detected language has no localization entry.

**Recommendation**: Add a "Supported Languages" subsection to design.md listing the initial language set (suggest: English, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Czech, Russian — covering common European book scan languages). Define fallback: if no localization exists for a detected language, use English labels. Include sample localized strings for at least 2–3 languages.

### H2 — `user_instruction` is also hardcoded English (vllm_worker.py line 664)

The design focuses on the system prompt but the per-request `user_instruction` ("Describe the attached image and output only the description text.") is also English. The token budget calculation includes this string. If this should also be localized or if it remains English (since the model understands English instructions regardless), this should be an explicit design decision.

**Recommendation**: State in design.md that `user_instruction` remains in English (models reliably follow English instructions even when outputting in other languages), and only the system prompt receives the language directive.

### H3 — Missing inter-task dependency graph (tasks.md)

The traceability matrix maps tasks to requirements but omits task-to-task dependencies. T4 clearly depends on T1–T3, and T5 depends on T1–T4, but this is not explicit.

**Recommendation**: Add a dependency section to tasks.md:
- T1: no dependencies
- T2: no dependencies (can be implemented in parallel with T1)
- T3: no dependencies (can be implemented in parallel with T1/T2)
- T4: depends on T1, T2, T3
- T5: depends on T1–T4

---

## Medium-Priority Issues

### M1 — T5 test scope is vague

T5 says "run nearby existing tests" but doesn't enumerate them. Relevant existing test files include:
- `test_vllm_worker_token_budget.py` (token budget changes from T2)
- `test_handler_image_description_helpers.py` (insertion changes from T3)

**Recommendation**: Explicitly list these files in T5.

### M2 — No performance consideration for language detection

For large documents (100K+ characters), language detection library calls may be slow if applied to the full text. A sampling strategy (e.g., first N characters) would be more efficient.

**Recommendation**: Add a design note in design.md that `infer_output_language` should operate on a text sample (e.g., first 2000 characters) rather than the full document, with rationale.

### M3 — Determinism of `langdetect` requires explicit seeding

If `langdetect` is chosen (C1), its results are non-deterministic by default due to internal randomization. NFR-1 requires deterministic behavior.

**Recommendation**: If `langdetect` is used, document that `langdetect.DetectorFactory.seed` must be set (e.g., `seed = 0`) at initialization. Add this to T1 implementation notes.

---

## Minor/Stylistic Issues

### S1 — Design Option B (settings.py configurable localization) dismissed without rationale

Design §3 prefers Option A but the rationale ("to avoid schema churn") is thin. Since `GlobalConfig` fields are frozen and env-configurable, adding a localization map there would conflict with the per-file dynamic nature of this feature.

**Recommendation**: Strengthen the rationale: "Option A is preferred because localization is per-file and dynamic, while `GlobalConfig` fields are frozen at startup. A runtime-configurable map would require a different config mechanism."

### S2 — Traceability matrix in tasks.md missing NFR-3 logging coverage

T4 is where logging (NFR-3) would naturally be wired, but T4 maps to no NFR. T1 mentions logging in its description but the traceability matrix maps T1 only to FR-1, FR-5, NFR-1.

**Recommendation**: Update traceability: `T1 -> FR-1, FR-5, NFR-1, NFR-3` (since T1 emits the per-file log entry).

---

## Summary of Recommended Changes

| ID | Artifact | Action |
|----|----------|--------|
| C1 | design.md, tasks.md | Commit to language detection approach; add dependency sub-task |
| C2 | design.md, tasks.md | Acknowledge frozen config; specify parameter-passing strategy |
| C3 | design.md | Define prompt + language instruction composition rules |
| H1 | design.md | Add supported-language list and sample localized strings |
| H2 | design.md | Explicitly decide user_instruction stays English |
| H3 | tasks.md | Add inter-task dependency section |
| M1 | tasks.md | Enumerate existing test files in T5 |
| M2 | design.md | Add text-sampling note for inference performance |
| M3 | design.md, tasks.md | Document langdetect seed requirement |
| S1 | design.md | Strengthen Option A rationale |
| S2 | tasks.md | Fix traceability for NFR-3 |
