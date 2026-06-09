# Brother DCP-L3550CDW — Linux Print Server + Windows Sharing

Linux host: **192.168.178.203** (Ubuntu/Debian, GNOME Wayland)  
Printer: **Brother DCP-L3550CDW** (network, WiFi/Ethernet)

---

## Step 1 — Run on the Linux machine

```bash
# SSH in or open a terminal on 192.168.178.203
ssh andrewyong@192.168.178.203

# Clone / copy setup_brother_printer.sh to the machine, then:
sudo bash setup_brother_printer.sh [PRINTER_IP]
```

If you don't know the printer's IP, omit it — the script will scan for it.  
To find the printer IP yourself first: **Brother printer LCD menu → Network → WLAN → IP Address**.

### What the script does
| Step | Action |
|------|--------|
| 1 | Installs CUPS + Avahi |
| 2 | Downloads & installs official Brother Linux driver |
| 3 | Adds printer to CUPS via `socket://PRINTER_IP:9100` |
| 4 | Opens CUPS to the whole `192.168.178.0/24` subnet |
| 5 | Installs Samba so Windows sees it as a network share |
| 6 | Opens UFW firewall ports 631, 445, 139, 137, 138 |

---

## Step 2 — Add printer on Windows (locked machine)

### Option A — IPP (no driver needed, recommended)

Windows 10/11 has a built-in **IPP Class Driver** — no Brother driver install required.

1. Settings → Bluetooth & devices → Printers & scanners
2. **Add device** → wait a few seconds → **Add manually** (link at bottom)
3. Choose **"Add a printer using an IP address or hostname"**
4. Device type: **IPP Device**
5. Hostname or IP:
   ```
   http://192.168.178.203:631/printers/Brother_DCP-L3550CDW
   ```
6. Windows auto-detects capabilities — no driver download needed

Or try the PowerShell script (may work as standard user):
```
Right-click add_printer_windows.ps1 → Run with PowerShell
```

### Option B — SMB (if IPP is blocked by policy)

1. Open File Explorer
2. In the address bar type: `\\192.168.178.203`
3. Double-click **Brother_DCP-L3550CDW**
4. Windows installs automatically (may pull driver from Windows Update)

---

## Verification

**On Linux:**
```bash
lpstat -p -d               # list printers and default
lpq -P Brother_DCP-L3550CDW   # queue status
echo "test" | lp -d Brother_DCP-L3550CDW   # test print
```

**CUPS web UI** (from any browser on the subnet):
```
http://192.168.178.203:631
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Printer not found during scan | Find IP on printer LCD: Menu → Network → WLAN → IP Address |
| CUPS shows printer stopped | `sudo cupsenable Brother_DCP-L3550CDW` |
| Windows "Access denied" on SMB | In `smb.conf`, confirm `guest ok = yes` and restart smbd |
| Driver PPD not found | Re-run script; or manually run `sudo bash linux-brprinter-installer-* DCP-L3550CDW` |
| Windows can't reach the IPP URL | Check UFW: `sudo ufw status` — port 631 should be ALLOW |
| Print job stuck in queue | `cancel -a; sudo systemctl restart cups` |

---

## Files

| File | Purpose |
|------|---------|
| `setup_brother_printer.sh` | Run on Linux to install driver + configure CUPS + Samba |
| `add_printer_windows.ps1` | Run on Windows to add the IPP printer automatically |
