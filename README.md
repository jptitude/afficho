# AFFICHO

**Offline digital signage for Raspberry Pi, built with Python.**

AFFICHO is a lightweight, offline slideshow player that turns an HDMI display into a digital signage screen. It was developed and tested on a **Raspberry Pi Zero Rev 1.3**, with the goal of delivering a usable embedded application on limited hardware.

> **Status:** v1.2.0 — functional MVP validated on the target device. Not a mass-market production product.

## Features

- Full-screen **1920 × 1080 PNG** slideshow with automatic looping.
- Filename-based ordering or custom order via `playlist.csv`.
- Default and per-slide display durations (1–600 seconds).
- Optional on-screen branding.
- Optional **MP3 or uncompressed WAV** background audio, looping alongside images.
- Offline campaign update from the Raspberry Pi boot partition.
- Automatic desktop startup without keyboard or mouse after setup.
- Transactional campaign replacement: invalid updates keep the previous campaign active.

## Tech stack

Python 3 · Tkinter · Raspberry Pi OS Bookworm · ALSA `aplay` · FFmpeg `ffplay` · Raspberry Pi Zero (ARMv6).

## How it works

```text
PC creates campaign
  → bootfs/HOUSTON_V12_MEDIA/
  → validation and import on boot
  → local active campaign
  → Tkinter slideshow + optional audio process
  → HDMI display
```

## Configuration example

`settings.ini`:

```ini
[display]
default_duration = 10
show_branding = true
brand_label = Powered by AFFICHO

[audio]
enabled = true
file = ambiance.mp3
loop = true
```

`playlist.csv`:

```csv
filename,duration_seconds
02_services.png,15
01_promotion.png,5
```

Each image in a playlist must be included exactly once. The media files themselves must be provided separately, with appropriate rights.

## Hardware validation

Tested with a Raspberry Pi Zero Rev 1.3, HDMI 1080p monitor, Raspberry Pi OS Bookworm, offline operation. Real-device QA covered custom slide order/durations, MP3/WAV playback, complete campaign import, a 30-minute continuous run, and automatic boot without input peripherals.

## Known limitations

- Video playback is **not** supported in v1.2.0.
- PNG images must be exactly 1920 × 1080 in the current implementation.
- One background audio file per campaign; the MP3 player can have a short startup delay.
- Updating content currently requires powering down and accessing the microSD card on a computer.
- The software was validated on one prototype device; broader hardware and long-duration testing are future work.

## Why this project exists

AFFICHO is an end-to-end embedded development project: hardware troubleshooting, Linux configuration, Python application development, offline asset import, QA, release management, and recovery planning.

## Project status and licensing

The project was developed with AI assistance and validated on physical hardware. The published repository is intended as a technical portfolio. **A license has not yet been selected**; a public repository does not, by itself, grant permission to reuse or redistribute the code. Do not add a license until the owner makes that decision.

## Demo

Add a real photograph or short demonstration video here **after it has been recorded and reviewed**. No demo media is included in this documentation package.
