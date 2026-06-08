#!/bin/bash

# Diagnostic script for Wacom tablet configuration issues

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

header() { echo -e "\n${BLUE}=== $1 ===${NC}\n"; }
log_pass() { echo -e "${GREEN}✓${NC} $1"; }
log_fail() { echo -e "${RED}✗${NC} $1"; }
log_info() { echo -e "${YELLOW}ℹ${NC} $1"; }

main() {
    header "Wacom Tablet Diagnostic Tool"

    # 1. Check dependencies
    header "Checking Dependencies"
    if command -v xsetwacom &> /dev/null; then
        log_pass "xsetwacom installed"
        xsetwacom --version
    else
        log_fail "xsetwacom NOT found"
    fi

    if command -v xinput &> /dev/null; then
        log_pass "xinput installed"
    else
        log_fail "xinput NOT found"
    fi

    # 2. Check X11 display
    header "Checking X11 Display"
    if [ -n "$DISPLAY" ]; then
        log_pass "DISPLAY set to: $DISPLAY"
    else
        log_fail "DISPLAY not set"
        log_info "This might be a Wayland session or X11 is not running"
    fi

    # 3. List all devices
    header "Listing All Input Devices"
    if command -v xsetwacom &> /dev/null; then
        xsetwacom list devices || log_fail "Could not list xsetwacom devices"
    fi

    # 4. Check for Wacom devices specifically
    header "Searching for Wacom Devices"
    if command -v xinput &> /dev/null; then
        echo "Devices matching 'Wacom' or 'pen':"
        xinput list | grep -iE "(wacom|pen|stylus|tablet)" || log_fail "No Wacom devices found via xinput"
    fi

    # 5. Check systemd service
    header "Checking Systemd Service"
    if systemctl list-unit-files | grep -q wacom-config; then
        log_pass "wacom-config service found"
        systemctl status wacom-config --no-pager 2>&1 | head -n 10
    else
        log_info "wacom-config service not installed (optional)"
    fi

    # 6. Check dmesg for Wacom hardware
    header "Hardware Detection (dmesg logs)"
    echo "Recent Wacom-related hardware events:"
    dmesg | grep -iE "(wacom|usb.*tablet|hid.*wacom)" | tail -n 5 || log_info "No recent Wacom hardware events"

    # 7. Check udev rules
    header "Udev Rules for Wacom"
    if [ -d /etc/udev/rules.d/ ] || [ -d /lib/udev/rules.d/ ]; then
        echo "Searching for Wacom udev rules..."
        find /etc/udev/rules.d/ /lib/udev/rules.d/ -name "*wacom*" 2>/dev/null | while read file; do
            log_info "Found: $file"
        done
        if ! find /etc/udev/rules.d/ /lib/udev/rules.d/ -name "*wacom*" 2>/dev/null | grep -q .; then
            log_info "No Wacom-specific udev rules found (may be built-in)"
        fi
    fi

    # 8. Check Wacom driver
    header "Wacom Driver Information"
    if [ -d /sys/class/hidraw/ ]; then
        echo "HID devices:"
        ls -la /sys/class/hidraw/ 2>/dev/null | grep -v "^total" | while read line; do
            [ -n "$line" ] && echo "  $line"
        done
    fi

    # 9. Environment info
    header "System Information"
    echo "OS: $(lsb_release -ds 2>/dev/null || echo 'Unknown')"
    echo "Kernel: $(uname -r)"
    echo "Session: ${XDG_SESSION_TYPE:-Unknown}"
    if [ -n "$WAYLAND_DISPLAY" ]; then
        log_info "Running Wayland session - may have limited Wacom support"
    fi

    # 10. Interactive device selection
    header "Interactive Device Configuration"
    if command -v xsetwacom &> /dev/null; then
        read -p "Do you want to configure a specific device? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo "Available devices:"
            xsetwacom list devices
            echo ""
            read -p "Enter device ID or name (from list above): " device_input
            if [ -n "$device_input" ]; then
                echo ""
                log_info "Device parameters for: $device_input"
                xsetwacom list param "$device_input" 2>/dev/null || log_fail "Could not retrieve parameters"
            fi
        fi
    fi

    header "Diagnostic Complete"
    echo ""
    echo "Next steps:"
    echo "  1. If no Wacom device is found, ensure your tablet is connected"
    echo "  2. If on Wayland, consider switching to X11 (Wacom support is limited)"
    echo "  3. Check journalctl for errors: journalctl -u wacom-config"
    echo "  4. Run configuration: ./wacom_config_advanced.sh"
    echo ""
}

main "$@"
