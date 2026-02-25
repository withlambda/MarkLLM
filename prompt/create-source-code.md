# Create Source Code

## Goal
Create a Dockerized solution that runs `marker-pdf` with `Ollama` LLM support in a single container. This container is intended for deployment on serverless GPU platforms like RunPod.io.

## Functionality
The system should:
1.  Monitor a specific input directory within a mounted storage bucket for PDF files.
2.  Process these PDFs using `marker-pdf`, leveraging a local `Ollama` instance for enhanced OCR/conversion.
3.  Output the resulting Markdown files to a specific output directory within the same storage bucket, mirroring the input directory structure.
4.  Clean up processed files and shut down automatically upon completion.

## Configuration
The Docker container must be configurable via the following environment variables:

### Storage Configuration
-   `STORAGE_BUCKET_PATH`: The local mount path where the storage bucket is accessible. Assume the platform handles the actual mounting.
-   `INPUT_DIR`: The subdirectory within `STORAGE_BUCKET_PATH` to scan for input PDFs.
-   `OUTPUT_DIR`: The subdirectory within `STORAGE_BUCKET_PATH` where generated Markdown files will be saved.

### Ollama & Model Configuration
-   `OLLAMA_MODEL`: The name of the LLM model to be used (e.g., `llama3`). This value is used to:
    -   Pull and run the model in the local Ollama instance.
    -   Pass as the value for the `--ollama_model` argument in `marker-pdf`.
-   `OLLAMA_MODELS_DIR`: (Optional) The directory where Ollama stores its models. Defaults to `~/.ollama/models`. This allows mounting a persistent volume (e.g., `/runpod-volume/ollama_models`) to avoid re-downloading models on every start.

### Marker-PDF Options
-   `MARKER_BLOCK_CORRECTION_PROMPT`: Value for the `--block_correction_prompt` option.
-   `MARKER_WORKERS`: Value for the `--workers` option (integer).
-   `MARKER_PAGINATE_OUTPUT`: Boolean flag. If true, adds `--paginate_output`.
-   `MARKER_USE_LLM`: Boolean flag. If true, adds `--use_llm`.
-   `MARKER_FORCE_OCR`: Boolean flag. If true, adds `--force_ocr`.

### GPU Configuration
-   Ensure environment variables (like `CUDA_VISIBLE_DEVICES`) are correctly set or passed through to allow both `marker-pdf` and `Ollama` to access the GPU.

## Implementation Details

### Base Image
-   Use a **PyTorch base image** optimized for RunPod.io serverless environments (e.g., `runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel` or similar).
-   Ensure it includes necessary CUDA drivers and is as lightweight as possible while maintaining compatibility.

### Software Versions
-   **Marker-PDF**: Pin to a recent stable release version to ensure reproducibility. The version should be compatible with the pytorch version.
-   **Ollama**: Install via the official curl script (`curl -fsSL https://ollama.com/install.sh | sh`). Pin to a recent stable version if possible, or ensure the installation method retrieves a stable release.

### Startup Script (`entrypoint.sh`)
The script must perform the following sequence:
1.  **Configure Ollama**: Set the `OLLAMA_MODELS` environment variable to the value of `OLLAMA_MODELS_DIR` if provided.
2.  **Start Ollama**: Launch the Ollama service in the background.
3.  **Health Check**: Implement a loop that checks if the Ollama server is up and responding (e.g., `curl localhost:11434`). Proceed only after confirmation.
4.  **Pull Model**: Check if the specified `OLLAMA_MODEL` exists locally. If not, pull it.
5.  **Construct Command**: Build the `marker-pdf` command string based on the provided environment variables.
6.  **Execute Processing**: Run `marker-pdf` against the `INPUT_DIR`.
    -   Ensure the output directory structure mirrors the input directory.
    -   Implement error handling: If processing fails for a specific file, log the error and continue with the next file.
7.  **Cleanup**: Upon successful processing of a file, delete the original file from the `INPUT_DIR`. Do not delete files that failed processing.
8.  **Shutdown**: Exit the script (and thus the container) to stop billing in a serverless environment.

### Dependencies
-   Ensure all necessary system libraries (e.g., `poppler-utils`, `tesseract-ocr` if needed by marker) and Python packages are installed.

## Output
Generate the following files:
1.  `Dockerfile`: The definition for the container image.
2.  `entrypoint.sh`: The startup script handling service orchestration, health checks, processing, and cleanup.
3.  `docker-compose.yml` (Optional): A sample composition for local testing.
4.  `README.md`: Instructions on how to build, configure, and run the container. Include a section with a sample RunPod Template configuration (JSON snippet) that maps the environment variables correctly.
