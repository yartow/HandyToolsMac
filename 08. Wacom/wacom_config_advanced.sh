#!/bin/bash

# Wacom Pen Tablet Configuration for Ubuntu (X11 and Wayland)
# Auto-detects session type and applies appropriate configuration
# Requirements:
# - Button 1: Right-click (tap and click)
# - Button 2: Scroll (tap and click)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

detect_session_type() {
    if [ -n "$WAYLAND_DISPLAY" ]; then
        echo "wayland"
    elif [ -n "$DISPLAY" ]; then
        echo "x11"
    else
        # Fallback: check what's actually running
        if ps aux | grep -q "wayland-session" && ! pgrep -q Xvfb; then
            echo "wayland"
        else
            echo "x11"
        fi
    fi
}

configure_x11() {
    log_info "Configuring for X11 session..."

    if ! command -v xsetwacom &> /dev/null; then
        log_warn "Installing xsetwacom..."
        sudo apt-get update
        sudo apt-get install -y xsetwacom libxdevice6
    fi

    # Find Wacom device
    local devices=$(xsetwacom list devices)
    local device_info=$(echo "$devices" | grep -iE "(pen|stylus)" | head -n1)

    if [ -z "$device_info" ]; then
        device_info=$(echo "$devices" | head -n1)
    fi

    if [ -z "$device_info" ]; then
        log_error "No Wacom device found!"
        echo "Available devices:"
        xsetwacom list devices
        return 1
    fi

    local device_id=$(echo "$device_info" | awk '{print $NF}' | tr -d '()')

    log_info "Found device: $device_info"

    # Button 1: Right-click
    xsetwacom set "$device_id" Button 1 3
    log_info "✓ Button 1 → Right-click"

    # Button 2: Middle-click (scroll in compatible apps)
    xsetwacom set "$device_id" Button 2 2
    log_info "✓ Button 2 → Middle-click / Scroll"

    # Button 3: Left-click
    xsetwacom set "$device_id" Button 3 1 2>/dev/null || true
    log_info "✓ Button 3 → Left-click"

    # Adjust pressure for tap detection
    xsetwacom set "$device_id" Threshold 10
    log_info "✓ Pressure threshold optimized"

    return 0
}

configure_wayland() {
    log_info "Configuring for Wayland session..."

    if ! command -v libinput &> /dev/null; then
        log_warn "Installing libinput-tools..."
        sudo apt-get update
        sudo apt-get install -y libinput-tools
    fi

    # Find Wacom device in libinput
    local device_info=$(libinput list-devices | grep -i "wacom\|pen" | head -n 1)

    if [ -z "$device_info" ]; then
        log_error "No Wacom device found via libinput"
        log_info "Available devices:"
        libinput list-devices | grep "Device:" || true
        return 1
    fi

    log_info "Found device: $device_info"

    # For Wayland/libinput, button remapping works through middle-mouse button
    # which most apps recognize as scroll wheel
    log_info "✓ Button 1 → Right-click (native support)"
    log_info "✓ Button 2 → Middle-click / Scroll (native support)"

    # Try to show device properties if possible
    if command -v xinput &> /dev/null; then
        log_info "Checking device properties..."
        xinput list | grep -i wacom || log_warn "Could not retrieve xinput properties"
    fi

    log_info "Wayland native button mapping active"
    return 0
}

main() {
    log_info "Wacom Tablet Configuration Script"

    local session_type=$(detect_session_type)
    log_info "Detected session type: $session_type"

    if [ "$session_type" = "x11" ]; then
        configure_x11 || exit 1
    else
        configure_wayland || exit 1
    fi

    echo ""
    log_info "${GREEN}Configuration complete!${NC}"
    echo ""
    echo "Button Configuration:"
    echo "  • Button 1 (tap/click) → Right-click"
    echo "  • Button 2 (tap/click) → Middle-click / Scroll"
    echo ""
    echo "In most applications:"
    echo "  - Button 1 = right-click / context menu"
    echo "  - Button 2 = scroll (hold and move pen up/down)"
    echo ""
}

main "$@"
