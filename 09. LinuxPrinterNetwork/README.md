# Linux Print Server + Network Display — 192.168.178.203

Linux host: **192.168.178.203** (Ubuntu/Debian, GNOME Wayland, user: andrewyong)  
Mac host:   **192.168.178.77**  (macOS)  
Printer:    **Brother DCP-L3550CDW** (network)

---

## Part 1 — Brother Printer Setup

See printer setup section below. Run `setup_brother_printer.sh` on the Linux machine.

---

## Part 2 — Three-Screen Setup (Mac → Linux monitor as extended display)

**Goal:** MacBook screen + HDMI monitor + Linux machine's monitor = 3 screens on the Mac.

**How it works:** BetterDisplay creates a virtual display on the Mac (free tier).  
macOS Screen Sharing (VNC) serves it. Remmina on Linux shows it full-screen at 1:1 zoom.  
The key trick: the virtual display is placed at the **far left** in macOS Display Arrangement  
so it sits at coordinate (0,0) — Remmina starts at (0,0), sees exactly that display, nothing else.

---

### Step 1 — Mac: Create the virtual display in BetterDisplay

BetterDisplay is already installed (`brew install --cask betterdisplay`).

1. Open **BetterDisplay** from Applications (or Spotlight)
2. In the menu bar icon → **Displays** → **Create virtual screen**
3. Set resolution to match the Linux monitor (e.g. **1920×1080** or **2560×1440**)
4. The virtual display now appears in macOS Display Settings as a real monitor

---

### Step 2 — Mac: Enable Screen Sharing (VNC)

Run this in a terminal on the Mac:

```bash
# Enable Screen Sharing
sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.screensharing.plist

# Verify it's listening
lsof -nP -iTCP:5900 -sTCP:LISTEN
```

Or manually: **System Settings → General → Sharing → Screen Sharing → ON**

Then set a VNC password:  
**Screen Sharing → Computer Settings → "VNC viewers may control screen with password"**

---

### Step 3 — Mac: Arrange displays (CRITICAL)

1. **System Settings → Displays → Arrangement** (or click Arrange on the Displays page)
2. You'll see all your displays as rectangles
3. **Drag the BetterDisplay virtual display to the FAR LEFT** — it must be the leftmost
4. Leave the MBP screen and HDMI monitor to its right

This puts the virtual display at macOS coordinate (0, 0). Remmina on Linux starts reading  
from (0,0) at 1:1 zoom → sees exactly the virtual display.

```
 ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
 │   Virtual    │ │  MBP screen  │ │ HDMI monitor │
 │ (Linux sees) │ │              │ │              │
 └──────────────┘ └──────────────┘ └──────────────┘
   x=0 (leftmost)    x=W1               x=W1+W2
```

---

### Step 4 — Linux: Install Remmina and connect

Copy the script to the Linux machine and run it:

```bash
# From the Mac terminal:
scp setup_network_display_linux.sh andrewyong@192.168.178.203:~/

# Pass your Linux monitor's actual resolution as argument (default: 1920x1080)
ssh andrewyong@192.168.178.203 "bash ~/setup_network_display_linux.sh 1920x1080"
```

Then on the Linux machine, launch the display:
```bash
bash ~/connect_mac_display.sh
```

Or double-click **"Mac Virtual Display"** on the GNOME desktop.

---

### Step 5 — Remmina: Enter VNC password and go full-screen

1. Remmina opens and prompts for the VNC password you set in Step 2
2. Click the **fullscreen button** (or press `F11`)
3. You should see the Mac's virtual display filling the Linux monitor

**If you see all three Mac displays instead of just the virtual one:**  
→ The virtual display is not leftmost. Go back to Step 3 and move it left.

---

### Keyboard shortcut: toggle full-screen in Remmina

| Action | Shortcut |
|--------|----------|
| Toggle fullscreen | `Ctrl+Shift+F` or `F11` |
| Grab/release keyboard | `Ctrl+Shift+G` |
| Disconnect | `Ctrl+Shift+W` |

---

### Re-connecting after reboot

On the Mac: Screen Sharing persists after reboot (it's a LaunchDaemon).  
On Linux: just run `bash ~/connect_mac_display.sh` again.

---

### Latency notes

Over a 1Gbps home LAN (wired): ~20–50ms — fine for productivity  
Over WiFi (5GHz): ~50–150ms — usable  
For better performance in Remmina: set **Quality → Best (LAN)** in the profile

---

## Part 3 — Brother DCP-L3550CDW Printer Setup

### Linux (print server)

```bash
scp setup_brother_printer.sh andrewyong@192.168.178.203:~/
ssh andrewyong@192.168.178.203 "sudo bash ~/setup_brother_printer.sh 192.168.178.XXX"
```

Replace `XXX` with the printer's IP (check on printer LCD: Menu → Network → WLAN → IP Address).

### Windows (wife's locked machine) — no driver install needed

| Method | Address |
|--------|---------|
| IPP (recommended) | `http://192.168.178.203:631/printers/Brother_DCP-L3550CDW` |
| SMB | `\\192.168.178.203\Brother_DCP-L3550CDW` |

Add via: Settings → Printers → Add device → Add manually → IPP Device → paste URL above.

---

## Files

| File | Where to run | Purpose |
|------|-------------|---------|
| `setup_brother_printer.sh` | Linux machine | Install driver, configure CUPS + Samba |
| `setup_network_display_linux.sh` | Linux machine | Install Remmina, create VNC profile |
| `setup_mac_screen_share.sh` | Mac (optional) | Enable VNC from terminal |
| `add_printer_windows.ps1` | Windows machine | Add IPP printer automatically |
