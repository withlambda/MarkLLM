# Task 02: Propagate language into vLLM image-description APIs in `vllm_worker.py`

## Task ordering number
2

## Task dependencies
None

## Structured implementation steps
1. Extend `describe_images`, `_describe_images_async`, and `_describe_single_image_async` signatures in `vllm_worker.py` with an optional `target_language` parameter.
2. Compose prompt instructions such that the model's output language is explicitly constrained to `target_language`.
3. Ensure backward-compatible behavior when `target_language` is not provided (e.g., defaulting to English or no instruction).
4. Re-calculate or check completion token budgeting, accounting for the additional language instruction text.

## Explicit test requirements
1. Unit test verifying prompt composition includes the correct language instruction.
2. Unit test verifying optional-argument backward compatibility.
3. Token-budget-related test update/addition to confirm that prompt length changes do not negatively impact thresholds.
