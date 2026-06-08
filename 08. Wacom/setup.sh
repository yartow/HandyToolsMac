#!/bin/bash

# Setup script for Wacom tablet button configuration on Ubuntu
# Supports both X11 and Wayland sessions

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

header() { echo -e "\n${BLUE}=== $1 ===${NC}\n"; }

main() {
    header "Wacom Tablet Configuration for Ubuntu"

    # Check if running on Ubuntu/Debian
    if [[ ! -f /etc/debian_version ]]; then
        log_error "This script is designed for Ubuntu/Debian. Exiting."
        exit 1
    fi

    # Get current username
    CURRENT_USER=$(whoami)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    log_info "Current user: $CURRENT_USER"
    log_info "Script directory: $SCRIPT_DIR"

    # Step 1: Install dependencies
    header "Step 1: Installing dependencies"
    log_info "Installing required packages..."
    sudo apt-get update
    sudo apt-get install -y xsetwacom libxdevice6 libinput-tools

    # Step 2: Make scripts executable
    header "Step 2: Setting up scripts"
    chmod +x "$SCRIPT_DIR/wacom_config_advanced.sh"
    log_info "Scripts are now executable"

    # Step 3: Test configuration
    header "Step 3: Testing configuration"
    log_info "Running configuration..."
    "$SCRIPT_DIR/wacom_config_advanced.sh"

    header "Setup complete!"
    echo "Your Wacom tablet is now configured:"
    echo "  • Button 1 → Right-click"
    echo "  • Button 2 → Scroll (hold and move pen)"
    echo ""
    echo "To run again manually:"
    echo "  $SCRIPT_DIR/wacom_config_advanced.sh"
}

main "$@"
