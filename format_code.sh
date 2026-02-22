#!/bin/bash
# Script to format code with black
# Run this before committing to ensure code passes black formatting checks

echo "Formatting code with black..."
echo ""

# Check if black is installed
if ! command -v black &> /dev/null; then
    echo "Black is not installed. Installing..."
    # Try different pip commands
    if command -v pip3 &> /dev/null; then
        pip3 install black
    elif command -v python3 &> /dev/null; then
        python3 -m pip install black
    elif command -v pip &> /dev/null; then
        pip install black
    else
        echo "❌ Error: Could not find pip. Please install black manually:"
        echo "   pip3 install black"
        echo "   or"
        echo "   python3 -m pip install black"
        exit 1
    fi
fi

# Format all Python files
if command -v black &> /dev/null; then
    black app/ tests/
    echo ""
    echo "✅ Code formatting complete!"
    echo "Run 'black --check app/ tests/' to verify formatting."
else
    echo "❌ Error: Black is still not available. Please install it manually:"
    echo "   pip3 install black"
    exit 1
fi
