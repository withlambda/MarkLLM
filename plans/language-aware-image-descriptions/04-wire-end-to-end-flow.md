# Task 04: Wire end-to-end per-file language flow in the `handler.py` post-processing loop

## Task ordering number
4

## Task dependencies
- 01-implement-language-inference.md
- 02-propagate-language-to-worker.md
- 03-localize-wrapper-insertion.md

## Structured implementation steps
1. Infer the language once per processed file in `handler.py` after text post-processing succeeds.
2. Pass the resolved language to both `describe_images(...)` and the insertion helper/localization resolver.
3. Ensure the no-image path remains unchanged; language inference-driven failures should not block file completion.

## Explicit test requirements
1. Integration-style test (with worker call mocks) asserting the language is inferred once and correctly propagated.
2. Regression test verifying that no-image files still complete correctly without image-description side effects.
