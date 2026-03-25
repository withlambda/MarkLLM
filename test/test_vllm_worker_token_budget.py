"""Tests for vLLM chunk request token budgeting."""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vllm_worker import VllmWorker


def _make_worker(max_model_len: int = 100) -> VllmWorker:
    """Create a lightweight worker configured for token-budget tests."""
    settings = types.SimpleNamespace(
        vllm_model="stub-model",
        vllm_host="127.0.0.1",
        vllm_port=8001,
        vllm_chunk_size=1024,
        vllm_max_model_len=max_model_len,
        vllm_max_retries=0,
        vllm_retry_delay=0.01,
    )
    worker = VllmWorker(settings=settings)

    response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="corrected"))]
    )
    worker._client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=AsyncMock(return_value=response))
        )
    )
    return worker


class TestVllmWorkerChunkTokenBudget(unittest.IsolatedAsyncioTestCase):
    """Validate chunk processing request construction against context limits."""

    def test_process_text_uses_prompt_aware_chunk_size(self):
        """process_text should reduce chunk_size by prompt/context budget before chunking."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", return_value=30), patch.object(
            worker,
            "_chunk_text",
            return_value=["alpha"],
        ) as chunk_mock, patch.object(
            worker,
            "_process_chunks_async",
            new=AsyncMock(return_value=["corrected"]),
        ):
            result = worker.process_text("original", "system", 1)

        self.assertEqual(result, "corrected")
        chunk_mock.assert_called_once_with("original", 5)

    def test_process_text_returns_original_when_prompt_exhausts_chunk_budget(self):
        """process_text should skip chunking/API work when prompt leaves no context room."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", return_value=99), patch.object(
            worker,
            "_chunk_text",
            return_value=["should-not-be-used"],
        ) as chunk_mock, patch.object(
            worker,
            "_process_chunks_async",
            new=AsyncMock(return_value=["should-not-be-used"]),
        ) as process_mock:
            result = worker.process_text("original", "system", 1)

        self.assertEqual(result, "original")
        chunk_mock.assert_not_called()
        process_mock.assert_not_called()

    async def test_chunk_request_caps_completion_tokens_by_prompt_size(self):
        """Request should use a completion budget smaller than full context when prompt is non-empty."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", side_effect=[10, 20]):
            result = await worker._process_single_chunk_async("chunk", "system", 0)

        self.assertEqual(result, "corrected")
        create_mock = worker._client.chat.completions.create
        self.assertEqual(create_mock.await_count, 1)
        self.assertLess(create_mock.await_args.kwargs["max_tokens"], worker.settings.vllm_max_model_len)
        self.assertGreater(create_mock.await_args.kwargs["max_tokens"], 0)

    async def test_chunk_processing_skips_api_call_when_prompt_exceeds_context(self):
        """If prompt already exhausts context, worker should return original chunk without API call."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", side_effect=[80, 40]):
            result = await worker._process_single_chunk_async("original", "system", 0)

        self.assertEqual(result, "original")
        create_mock = worker._client.chat.completions.create
        self.assertEqual(create_mock.await_count, 0)


if __name__ == "__main__":
    unittest.main()
