#!/usr/bin/env bash
# Quick fix: replace snap Remmina with apt version, update launch script.
# Run on the Linux machine: bash fix_remmina_wayland.sh

set -euo pipefail
info() { echo "[INFO]  $*"; }

# 1. Remove the snap version
if snap list remmina &>/dev/null 2>&1; then
    info "Removing snap Remmina (broken on Wayland)..."
    sudo snap remove remmina
fi

# 2. Install apt version from PPA
info "Installing Remmina via apt..."
sudo apt-get install -y -qq software-properties-common
sudo add-apt-repository -y ppa:remmina-ppa-team/remmina-next 2>/dev/null || true
sudo apt-get update -qq
sudo apt-get install -y -qq remmina remmina-plugin-vnc libvncclient1 libsecret-1-0
info "Remmina $(remmina --version 2>&1 | head -1) installed."

# 3. Overwrite the launch script with a Wayland-aware version
cat > "$HOME/connect_mac_display.sh" <<'SCRIPT'
#!/usr/bin/env bash
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

if [[ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]]; then
    echo "[WARN] Wayland socket not found — trying X11 fallback..."
    export GDK_BACKEND=x11
    export DISPLAY="${DISPLAY:-:0}"
fi

PROFILE="$HOME/.local/share/remmina/Mac_Virtual_Display.remmina"
[[ -f "$PROFILE" ]] || { echo "[ERROR] Profile missing: $PROFILE"; exit 1; }

exec remmina -c "$PROFILE"
SCRIPT
chmod +x "$HOME/connect_mac_display.sh"
info "Launch script updated: ~/connect_mac_display.sh"

echo ""
echo "Done. Now run:  bash ~/connect_mac_display.sh"
