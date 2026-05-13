.PHONY: help install run test test-backend test-frontend build clean dist-clean

# Defaults — override via `make run PY=python3.12` etc.
PY ?= python3
PIP ?= $(PY) -m pip
PROJECT_ROOT := $(shell pwd)
FRONTEND_DIR := $(PROJECT_ROOT)/Frontend
BACKEND_DIR := $(PROJECT_ROOT)/Backend

# PYTHONPATH that mirrors the sys.path hacks the code already does.
RUNTIME_PYPATH := $(PROJECT_ROOT):$(FRONTEND_DIR):$(BACKEND_DIR)

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install:  ## install all runtime + build dependencies
	@echo ">> installing dependencies from root requirements.txt"
	$(PIP) install -r requirements.txt

run:  ## launch the dashboard
	@echo ">> launching Frontend/main.py"
	PYTHONPATH=$(RUNTIME_PYPATH) $(PY) $(FRONTEND_DIR)/main.py

test: test-backend test-frontend  ## run both test suites
	@echo ">> finished running all tests"

test-backend:  ## run Backend/tests
	@echo ">> running Backend/tests via unittest discover"
	cd $(BACKEND_DIR) && PYTHONPATH=$(PROJECT_ROOT):$(BACKEND_DIR) $(PY) -m unittest discover tests

test-frontend:  ## run Frontend/tests
	@echo ">> running Frontend/tests via unittest discover"
	cd $(FRONTEND_DIR) && PYTHONPATH=$(PROJECT_ROOT):$(FRONTEND_DIR) $(PY) -m unittest discover tests

build:  ## build the .app / .exe via PyInstaller
	@echo ">> building application via PyInstaller (ConflictChecker.spec)"
	$(PY) -m PyInstaller ConflictChecker.spec --clean --noconfirm

clean:  ## remove pyinstaller build/ and pyc caches
	@echo ">> removing build/ and __pycache__ trees"
	rm -rf build __pycache__ */__pycache__ */*/__pycache__ */*/*/__pycache__
	find . -name "*.pyc" -not -path "./.git/*" -not -path "./.venv/*" -delete

dist-clean: clean  ## also remove dist/
	@echo ">> removing dist/"
	rm -rf dist
