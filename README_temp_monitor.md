# temp_monitor.sh

CPU temperature logger for the 2018 MacBook Pro i7. Logs readings to a CSV file in the background and produces a statistics report on demand — or automatically when you press Ctrl+C.

## Requirements

```bash
brew install osx-cpu-temp
```

## Quick start

```bash
# Log in the foreground — press Ctrl+C at any time to see a full summary
./temp_monitor.sh run

# Or run silently in the background
./temp_monitor.sh start
```

## Commands

| Command | Description |
|---------|-------------|
| `run [sec]` | Foreground logging. Shows live temp. **Ctrl+C prints full summary and exits.** Default interval: 120s |
| `start [sec]` | Background daemon. Keeps logging after you close the terminal. Default: 120s |
| `stop` | Stop the background daemon and print a summary |
| `status` | Check if running, see last reading and current temp |
| `tail` | Stream the raw log live (Ctrl+C to quit) |
| `report` | Full statistics report for all logged data |
| `report --last 2h` | Stats for the last 2 hours only |
| `report --last 30m` | Stats for the last 30 minutes only |

## Example: foreground session

```
$ ./temp_monitor.sh run
Logging every 120s — Ctrl+C to stop and show summary.
Log: ~/Library/Logs/cpu_temp.csv

  14:32:01   61.2°C   ^C

Stopped. Generating summary…

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CPU Temperature Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Period      : 2026-05-17 12:00 → 2026-05-17 14:32 UTC
  Logged      : 2h 32m  (77 readings)
  Sleep/pause : 0h 48m  (2 gaps)

  ── Central tendency ──────────────────────
  Mean        : 63.4°C
  Median      : 62.1°C
  Mode        : 61.5°C

  ── Range ─────────────────────────────────
  Min         : 58.0°C
  Max         : 91.3°C
  Std dev     : 7.2°C

  ── Threshold breaches ────────────────────
  ≥80°C      : ▓▓ 4× (5%)
  ≥85°C      : ▓ 2× (3%)
  ≥90°C      : ▓ 1× (1%)

  ── Distribution ──────────────────────────
  51–60°C   ████████ 18 (23%)
  61–70°C   ██████████████████ 43 (56%)
  71–80°C   ████ 12 (16%)
  81–90°C   ██ 3 (4%)
  91–100°C  █ 1 (1%)

  ── Analysis ──────────────────────────────
  Trend       : ↑ rising   (+2.3°C/hr)
  Idle baseline: 58.4°C  (coolest 7 readings)
  Streak ≥85°C : 2 consecutive readings  (~4 min)
  Streak ≥90°C : 1 consecutive readings  (~2 min)
  Hottest hour: 14:00  (avg 78.3°C)
  Coolest hour: 12:00  (avg 61.1°C)
  Volatility  : 7.2°C std dev  (moderate)

  ── Suggestions ───────────────────────────
  ⚠ Gradual upward trend (+2.3°C/hr). Normal for sustained
    workloads, but worth monitoring if it continues after
    your task finishes.
  ⚠ Sustained ≥90°C for ~2 min. Prolonged heat at this level
    throttles the CPU and accelerates wear. Enable Turbo Boost
    Switcher and check for background tasks.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Log file

Readings are saved to:

```
~/Library/Logs/cpu_temp.csv
```

Plain CSV with two columns — readable in Excel or Numbers:

```
timestamp,temp_c
2026-05-17T12:00:01Z,61.2
2026-05-17T12:02:01Z,63.5
...
```

## Analysis & suggestions

Every report includes two sections beyond the raw numbers:

**Analysis** examines patterns in the data:

| Field | What it tells you |
|-------|------------------|
| **Trend** | Linear regression slope — is the Mac heating up, cooling down, or holding steady over the session? |
| **Idle baseline** | Average of the coolest 10% of readings — approximates the resting temperature when nothing heavy is running |
| **Streak ≥N°C** | Longest consecutive run of readings above each threshold, converted to minutes |
| **Hottest / coolest hour** | Which hour of the day (local time) averaged the highest and lowest temperatures — only shown when enough hourly data exists |
| **Volatility** | Standard deviation described as steady / moderate / bursty — high variance points to intermittent CPU spikes rather than sustained load |

**Suggestions** are generated automatically based on what the data shows:

| Condition | Suggestion |
|-----------|------------|
| Trend > +3°C/hr | Background process likely running — check Activity Monitor |
| Trend +1.5–3°C/hr | Gradual rise — normal for sustained work, monitor if it continues after task ends |
| Idle baseline > 72°C | High resting temp — likely dried-out thermal paste (common on 2018 MBP) |
| Idle baseline 65–72°C | Moderate resting temp — ensure Turbo Boost Switcher is off during light use |
| Streak ≥ 3 readings above 90°C | Prolonged critical heat — enable Turbo Boost Switcher, check for background tasks |
| Streak ≥ 5 readings above 85°C | Extended high load — consider Turbo Boost Switcher for long sessions |
| Hottest hour 8°C+ above coolest | Clear daily heat pattern — schedule heavy tasks away from the hot window |
| Std dev > 10°C | Bursty spikes — common causes: Time Machine, Spotlight, iCloud sync, browser JS |

If none of the conditions above are triggered, the suggestions section shows a single `✓ All good` line.

---

## Sleep behaviour

When the Mac sleeps, the logger pauses automatically (macOS suspends background processes). On wake-up it resumes. The report detects gaps larger than 3× the logging interval and labels them as sleep/inactive time, excluding them from the active logging duration shown in the summary.

## Notes

- **Does not survive a reboot.** After restarting, run `./temp_monitor.sh start` again.
- Choosing a shorter interval (e.g. `run 30`) gives more granular data but grows the CSV faster.
- The log is **append-only** — each new session adds to the existing file. To start fresh, delete `~/Library/Logs/cpu_temp.csv`.
- Threshold alerts are informational. The 2018 MBP i7 throttles around 95°C. Sustained readings above 90°C are a sign to enable Turbo Boost Switcher or check for a runaway process.
