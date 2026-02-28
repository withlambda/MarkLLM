# 1. BASE IMAGE
# Use a slim Python image instead of the heavy PyTorch/CUDA image
FROM python:3.10-slim

# 2. DEFINE APP ARGS
ARG MARKER_VERSION=1.10.2
ARG RUNPOD_VERSION=1.8.1

# 3. ENVIRONMENT SETTINGS
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    OLLAMA_HOST=0.0.0.0

# 4. SYSTEM DEPENDENCIES
# poppler-utils: Required for PDF processing
# tesseract-ocr: Required for OCR capabilities
# curl: Required for installing Ollama
# git: Required for installing marker-pdf from source if needed
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    curl \
    zstd \
    git \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. OLLAMA INSTALLATION
# Install Ollama (CPU-only mode will be used automatically if no GPU is found)
RUN curl -fsSL https://ollama.com/install.sh | sh

# 6. PYTHON DEPENDENCIES
# Install PyTorch CPU version explicitly to keep image size small
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    psutil \
    marker-pdf==${MARKER_VERSION} \
    runpod==${RUNPOD_VERSION}

# PRE-DOWNLOAD ALL MARKER & DATALAB MODELS
# This covers layout, OCR, and the error detection models
RUN TORCH_DEVICE=cpu python3 -c "from marker.converters.pdf import PdfConverter; \
    from marker.models import create_model_dict; \
    PdfConverter(artifact_dict=create_model_dict())"

# 7. APPLICATION SETUP
WORKDIR /app
COPY handler.py test-handler.py entrypoint/ ./
RUN chmod +x entrypoint.sh

# 8. START COMMAND
CMD [ "./entrypoint.sh" ]
