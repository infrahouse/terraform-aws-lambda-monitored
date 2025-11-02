.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-40s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

TEST_REGION ?= "us-west-2"
TEST_ROLE ?= "arn:aws:iam::303467602807:role/lambda-monitored-tester"
TEST_SELECTOR ?= "test_"
KEEP_AFTER ?=

# Function to run pytest with common parameters
# Args: $(1) = test filter pattern, $(2) = test path, $(3) = force keep-after flag
define run_pytest
	pytest -xvvs \
		--aws-region=${TEST_REGION} \
		--test-role-arn=${TEST_ROLE} \
		$(if $(or $(KEEP_AFTER),$(3)),--keep-after,) \
		-k "$(1) and $(TEST_SELECTOR)" \
		$(2) 2>&1 | tee pytest-`date +%Y%m%d-%H%M%S`-output.log
endef

help: install-hooks
	@python -c "$$PRINT_HELP_PYSCRIPT" < Makefile

.PHONY: install-hooks
install-hooks:  ## Install repo hooks
	@echo "Checking and installing hooks"
	@test -d .git/hooks || (echo "Looks like you are not in a Git repo" ; exit 1)
	@test -L .git/hooks/pre-commit || ln -fs ../../hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

.PHONY: test
test: test-simple test-deps test-monitoring test-sns ## Run all tests (use TEST_SELECTOR to filter, KEEP_AFTER=1 to preserve resources)
	@echo "All tests are done"

.PHONY: test-simple
test-simple:  ## Run simple Lambda tests (use TEST_SELECTOR to filter)
	$(call run_pytest,TestSimpleLambda,tests/test_module.py)

.PHONY: test-deps
test-deps:  ## Run dependency packaging tests (use TEST_SELECTOR to filter)
	$(call run_pytest,TestLambdaWithDependencies,tests/test_module.py)

.PHONY: test-monitoring
test-monitoring:  ## Run error monitoring tests (use TEST_SELECTOR to filter)
	$(call run_pytest,TestErrorMonitoring,tests/test_module.py)

.PHONY: test-sns
test-sns:  ## Run SNS integration tests (use TEST_SELECTOR to filter)
	$(call run_pytest,TestSNSIntegration,tests/test_module.py)

.PHONY: test-x86
test-x86:  ## Run tests for x86_64 architecture only (use TEST_SELECTOR to filter)
	$(call run_pytest,x86,tests/)

.PHONY: test-arm
test-arm:  ## Run tests for arm64 architecture only (use TEST_SELECTOR to filter)
	$(call run_pytest,arm64,tests/)

.PHONY: lint
lint:  ## Check code style
	yamllint .github/workflows
	terraform fmt -check -recursive

.PHONY: bootstrap
bootstrap:  ## Bootstrap the development environment
	pip install -U "pip ~= 25.2"
	pip install -U "setuptools ~= 80.9"
	pip install -r tests/requirements.txt

.PHONY: clean
clean:  ## Clean the repo from cruft
	rm -rf .pytest_cache
	rm -rf test_data
	find . -name '.terraform' -exec rm -fr {} +
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .build
	rm -f pytest-*.log

.PHONY: fmt
fmt: format

.PHONY: format
format:  ## Format terraform and Python files
	@echo "Formatting terraform files"
	terraform fmt -recursive
	@echo "Formatting Python files"
	black tests/
