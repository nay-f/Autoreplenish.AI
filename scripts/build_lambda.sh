#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${ROOT}/build/lambda.zip"
STAGE="${ROOT}/build/lambda-stage"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

rm -rf "${STAGE}" "${OUTPUT}"
mkdir -p "${STAGE}" "${ROOT}/build"

docker run --rm \
  -v "${ROOT}:/src" \
  -w /src \
  "public.ecr.aws/lambda/python:${PYTHON_VERSION}" \
  /bin/bash -lc "cp -R /src/backend /src/build/lambda-stage/backend && pip install --no-cache-dir -r /src/backend/requirements-lambda.txt -t /src/build/lambda-stage && python -c 'import pathlib, zipfile; root=pathlib.Path(\"/src/build/lambda-stage\"); z=zipfile.ZipFile(\"/src/build/lambda.zip\", \"w\", zipfile.ZIP_DEFLATED); [z.write(p, p.relative_to(root)) for p in root.rglob(\"*\") if p.is_file()]; z.close()'"

test -f "${OUTPUT}"
echo "Created ${OUTPUT}"
