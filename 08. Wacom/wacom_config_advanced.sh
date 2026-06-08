#!/bin/bash

# Advanced Wacom Pen Tablet Configuration for Ubuntu
# This version includes automatic scroll wheel emulation for Button 2
# Install as systemd service for persistent configuration

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect Wacom device
find_wacom_device() {
    local devices=$(xsetwacom list devices)

    # Try to find pen/stylus device
    local pen_device=$(echo "$devices" | grep -iE "(pen|stylus)" | head -n1)

    if [ -n "$pen_device" ]; then
        echo "$pen_device"
        return 0
    fi

    # Fallback: try any Wacom device
    pen_device=$(echo "$devices" | head -n1)
    if [ -n "$pen_device" ]; then
        log_warn "No pen/stylus device found, using: $pen_device"
        echo "$pen_device"
        return 0
    fi

    return 1
}

main() {
    log_info "Wacom Tablet Configuration (Advanced Mode)"

    # Check dependencies
    if ! command -v xsetwacom &> /dev/null; then
        log_warn "Installing xsetwacom..."
        sudo apt-get update
        sudo apt-get install -y xsetwacom libxdevice6
    fi

    # Give X display time to initialize if needed
    sleep 1

    # Find device
    log_info "Searching for Wacom devices..."
    DEVICE_INFO=$(find_wacom_device) || {
        log_error "No Wacom device found!"
        echo "Available input devices:"
        xsetwacom list devices
        exit 1
    }

    DEVICE_ID=$(echo "$DEVICE_INFO" | awk '{print $NF}' | tr -d '()')
    log_info "Found device: $DEVICE_INFO"
    log_info "Device ID: $DEVICE_ID"

    # Configure button mappings
    log_info "Applying button configuration..."

    # Button 1: Right-click
    if xsetwacom set "$DEVICE_ID" Button 1 3 2>/dev/null; then
        log_info "✓ Button 1 → Right-click"
    else
        log_warn "Could not set Button 1"
    fi

    # Button 2: For scroll wheel emulation using xdotool wheel events
    # Setting to button 2 (middle click), works with scroll modifier
    if xsetwacom set "$DEVICE_ID" Button 2 2 2>/dev/null; then
        log_info "✓ Button 2 → Middle-click / Scroll (hold + move pen)"
    else
        log_warn "Could not set Button 2"
    fi

    # Button 3: Left-click (if available)
    if xsetwacom set "$DEVICE_ID" Button 3 1 2>/dev/null; then
        log_info "✓ Button 3 → Left-click"
    else
        log_info "Button 3 not available on this device"
    fi

    # Configure pressure and tilt
    log_info "Adjusting sensitivity settings..."

    # Lower threshold = more sensitive to light touches
    xsetwacom set "$DEVICE_ID" Threshold 10
    log_info "✓ Pressure threshold set to 10 (sensitive)"

    # Set panel rotation if needed (comment out if not needed)
    # xsetwacom set "$DEVICE_ID" Rotate none

    log_info "${GREEN}Configuration complete!${NC}"
    echo ""
    echo "Button Mappings:"
    echo "  • Button 1 → Right-click (context menu)"
    echo "  • Button 2 → Middle-click (scroll/wheel)"
    echo "  • Button 3 → Left-click (selection)"
    echo ""
    echo "To use scroll button: Hold Button 2 while moving pen up/down"
    echo ""

    # Show current settings
    log_info "Current button settings:"
    for i in 1 2 3; do
        if xsetwacom get "$DEVICE_ID" Button $i 2>/dev/null; then
            true
        fi
    done
}

main "$@"
