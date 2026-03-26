# Task 01: Implement per-file language inference in `handler.py`

## Task ordering number
1

## Task dependencies
None

## Structured implementation steps
1. Add `langdetect` to `requirements.txt`.
2. Set `langdetect.DetectorFactory.seed = 0` at module level in `handler.py` for deterministic results (NFR-1).
3. Add helper(s) to `handler.py` to infer/normalize a single target language from processed text.
4. Operate on a text sample (first ~2000 characters) for performance on large documents.
5. Ensure deterministic fallback to English for low-signal/unknown cases.
6. Emit one log entry per file with resolved language and fallback reason when applicable.

## Explicit test requirements
1. Unit tests for inference on clear-language text samples.
2. Unit tests for short/noisy text fallback behavior.
3. Unit tests for deterministic mixed-language tiebreaking.
