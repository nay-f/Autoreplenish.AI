#!/usr/bin/env bash
#
# AutoReplenish.ai — Lambda deployment package builder.
#
# Produces backend/build/ = the root of the Lambda deployment zip:
#
#   backend/build/
#   ├── src/                        <- copied verbatim from backend/src
#   │   ├── handlers/
#   │   ├── services/
#   │   ├── models/
#   │   └── config.py
#   └── <pip-installed dependencies>
#
# Terraform (infra/lambda.tf) then zips this directory. Because src/ sits at
# the zip root, the handlers resolve as `src.handlers.<module>.lambda_handler`.
#
# Usage:
#   bash build.sh                 build the deployment directory
#   bash build.sh --print         print the resolved build dir (used by tooling)
#   bash build.sh --clean         remove backend/build and exit
#   SKIP_PIP=1 bash build.sh       copy sources without reinstalling dependencies
#
# Requirements: Python 3.11+ and pip on PATH.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
SRC_DIR="${BACKEND_DIR}/src"
BUILD_DIR="${BACKEND_DIR}/build"

case "${1:-}" in
  --print)
    printf '%s\n' "${BUILD_DIR}"
    exit 0
    ;;
  --clean)
    echo "Removing ${BUILD_DIR}"
    rm -rf "${BUILD_DIR}"
    exit 0
    ;;
  -h|--help)
    grep '^#' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  "") ;;
  *)
    echo "Unknown option: $1" >&2
    echo "Run 'bash build.sh --help' for usage." >&2
    exit 2
    ;;
esac

# ---- Resolve the interpreter -----------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  for candidate in python python3 python3.11; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      PYTHON_BIN="${candidate}"
      break
    fi
  done
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: no python interpreter found on PATH (tried python, python3, python3.11)." >&2
  exit 1
fi

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "==> Using ${PYTHON_BIN} (${PYTHON_VERSION})"

if [[ "${PYTHON_VERSION}" != "3.11" ]]; then
  echo "WARNING: Lambda runtime is python3.11 but local interpreter is ${PYTHON_VERSION}." >&2
  echo "         Native wheels may not match the target runtime. Use a 3.11 venv if possible." >&2
fi

# ---- 1. Clean previous build ----------------------------------------------
echo "==> Cleaning ${BUILD_DIR}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# ---- 2. Copy application sources ------------------------------------------
echo "==> Copying sources ${SRC_DIR} -> ${BUILD_DIR}/src"
mkdir -p "${SRC_DIR}"
cp -R "${SRC_DIR}/." "${BUILD_DIR}/src/"

# Strip caches so the artifact is deterministic and small.
find "${BUILD_DIR}/src" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}/src" -type f -name '*.py[co]' -delete 2>/dev/null || true

# ---- 3. Install dependencies ----------------------------------------------
# The dependency tree (boto3, botocore, requests, jmespath, urllib3, s3transfer)
# is pure Python, so a plain `pip install --target` builds a package that is
# portable between the build host and the Linux Lambda runtime without needing
# platform-specific wheel selection.
if [[ "${SKIP_PIP:-0}" == "1" ]]; then
  echo "==> SKIP_PIP=1 — skipping dependency installation"
else
  echo "==> Installing backend/requirements.txt into ${BUILD_DIR}"
  "${PYTHON_BIN}" -m pip install \
    --quiet \
    --disable-pip-version-check \
    --no-warn-script-location \
    --target "${BUILD_DIR}" \
    -r "${BACKEND_DIR}/requirements.txt"
fi

# ---- 4. Trim noise ---------------------------------------------------------
find "${BUILD_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -type d \( -name 'tests' -o -name 'test' -o -name '*.dist-info' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -type f -name '*.py[co]' -delete 2>/dev/null || true

# ---- 5. Verify the deployable entry points exist ---------------------------
check_handler() {
  local handler_path="$1"
  if [[ ! -f "${BUILD_DIR}/${handler_path}" ]]; then
    echo "ERROR: expected handler file missing from the package: ${handler_path}" >&2
    exit 1
  fi
}

check_handler "src/handlers/scheduled_eval_handler.py"
check_handler "src/handlers/telegram_webhook_handler.py"
check_handler "src/handlers/sap_worker_handler.py"
check_handler "src/handlers/dashboard_api_handler.py"
check_handler "src/config.py"

# ---- 6. Summary ------------------------------------------------------------
ARTIFACT_SIZE="$(du -sh "${BUILD_DIR}" 2>/dev/null | cut -f1 || echo '?')"
echo ""
echo "Build complete: ${BUILD_DIR} (${ARTIFACT_SIZE})"
echo "Contents:"
( cd "${BUILD_DIR}" && ls -1 | head -20 | sed 's/^/  /' )
echo ""
echo "Next: cd infra && terraform init && terraform apply"
