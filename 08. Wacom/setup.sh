#!/bin/bash

# Setup script for Wacom tablet configuration on Ubuntu
# This script installs dependencies and sets up auto-configuration

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
    header "Wacom Tablet Setup for Ubuntu"

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
    log_info "Installing xsetwacom and related packages..."
    sudo apt-get update
    sudo apt-get install -y xsetwacom libxdevice6 libinput-tools

    # Step 2: Make scripts executable
    header "Step 2: Setting up scripts"
    chmod +x "$SCRIPT_DIR/wacom_config.sh"
    chmod +x "$SCRIPT_DIR/wacom_config_advanced.sh"
    log_info "Scripts are now executable"

    # Step 3: Test configuration
    header "Step 3: Testing configuration"
    log_info "Running configuration test..."
    "$SCRIPT_DIR/wacom_config_advanced.sh"

    # Step 4: Ask about auto-startup
    header "Step 4: Auto-startup setup"
    read -p "Do you want to set up auto-configuration on startup? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_autostart "$SCRIPT_DIR" "$CURRENT_USER"
    else
        log_warn "Skipping auto-startup setup. You can run the script manually with: $SCRIPT_DIR/wacom_config_advanced.sh"
    fi

    header "Setup complete!"
    echo "Quick reference:"
    echo "  • Test configuration: $SCRIPT_DIR/wacom_config_advanced.sh"
    echo "  • Manual run: bash $SCRIPT_DIR/wacom_config.sh"
    echo ""
}

setup_autostart() {
    local script_dir=$1
    local user=$2
    local service_file="/etc/systemd/system/wacom-config.service"
    local service_name="wacom-config"

    log_info "Setting up systemd service for auto-configuration..."

    # Create service file
    sudo tee "$service_file" > /dev/null <<EOF
[Unit]
Description=Configure Wacom Pen Tablet Buttons
After=display-manager.service
BindsTo=display-manager.service

[Service]
Type=oneshot
User=$user
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$user/.Xauthority"
ExecStart=$script_dir/wacom_config_advanced.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

    log_info "Service file created at: $service_file"

    # Enable and start service
    sudo systemctl daemon-reload
    sudo systemctl enable "$service_name"

    read -p "Start the service now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl start "$service_name"
        sleep 1
        if systemctl is-active --quiet "$service_name"; then
            log_info "Service started successfully"
            log_info "View logs with: journalctl -u $service_name -f"
        else
            log_error "Service failed to start. Check logs with: journalctl -u $service_name"
        fi
    fi
}

main "$@"
