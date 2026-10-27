param(
    [string]$Output = "build/lambda.zip",
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$stage = Join-Path $root "build/lambda-stage"
$outputPath = Join-Path $root $Output

if (Test-Path $stage) {
    Remove-Item -Recurse -Force $stage
}
New-Item -ItemType Directory -Force $stage | Out-Null
New-Item -ItemType Directory -Force (Split-Path $outputPath) | Out-Null

Write-Host "Building Linux-compatible Lambda artifact with Python $PythonVersion."
Write-Host "Run this script in Linux/WSL or CI for production deployment."

docker run --rm `
    -v "${root}:/src" `
    -w /src `
    "public.ecr.aws/lambda/python:$PythonVersion" `
    /bin/bash -lc "rm -rf /src/build/lambda-stage /src/build/lambda.zip && mkdir -p /src/build/lambda-stage && cp -R /src/backend /src/build/lambda-stage/backend && pip install --no-cache-dir -r /src/backend/requirements-lambda.txt -t /src/build/lambda-stage && python -c 'import pathlib, zipfile; root=pathlib.Path(\"/src/build/lambda-stage\"); z=zipfile.ZipFile(\"/src/build/lambda.zip\", \"w\", zipfile.ZIP_DEFLATED); [z.write(p, p.relative_to(root)) for p in root.rglob(\"*\") if p.is_file()]; z.close()'"

if (-not (Test-Path $outputPath)) {
    throw "Lambda artifact was not created: $outputPath"
}

Write-Host "Created $outputPath"
