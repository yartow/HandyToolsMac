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
from collections import defaultdict
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

# ── analysis ───────────────────────────────────────────────────────────────
suggestions = []

print()
print("  ── Analysis ──────────────────────────────")

# 1. Trend: linear regression slope in °C per hour
if len(temps) >= 4:
    n  = len(temps)
    xs = [(ts - timestamps[0]).total_seconds() / 3600 for ts in timestamps]
    xm = sum(xs) / n
    tm = mean(temps)
    num = sum((xs[i] - xm) * (temps[i] - tm) for i in range(n))
    den = sum((xs[i] - xm) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0

    if   slope >  2: trend_label = f"↑ rising   (+{slope:.1f}°C/hr)"
    elif slope < -2: trend_label = f"↓ falling  ({slope:.1f}°C/hr)"
    else:            trend_label = f"→ stable   ({slope:+.1f}°C/hr)"
    print(f"  Trend       : {trend_label}")

    if slope > 3:
        suggestions.append(
            "Temperature is trending up sharply (+{:.1f}°C/hr). A background task\n"
            "  may be running — check Activity Monitor (sort by CPU %).".format(slope)
        )
    elif slope > 1.5:
        suggestions.append(
            "Gradual upward trend (+{:.1f}°C/hr). Normal for sustained workloads,\n"
            "  but worth monitoring if it continues after your task finishes.".format(slope)
        )
    elif slope < -2:
        suggestions.append("Temperature is cooling down — workload has eased off.")

# 2. Idle baseline: average of the coolest 10 % of readings
n_baseline = max(1, len(temps) // 10)
baseline   = mean(sorted(temps)[:n_baseline])
print(f"  Idle baseline: {baseline:.1f}°C  (coolest {n_baseline} reading{'s' if n_baseline>1 else ''})")

if baseline > 72:
    suggestions.append(
        f"Idle baseline is high ({baseline:.1f}°C). On a 2018 MBP this often means\n"
        "  dried-out thermal paste. Reapplying it is the single most effective\n"
        "  hardware fix for chronic heat on this model."
    )
elif baseline > 65:
    suggestions.append(
        f"Idle baseline of {baseline:.1f}°C is moderate. Ensure Turbo Boost Switcher\n"
        "  is OFF during light use to keep the CPU at its base clock."
    )

# 3. Sustained heat streaks: longest consecutive run above each threshold
streak_thresholds = [85, 90, 95]
any_streak = False
for thr in streak_thresholds:
    max_streak = cur = 0
    for t in temps:
        if t >= thr:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    if max_streak > 0:
        duration_min = int(max_streak * inferred_interval / 60)
        print(f"  Streak ≥{thr}°C : {max_streak} consecutive reading{'s' if max_streak>1 else ''}"
              f"  (~{duration_min} min)")
        any_streak = True
        if thr >= 90 and max_streak >= 3:
            suggestions.append(
                f"Sustained ≥{thr}°C for ~{duration_min} min. Prolonged heat at this level\n"
                "  throttles the CPU and accelerates wear. Enable Turbo Boost Switcher\n"
                "  and check for background tasks (backups, Spotlight, sync)."
            )
        elif thr == 85 and max_streak >= 5:
            suggestions.append(
                f"Ran above 85°C for ~{duration_min} min continuously. Consider enabling\n"
                "  Turbo Boost Switcher during long sessions."
            )
if not any_streak:
    print("  Streaks     : none above 85°C")

# 4. Hottest hour of day (local time, only hours with ≥ 3 readings)
hour_temps: dict[int, list[float]] = defaultdict(list)
for ts, t in zip(timestamps, temps):
    hour_temps[ts.astimezone().hour].append(t)

ranked = sorted(
    [(h, mean(ts)) for h, ts in hour_temps.items() if len(ts) >= 3],
    key=lambda x: x[1],
    reverse=True,
)
if ranked:
    hot_hour, hot_avg = ranked[0]
    cool_hour, cool_avg = ranked[-1]
    print(f"  Hottest hour: {hot_hour:02d}:00  (avg {hot_avg:.1f}°C)")
    if len(ranked) >= 3:
        print(f"  Coolest hour: {cool_hour:02d}:00  (avg {cool_avg:.1f}°C)")
        if hot_avg - cool_avg >= 8:
            suggestions.append(
                f"Temperature peaks around {hot_hour:02d}:00 (avg {hot_avg:.1f}°C) vs\n"
                f"  {cool_hour:02d}:00 (avg {cool_avg:.1f}°C). Schedule CPU-heavy tasks\n"
                f"  outside the {hot_hour:02d}:00 window if possible."
            )

# 5. Volatility
if len(temps) > 1:
    sd = stdev(temps)
    volatility = "high — bursty workload" if sd > 8 else ("moderate" if sd > 4 else "low — steady load")
    print(f"  Volatility  : {sd:.1f}°C std dev  ({volatility})")
    if sd > 10:
        suggestions.append(
            f"High temperature variance ({sd:.1f}°C std dev) suggests intermittent\n"
            "  CPU spikes — common causes: Time Machine, Spotlight indexing, iCloud\n"
            "  sync, or browser tabs running background JS."
        )

# ── suggestions ────────────────────────────────────────────────────────────
print()
print("  ── Suggestions ───────────────────────────")
if not suggestions:
    print("  ✓ All good — temps look healthy for this session.")
else:
    for i, s in enumerate(suggestions, 1):
        # Indent continuation lines to align with the bullet
        lines = s.split("\n")
        print(f"  {'⚠' if i <= len(suggestions) else '•'} {lines[0]}")
        for line in lines[1:]:
            print(f"    {line}")

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
