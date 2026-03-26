# Tasks: language-aware-image-descriptions

## Traceability Matrix

- T1 -> FR-1, FR-5, NFR-1, NFR-3
- T2 -> FR-2, FR-3, NFR-2, NFR-4
- T3 -> FR-4, FR-6, NFR-2
- T4 -> NFR-3
- T5 -> DoD 5/6, FR-6 regression guarantees

## Task Dependencies

- T1: no dependencies
- T2: no dependencies (can be implemented in parallel with T1)
- T3: no dependencies (can be implemented in parallel with T1/T2)
- T4: depends on T1, T2, T3
- T5: depends on T1–T4

## Implementation Tasks

1. Implement per-file language inference in `handler.py`.
   - Add `langdetect` to `requirements.txt`.
   - Set `langdetect.DetectorFactory.seed = 0` at module level for deterministic results (NFR-1).
   - Add helper(s) to infer/normalize a single target language from processed text.
   - Operate on a text sample (first ~2000 characters) for performance on large documents.
   - Ensure deterministic fallback to English for low-signal/unknown cases.
   - Emit one log entry per file with resolved language and fallback reason when applicable.
   - **Test requirements**:
     - Unit tests for inference on clear-language text samples.
     - Unit tests for short/noisy text fallback behavior.
     - Unit tests for deterministic mixed-language tiebreaking.

2. Propagate language into vLLM image-description APIs in `vllm_worker.py`.
   - Extend `describe_images`, `_describe_images_async`, and `_describe_single_image_async` signatures with optional `target_language`.
   - Compose prompt instructions so model output language is explicitly constrained to `target_language`.
   - Keep backward-compatible behavior when `target_language` is not provided.
   - Re-check completion token budgeting with the additional language instruction text.
   - **Test requirements**:
     - Unit test verifying prompt composition includes language instruction.
     - Unit test verifying optional-argument backward compatibility.
     - Token-budget-related test update/addition if prompt length changes impact thresholds.

3. Localize wrapper insertion in `handler.py` output mutation path.
   - Extend `insert_image_descriptions_to_text_file(...)` with optional label-override parameters (e.g., `heading_override`, `end_override`, `section_heading_override`) that default to `app_config` values. Note: `GlobalConfig` wrapper fields are `frozen=True` and cannot be mutated, so localized labels must be passed as explicit parameters.
   - Use the localization map (see design.md Supported Languages) to resolve labels.
   - Apply localization consistently for both inline insertion and end-of-file fallback section.
   - Preserve existing skip behavior for non-text output files.
   - **Test requirements**:
     - Unit test for inline insertion with localized wrappers.
     - Unit test for a fallback append section with localized wrappers.
     - Regression test verifying unchanged behavior for `json`/`html` output files.

4. Wire end-to-end per-file language flow in the handler post-processing loop.
   - Infer language once per processed file after text post-processing succeeds.
   - Pass resolved language to both `describe_images(...)` and insertion helper/localization resolver.
   - Keep the no-image path unchanged (no inference-driven failures should block file completion).
   - **Test requirements**:
     - Integration-style test (mocking worker calls) to assert language is inferred once and passed through.
     - Regression test verifying no-image files still complete without image-description side effects.

5. Validate and run relevant tests.
   - Run all newly added/updated tests for handler and vLLM worker language-aware image description behavior.
   - Run existing tests that cover related behavior:
     - `test/test_vllm_worker_token_budget.py` (token budget changes from T2)
     - `test/test_handler_image_description_helpers.py` (insertion changes from T3)
   - Fix any regressions before completion.
   - **Test requirements**:
     - Evidence that all relevant tests pass.
     - No test weakening/skip annotations introduced to force passing.
