#!/bin/bash

set -e

# --- Run Handler ---

echo "Starting RunPod Handler..."
# Execute the Python handler script.
# -u ensures unbuffered output so logs appear immediately.

exec gosu appuser python3 -u "${HANDLER_FILE_NAME}"

# Note: The handler script calls runpod.serverless.start(), which blocks.
# If the handler exits, the container should exit.
