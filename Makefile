# AutoReplenish.ai — task runner
#
# Usage:  make <target>

PYTHON ?= python
SHELL  := /bin/bash

.PHONY: help build clean test test-verbose lint terraform-init terraform-plan terraform-apply deploy check-env

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

build: ## Package backend/ into backend/build/ (Lambda zip root)
	bash build.sh

clean: ## Remove build artifacts and caches
	bash build.sh --clean
	rm -rf infra/build
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true

test: ## Run the unit test suite (moto-emulated AWS)
	cd backend/src/.. && $(PYTHON) -m pytest ../tests -q

test-verbose: ## Run tests with full output
	cd backend/src/.. && $(PYTHON) -m pytest ../tests -v

lint: ## Syntax-check every backend module
	$(PYTHON) -m compileall -q backend/src

terraform-init: ## terraform init in infra/
	cd infra && terraform init

terraform-plan: build ## Build then produce an execution plan
	cd infra && terraform plan -out=tfplan

terraform-apply: terraform-plan ## Build, plan, and apply
	cd infra && terraform apply tfplan

deploy: terraform-apply ## Full deploy

check-env: ## Verify required tooling is available
	@command -v $(PYTHON) >/dev/null || { echo "python: MISSING"; exit 1; }
	@command -v bash >/dev/null || { echo "bash: MISSING"; exit 1; }
	@command -v terraform >/dev/null || { echo "terraform: MISSING (install to deploy)"; } || true
	@echo "python:  $$($(PYTHON) --version 2>&1)"
	@echo "bash:    $$(bash --version 2>&1 | head -1)"
	@echo "aws-cli: $$(command -v aws >/dev/null && aws --version 2>&1 || echo 'not installed (optional)')"
