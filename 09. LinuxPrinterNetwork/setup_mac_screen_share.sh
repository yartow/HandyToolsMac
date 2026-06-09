#!/usr/bin/env bash
# Run on the Mac (192.168.178.77) to enable VNC Screen Sharing.
# Usage: bash setup_mac_screen_share.sh [vnc_password]
# Example: bash setup_mac_screen_share.sh mypassword123
#
# After this runs:
#   - VNC is available at 192.168.178.77:5900
#   - Linux can connect with the password you set

set -euo pipefail

VNC_PASSWORD="${1:-}"

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

# ── 1. Enable Screen Sharing (VNC) daemon ─────────────────────────────────────
enable_screen_sharing() {
    info "Enabling macOS Screen Sharing (VNC) on port 5900..."

    # Load the Screen Sharing launch daemon
    sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.screensharing.plist 2>/dev/null \
        || sudo launchctl enable system/com.apple.screensharing 2>/dev/null \
        || true

    # Verify it's listening
    sleep 2
    if lsof -nP -iTCP:5900 -sTCP:LISTEN &>/dev/null; then
        info "VNC is listening on port 5900."
    else
        warn "VNC may not be listening yet."
        warn "If this fails, enable manually:"
        warn "  System Settings → General → Sharing → Screen Sharing → ON"
    fi
}

# ── 2. Set VNC password ────────────────────────────────────────────────────────
set_vnc_password() {
    local pass="$1"
    info "Setting VNC password..."

    # macOS stores the VNC-only password as AES-encrypted data
    # This uses the ARD kickstart tool to set it
    if [[ -x /System/Library/CoreServices/RemoteManagement/ARDAgent.app/Contents/Resources/kickstart ]]; then
        sudo /System/Library/CoreServices/RemoteManagement/ARDAgent.app/Contents/Resources/kickstart \
            -configure -clientopts -setvnclegacy -vnclegacy yes -vncpw "$pass" \
            2>/dev/null || warn "Could not set VNC password via kickstart."
    fi

    # Alternative: write password via defaults (macOS Ventura+)
    # The password is stored as 8-byte AES-128 ECB encrypted hex
    # Using Python to generate the encrypted form
    python3 - "$pass" <<'PYEOF'
import sys, struct, subprocess

pw = sys.argv[1].encode()[:8].ljust(8, b'\0')  # max 8 chars, padded

# macOS Screen Sharing uses DES CBC to store VNC password (same as standard VNC)
try:
    from Crypto.Cipher import DES
    # VNC DES key — bit-reversal of the password bytes
    key = bytes([int(f'{b:08b}'[::-1], 2) for b in pw])
    cipher = DES.new(key, DES.MODE_ECB)
    enc = cipher.encrypt(b'\x00' * 8)
    hex_enc = enc.hex().upper()
    result = subprocess.run(
        ['sudo', 'defaults', 'write', '/Library/Preferences/com.apple.RemoteManagement',
         'VNCLegacyPasswordAES', '-data', hex_enc],
        capture_output=True
    )
    if result.returncode == 0:
        print("[INFO]  VNC password set via defaults.")
    else:
        print("[WARN]  Could not write VNC password via defaults (needs pycryptodome).")
except ImportError:
    print("[WARN]  pycryptodome not installed — VNC password not set automatically.")
    print("[INFO]  Set it manually: System Settings → Sharing → Screen Sharing → Computer Settings → VNC viewers may control screen with password")
PYEOF
}

# ── 3. Check firewall ──────────────────────────────────────────────────────────
check_firewall() {
    if /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -q enabled; then
        info "macOS firewall is active. Adding Screen Sharing exception..."
        sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add \
            /System/Library/CoreServices/RemoteManagement/ARDAgent.app 2>/dev/null || true
        sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp \
            /System/Library/CoreServices/RemoteManagement/ARDAgent.app 2>/dev/null || true
        info "Firewall exception added."
    fi
}

# ── 4. Show display layout info ───────────────────────────────────────────────
show_display_info() {
    info "Current display layout (you need to arrange the virtual display leftmost):"
    system_profiler SPDisplaysDataType 2>/dev/null \
        | grep -E "Resolution:|Display Type:|Online:|Main Display:" \
        | sed 's/^/         /'
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    enable_screen_sharing
    check_firewall

    if [[ -n "$VNC_PASSWORD" ]]; then
        set_vnc_password "$VNC_PASSWORD"
    else
        warn "No VNC password given. Set one manually:"
        warn "  System Settings → Sharing → Screen Sharing → Computer Settings"
        warn "  → Enable 'VNC viewers may control screen with password'"
    fi

    show_display_info

    echo ""
    echo "══════════════════════════════════════════════════════════"
    echo "  Mac VNC Setup Complete"
    echo ""
    echo "  Mac IP   : 192.168.178.77"
    echo "  VNC Port : 5900"
    echo ""
    echo "  NEXT STEP — Arrange displays in macOS:"
    echo "  System Settings → Displays → Arrange"
    echo "  Drag the BetterDisplay virtual display to the FAR LEFT"
    echo "  (This ensures the Linux VNC viewer sees only that display)"
    echo "══════════════════════════════════════════════════════════"
}

main "$@"
