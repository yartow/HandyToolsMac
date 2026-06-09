#!/usr/bin/env bash
# Install and configure Remmina VNC to show the Mac's virtual display
# on the Linux machine's monitor.
#
# How it works:
#   - Mac runs Screen Sharing (VNC) and has a BetterDisplay virtual display
#     arranged as the LEFTMOST display in macOS Display Settings
#   - Remmina connects to Mac's VNC in scrolled-fullscreen at 1:1 zoom
#   - Since the virtual display is at coordinate (0,0) and matches the Linux
#     monitor's resolution, Remmina shows exactly that display — nothing else
#
# Run as: bash setup_network_display_linux.sh [linux_monitor_resolution]
# Example: bash setup_network_display_linux.sh 1920x1080
#
# Defaults to 1920x1080 if no resolution given.

set -euo pipefail

MAC_IP="192.168.178.77"
MAC_VNC_PORT="5900"
RESOLUTION="${1:-1920x1080}"
DISPLAY_NAME="Mac_Virtual_Display"

WIDTH="${RESOLUTION%%x*}"
HEIGHT="${RESOLUTION##*x}"

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

# ── 1. Install Remmina and VNC plugin ─────────────────────────────────────────
install_remmina() {
    info "Installing Remmina VNC client..."

    # Remove snap version if present — it breaks on Wayland (sandbox blocks
    # the Wayland socket and uses a different config path than ~/.local/share/remmina)
    if snap list remmina &>/dev/null 2>&1; then
        info "Removing broken snap version of Remmina..."
        sudo snap remove remmina 2>/dev/null || true
    fi

    # Use apt + PPA — works reliably on GNOME Wayland
    sudo apt-get install -y -qq software-properties-common
    sudo add-apt-repository -y ppa:remmina-ppa-team/remmina-next 2>/dev/null || true
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        remmina \
        remmina-plugin-vnc \
        remmina-plugin-rdp \
        libvncclient1 \
        libsecret-1-0
    info "Remmina installed via apt."
}

# ── 2. Create the Remmina VNC connection profile ──────────────────────────────
create_remmina_profile() {
    local profile_dir="$HOME/.local/share/remmina"
    mkdir -p "$profile_dir"

    local profile_file="$profile_dir/${DISPLAY_NAME}.remmina"

    info "Creating Remmina profile: $profile_file"
    info "Connecting to Mac at $MAC_IP:$MAC_VNC_PORT, resolution ${WIDTH}x${HEIGHT}"

    cat > "$profile_file" <<EOF
[remmina]
name=${DISPLAY_NAME}
group=Network Display
protocol=VNC
server=${MAC_IP}:${MAC_VNC_PORT}
username=
password=
colordepth=24
quality=9

# viewmode 2 = SCROLLED_FULLSCREEN
# The window fills the local monitor but does NOT scale the remote desktop.
# The remote desktop is shown 1:1 starting from coordinate (0,0).
# Since the Mac virtual display is arranged leftmost (at 0,0) and its
# resolution matches the Linux monitor (${WIDTH}x${HEIGHT}), you see
# exactly the virtual display and nothing else.
viewmode=2

# Disable all scaling so pixels are 1:1
scale=0
aspectscale=0

# Initial window/viewport size matches the virtual display
resolution_width=${WIDTH}
resolution_height=${HEIGHT}

# Do NOT ask macOS to resize — that would resize all Mac displays
disableclipboard=0
disablepasswordstoring=0
showcursor=1
viewonly=0

# Performance: disable compression on LAN (faster)
vnc_encodings=copyrect hextile zrle ultra
EOF

    info "Profile saved."
}

# ── 3. Create a launch script ─────────────────────────────────────────────────
create_launch_script() {
    local script="$HOME/connect_mac_display.sh"
    cat > "$script" <<'SCRIPT'
#!/usr/bin/env bash
# Launch the Mac virtual display VNC session full-screen.
# Works on GNOME Wayland — sets display environment before launching Remmina.

# On Wayland the display socket lives in XDG_RUNTIME_DIR.
# SSH sessions and some terminals don't inherit these from the login session.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

# Verify Wayland socket exists; fall back to XWayland if not
if [[ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]]; then
    echo "[WARN] Wayland socket not found at $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"
    echo "[WARN] Trying X11 fallback..."
    export GDK_BACKEND=x11
    export DISPLAY="${DISPLAY:-:0}"
fi

PROFILE="$HOME/.local/share/remmina/Mac_Virtual_Display.remmina"

if [[ ! -f "$PROFILE" ]]; then
    echo "[ERROR] Profile not found: $PROFILE"
    echo "Run setup_network_display_linux.sh first."
    exit 1
fi

# Kill any stale snap remmina (different binary path, breaks with our config)
if pgrep -f "snap/remmina" &>/dev/null; then
    pkill -f "snap/remmina" || true
    sleep 1
fi

echo "[INFO] Launching Remmina → Mac virtual display..."
exec remmina -c "$PROFILE"
SCRIPT
    chmod +x "$script"
    info "Launch script saved: $script"
    info "Run it any time with:  bash ~/connect_mac_display.sh"
}

# ── 4. Create a desktop shortcut ──────────────────────────────────────────────
create_desktop_shortcut() {
    local desktop="$HOME/Desktop"
    mkdir -p "$desktop"

    cat > "$desktop/Mac Virtual Display.desktop" <<EOF
[Desktop Entry]
Name=Mac Virtual Display
Comment=Connect to MacBook extended display
Exec=bash $HOME/connect_mac_display.sh
Icon=preferences-desktop-display
Terminal=false
Type=Application
Categories=Network;RemoteAccess;
EOF
    chmod +x "$desktop/Mac Virtual Display.desktop"
    info "Desktop shortcut created."
}

# ── 5. Quick connectivity check ───────────────────────────────────────────────
check_mac_reachable() {
    info "Checking Mac at $MAC_IP..."
    if ping -c1 -W2 "$MAC_IP" &>/dev/null; then
        info "Mac is reachable."
        if nc -z -w2 "$MAC_IP" "$MAC_VNC_PORT" &>/dev/null; then
            info "VNC port $MAC_VNC_PORT is open — Screen Sharing is active."
        else
            warn "VNC port $MAC_VNC_PORT is not open yet."
            warn "Enable on Mac: System Settings → General → Sharing → Screen Sharing ON"
        fi
    else
        warn "Cannot reach Mac at $MAC_IP. Check both machines are on the same network."
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    info "Setting up network display (${WIDTH}x${HEIGHT}) → Mac at $MAC_IP"

    install_remmina
    create_remmina_profile
    create_launch_script
    create_desktop_shortcut
    check_mac_reachable

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Linux side ready!"
    echo ""
    echo "  Launch the display with:"
    echo "    bash ~/connect_mac_display.sh"
    echo "  Or double-click 'Mac Virtual Display' on the Desktop."
    echo ""
    echo "  IMPORTANT — on the Mac, before connecting:"
    echo "  1. Open BetterDisplay → create a virtual display"
    echo "     at ${WIDTH}x${HEIGHT} (your Linux monitor's resolution)"
    echo "  2. System Settings → Displays → Arrangement:"
    echo "     DRAG the virtual display to the FAR LEFT position"
    echo "  3. System Settings → Sharing → Screen Sharing: ON"
    echo "     → Computer Settings → set a VNC password"
    echo "════════════════════════════════════════════════════════════"
}

main "$@"
