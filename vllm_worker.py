# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
vLLM worker for document post-processing.
This module manages the lifecycle of a vLLM server subprocess, including
startup with health-check polling, graceful shutdown, and OpenAI-compatible
API communication for OCR error correction and image description generation.
"""

import asyncio
import base64
import logging
import random
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Tuple

import httpx
import openai

from settings import VllmSettings

# Configure logging
logger = logging.getLogger(__name__)

# Default timeout (seconds) for graceful shutdown before SIGKILL
_SHUTDOWN_GRACE_PERIOD = 10

# Health-check polling interval in seconds
_HEALTH_CHECK_INTERVAL = 2


class VllmWorker:
    """
    Manages the vLLM server lifecycle and handles LLM text processing tasks.

    This class provides methods to:
    - Start and stop the vLLM server as a subprocess.
    - Poll the health endpoint until the server is ready.
    - Process text chunks in parallel using the OpenAI-compatible vLLM API.
    - Describe images via the vision-language model endpoint.
    - Handle server crashes with one automatic restart attempt.

    The vLLM server is started on-demand and communicates via an
    OpenAI-compatible REST API using the ``openai`` Python client.
    """

    def __init__(self, settings: VllmSettings) -> None:
        """
        Initialize the VllmWorker.

        Args:
            settings: Validated vLLM configuration (model path, VRAM, ports, etc.).
        """
        self.settings = settings
        self.process: Optional[subprocess.Popen] = None
        self._client: Optional[openai.AsyncOpenAI] = None
        self._restart_attempted: bool = False

        logger.info(
            f"VllmWorker initialized with model={self.settings.vllm_model}, "
            f"host={self.settings.vllm_host}, port={self.settings.vllm_port}"
        )

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "VllmWorker":
        """
        Context manager entry: starts the vLLM server, waits for readiness,
        and initializes the OpenAI client.
        """
        try:
            self.start_server()
        except Exception:
            self.stop_server()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit: gracefully shuts down the vLLM server."""
        self.stop_server()

    def __del__(self) -> None:
        """Ensure the server subprocess is stopped on garbage collection."""
        self.stop_server()

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start_server(self, vram_recovery_delay: Optional[int] = None) -> None:
        """
        Launch the vLLM server as a subprocess and wait for it to become ready.

        1. Wait for ``vllm_vram_recovery_delay`` seconds (VRAM recovery phase).
        2. Spawn ``vllm serve`` with CLI arguments derived from ``VllmSettings``.
        3. Poll ``GET /health`` until HTTP 200 or ``vllm_startup_timeout`` elapses.
        4. Initialize the ``openai.AsyncOpenAI`` client.

        Args:
            vram_recovery_delay: Override for the VRAM recovery delay.  If *None*,
                uses ``self.settings.vllm_vram_recovery_delay``.

        Raises:
            RuntimeError: If the server fails to start or the health check times out.
        """
        # If already running, nothing to do
        if self.process is not None and self.process.poll() is None:
            logger.info("vLLM server is already running.")
            return

        # Clean up any dead process handle
        if self.process is not None:
            logger.warning("vLLM server process was found dead. Cleaning up before restart.")
            self._cleanup_process()

        # --- VRAM Recovery Phase ---
        delay = vram_recovery_delay if vram_recovery_delay is not None else self.settings.vllm_vram_recovery_delay
        if delay > 0:
            logger.info(f"Waiting {delay}s for GPU VRAM recovery before starting vLLM...")
            time.sleep(delay)

        # --- Build CLI command ---
        cmd = self._build_serve_command()
        logger.info(f"Starting vLLM server: {' '.join(cmd)}")

        # --- Launch subprocess ---
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        logger.info(f"vLLM subprocess started (PID {self.process.pid})")

        # --- Health-check polling ---
        self._wait_for_ready()

        # --- Create OpenAI client ---
        self._client = openai.AsyncOpenAI(
            base_url=f"http://localhost:{self.settings.vllm_port}/v1",
            api_key="EMPTY",  # vLLM does not require a real API key
        )

        logger.info("vLLM server is ready and OpenAI client initialized.")

    def stop_server(self) -> None:
        """
        Gracefully shut down the vLLM server subprocess.

        Sends SIGTERM, waits up to ``_SHUTDOWN_GRACE_PERIOD`` seconds,
        then sends SIGKILL if the process is still running.
        """
        if self.process is None:
            return

        pid = self.process.pid
        logger.info(f"Stopping vLLM server (PID {pid})...")

        try:
            # Send SIGTERM for graceful shutdown
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=_SHUTDOWN_GRACE_PERIOD)
                logger.info(f"vLLM server (PID {pid}) terminated gracefully.")
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"vLLM server (PID {pid}) did not exit within {_SHUTDOWN_GRACE_PERIOD}s. "
                    f"Sending SIGKILL..."
                )
                self.process.kill()
                self.process.wait(timeout=5)
                logger.info(f"vLLM server (PID {pid}) killed.")
        except ProcessLookupError:
            logger.info(f"vLLM server (PID {pid}) already exited.")
        except Exception as e:
            logger.error(f"Error stopping vLLM server (PID {pid}): {e}")
        finally:
            self._cleanup_process()

    # ------------------------------------------------------------------
    # Text processing
    # ------------------------------------------------------------------

    def process_text(
        self,
        text: str,
        prompt_template: Optional[str],
        max_chunk_workers: int,
    ) -> str:
        """
        Post-process text using the vLLM model for OCR error correction.

        Chunks the text to stay within the context window and processes chunks
        concurrently using ``asyncio``.

        Args:
            text: The full document text to process.
            prompt_template: Optional system prompt override for correction.
            max_chunk_workers: Maximum number of concurrent async tasks.

        Returns:
            The corrected text with all chunks rejoined.

        Raises:
            ValueError: If the model name is not configured.
        """
        if not self.settings.vllm_model:
            raise ValueError("vllm_model not set for processing")

        chunks = self._chunk_text(text, self.settings.vllm_chunk_size)

        system_prompt = prompt_template if prompt_template else (
            "You are a helpful assistant. Correct the OCR errors in the text provided below. "
            "Output ONLY the corrected text, maintaining original formatting as much as possible."
        )

        max_workers = max(1, int(max_chunk_workers))
        logger.info(f"Processing {len(chunks)} chunks with vLLM using {max_workers} async workers...")

        corrected_chunks = asyncio.get_event_loop().run_until_complete(
            self._process_chunks_async(chunks, system_prompt, max_workers)
        )

        return "\n\n".join(corrected_chunks)

    def process_file(
        self,
        file_path: Path,
        prompt_template: Optional[str],
        max_chunk_workers: int,
    ) -> bool:
        """
        Process a single file with the vLLM model.

        Reads the file, applies OCR error correction via :meth:`process_text`,
        and overwrites the file with the corrected content.

        Args:
            file_path: Path to the file to process.
            prompt_template: Optional custom system prompt.
            max_chunk_workers: Maximum number of concurrent async tasks.

        Returns:
            True if processing succeeded, False otherwise.
        """
        if not file_path.exists():
            return False

        logger.info(f"LLM Processing: {file_path.name}")
        try:
            original_text = file_path.read_text(encoding="utf-8")
            processed_text = self.process_text(
                text=original_text,
                prompt_template=prompt_template,
                max_chunk_workers=max_chunk_workers,
            )
            file_path.write_text(processed_text, encoding="utf-8")
            logger.info(f"Finished LLM processing for {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to post-process {file_path.name}: {e}")
            return False

    # ------------------------------------------------------------------
    # Image description
    # ------------------------------------------------------------------

    def describe_images(
        self,
        image_paths: List[Path],
        prompt_template: Optional[str],
        max_image_workers: int,
    ) -> List[Tuple[Path, str]]:
        """
        Generate descriptions for multiple images via the vision-language model.

        Args:
            image_paths: Paths of images to describe.
            prompt_template: Optional custom system prompt for image description.
            max_image_workers: Maximum number of concurrent async tasks.

        Returns:
            List of (image_path, description) tuples for successfully described images,
            preserving the original order.
        """
        if not image_paths:
            return []

        max_workers = max(1, int(max_image_workers))
        logger.info(f"Describing {len(image_paths)} extracted images with {max_workers} async worker(s)...")

        descriptions: List[Optional[str]] = asyncio.get_event_loop().run_until_complete(
            self._describe_images_async(image_paths, prompt_template, max_workers)
        )

        return [
            (image_path, description)
            for image_path, description in zip(image_paths, descriptions)
            if description
        ]

    # ------------------------------------------------------------------
    # Internal helpers — async processing
    # ------------------------------------------------------------------

    async def _process_chunks_async(
        self,
        chunks: List[str],
        system_prompt: str,
        max_workers: int,
    ) -> List[str]:
        """
        Process all text chunks concurrently, bounded by *max_workers*.

        Args:
            chunks: List of text chunks.
            system_prompt: The system prompt for OCR correction.
            max_workers: Semaphore limit for concurrent API calls.

        Returns:
            List of corrected chunks in original order.
        """
        semaphore = asyncio.Semaphore(max_workers)

        async def _bounded_process(idx: int, chunk: str) -> Tuple[int, str]:
            async with semaphore:
                result = await self._process_single_chunk_async(chunk, system_prompt, idx)
                return idx, result

        tasks = [_bounded_process(i, c) for i, c in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        corrected: List[str] = list(chunks)  # fallback copy
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async chunk task failed: {result}")
                continue
            idx, text = result
            corrected[idx] = text

        return corrected

    async def _process_single_chunk_async(
        self,
        chunk: str,
        system_prompt: str,
        chunk_index: int,
    ) -> str:
        """
        Process a single text chunk via the OpenAI chat completions API with retry logic.

        On retryable errors (connection, timeout, overloaded, server crash) the method
        backs off exponentially.  If the vLLM subprocess has died, one restart is
        attempted before giving up.

        Args:
            chunk: The text chunk to correct.
            system_prompt: System prompt for the model.
            chunk_index: Index of this chunk (for logging).

        Returns:
            The corrected text, or the original chunk as fallback on failure.
        """
        for attempt in range(self.settings.vllm_max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self.settings.vllm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk},
                    ],
                    max_tokens=self.settings.vllm_max_model_len,
                )
                content = response.choices[0].message.content
                return content.strip() if content else chunk
            except Exception as e:
                is_last = attempt == self.settings.vllm_max_retries
                if self._is_retryable_error(e) and not is_last:
                    delay = self._compute_backoff(attempt, e)
                    logger.warning(
                        f"Retryable error on chunk {chunk_index} "
                        f"(attempt {attempt + 1}/{self.settings.vllm_max_retries + 1}). "
                        f"Retrying in {delay:.2f}s... Error: {e}"
                    )
                    # Check if vLLM subprocess crashed and attempt one restart
                    await self._maybe_restart_server()
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Fatal error processing chunk {chunk_index} "
                        f"after {attempt + 1} attempts: {e}"
                    )
                    return chunk  # fallback to original

        logger.warning(f"Chunk {chunk_index} processing loop exited unexpectedly. Returning original.")
        return chunk

    async def _describe_images_async(
        self,
        image_paths: List[Path],
        prompt_template: Optional[str],
        max_workers: int,
    ) -> List[Optional[str]]:
        """
        Describe all images concurrently, bounded by *max_workers*.

        Args:
            image_paths: Paths of images to describe.
            prompt_template: Optional system prompt override.
            max_workers: Semaphore limit for concurrent API calls.

        Returns:
            List of description strings (or None) in original order.
        """
        semaphore = asyncio.Semaphore(max_workers)

        async def _bounded_describe(idx: int, path: Path) -> Tuple[int, Optional[str]]:
            async with semaphore:
                result = await self._describe_single_image_async(path, prompt_template, idx)
                return idx, result

        tasks = [_bounded_describe(i, p) for i, p in enumerate(image_paths)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        descriptions: List[Optional[str]] = [None] * len(image_paths)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async image description task failed: {result}")
                continue
            idx, desc = result
            descriptions[idx] = desc

        return descriptions

    async def _describe_single_image_async(
        self,
        image_path: Path,
        prompt_template: Optional[str],
        image_index: int,
    ) -> Optional[str]:
        """
        Generate a description for a single image using the vision-language model.

        The image is base64-encoded and sent as part of a multi-modal chat completion
        request via the OpenAI client.

        Args:
            image_path: Path to the image file.
            prompt_template: Optional custom system prompt for the description.
            image_index: Zero-based image index for logging.

        Returns:
            The description string, or None on failure.
        """
        if not self.settings.vllm_model:
            raise ValueError("vllm_model not set for image description")

        system_prompt = prompt_template if prompt_template else (
            "You are an expert document-vision assistant. "
            "Describe the provided image precisely and factually. "
            "Include visible text, tables, charts, figures, equations, and layout details when present. "
            "Do not infer details that are not visible."
        )

        try:
            # Read and base64-encode the image
            image_data = image_path.read_bytes()
            b64_image = base64.b64encode(image_data).decode("utf-8")

            # Determine MIME type from suffix
            suffix = image_path.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".tif": "image/tiff",
                ".tiff": "image/tiff",
            }
            mime_type = mime_map.get(suffix, "image/png")

            response = await self._client.chat.completions.create(
                model=self.settings.vllm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{b64_image}",
                                },
                            },
                            {
                                "type": "text",
                                "text": "Provide a precise and concise description of this image.",
                            },
                        ],
                    },
                ],
                max_tokens=self.settings.vllm_max_model_len,
            )

            content = response.choices[0].message.content
            description = content.strip() if content else ""
            if not description:
                logger.warning(f"Empty image description returned for {image_path.name}")
                return None
            return description

        except Exception as e:
            logger.error(f"Failed to describe image {image_index + 1} ({image_path.name}): {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers — server management
    # ------------------------------------------------------------------

    def _build_serve_command(self) -> List[str]:
        """
        Build the CLI command list for launching ``vllm serve``.

        Returns:
            List of command-line tokens.
        """
        cmd = [
            "vllm", "serve",
            str(self.settings.vllm_model_path),
            "--port", str(self.settings.vllm_port),
            "--gpu-memory-utilization", str(self.settings.vllm_gpu_util),
            "--max-model-len", str(self.settings.vllm_max_model_len),
            "--max-num-seqs", str(self.settings.vllm_max_num_seqs),
        ]

        # If the model name differs from the path, pass --served-model-name
        if self.settings.vllm_model:
            cmd.extend(["--served-model-name", self.settings.vllm_model])

        return cmd

    def _wait_for_ready(self) -> None:
        """
        Poll the vLLM health endpoint until the server is ready.

        Retries every ``_HEALTH_CHECK_INTERVAL`` seconds until either HTTP 200
        is received or ``vllm_startup_timeout`` elapses.

        Raises:
            RuntimeError: If the health check times out or the subprocess exits
                prematurely.
        """
        health_url = f"http://localhost:{self.settings.vllm_port}/health"
        deadline = time.time() + self.settings.vllm_startup_timeout

        logger.info(
            f"Polling vLLM health endpoint ({health_url}) "
            f"with timeout={self.settings.vllm_startup_timeout}s..."
        )

        while time.time() < deadline:
            # Check if subprocess has exited
            if self.process is not None and self.process.poll() is not None:
                # Capture any remaining stderr/stdout for diagnostics
                output = ""
                if self.process.stdout:
                    output = self.process.stdout.read()
                self._cleanup_process()
                raise RuntimeError(
                    f"vLLM server exited prematurely (exit code: {self.process.returncode if self.process else 'N/A'}). "
                    f"Output:\n{output}"
                )

            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(health_url)
                    if resp.status_code == 200:
                        logger.info("vLLM health check passed.")
                        return
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
                pass  # Server not ready yet

            time.sleep(_HEALTH_CHECK_INTERVAL)

        # Timeout reached — collect subprocess output and terminate
        output = ""
        if self.process is not None and self.process.stdout:
            output = self.process.stdout.read()
        self.stop_server()
        raise RuntimeError(
            f"vLLM health check timed out after {self.settings.vllm_startup_timeout}s. "
            f"Server output:\n{output}"
        )

    async def _maybe_restart_server(self) -> None:
        """
        Check if the vLLM subprocess has died and attempt one restart.

        This is called from within retry loops to recover from mid-processing
        crashes. Only one restart is attempted per worker lifetime to avoid
        infinite restart loops.
        """
        if self.process is None or self.process.poll() is None:
            return  # Still running or never started

        if self._restart_attempted:
            logger.error("vLLM server died and a restart was already attempted. Not retrying.")
            return

        self._restart_attempted = True
        logger.warning(
            f"vLLM server process (PID {self.process.pid}) died unexpectedly. "
            f"Attempting one restart..."
        )

        try:
            self._cleanup_process()
            # Use a shorter VRAM recovery delay for restarts
            self.start_server(vram_recovery_delay=2)
            logger.info("vLLM server restarted successfully.")
        except Exception as e:
            logger.error(f"Failed to restart vLLM server: {e}")

    def _cleanup_process(self) -> None:
        """
        Clean up the subprocess handle and close stdout pipe.
        """
        if self.process is not None:
            try:
                if self.process.stdout:
                    self.process.stdout.close()
            except Exception:
                pass
            self.process = None

    # ------------------------------------------------------------------
    # Internal helpers — retry logic
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """
        Determine whether an API error is transient and worth retrying.

        Args:
            error: The exception raised during an API call.

        Returns:
            True if the error is considered retryable.
        """
        error_msg = str(error).lower()
        retryable_patterns = [
            "connection refused",
            "connection error",
            "try again",
            "overloaded",
            "timeout",
            "503",
            "504",
            "server disconnected",
            "service unavailable",
        ]
        return any(pattern in error_msg for pattern in retryable_patterns)

    def _compute_backoff(self, attempt: int, error: Exception) -> float:
        """
        Compute the backoff delay for a given retry attempt.

        Uses exponential backoff with jitter. Severe errors (connection refused,
        server disconnected) use a 3× base delay.

        Args:
            attempt: Zero-based retry attempt number.
            error: The exception that triggered the retry.

        Returns:
            Delay in seconds before the next retry.
        """
        error_msg = str(error).lower()
        is_severe = "connection refused" in error_msg or "server disconnected" in error_msg
        base_delay = (self.settings.vllm_retry_delay * 3) if is_severe else self.settings.vllm_retry_delay
        return (base_delay * (2 ** attempt)) + (random.random() * self.settings.vllm_retry_delay)

    # ------------------------------------------------------------------
    # Internal helpers — text chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, chunk_size: Optional[int] = None) -> List[str]:
        """
        Split text into chunks of approximately *chunk_size* characters,
        preferring to break on newline boundaries.

        Args:
            text: The text to split.
            chunk_size: Maximum characters per chunk.  Defaults to
                ``self.settings.vllm_chunk_size``.

        Returns:
            List of text chunks.
        """
        if chunk_size is None:
            chunk_size = self.settings.vllm_chunk_size

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunks.append(text[start:])
                break

            # Try to find the last newline within the chunk limit
            last_newline = text.rfind("\n", start, end)

            if last_newline != -1 and last_newline > start:
                chunks.append(text[start:last_newline])
                start = last_newline + 1  # Skip the newline character
            else:
                # Force break if no newline found
                chunks.append(text[start:end])
                start = end

        return chunks
