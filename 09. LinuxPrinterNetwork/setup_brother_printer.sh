#!/usr/bin/env bash
# Setup Brother DCP-L3550CDW as a shared CUPS print server on Ubuntu/Debian.
# Uses IPP Everywhere (driverless) — no driver download required.
# Optionally installs the official Brother driver for extra features.
#
# Run as: sudo bash setup_brother_printer.sh [PRINTER_IP]
# Example: sudo bash setup_brother_printer.sh 192.168.178.50
#
# After this runs, Windows machines can print via:
#   IPP:  http://192.168.178.203:631/printers/Brother_DCP-L3550CDW
#   SMB:  \\192.168.178.203\Brother_DCP-L3550CDW

set -euo pipefail

PRINTER_IP="${1:-}"
PRINTER_NAME="Brother_DCP-L3550CDW"
LINUX_HOST_IP="192.168.178.203"
REAL_USER="${SUDO_USER:-${USER:-andrewyong}}"

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "Run this script with sudo: sudo bash $0"
}

# ── 0. Fix lpadmin group so CUPS admin commands don't prompt for a password ───
fix_lpadmin_group() {
    if ! groups "$REAL_USER" | grep -q lpadmin; then
        info "Adding $REAL_USER to lpadmin group (prevents CUPS password prompts)..."
        usermod -aG lpadmin "$REAL_USER"
        info "Group added. You may need to log out and back in for non-sudo sessions."
    else
        info "$REAL_USER is already in the lpadmin group."
    fi
}

# ── 1. Discover printer IP if not provided ────────────────────────────────────
discover_printer_ip() {
    info "Scanning network for Brother printer..."

    # Try avahi/mDNS first (fast)
    if command -v avahi-browse &>/dev/null; then
        local found
        found=$(avahi-browse -r -t _ipp._tcp 2>/dev/null \
            | grep -i "DCP-L3550\|Brother" \
            | grep -oP '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}' \
            | head -1 || true)
        if [[ -n "$found" ]]; then
            info "Found via mDNS: $found"
            echo "$found"; return 0
        fi
    fi

    # Fallback: arp-scan (fast, requires arp-scan)
    if command -v arp-scan &>/dev/null; then
        local found
        found=$(arp-scan --localnet 2>/dev/null \
            | grep -i "brother\|00:80:77\|00:1b:a9\|00:0e:98\|00:1b:a9" \
            | awk '{print $1}' | head -1 || true)
        if [[ -n "$found" ]]; then
            info "Found via arp-scan: $found"
            echo "$found"; return 0
        fi
    fi

    # Last resort: port scan the subnet (slow, ~30s)
    warn "mDNS scan found nothing. Trying port scan of 192.168.178.1-254..."
    for i in $(seq 1 254); do
        local ip="192.168.178.$i"
        if ping -c1 -W1 "$ip" &>/dev/null 2>&1; then
            if nc -z -w1 "$ip" 9100 &>/dev/null 2>&1 \
            || nc -z -w1 "$ip" 631  &>/dev/null 2>&1; then
                info "Found open print port at: $ip"
                echo "$ip"; return 0
            fi
        fi
    done
    return 1
}

# ── 2. Install CUPS and dependencies ──────────────────────────────────────────
install_cups() {
    info "Installing CUPS and helpers..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        cups \
        cups-client \
        cups-filters \
        cups-ipp-utils \
        avahi-daemon \
        avahi-utils \
        ipp-usb \
        netcat-openbsd \
        wget \
        ghostscript \
        printer-driver-cups-pdf
    systemctl enable --now cups avahi-daemon
    info "CUPS $(lpstat -v 2>/dev/null | wc -l || echo '?') — ready."
}

# ── 3. Add printer using IPP Everywhere (driverless — no download needed) ─────
add_printer_driverless() {
    local ip="$1"
    info "Adding $PRINTER_NAME using IPP Everywhere (driverless)..."

    # Remove stale entry if it exists
    lpadmin -x "$PRINTER_NAME" 2>/dev/null || true

    # IPP Everywhere uses the printer's own built-in capability description.
    # '-m everywhere' tells CUPS to query the printer directly — no PPD file needed.
    lpadmin -p "$PRINTER_NAME" \
        -E \
        -v "ipp://${ip}/ipp/print" \
        -m everywhere \
        -D "Brother DCP-L3550CDW" \
        -L "Network Printer (IPP Everywhere)"

    lpoptions -d "$PRINTER_NAME"
    cupsaccept "$PRINTER_NAME"
    cupsenable  "$PRINTER_NAME"
    info "Printer added via IPP Everywhere — no driver download was needed."
}

# ── 4. (Optional) Install official Brother driver for extra features ───────────
# Skipped if driverless already works. Run manually if you need colour profiles,
# stapling, or advanced media options that IPP Everywhere doesn't expose.
try_install_brother_driver() {
    local ip="$1"
    info "Attempting to install official Brother driver (optional)..."

    # Brother's installer URL changes frequently.
    # We try several known versions in order; skip silently if all fail.
    local tmpdir
    tmpdir=$(mktemp -d)
    # shellcheck disable=SC2064
    trap "rm -rf $tmpdir" RETURN

    local urls=(
        "https://download.brother.com/welcome/dlf006893/linux-brprinter-installer-2.2.2-1.gz"
        "https://download.brother.com/welcome/dlf104515/linux-brprinter-installer-2.2.3-1.gz"
        "https://download.brother.com/welcome/dlf006652/linux-brprinter-installer-2.2.1-1.gz"
    )

    local installer_gz=""
    for url in "${urls[@]}"; do
        info "Trying: $url"
        if wget -q --timeout=15 "$url" -O "$tmpdir/installer.gz" 2>/dev/null; then
            installer_gz="$tmpdir/installer.gz"
            info "Downloaded successfully."
            break
        else
            warn "Failed: $url"
        fi
    done

    if [[ -z "$installer_gz" ]]; then
        warn "Could not download Brother installer (all URLs failed)."
        warn "Driverless IPP Everywhere is already configured and will work fine."
        warn "To install the official driver manually later:"
        warn "  https://support.brother.com → DCP-L3550CDW → Linux (deb)"
        return 0
    fi

    gunzip "$installer_gz"
    local installer
    installer=$(ls "$tmpdir"/linux-brprinter-installer-* 2>/dev/null | head -1)
    chmod +x "$installer"

    info "Running Brother driver installer..."
    printf "DCP-L3550CDW\n0\n" | bash "$installer" DCP-L3550CDW 2>&1 | tail -20 || {
        warn "Brother installer exited non-zero; checking if PPD was installed anyway..."
    }

    # If PPD was installed, re-add the printer with the proper driver
    local ppd
    ppd=$(find /usr/share/cups/model /usr/share/ppd -name "*.ppd*" 2>/dev/null \
        | grep -i "l3550\|L3550CDW" | head -1 || true)

    if [[ -n "$ppd" ]]; then
        info "Brother PPD found: $ppd — upgrading printer entry..."
        lpadmin -x "$PRINTER_NAME" 2>/dev/null || true
        lpadmin -p "$PRINTER_NAME" \
            -E \
            -v "socket://${ip}:9100" \
            -P "$ppd" \
            -D "Brother DCP-L3550CDW" \
            -L "Network Printer (Brother driver)"
        lpoptions -d "$PRINTER_NAME"
        cupsaccept "$PRINTER_NAME"
        cupsenable  "$PRINTER_NAME"
        info "Printer upgraded to official Brother driver."
    else
        info "PPD not found — staying with IPP Everywhere (works fine)."
    fi
}

# ── 5. Configure CUPS for network sharing ─────────────────────────────────────
configure_cups_sharing() {
    info "Configuring CUPS for network sharing on subnet 192.168.178.0/24..."
    local cfg="/etc/cups/cupsd.conf"
    cp "$cfg" "${cfg}.bak.$(date +%s)"

    python3 - "$cfg" "$LINUX_HOST_IP" <<'PYEOF'
import sys, re

path   = sys.argv[1]
host   = sys.argv[2]
subnet = ".".join(host.split(".")[:3]) + ".0/24"

with open(path) as f:
    txt = f.read()

# Listen on all interfaces
txt = re.sub(r'^Listen\s+localhost:\d+', 'Listen 0.0.0.0:631', txt, flags=re.MULTILINE)

# Enable browsing
if re.search(r'^Browsing\s', txt, re.MULTILINE):
    txt = re.sub(r'^Browsing\s+\w+', 'Browsing On', txt, flags=re.MULTILINE)
else:
    txt += '\nBrowsing On\n'

if 'BrowseLocalProtocols' in txt:
    txt = re.sub(r'BrowseLocalProtocols.*', 'BrowseLocalProtocols dnssd', txt)
else:
    txt += 'BrowseLocalProtocols dnssd\n'

if 'ServerAlias' not in txt:
    txt = re.sub(r'(LogLevel\s+\w+)', r'\1\nServerAlias *', txt)

def replace_location(text, loc, new_block):
    m = re.search(r'<Location\s+' + re.escape(loc) + r'\s*>.*?</Location>', text, re.DOTALL)
    if m:
        return text[:m.start()] + new_block + text[m.end():]
    return text + '\n' + new_block + '\n'

root_block = f"""<Location />
  Order allow,deny
  Allow localhost
  Allow {subnet}
</Location>"""

admin_block = f"""<Location /admin>
  Order allow,deny
  Allow localhost
  Allow {subnet}
</Location>"""

txt = replace_location(txt, '/', root_block)
txt = replace_location(txt, '/admin', admin_block)

with open(path, 'w') as f:
    f.write(txt)

print(f"cupsd.conf updated — subnet {subnet} allowed.")
PYEOF

    # Share all printers and accept remote jobs
    cupsctl --share-printers --remote-any
    lpadmin -p "$PRINTER_NAME" -o printer-is-shared=true 2>/dev/null || true

    systemctl restart cups
    systemctl enable cups
    info "CUPS restarted and sharing enabled."
}

# ── 6. Configure Samba for Windows SMB printing ───────────────────────────────
install_samba_print_share() {
    info "Installing Samba for Windows printer sharing..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq samba samba-client

    local cfg="/etc/samba/smb.conf"
    cp "$cfg" "${cfg}.bak.$(date +%s)"

    # Remove any block we previously added, then append a fresh one
    python3 - "$cfg" <<'PYEOF'
import sys, re

path = sys.argv[1]
with open(path) as f:
    txt = f.read()

txt = re.sub(r'\n?#=== CUPS PRINTER SHARE BEGIN ===.*?#=== CUPS PRINTER SHARE END ===\n?',
             '', txt, flags=re.DOTALL)

block = """
#=== CUPS PRINTER SHARE BEGIN ===
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
#=== CUPS PRINTER SHARE END ===
"""

with open(path, 'a') as f:
    f.write(block)

print("smb.conf updated.")
PYEOF

    mkdir -p /var/spool/samba && chmod 1777 /var/spool/samba
    mkdir -p /var/lib/samba/printers

    systemctl restart smbd nmbd
    systemctl enable smbd nmbd
    info "Samba running. Windows path: \\\\${LINUX_HOST_IP}\\${PRINTER_NAME}"
}

# ── 7. Firewall ────────────────────────────────────────────────────────────────
open_firewall() {
    if command -v ufw &>/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
        info "Opening firewall ports..."
        ufw allow 631/tcp  comment "CUPS IPP"   2>/dev/null || true
        ufw allow 137/udp  comment "Samba NB"   2>/dev/null || true
        ufw allow 138/udp  comment "Samba NB"   2>/dev/null || true
        ufw allow 139/tcp  comment "Samba NB"   2>/dev/null || true
        ufw allow 445/tcp  comment "Samba SMB"  2>/dev/null || true
        info "Firewall rules added."
    else
        info "UFW not active — skipping firewall config."
    fi
}

# ── 8. Verify printer is reachable ────────────────────────────────────────────
verify_printer() {
    local ip="$1"
    info "Verifying printer at $ip..."
    if nc -z -w3 "$ip" 631 &>/dev/null; then
        info "Port 631 (IPP) open — printer is reachable."
    elif nc -z -w3 "$ip" 9100 &>/dev/null; then
        info "Port 9100 (raw) open — printer is reachable."
    else
        warn "Cannot reach printer at $ip on ports 631 or 9100."
        warn "Check: is the printer powered on and connected to the WiFi?"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    require_root
    fix_lpadmin_group

    if [[ -z "$PRINTER_IP" ]]; then
        info "No printer IP given — auto-discovering..."
        PRINTER_IP=$(discover_printer_ip) \
            || die "Printer not found on network. Pass IP as argument: sudo bash $0 <PRINTER_IP>"
        info "Using printer IP: $PRINTER_IP"
    fi

    verify_printer      "$PRINTER_IP"
    install_cups
    add_printer_driverless "$PRINTER_IP"
    configure_cups_sharing
    install_samba_print_share
    open_firewall

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Setup complete! (IPP Everywhere — no driver download)"
    echo ""
    echo "  Printer : $PRINTER_NAME"
    echo "  At      : $PRINTER_IP"
    echo ""
    echo "  CUPS admin: http://${LINUX_HOST_IP}:631"
    echo ""
    echo "  How to print from Windows (no driver install required):"
    echo "  ┌─ Option A — IPP (recommended) ──────────────────────"
    echo "  │  Settings → Printers → Add device → Add manually"
    echo "  │  → 'Add using IP address or hostname'"
    echo "  │  → Device type: IPP Device"
    echo "  │  → Hostname: http://${LINUX_HOST_IP}:631/printers/${PRINTER_NAME}"
    echo "  │"
    echo "  └─ Option B — SMB ────────────────────────────────────"
    echo "     File Explorer → address bar → \\\\${LINUX_HOST_IP}"
    echo "     Double-click ${PRINTER_NAME}"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    read -rp "Try to install official Brother driver too? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] && try_install_brother_driver "$PRINTER_IP"

    echo ""
    read -rp "Send a test page now? [y/N] " ans2
    if [[ "$ans2" =~ ^[Yy]$ ]]; then
        info "Sending test page..."
        echo "Brother DCP-L3550CDW test — $(hostname) $(date)" \
            | lp -d "$PRINTER_NAME" -o media=A4 \
            && info "Test page sent." \
            || warn "Test page failed. Check: lpstat -p $PRINTER_NAME"
    fi
}

main "$@"
