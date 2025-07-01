#!/bin/bash

echo "Starting 3D Model Generator GUI..."
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or later"
    exit 1
fi

# Check if required packages are installed
if ! python3 -c "import customtkinter" &> /dev/null; then
    echo "Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error installing packages. Please run: pip3 install -r requirements.txt"
        exit 1
    fi
fi

# Start the GUI
echo "Starting GUI..."
python3 ui.py 