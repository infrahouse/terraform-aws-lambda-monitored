#!/usr/bin/env bash
#
# Package Lambda function with dependencies for specified architecture
#
# Usage: package.sh <source_dir> <requirements_file> <output_file> <architecture> <python_version>
#
# Arguments:
#   source_dir        - Directory containing Lambda function source code
#   requirements_file - Path to requirements.txt (optional, use "none" to skip)
#   output_file       - Output ZIP file path
#   architecture      - Target architecture: x86_64 or arm64
#   python_version    - Python version (e.g., python3.12)
#

set -euo pipefail

# Parse arguments
SOURCE_DIR="${1:?Source directory required}"
REQUIREMENTS_FILE="${2:-none}"
OUTPUT_FILE="${3:?Output file required}"
ARCHITECTURE="${4:-x86_64}"
PYTHON_VERSION="${5:-python3.12}"

# Extract Python version number (e.g., python3.12 -> 3.12)
PY_VER="${PYTHON_VERSION#python}"

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

echo "Packaging Lambda function:"
echo "  Source: ${SOURCE_DIR}"
echo "  Requirements: ${REQUIREMENTS_FILE}"
echo "  Output: ${OUTPUT_FILE}"
echo "  Architecture: ${ARCH} (${PLATFORM})"
echo "  Python: ${PYTHON_VERSION} (${PY_VER})"

# Create temporary build directory
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "${BUILD_DIR}"' EXIT

# Copy source files to build directory
echo "Copying source files..."
cp -r "${SOURCE_DIR}"/* "${BUILD_DIR}/"

# Install dependencies if requirements file exists and is not "none"
if [[ "${REQUIREMENTS_FILE}" != "none" ]] && [[ -f "${REQUIREMENTS_FILE}" ]]; then
    echo "Installing dependencies from ${REQUIREMENTS_FILE}..."

    # Install dependencies with platform-specific wheels
    python3 -m pip install \
        --only-binary=:all: \
        --platform "${PLATFORM}" \
        --implementation cp \
        --python-version "${PY_VER}" \
        --target "${BUILD_DIR}" \
        --upgrade \
        -r "${REQUIREMENTS_FILE}"

    echo "Dependencies installed successfully"
else
    echo "No requirements file specified or file not found, skipping dependency installation"
fi

# Clean up Python cache files
echo "Cleaning up Python cache files..."
find "${BUILD_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${BUILD_DIR}" -type f -name "*.pyo" -delete 2>/dev/null || true

# Create output directory if it doesn't exist
OUTPUT_DIR="$(dirname "${OUTPUT_FILE}")"
mkdir -p "${OUTPUT_DIR}"

# Create ZIP file
echo "Creating ZIP archive..."
(cd "${BUILD_DIR}" && zip -q -r - .) > "${OUTPUT_FILE}"

# Get file size
FILE_SIZE="$(du -h "${OUTPUT_FILE}" | cut -f1)"
echo "Package created successfully: ${OUTPUT_FILE} (${FILE_SIZE})"