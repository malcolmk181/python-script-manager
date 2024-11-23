# Variables
PYTHON_FORMATTERS = black . ; isort .

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

# Default target
.PHONY: all
all: format
