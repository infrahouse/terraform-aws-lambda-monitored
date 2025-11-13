#!/usr/bin/env bash
#
# Package Lambda function with dependencies for specified architecture
#
# Usage: package.sh <source_dir> <requirements_file> <build_dir> <zip_output> <architecture> <python_version>
#
# Arguments:
#   source_dir        - Directory containing Lambda function source code
#   requirements_file - Path to requirements.txt (optional, use "none" to skip)
#   build_dir         - Build directory path for prepared package
#   zip_output        - Output path for the zip file
#   architecture      - Target architecture: x86_64 or arm64
#   python_version    - Python version (e.g., python3.12)
#

set -euo pipefail

# Parse arguments
SOURCE_DIR="${1:?Source directory required}"
REQUIREMENTS_FILE="${2:-none}"
BUILD_DIR="${3:?Build directory required}"
ZIP_OUTPUT="${4:?Zip output path required}"
ARCHITECTURE="${5:-x86_64}"
PYTHON_VERSION="${6:-python3.12}"

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
echo "  Build: ${BUILD_DIR}"
echo "  Zip: ${ZIP_OUTPUT}"
echo "  Architecture: ${ARCH} (${PLATFORM})"
echo "  Python: ${PYTHON_VERSION} (${PY_VER})"

# Get absolute paths for comparison (before creating build dir)
SOURCE_ABS=$(cd "${SOURCE_DIR}" && pwd)

# Create build directory if it doesn't exist
mkdir -p "${BUILD_DIR}"

# Normalize BUILD_DIR to absolute path
BUILD_ABS=$(cd "${BUILD_DIR}" && pwd)

# Only clean and copy if source and build are different directories
if [ "${SOURCE_ABS}" = "${BUILD_ABS}" ]; then
    echo "Source and build directories are the same, building in place..."
else
    # Clean build directory
    echo "Cleaning existing build directory..."
    rm -rf "${BUILD_DIR:?}"/*

    # Copy source files to build directory
    echo "Copying source files..."
    cp -r "${SOURCE_DIR}"/* "${BUILD_DIR}/"
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

# Create zip file
echo "Creating zip file..."
ZIP_DIR=$(dirname "${ZIP_OUTPUT}")
mkdir -p "${ZIP_DIR}"

# Convert ZIP_OUTPUT to absolute path before cd'ing into build directory
ZIP_OUTPUT_ABS=$(cd "${ZIP_DIR}" && pwd)/$(basename "${ZIP_OUTPUT}")

# Create zip from build directory
(cd "${BUILD_DIR}" && zip -q -r "${ZIP_OUTPUT_ABS}" .)

echo "✓ Package created successfully: ${ZIP_OUTPUT_ABS}"
