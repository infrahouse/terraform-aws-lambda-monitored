#!/usr/bin/env bash
#
# Package Lambda function with dependencies for specified architecture
#
# Usage: package.sh <source_dir> <requirements_file> <output_dir> <architecture> <python_version>
#
# Arguments:
#   source_dir        - Directory containing Lambda function source code
#   requirements_file - Path to requirements.txt (optional, use "none" to skip)
#   output_dir        - Output directory path for prepared package
#   architecture      - Target architecture: x86_64 or arm64
#   python_version    - Python version (e.g., python3.12)
#

set -euo pipefail

# Parse arguments
SOURCE_DIR="${1:?Source directory required}"
REQUIREMENTS_FILE="${2:-none}"
OUTPUT_DIR="${3:?Output directory required}"
ARCHITECTURE="${4:-x86_64}"
PYTHON_VERSION="${5:-python3.12}"

# Extract Python version number (e.g., python3.12 -> 3.12)
PY_VER="${PYTHON_VERSION#python}"

# Check for required commands
check_command() {
    local cmd="$1"
    local install_msg="$2"

    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Required command '$cmd' not found" >&2
        echo "" >&2
        echo "$install_msg" >&2
        echo "" >&2
        return 1
    fi
}

echo "Checking required dependencies..."

# Check for Python
check_command "python3" "To install Python 3:
  - Ubuntu/Debian: sudo apt-get install python3 python3-pip
  - macOS: brew install python3
  - Amazon Linux: sudo yum install python3 python3-pip
  - Windows: Download from https://www.python.org/downloads/"

# Check for pip
check_command "pip3" "To install pip:
  - Ubuntu/Debian: sudo apt-get install python3-pip
  - macOS: python3 -m ensurepip
  - Amazon Linux: sudo yum install python3-pip
  - Windows: python -m ensurepip"

echo "✓ All required dependencies found"

# Normalize architecture and map to manylinux platform tags
case "${ARCHITECTURE}" in
    auto)
        ARCH="$(uname -m)"
        ;;
    arm64|aarch64)
        ARCH="aarch64"
        ;;
    x86_64|amd64)
        ARCH="x86_64"
        ;;
    *)
        echo "Error: Unsupported architecture: ${ARCHITECTURE}" >&2
        exit 1
        ;;
esac

# Map architecture to manylinux platform
case "${ARCH}" in
    aarch64)
        PLATFORM="manylinux2014_aarch64"
        ;;
    x86_64)
        PLATFORM="manylinux2014_x86_64"
        ;;
    *)
        echo "Error: Could not map architecture to manylinux platform: ${ARCH}" >&2
        exit 1
        ;;
esac

echo "Preparing Lambda package:"
echo "  Source: ${SOURCE_DIR}"
echo "  Requirements: ${REQUIREMENTS_FILE}"
echo "  Output: ${OUTPUT_DIR}"
echo "  Architecture: ${ARCH} (${PLATFORM})"
echo "  Python: ${PYTHON_VERSION} (${PY_VER})"

# Get absolute paths for comparison (before creating output dir)
SOURCE_ABS=$(cd "${SOURCE_DIR}" && pwd)

# Normalize OUTPUT_DIR to absolute path
if [ -d "${OUTPUT_DIR}" ]; then
    OUTPUT_ABS=$(cd "${OUTPUT_DIR}" && pwd)
else
    # If output dir doesn't exist, resolve it relative to current directory
    OUTPUT_ABS=$(mkdir -p "${OUTPUT_DIR}" && cd "${OUTPUT_DIR}" && pwd)
fi

# Only clean and copy if source and output are different directories
if [ "${SOURCE_ABS}" = "${OUTPUT_ABS}" ]; then
    echo "Source and output directories are the same, building in place..."
else
    # Clean output directory if it exists
    if [ -d "${OUTPUT_DIR}" ]; then
        echo "Cleaning existing output directory..."
        rm -rf "${OUTPUT_DIR:?}"/*
    else
        # Create output directory if it doesn't exist
        mkdir -p "${OUTPUT_DIR}"
    fi

    # Copy source files to output directory
    echo "Copying source files..."
    cp -r "${SOURCE_DIR}"/* "${OUTPUT_DIR}/"
fi

# Install dependencies if requirements file exists and is not "none"
if [[ "${REQUIREMENTS_FILE}" != "none" ]] && [[ -f "${REQUIREMENTS_FILE}" ]]; then
    echo "Installing dependencies from ${REQUIREMENTS_FILE}..."

    # Install dependencies with platform-specific wheels
    python3 -m pip install \
        --only-binary=:all: \
        --platform "${PLATFORM}" \
        --implementation cp \
        --python-version "${PY_VER}" \
        --target "${OUTPUT_DIR}" \
        --upgrade \
        -r "${REQUIREMENTS_FILE}"

    echo "Dependencies installed successfully"
else
    echo "No requirements file specified or file not found, skipping dependency installation"
fi

# Clean up Python cache files
echo "Cleaning up Python cache files..."
find "${OUTPUT_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${OUTPUT_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${OUTPUT_DIR}" -type f -name "*.pyo" -delete 2>/dev/null || true

echo "Package prepared successfully: ${OUTPUT_DIR}"
