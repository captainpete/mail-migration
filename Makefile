.PHONY: setup lint test format

VENV?=.venv
PYTHON?=python3
PIP?=$(VENV)/bin/pip

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(PIP) install -e .[dev]

setup: $(VENV)/bin/python
	@echo "Virtual environment ready at $(VENV)"

lint: $(VENV)/bin/python
	$(VENV)/bin/python -m ruff check src tests
	$(VENV)/bin/python -m black --check src tests

format: $(VENV)/bin/python
	$(VENV)/bin/python -m ruff check --fix src tests
	$(VENV)/bin/python -m black src tests

test: $(VENV)/bin/python
	$(VENV)/bin/python -m pytest
