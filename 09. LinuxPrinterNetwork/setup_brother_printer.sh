#!/usr/bin/env bash
# Setup Brother DCP-L3550CDW as a shared CUPS print server on Ubuntu/Debian
# Run as: sudo bash setup_brother_printer.sh [PRINTER_IP]
# Example: sudo bash setup_brother_printer.sh 192.168.178.50
#
# After this runs, Windows machines can print via:
#   IPP:   http://192.168.178.203:631/printers/Brother_DCP-L3550CDW
#   SMB:   \\192.168.178.203\Brother_DCP-L3550CDW

set -euo pipefail

PRINTER_IP="${1:-}"
PRINTER_NAME="Brother_DCP-L3550CDW"
LINUX_HOST_IP="192.168.178.203"

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "Run this script with sudo: sudo bash $0"
}

# ── 1. Discover printer IP if not provided ───────────────────────────────────
discover_printer_ip() {
    info "Scanning network for Brother DCP-L3550CDW..."
    if command -v avahi-browse &>/dev/null; then
        local found
        found=$(avahi-browse -r -t _ipp._tcp 2>/dev/null | grep -i "DCP-L3550CDW" | grep -oP '192\.168\.\d+\.\d+' | head -1 || true)
        if [[ -n "$found" ]]; then
            echo "$found"
            return 0
        fi
    fi
    # Fallback: ping-scan common range
    info "Trying ping scan 192.168.178.1-254 (slow, ~30s)..."
    for i in $(seq 1 254); do
        local ip="192.168.178.$i"
        if ping -c1 -W1 "$ip" &>/dev/null; then
            # Check if port 631 (IPP) or 9100 (raw printing) is open
            if nc -z -w1 "$ip" 631 &>/dev/null || nc -z -w1 "$ip" 9100 &>/dev/null; then
                echo "$ip"
                return 0
            fi
        fi
    done
    return 1
}

# ── 2. Install CUPS and dependencies ─────────────────────────────────────────
install_cups() {
    info "Installing CUPS and network tools..."
    apt-get update -qq
    apt-get install -y -qq \
        cups \
        cups-client \
        cups-filters \
        avahi-daemon \
        avahi-utils \
        printer-driver-cups-pdf \
        netcat-openbsd \
        wget \
        ghostscript
    info "CUPS installed."
}

# ── 3. Download and install Brother driver ───────────────────────────────────
install_brother_driver() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap "rm -rf $tmpdir" EXIT

    info "Downloading Brother all-in-one Linux installer..."
    cd "$tmpdir"

    # Official Brother installer — downloads the right driver packages automatically
    local installer="linux-brprinter-installer-2.2.3-1"
    wget -q "https://download.brother.com/welcome/dlf104515/${installer}.gz" -O "${installer}.gz" \
        || die "Failed to download Brother installer. Check your internet connection."

    gunzip "${installer}.gz"
    chmod +x "$installer"

    info "Running Brother driver installer for DCP-L3550CDW (this may take a minute)..."
    # The installer is interactive; we pre-answer the prompts:
    #   - Model name: DCP-L3550CDW
    #   - Will you specify the Device URI? -> no (0)
    printf "DCP-L3550CDW\n0\n" | bash "$installer" DCP-L3550CDW || {
        warn "Brother installer exited non-zero; verifying driver presence..."
    }

    # Verify the PPD was installed
    if ls /usr/share/cups/model/Brother/*.ppd 2>/dev/null | grep -qi "l3550\|DCP"; then
        info "Brother driver PPD found."
    elif ls /usr/share/ppd/brother/*.ppd 2>/dev/null | grep -qi "l3550\|DCP"; then
        info "Brother driver PPD found."
    else
        warn "Brother PPD not found in standard locations. The driver may still work."
        warn "Check: find /usr/share -name '*.ppd' | grep -i brother"
    fi
}

# ── 4. Add printer to CUPS ───────────────────────────────────────────────────
add_printer_to_cups() {
    local ip="$1"
    info "Adding $PRINTER_NAME at $ip to CUPS..."

    # Find the PPD file for DCP-L3550CDW
    local ppd
    ppd=$(find /usr/share/cups/model /usr/share/ppd -name "*.ppd" 2>/dev/null \
        | grep -i "l3550\|DCP-L3550CDW" | head -1 || true)

    if [[ -z "$ppd" ]]; then
        # Try compressed PPDs
        ppd=$(find /usr/share/cups/model /usr/share/ppd -name "*.ppd.gz" 2>/dev/null \
            | grep -i "l3550\|DCP-L3550CDW" | head -1 || true)
    fi

    # Use socket (port 9100) for direct network printing — most reliable for Brother
    local device_uri="socket://${ip}:9100"

    if [[ -n "$ppd" ]]; then
        info "Using PPD: $ppd"
        lpadmin -p "$PRINTER_NAME" \
            -E \
            -v "$device_uri" \
            -P "$ppd" \
            -D "Brother DCP-L3550CDW" \
            -L "Network Printer" \
            -o media=A4 \
            -o sides=one-sided \
            -o ColorModel=Color
    else
        warn "No PPD found — adding printer with generic IPP driver."
        warn "Run 'sudo bash setup_brother_printer.sh $ip' again after confirming driver install."
        lpadmin -p "$PRINTER_NAME" \
            -E \
            -v "$device_uri" \
            -m everywhere \
            -D "Brother DCP-L3550CDW" \
            -L "Network Printer"
    fi

    # Set as default printer
    lpoptions -d "$PRINTER_NAME"
    cupsaccept "$PRINTER_NAME"
    cupsenable "$PRINTER_NAME"
    info "Printer added and enabled."
}

# ── 5. Configure CUPS for network sharing ────────────────────────────────────
configure_cups_sharing() {
    info "Configuring CUPS for network sharing..."
    local cfg="/etc/cups/cupsd.conf"
    cp "$cfg" "${cfg}.bak.$(date +%s)"

    # Replace the Listen line to also listen on the network interface
    # and open up access from the local subnet
    python3 - "$cfg" "$LINUX_HOST_IP" <<'PYEOF'
import sys, re

path = sys.argv[1]
host_ip = sys.argv[2]
subnet = ".".join(host_ip.split(".")[:3]) + ".0/24"

with open(path) as f:
    content = f.read()

# Make CUPS listen on all interfaces (not just localhost)
content = re.sub(r'^Listen\s+localhost:\d+', 'Listen 0.0.0.0:631', content, flags=re.MULTILINE)
content = re.sub(r'^Listen\s+/run/cups/cups\.sock', 'Listen /run/cups/cups.sock', content, flags=re.MULTILINE)

# Enable sharing
content = re.sub(r'Browsing\s+\w+', 'Browsing On', content)
content = re.sub(r'BrowseLocalProtocols\s+.*', 'BrowseLocalProtocols dnssd', content)

# Add sharing directive if missing
if 'ServerAlias' not in content:
    content = content.replace('LogLevel warn', 'LogLevel warn\nServerAlias *')

# Update <Location /> to allow subnet access
loc_root = re.search(r'<Location\s+/\s*>(.*?)</Location>', content, re.DOTALL)
if loc_root:
    new_loc = f"""<Location />
  Order allow,deny
  Allow localhost
  Allow {subnet}
</Location>"""
    content = content[:loc_root.start()] + new_loc + content[loc_root.end():]

# Update <Location /admin> to allow subnet access
loc_admin = re.search(r'<Location\s+/admin\s*>(.*?)</Location>', content, re.DOTALL)
if loc_admin:
    new_admin = f"""<Location /admin>
  Order allow,deny
  Allow localhost
  Allow {subnet}
</Location>"""
    content = content[:loc_admin.start()] + new_admin + content[loc_admin.end():]

with open(path, 'w') as f:
    f.write(content)

print("cupsd.conf updated.")
PYEOF

    # Enable printer sharing globally
    cupsctl --share-printers --remote-any

    # Mark the printer as shared
    lpadmin -p "$PRINTER_NAME" -o printer-is-shared=true 2>/dev/null || true

    systemctl restart cups
    systemctl enable cups
    info "CUPS configured and restarted."
}

# ── 6. Configure Samba for Windows printing ──────────────────────────────────
install_samba_print_share() {
    info "Installing Samba for Windows SMB printer sharing..."
    apt-get install -y -qq samba samba-client

    local smb_cfg="/etc/samba/smb.conf"
    cp "$smb_cfg" "${smb_cfg}.bak.$(date +%s)"

    # Append printer share config (idempotent: remove existing block first)
    python3 - "$smb_cfg" "$PRINTER_NAME" <<'PYEOF'
import sys, re

path = sys.argv[1]
printer_name = sys.argv[2]

with open(path) as f:
    content = f.read()

# Remove any existing [printers] and [print$] sections we may have added
content = re.sub(r'\n#=== BEGIN CUPS PRINTER SHARE ===(.*?)#=== END CUPS PRINTER SHARE ===\n',
                 '', content, flags=re.DOTALL)

share_block = f"""
#=== BEGIN CUPS PRINTER SHARE ===
[global]
   workgroup = WORKGROUP
   server string = Linux Print Server
   security = user
   map to guest = Bad User
   guest account = nobody
   printing = cups
   printcap name = cups
   load printers = yes

[printers]
   comment = All Printers
   browseable = yes
   path = /var/spool/samba
   printable = yes
   guest ok = yes
   read only = yes
   create mask = 0700

[print$]
   comment = Printer Drivers
   path = /var/lib/samba/printers
   browseable = yes
   read only = yes
   guest ok = yes
#=== END CUPS PRINTER SHARE ===
"""

with open(path, 'a') as f:
    f.write(share_block)

print("smb.conf updated.")
PYEOF

    mkdir -p /var/spool/samba
    chmod 1777 /var/spool/samba
    mkdir -p /var/lib/samba/printers

    systemctl restart smbd nmbd
    systemctl enable smbd nmbd
    info "Samba configured. Windows can now reach: \\\\${LINUX_HOST_IP}\\${PRINTER_NAME}"
}

# ── 7. Firewall rules ────────────────────────────────────────────────────────
open_firewall() {
    if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
        info "Opening firewall ports for CUPS (631) and Samba (137,138,139,445)..."
        ufw allow 631/tcp comment "CUPS IPP"
        ufw allow 137/udp comment "Samba NetBIOS"
        ufw allow 138/udp comment "Samba NetBIOS"
        ufw allow 139/tcp comment "Samba NetBIOS"
        ufw allow 445/tcp comment "Samba SMB"
        info "Firewall rules added."
    else
        info "ufw not active; skipping firewall config."
    fi
}

# ── 8. Print test page ───────────────────────────────────────────────────────
print_test() {
    info "Sending test page to $PRINTER_NAME..."
    echo "Brother DCP-L3550CDW — test page from $(hostname) on $(date)" \
        | lp -d "$PRINTER_NAME" -o media=A4 && info "Test page sent." \
        || warn "Test page failed — check 'lpstat -p $PRINTER_NAME'"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    require_root

    # Resolve printer IP
    if [[ -z "$PRINTER_IP" ]]; then
        info "No printer IP given — auto-discovering..."
        PRINTER_IP=$(discover_printer_ip) || die "Could not find printer on network. Pass IP as argument: sudo bash $0 <PRINTER_IP>"
        info "Found printer at: $PRINTER_IP"
    fi

    install_cups
    install_brother_driver
    add_printer_to_cups     "$PRINTER_IP"
    configure_cups_sharing
    install_samba_print_share
    open_firewall

    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "  Setup complete!"
    echo ""
    echo "  Linux printer:  $PRINTER_NAME  →  $PRINTER_IP"
    echo ""
    echo "  How to print from Windows (no driver install needed):"
    echo "  ┌─ Option A — IPP (recommended) ────────────────────"
    echo "  │  1. Open: Settings → Bluetooth & devices → Printers"
    echo "  │  2. 'Add device' → 'Add manually'"
    echo "  │  3. 'Add printer using IP' → enter:"
    echo "  │     http://${LINUX_HOST_IP}:631/printers/${PRINTER_NAME}"
    echo "  │"
    echo "  └─ Option B — SMB (if IPP blocked) ─────────────────"
    echo "     1. Open File Explorer → address bar → type:"
    echo "        \\\\${LINUX_HOST_IP}"
    echo "     2. Double-click '$PRINTER_NAME' to install"
    echo "════════════════════════════════════════════════════════"

    read -rp "Send a test page now? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] && print_test

    # Run CUPS web UI hint
    info "CUPS web admin: http://${LINUX_HOST_IP}:631"
}

main "$@"
