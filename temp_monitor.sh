#!/usr/bin/env bash
# temp_monitor.sh — CPU temperature logger for 2018 MBP i7
#
# Usage:
#   ./temp_monitor.sh run    [interval_sec]   foreground; Ctrl+C shows summary
#   ./temp_monitor.sh start  [interval_sec]   background daemon
#   ./temp_monitor.sh stop                    stop daemon + show summary
#   ./temp_monitor.sh status                  running state + last reading
#   ./temp_monitor.sh report [--last <N>h|m]  full statistics report
#   ./temp_monitor.sh tail                    stream log live

LOG_FILE="$HOME/Library/Logs/cpu_temp.csv"
PID_FILE="$HOME/Library/Logs/cpu_temp.pid"
TEMP_BIN="$(which osx-cpu-temp 2>/dev/null)"
DEFAULT_INTERVAL=120

# ── helpers ───────────────────────────────────────────────────────────────────

die()        { echo "Error: $*" >&2; exit 1; }
check_tool() { [ -x "$TEMP_BIN" ] || die "osx-cpu-temp not found. Install: brew install osx-cpu-temp"; }
is_running() { [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; }
read_temp()  { "$TEMP_BIN" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+'; }

ensure_header() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "timestamp,temp_c" > "$LOG_FILE"
    fi
}

log_reading() {
    local temp
    temp=$(read_temp)
    if [ -n "$temp" ]; then
        printf "%s,%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$temp" >> "$LOG_FILE"
        echo "$temp"
    fi
}

# ── Python stats engine ───────────────────────────────────────────────────────

run_report() {
    local filter_arg="${1:-}"
    python3 - "$LOG_FILE" "$filter_arg" <<'PYEOF'
import sys, csv, os
from datetime import datetime, timezone, timedelta
from statistics import mean, median, multimode, stdev

log_file   = sys.argv[1]
filter_arg = sys.argv[2] if len(sys.argv) > 2 else ""

if not os.path.exists(log_file):
    print("No log file yet. Run 'start' or 'run' first.")
    sys.exit(0)

# Parse optional --last filter
cutoff = None
if filter_arg.startswith("--last"):
    parts = filter_arg.split()
    if len(parts) == 2:
        val = parts[1]
        try:
            if   val.endswith("h"): cutoff = datetime.now(timezone.utc) - timedelta(hours=float(val[:-1]))
            elif val.endswith("m"): cutoff = datetime.now(timezone.utc) - timedelta(minutes=float(val[:-1]))
        except ValueError:
            pass

temps, timestamps = [], []
with open(log_file) as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            t  = float(row["temp_c"])
        except (ValueError, KeyError):
            continue
        if cutoff and ts < cutoff:
            continue
        temps.append(t)
        timestamps.append(ts)

if not temps:
    print("No data found for the requested period.")
    sys.exit(0)

# ── detect sleep/inactive gaps ─────────────────────────────────────────────
# Infer the logging interval from the most common gap between readings
gaps = [(timestamps[i+1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps)-1)]

if gaps:
    sorted_gaps = sorted(gaps)
    inferred_interval = sorted_gaps[len(sorted_gaps)//2]   # median gap
    sleep_threshold   = max(inferred_interval * 3, 300)     # 3× interval or 5 min
    sleep_gaps        = [g for g in gaps if g > sleep_threshold]
    total_sleep_s     = sum(sleep_gaps)
else:
    inferred_interval = DEFAULT_INTERVAL = 120
    sleep_gaps        = []
    total_sleep_s     = 0

active_s = (timestamps[-1] - timestamps[0]).total_seconds() - total_sleep_s

def fmt_duration(seconds):
    h, r = divmod(int(abs(seconds)), 3600)
    m    = r // 60
    return f"{h}h {m}m"

# ── thresholds ─────────────────────────────────────────────────────────────
thresholds = [80, 85, 90, 95, 100]

# ── report ─────────────────────────────────────────────────────────────────
rounded = [round(t, 1) for t in temps]
modes   = multimode(rounded)

print()
print("━" * 52)
print("  CPU Temperature Report")
print("━" * 52)
print(f"  Period      : {timestamps[0].strftime('%Y-%m-%d %H:%M')} → "
      f"{timestamps[-1].strftime('%Y-%m-%d %H:%M')} UTC")
print(f"  Logged      : {fmt_duration(active_s)}  ({len(temps)} readings)")
if sleep_gaps:
    print(f"  Sleep/pause : {fmt_duration(total_sleep_s)}  ({len(sleep_gaps)} gap{'s' if len(sleep_gaps)>1 else ''})")
print()
print("  ── Central tendency ──────────────────────")
print(f"  Mean        : {mean(temps):.1f}°C")
print(f"  Median      : {median(temps):.1f}°C")
if len(modes) == 1:
    print(f"  Mode        : {modes[0]}°C")
else:
    print(f"  Mode        : {', '.join(str(m) for m in modes[:3])}°C  (tie)")
print()
print("  ── Range ─────────────────────────────────")
print(f"  Min         : {min(temps):.1f}°C")
print(f"  Max         : {max(temps):.1f}°C")
if len(temps) > 1:
    print(f"  Std dev     : {stdev(temps):.1f}°C")
print()
print("  ── Threshold breaches ────────────────────")
any_breach = False
for t in thresholds:
    count = sum(1 for x in temps if x >= t)
    if count > 0:
        pct = count / len(temps) * 100
        bar = "▓" * min(int(pct / 5), 20)
        print(f"  ≥{t}°C      : {bar} {count}× ({pct:.0f}%)")
        any_breach = True
if not any_breach:
    print("  None — all readings below 80°C  ✓")
print()
print("  ── Distribution ──────────────────────────")
brackets = [
    ("≤50°C",  lambda x: x <= 50),
    ("51–60°C", lambda x: 50 < x <= 60),
    ("61–70°C", lambda x: 60 < x <= 70),
    ("71–80°C", lambda x: 70 < x <= 80),
    ("81–90°C", lambda x: 80 < x <= 90),
    ("91–100°C",lambda x: 90 < x <= 100),
    (">100°C",  lambda x: x > 100),
]
for label, fn in brackets:
    count = sum(1 for x in temps if fn(x))
    if count == 0:
        continue
    bar = "█" * max(1, int(count / len(temps) * 30))
    print(f"  {label:9s} {bar} {count} ({count/len(temps)*100:.0f}%)")
print("━" * 52)
print()
PYEOF
}

# ── run (foreground, Ctrl+C → summary) ───────────────────────────────────────

cmd_run() {
    check_tool
    local interval="${1:-$DEFAULT_INTERVAL}"
    [[ "$interval" =~ ^[0-9]+$ ]] || die "Interval must be a whole number of seconds."
    ensure_header

    echo "Logging every ${interval}s — Ctrl+C to stop and show summary."
    echo "Log: $LOG_FILE"
    echo ""

    # On Ctrl+C: print a blank line then the report, then exit cleanly
    trap 'echo ""; echo "Stopped. Generating summary…"; echo ""; run_report; exit 0' INT TERM

    while true; do
        local temp
        temp=$(read_temp)
        if [ -n "$temp" ]; then
            printf "%s,%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$temp" >> "$LOG_FILE"
            printf "\r  %s   %s°C   " "$(date '+%H:%M:%S')" "$temp"
        fi
        sleep "$interval"
    done
}

# ── start (background daemon) ─────────────────────────────────────────────────

cmd_start() {
    check_tool
    local interval="${1:-$DEFAULT_INTERVAL}"
    [[ "$interval" =~ ^[0-9]+$ ]] || die "Interval must be a whole number of seconds."

    if is_running; then
        echo "Already running (PID $(cat "$PID_FILE")). Use 'stop' first."
        exit 0
    fi
    ensure_header

    (
        trap exit INT TERM
        while true; do
            local temp
            temp=$(read_temp)
            [ -n "$temp" ] && printf "%s,%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$temp" >> "$LOG_FILE"
            sleep "$interval"
        done
    ) &

    echo $! > "$PID_FILE"
    echo "Started background logging every ${interval}s (PID $!)."
    echo "Log: $LOG_FILE"
}

# ── stop ──────────────────────────────────────────────────────────────────────

cmd_stop() {
    if ! is_running; then
        echo "Not running."
    else
        kill "$(cat "$PID_FILE")" 2>/dev/null
        rm -f "$PID_FILE"
        echo "Stopped."
    fi
    echo ""
    run_report
}

# ── status ────────────────────────────────────────────────────────────────────

cmd_status() {
    if is_running; then
        echo "Running (PID $(cat "$PID_FILE"))"
    else
        echo "Not running."
    fi
    if [ -f "$LOG_FILE" ]; then
        local count
        count=$(tail -n +2 "$LOG_FILE" | wc -l | tr -d ' ')
        echo "Log  : $LOG_FILE  ($count readings)"
        echo "Last : $(tail -1 "$LOG_FILE")"
    fi
    echo "Now  : $(read_temp)°C"
}

# ── tail ──────────────────────────────────────────────────────────────────────

cmd_tail() {
    [ -f "$LOG_FILE" ] || die "No log file yet."
    echo "Streaming $LOG_FILE  (Ctrl+C to quit)"
    tail -f "$LOG_FILE"
}

# ── dispatch ──────────────────────────────────────────────────────────────────

case "${1:-}" in
    run)    cmd_run    "${2:-}" ;;
    start)  cmd_start  "${2:-}" ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    tail)   cmd_tail ;;
    report) run_report "${2:-}" ;;
    *)
        cat <<EOF
Usage: $(basename "$0") <command> [options]

  run    [sec]        Foreground logging; Ctrl+C prints full summary (default ${DEFAULT_INTERVAL}s)
  start  [sec]        Background daemon (default ${DEFAULT_INTERVAL}s)
  stop                Stop daemon and print summary
  status              Running state, last reading, current temp
  tail                Stream log live (Ctrl+C to quit)
  report              Full stats for all logged data
  report --last 2h    Stats for the last 2 hours
  report --last 30m   Stats for the last 30 minutes

Log file: $LOG_FILE
EOF
        exit 1
        ;;
esac
