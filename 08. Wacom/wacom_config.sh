#!/bin/bash

# Wacom Pen Tablet Configuration Script for Ubuntu
# This script configures Wacom pen tablet buttons to match Windows behavior
# Button 1: Tap and Right-click
# Button 2: Scroll button

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if xsetwacom is installed
if ! command -v xsetwacom &> /dev/null; then
    log_error "xsetwacom is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y xsetwacom
fi

# Get Wacom device ID
log_info "Searching for Wacom devices..."
WACOM_ID=$(xsetwacom list devices | grep -i "pen" | head -n1 | awk '{print $1}')

if [ -z "$WACOM_ID" ]; then
    WACOM_ID=$(xsetwacom list devices | grep -i "stylus" | head -n1 | awk '{print $1}')
fi

if [ -z "$WACOM_ID" ]; then
    log_error "No Wacom pen device found. Available devices:"
    xsetwacom list devices
    exit 1
fi

log_info "Found Wacom device: $WACOM_ID"

# Get the device ID number
DEVICE_ID=$(echo "$WACOM_ID" | awk '{print $NF}' | tr -d '()')

if [ -z "$DEVICE_ID" ]; then
    log_error "Could not extract device ID"
    exit 1
fi

log_info "Device ID: $DEVICE_ID"

# Configure buttons
log_info "Configuring button mappings..."

# Button 1: Set to right-click (button 3)
xsetwacom set $DEVICE_ID Button 1 3
log_info "Button 1 → Right-click"

# Button 2: Set to scroll mode (button 2 with modifier support)
# Using button 2 for middle-click which can be used for scrolling in many apps
xsetwacom set $DEVICE_ID Button 2 2
log_info "Button 2 → Middle-click (scroll in compatible apps)"

# Button 3 (if exists): Set to left-click
xsetwacom set $DEVICE_ID Button 3 1 2>/dev/null || true
log_info "Button 3 → Left-click (if available)"

# Optional: Adjust pressure sensitivity for better tap detection
# Decrease threshold for more sensitive taps (range 0-2048, lower = more sensitive)
xsetwacom set $DEVICE_ID Threshold 10
log_info "Pressure threshold adjusted for better tap detection"

log_info "${GREEN}Wacom tablet configuration complete!${NC}"
log_info "Button mappings applied:"
echo "  • Button 1 → Right-click"
echo "  • Button 2 → Middle-click (for scrolling)"
echo "  • Button 3 → Left-click (if available)"

# Check current settings
echo ""
log_info "Current settings:"
xsetwacom get $DEVICE_ID Button 1
xsetwacom get $DEVICE_ID Button 2
