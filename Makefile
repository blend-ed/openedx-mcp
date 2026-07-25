.PHONY: help test quality validate test.requirements upgrade clean

help: ## show this help
	@grep -E '^[a-zA-Z._-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n",$$1,$$2}'

test.requirements: ## install test dependencies
	pip install -r requirements/test.txt

test: ## run the test suite (platform-free: models, admin, auth, rails)
	pytest

quality: ## lint with ruff
	ruff check openedx_mcp tests

validate: quality test ## lint + test

clean: ## remove build/coverage artifacts
	rm -rf .pytest_cache .coverage htmlcov build dist *.egg-info

upgrade: ## (optional) pin requirements with pip-tools
	@echo "pip install pip-tools && pip-compile requirements/base.in && pip-compile requirements/test.in"
