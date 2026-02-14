PYTHON=python3
BACKEND_DIR=backend
VENV?=.venv

.PHONY: test test-unit test-fast lint format setup

setup:
	cd $(BACKEND_DIR) && $(PYTHON) -m pip install -r requirements.txt

test:
	cd $(BACKEND_DIR) && $(PYTHON) -m pytest

test-unit test-fast:
	cd $(BACKEND_DIR) && $(PYTHON) -m pytest app/tests/unit

lint:
	@echo "TODO: lint (pendiente de definir)"

format:
	@echo "TODO: format (pendiente de definir)"
