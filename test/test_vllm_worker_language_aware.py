import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import sys

# Mock dependencies that might be missing or cause issues in this environment
with patch.dict(sys.modules, {
    "runpod": MagicMock(),
    "torch": MagicMock(),
    "torch.multiprocessing": MagicMock(),
    "marker": MagicMock(),
    "marker.converters": MagicMock(),
    "marker.converters.pdf": MagicMock(),
    "marker.models": MagicMock(),
    "marker.config": MagicMock(),
    "marker.config.parser": MagicMock(),
    "marker.output": MagicMock(),
}):
    from vllm_worker import VllmWorker
    from settings import VllmSettings, GlobalConfig

class TestVllmWorkerLanguageAware(unittest.TestCase):
    def setUp(self):
        # Create a mock GlobalConfig that behaves enough like a Pydantic model
        self.app_config = MagicMock(spec=GlobalConfig)
        self.app_config.vram_gb_total = 16
        self.app_config.vram_gb_reserve = 4
        self.app_config.vram_gb_per_token_factor = 0.0001
        self.app_config.block_correction_prompts_library = {}

        # We need a real-ish VllmSettings for VllmWorker
        self.settings = VllmSettings(
            app_config=self.app_config,
            vllm_model="test-model",
            vllm_vram_gb_model=4,
            vllm_port=8000,
            vllm_max_model_len=1024
        )
        # Mock the AsyncOpenAI client
        self.mock_client = MagicMock()
        self.mock_client.chat = MagicMock()
        self.mock_client.chat.completions = MagicMock()
        self.mock_client.chat.completions.create = AsyncMock()

    @patch('vllm_worker.openai.AsyncOpenAI')
    @patch('vllm_worker.VllmWorker.start_server')
    def test_describe_single_image_with_language(self, mock_start, mock_openai_class):
        mock_openai_class.return_value = self.mock_client
        worker = VllmWorker(self.settings)
        worker._client = self.mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is a description in German."
        self.mock_client.chat.completions.create.return_value = mock_response

        image_path = Path("test.png")
        # Mock image read
        with patch.object(Path, "read_bytes", return_value=b"fake-image-data"):
            import asyncio
            description = asyncio.run(worker._describe_single_image_async(
                image_path,
                prompt_template=None,
                image_index=0,
                target_language="German"
            ))

        self.assertEqual(description, "This is a description in German.")

        # Check if the system prompt was updated correctly
        call_args = self.mock_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        system_msg = next(m for m in messages if m['role'] == 'system')
        self.assertIn("Respond in German.", system_msg['content'])

    @patch('vllm_worker.openai.AsyncOpenAI')
    @patch('vllm_worker.VllmWorker.start_server')
    def test_describe_single_image_without_language(self, mock_start, mock_openai_class):
        mock_openai_class.return_value = self.mock_client
        worker = VllmWorker(self.settings)
        worker._client = self.mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "English description."
        self.mock_client.chat.completions.create.return_value = mock_response

        image_path = Path("test.png")
        with patch.object(Path, "read_bytes", return_value=b"fake-image-data"):
            import asyncio
            description = asyncio.run(worker._describe_single_image_async(
                image_path,
                prompt_template=None,
                image_index=0,
                target_language=None
            ))

        self.assertEqual(description, "English description.")
        call_args = self.mock_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        system_msg = next(m for m in messages if m['role'] == 'system')
        self.assertNotIn("Respond in", system_msg['content'])

if __name__ == "__main__":
    unittest.main()
