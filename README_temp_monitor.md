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

## Sleep behaviour

When the Mac sleeps, the logger pauses automatically (macOS suspends background processes). On wake-up it resumes. The report detects gaps larger than 3× the logging interval and labels them as sleep/inactive time, excluding them from the active logging duration shown in the summary.

## Notes

- **Does not survive a reboot.** After restarting, run `./temp_monitor.sh start` again.
- Choosing a shorter interval (e.g. `run 30`) gives more granular data but grows the CSV faster.
- The log is **append-only** — each new session adds to the existing file. To start fresh, delete `~/Library/Logs/cpu_temp.csv`.
- Threshold alerts are informational. The 2018 MBP i7 throttles around 95°C. Sustained readings above 90°C are a sign to enable Turbo Boost Switcher or check for a runaway process.
