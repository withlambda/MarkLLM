# Task 03: Localize wrapper insertion in `handler.py` output mutation path

## Task ordering number
3

## Task dependencies
None

## Structured implementation steps
1. Extend `insert_image_descriptions_to_text_file(...)` in `handler.py` with optional label-override parameters (e.g., `heading_override`, `end_override`, `section_heading_override`). These should default to `app_config` values since `GlobalConfig` is frozen.
2. Use the localization map (referenced in `design.md`) to resolve language-specific labels in `handler.py`.
3. Apply localization consistently for both inline insertion and end-of-file fallback sections.
4. Preserve the existing behavior of skipping image description insertion for non-text output files (e.g., `json`, `html`).

## Explicit test requirements
1. Unit test for inline insertion with localized wrappers.
2. Unit test for fallback append section with localized wrappers.
3. Regression test verifying that behavior remains unchanged for `json` and `html` output files.
