# Wacom Tablet Configuration for Ubuntu

This toolkit provides scripts to configure your Wacom pen tablet on Ubuntu to behave like the Windows driver, with customizable button mappings.

## Features

- **Button 1**: Right-click (context menu)
- **Button 2**: Middle-click / Scroll button
- **Button 3**: Left-click (if available)
- Auto-detection of Wacom devices
- Optional auto-startup via systemd service
- Sensitive pressure detection for better tap response

## Installation

### Quick Setup (Recommended)

```bash
cd ~/path/to/wacom/directory
chmod +x setup.sh
./setup.sh
```

This will:
1. Install required dependencies (`xsetwacom`, `libxdevice6`, etc.)
2. Test your Wacom device configuration
3. Offer to set up auto-configuration on startup

### Manual Setup

If you prefer to set up manually:

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y xsetwacom libxdevice6 libinput-tools

# Make scripts executable
chmod +x wacom_config.sh wacom_config_advanced.sh

# Run configuration
./wacom_config_advanced.sh
```

## Usage

### Run Configuration Manually

```bash
./wacom_config_advanced.sh
```

### Check Installed Service

If you used the automated setup:

```bash
# Check service status
systemctl status wacom-config

# View logs
journalctl -u wacom-config -f

# Restart service
sudo systemctl restart wacom-config
```

## Button Mapping Details

### Default Configuration

| Button | Function | Action |
|--------|----------|--------|
| Button 1 | Right-click | Opens context menus |
| Button 2 | Middle-click | Scroll in compatible apps |
| Button 3 | Left-click | Primary selection |

### Advanced Scroll Usage

In most applications that support middle-mouse-button scrolling:
1. Hold **Button 2** (pen button)
2. Move your pen up/down to scroll

If an app doesn't support middle-button scrolling natively, you can:
- Use Button 2 for pasting in compatible applications
- Remap buttons in app-specific settings

## Troubleshooting

### Device Not Found

If you get "No Wacom device found":

```bash
# List all input devices
xsetwacom list devices

# Or use xinput to see all devices
xinput list
```

Then manually update the script with your device ID.

### Changes Not Persisting After Reboot

Make sure the systemd service is enabled:

```bash
sudo systemctl enable wacom-config
sudo systemctl status wacom-config
```

### Service Not Starting

Check the systemd service logs:

```bash
journalctl -u wacom-config -f
```

Common issues:
- **DISPLAY not set**: May happen on multi-display setups
- **User permissions**: Service must run as your user (check setup.sh username)
- **X server not ready**: Try waiting longer with `After=` directives

### Manual Configuration

If automated setup fails, you can manually set buttons:

```bash
# Get your device ID (look for pen/stylus)
xsetwacom list devices

# Then use:
xsetwacom set <DEVICE_ID> Button 1 3  # Button 1 = right-click
xsetwacom set <DEVICE_ID> Button 2 2  # Button 2 = middle-click
xsetwacom set <DEVICE_ID> Button 3 1  # Button 3 = left-click
```

## Advanced Configuration

### Adjust Pressure Sensitivity

Edit `wacom_config_advanced.sh` and modify:

```bash
xsetwacom set "$DEVICE_ID" Threshold 10
```

- **Lower values** (1-5): More sensitive, lighter taps trigger
- **Higher values** (15-20): Less sensitive, harder presses needed

### Disable Specific Buttons

To disable a button (useful if you keep accidentally pressing it):

```bash
xsetwacom set <DEVICE_ID> Button <N> 0
```

### View All Settings

```bash
xsetwacom list param <DEVICE_ID>
```

## Scripts Overview

### `setup.sh`
Interactive setup script that installs dependencies and configures systemd auto-start.

### `wacom_config_advanced.sh`
Main configuration script with automatic device detection and comprehensive button setup.

### `wacom_config.sh`
Basic configuration script (simpler version).

### `wacom-config.service`
Systemd service unit file (created/modified during setup).

## Uninstall / Disable

To remove the auto-startup configuration:

```bash
sudo systemctl disable wacom-config
sudo systemctl stop wacom-config
sudo rm /etc/systemd/system/wacom-config.service
sudo systemctl daemon-reload
```

The button configuration will still work manually with `./wacom_config_advanced.sh`.

## Notes

- These scripts use `xsetwacom` which is the standard Wacom configuration tool for X11
- Wayland support may be limited; these scripts are primarily for X11 sessions
- Configurations persist until the next reboot (unless you set up the systemd service)
- Some buttons may not be available depending on your tablet model

## Support

If you encounter issues:

1. Check device detection: `xsetwacom list devices`
2. View service logs: `journalctl -u wacom-config -f`
3. Try running the script manually: `./wacom_config_advanced.sh`
4. Check the Wacom Linux documentation: https://linuxwacom.github.io/
