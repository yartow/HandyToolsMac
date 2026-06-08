# Wacom Pen Tablet Configuration for Ubuntu

Configure your Wacom pen tablet buttons via CLI to enable:
- **Button 1**: Right-click (tap and click)
- **Button 2**: Scroll (tap and click)

Supports both X11 and Wayland sessions with automatic detection.

## Quick Start

```bash
cd ~/path/to/wacom/directory
chmod +x setup.sh
./setup.sh
```

That's it! Your tablet is configured.

## Manual Configuration

If you prefer to run the configuration manually:

```bash
./wacom_config_advanced.sh
```

## How It Works

### Button Mapping

| Button | Action |
|--------|--------|
| Button 1 | Right-click (context menu) |
| Button 2 | Middle-click / Scroll |

### Scrolling

In most applications that support middle-mouse scrolling:
1. Hold **Button 2** (pen button)
2. Move your pen up/down to scroll

## Session Detection

The script automatically detects your session type:
- **X11**: Uses `xsetwacom` for button mapping
- **Wayland**: Uses native libinput button mapping

## Troubleshooting

### Check Your Session Type

```bash
# X11
echo $DISPLAY

# Wayland
echo $WAYLAND_DISPLAY
```

### List Connected Wacom Devices

```bash
# For X11
xsetwacom list devices

# For Wayland
libinput list-devices | grep -i wacom
```

### Re-run Configuration

```bash
./wacom_config_advanced.sh
```

Check the output for any errors. If your device isn't detected, please verify it's connected and run the device listing commands above.

## What Gets Installed

- `xsetwacom` — X11 button mapping tool
- `libinput-tools` — Wayland input device tools
- `libxdevice6` — X11 device library

## Scripts

- **setup.sh** — One-time setup installer
- **wacom_config_advanced.sh** — Configuration script (works on X11 and Wayland)
- **diagnose.sh** — Troubleshooting and device detection tool

## Notes

- Configuration persists until next manual change
- Works on both X11 and Wayland sessions
- Pen pressure sensitivity is optimized for tap detection
- For additional Wacom settings, use your system's input settings GUI
