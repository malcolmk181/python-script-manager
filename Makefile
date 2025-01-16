# Variables
PYTHON_FORMATTERS = black . ; isort .
APP_FILE = app.py

# Platform-specific Python interpreter resolution
ifeq ($(OS),Windows_NT)
	# On Windows, find python.exe using 'where'
	PYTHON_INTERPRETER := $(shell for %%i in (python.exe) do @where %%i 2>nul | findstr /R /C:".exe" | head -n 1)
else
	# On Unix-like systems, use 'command -v'
	PYTHON_INTERPRETER := $(shell command -v python3 || command -v python)
endif

# Formatting rules
.PHONY: format
format:
	@echo "Running Black and isort..."
	$(PYTHON_INTERPRETER) -m black . && $(PYTHON_INTERPRETER) -m isort .

# Cleaning rules
.PHONY: clean
clean:
ifeq ($(OS),Windows_NT)
	@echo "Cleaning up Python cache and temporary files..."
	@del /s /q __pycache__ 2>nul || true
	@for /r %%f in (*.pyc *.pyo *~) do del "%%f" 2>nul || true
	@for /d %%d in (*.egg-info) do rmdir /s /q "%%d" 2>nul || true
else
	@echo "Cleaning up Python cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
endif

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
