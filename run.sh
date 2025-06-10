#!/bin/bash

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if the CLI file exists
if [ ! -f "src/cli/simple.py" ]; then
    echo "Error: src/cli/simple.py not found"
    exit 1
fi

# Run the CLI
PYTHONPATH=./src $PYTHON_CMD src/cli/simple.py