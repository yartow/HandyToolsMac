# HDMI audio fails: "could not establish a timeline"

Read this first if HDMI audio from this Mac stops working. It records one past incident, what was ruled out, and the fix that worked.

## Setup
- MacBook Pro M1 Max (`MacBookPro18,2`), macOS Tahoe 26.6.2 (25G83)
- Output over the built-in HDMI port to an LG ULTRAWIDE monitor (2560x1080), default output device, 2ch / 48 kHz
- HAL plug-ins installed: `MSTeamsAudioDevice.driver`, `ParrotAudioPlugin.driver` (Apple, shipped with the OS)
- Monitors and TVs connected have not changed over the months before the incident

## Symptom signature
- `afplay /System/Library/Sounds/Ping.aiff` hangs about 10 s, then prints `Error: AudioQueueStart failed ('stop')` and exits 1. `'stop'` = 0x73746F70 = `kAudioHardwareNotRunningError`.
- The same error appears in other apps. YouTube occasionally worked after moving the volume slider.
- coreaudiod log lines, repeated once per attempt:
  - `IsTimeRunning_Helper: Device <uuid> is not running.`
  - `IOWorkLoop: could not establish a timeline after waiting 10000000 microseconds`
- `StartIO` succeeds with a normal format, then 0 frames are consumed. The HDMI driver accepts the start command but never posts a clock timestamp.
- Not related: `Exclave...`, `BTAudio`, and `RTAID ... -120 dB` log lines (they just report silence).

## Quick check
```
afplay /System/Library/Sounds/Ping.aiff; echo "exit: $?"
/usr/bin/log show --last 2m --style compact --predicate 'process == "coreaudiod" AND eventMessage CONTAINS "could not establish a timeline"'
```
Healthy = exit 0 and no log lines. macOS has no `timeout` command; note `log` must be called as `/usr/bin/log` under zsh.

## What did NOT help
- Setting bit depth / format
- Restarting coreaudiod
- Switching to a USB-C -> HDMI adapter (failed the same way as the built-in port)
- Changing the monitor from 75 Hz to 60 Hz (still failed)
- A plain restart. The problem persisted until the Mac was cold booted.

## What fixed it
A full cold boot with the HDMI cable unplugged:
1. Apple menu -> **Shut Down** (not Restart)
2. Unplug the HDMI cable from the Mac
3. Wait 30 seconds
4. Power on and log in, then plug the HDMI cable back in
5. Run the quick check above

After this, `afplay` exited 0 and the log was clean. The Mac had been up since Sep 9 (about 6 weeks) when it failed on Oct 20, 2026.

Not confirmed by the user: whether the Ping was actually audible from the monitor. If `afplay` exits 0 but there is no sound, check the monitor's volume / mute / audio-out jack setting.

## Working theory (unproven)
The display coprocessor (DCP) / HDMI audio path got stuck after long uptime. The failure sits below coreaudiod, which is why coreaudiod restarts and format changes did nothing. A cold boot re-initialises it. The 75 Hz non-standard timing theory was not supported, since 60 Hz alone did not fix it.

## If it happens again, in order
1. Run the quick check to confirm the same signature.
2. Cold boot as above. This fixed it last time. Try it before anything else.
3. If it recurs often, check `sysctl kern.boottime` for long uptime and shut down fully every few weeks.
4. Still failing after a cold boot: while switching output to the monitor, run
   `/usr/bin/log stream --predicate 'process == "kernel"' | grep -iE 'dcp|dptx|hdmi|audio'`
5. Rule out plug-ins: test in Safe Mode, or temporarily remove `MSTeamsAudioDevice.driver` (needs sudo, ask first).
6. Check `softwareupdate --history` for a recent macOS update (history up to the incident: 26.6.2 on Sep 3, so no update was involved this time).
7. File in Feedback Assistant with a sysdiagnose taken while it is failing (Ctrl+Opt+Shift+Cmd+.), mentioning "no timeline, 0 frames".
8. Workaround meanwhile: headphone jack, USB or Bluetooth audio, or AirPlay.

## History
- 2026-10-20: Failure first seen in the log on Oct 20 (logs only reached back to Oct 19, so the true start is unknown). Diagnosed, 60 Hz tried (no effect), cold boot fixed it.
