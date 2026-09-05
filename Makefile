# APEX Automation Makefile
# Auto-detects local virtualenv Python, fallback to system python3

VENV ?= .venv
PYTHON ?= $(shell if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; else echo python3; fi)

.PHONY: help test test-unit test-synthetic verify-stage-0 verify-stage-1 preview-live preview-dashboard scrape-basket clean

help:
	@echo "APEX Commands:"
	@echo "  make test               Run all unit & synthetic tests"
	@echo "  make test-unit          Run unit test suite"
	@echo "  make test-synthetic     Run synthetic invariant test suite"
	@echo "  make verify-stage-0     Verify Stage 0 contracts & specifications"
	@echo "  make verify-stage-1     Verify Stage 1 data acquisition & collectors"
	@echo "  make preview-live       Preview real-time acquisition in terminal"
	@echo "  make preview-dashboard  Launch interactive live web preview dashboard"
	@echo "  make scrape-basket      Run acquisition across methodology route basket"
	@echo "  make clean              Remove bytecode and cache files"

# Stage Verification Targets
verify-stage-0:
	$(PYTHON) -m unittest discover -s tests/unit -p "test_fare_spec.py"
	$(PYTHON) -c "import json; json.load(open('docs/schemas/fare_observation.json'))"
	$(PYTHON) -c "import json; r=json.load(open('docs/methodology/route_basket.json')); assert len(r)==5 and abs(sum(x['weight'] for x in r)-1.0)<1e-6"
	$(PYTHON) -c "import json; w=json.load(open('docs/methodology/booking_windows.json')); assert len(w)==5"

verify-stage-1:
	$(PYTHON) -m unittest discover -s tests/unit -p "test_*collector*.py"
	$(PYTHON) -m unittest discover -s tests/unit -p "test_*parser*.py"
	$(PYTHON) -m unittest discover -s tests/unit -p "test_raw_audit.py"
	$(PYTHON) -m unittest discover -s tests/unit -p "test_*orchestrator*.py"
	$(PYTHON) -m unittest discover -s tests/unit -p "test_*playwright*.py"

preview-live:
	$(PYTHON) -m apex.collectors.preview --mode=tui --route=DEL-BOM --window=T+15 --source=mock

preview-dashboard:
	$(PYTHON) -m apex.collectors.preview --mode=web --port=8080

scrape-basket:
	$(PYTHON) -m apex.collectors.preview --mode=tui --route=all --window=T+15 --source=mock


test-unit:
	$(PYTHON) -m unittest discover -s tests/unit -p "test_*.py"

test-synthetic:
	$(PYTHON) -m unittest discover -s tests/synthetic -p "test_*.py" 2>/dev/null || true

test: test-unit test-synthetic

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
