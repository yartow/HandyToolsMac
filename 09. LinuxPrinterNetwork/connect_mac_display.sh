#!/usr/bin/env bash
# Connects to the Mac's virtual display using TigerVNC vncviewer.
# Works from SSH, GNOME autostart, and direct terminal.

MAC_IP="192.168.178.77"
MAC_PORT="5900"

# ── Inject GNOME session environment ──────────────────────────────────────────
# SSH and autostart contexts don't inherit WAYLAND_DISPLAY / DISPLAY / DBUS.
# Read them directly from the running gnome-session process.
inject_session_env() {
    local pid
    pid=$(pgrep -u "$(id -u)" -x gnome-session 2>/dev/null \
        || pgrep -u "$(id -u)" gnome-session-b 2>/dev/null | head -1)
    [[ -z "$pid" ]] && return
    while IFS= read -r line; do
        [[ "$line" == *=* ]] && export "$line"
    done < <(cat "/proc/$pid/environ" 2>/dev/null | tr '\0' '\n' \
        | grep -E '^(WAYLAND_DISPLAY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS|DISPLAY)=')
}

inject_session_env

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# If DISPLAY is still empty, find XWayland's socket
if [[ -z "${DISPLAY:-}" ]]; then
    DISPLAY=$(ls /tmp/.X11-unix/X* 2>/dev/null | sed 's|/tmp/.X11-unix/X|:|' | head -1)
    export DISPLAY
fi

echo "[INFO] WAYLAND=${WAYLAND_DISPLAY:-unset}  DISPLAY=${DISPLAY:-unset}"

# ── Wait for Mac VNC ───────────────────────────────────────────────────────────
echo "[INFO] Waiting for Mac at $MAC_IP:$MAC_PORT..."
for i in $(seq 1 12); do
    nc -z -w3 "$MAC_IP" "$MAC_PORT" 2>/dev/null && { echo "[INFO] Mac reachable."; break; }
    [[ $i -eq 12 ]] && echo "[WARN] Mac not reachable after 60 s — trying anyway."
    sleep 5
done

# ── Connect ────────────────────────────────────────────────────────────────────
# Full-screen, no scaling (1:1 pixels), starting at coordinate 0,0 so the
# Mac's leftmost virtual display fills the Linux monitor exactly.
exec vncviewer \
    -FullScreen \
    -FullColour \
    -RemoteResize=0 \
    -MenuKey F12 \
    "${MAC_IP}::${MAC_PORT}"
