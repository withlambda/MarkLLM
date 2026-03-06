#!/bin/bash

set -e

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)

# load functions
. "${SCRIPT_DIR}/functions.sh"

process_list_file -c hf_download -f "${MODELS_FILE:?No models file specified.}"
