# Feature: language-aware-image-descriptions

## Functional requirements

1. **Language inference before image description (FR-1)**
   - For each successfully converted output file, the pipeline MUST infer a target language from the text content before calling image-description generation.
   - Inference MUST happen in `handler.py` after text post-processing and before `vllm_worker.describe_images(...)`.

2. **Language propagation to image description generation (FR-2)**
   - The inferred language MUST be passed from `handler.py` into image-description functions in `vllm_worker.py`.
   - The worker API MUST preserve backward compatibility by supporting calls without an explicit language (fallback behavior is still valid).

3. **Language-aware image prompting (FR-3)**
   - Image description prompts sent to the model MUST explicitly instruct output in the inferred target language.
   - This requirement applies to both default prompt behavior and custom prompt-template usage.
   - If inference fails or confidence is insufficient, the system MUST fall back to a deterministic default language (English).

4. **Localized image-description wrappers in output text (FR-4)**
   - The insertion markers currently represented by heading/footer text (e.g., begin/end image description markers and fallback section heading) MUST be rendered in the same target language used for generated image descriptions.
   - Localization MUST apply both to inline insertions (after image tags) and fallback appended sections.

5. **Per-file consistency (FR-5)**
   - All image descriptions and wrapper markers for a single output document MUST use one consistent resolved language per file.
   - Mixed-language source text MUST still resolve to one deterministic language for that file.

6. **No regression in the existing flow (FR-6)**
   - Files without images MUST continue to skip image-description generation.
   - Non-text outputs (`json`, `html`) MUST continue to skip insertion of markdown-style image descriptions.
   - The existing OCR block correction flow MUST remain unaffected.

## Non-functional requirements

1. **Deterministic behavior (NFR-1)**
   - Given the same file text and configuration, the inferred language and resulting prompt language MUST be stable across runs.

2. **Operational safety and compatibility (NFR-2)**
   - The feature MUST not break existing job input contracts.
   - New parameters (if introduced) SHOULD be optional and default-safe.

3. **Observability (NFR-3)**
   - Logs MUST include the resolved target language per processed file before image descriptions are generated.
   - Failure to infer language MUST be logged once per file with explicit fallback language.

4. **Token-budget awareness (NFR-4)**
   - Adding language guidance to prompts MUST preserve existing token-budget safeguards for image descriptions.

## Edge cases/pitfalls

1. Very short text, numeric-only text, or symbol-heavy text may not provide reliable language signals.
2. OCR noise can bias language detection; fallback must remain robust.
3. Documents containing multiple languages need deterministic tiebreaking.
4. Custom user-provided image prompt templates might conflict with language instructions; composition order must ensure language instruction is preserved.
5. Language labels used in prompts (e.g., `de`, `German`) must be normalized to a model-friendly form.
6. Existing static English markers in global config require a localization strategy that does not break environment-variable overrides.

## Definition of Done (measurable success criteria)

1. Language is inferred per processed file before image description generation and passed to vLLM image-description APIs.
2. Prompt payloads used for image description include an explicit target-language instruction.
3. Inserted image-description wrappers (begin/end/section heading) appear in the same resolved language as image descriptions.
4. Fallback to English is deterministic when inference is unavailable or unreliable.
5. Unit/integration tests cover:
   - language inference and fallback,
   - propagation into `describe_images(...)`,
   - localized wrapper insertion,
   - unchanged behavior for files without images and non-text output formats.
6. All relevant tests pass without disabling or weakening existing assertions.
