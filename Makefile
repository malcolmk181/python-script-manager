# Variables
PYTHON_FORMATTERS = black . ; isort .
APP_FILE = app.py

# Platform-specific Python interpreter resolution
PYTHON_INTERPRETER := $(shell command -v python3 || command -v python)

# Formatting rules
.PHONY: format
format:
	@echo "Running Black and isort..."
	$(PYTHON_FORMATTERS)

# Cleaning rules
.PHONY: clean
clean:
	@echo "Cleaning up Python cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Running the app
.PHONY: run
run:
ifndef PYTHON_INTERPRETER
	@echo "Error: No Python interpreter found. Please ensure Python is installed and in your PATH." && exit 1
endif
	@echo "Using Python interpreter: $(PYTHON_INTERPRETER)"
	$(PYTHON_INTERPRETER) $(APP_FILE)

# Default target
.PHONY: all
all: format
