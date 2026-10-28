#!/usr/bin/env python3
"""Houston Display V1.2-dev: validated offline image/audio campaign configuration.

Accepts Full-HD PNG and optional WAV/MP3, settings.ini and playlist.csv.
Dependencies: Python standard library only.
"""
from __future__ import annotations

import configparser
import wave
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DURATION = 10.0
MIN_DURATION = 1.0
MAX_DURATION = 600.0


@dataclass(frozen=True)
class Slide:
    path: Path
    duration: float


@dataclass(frozen=True)
class Campaign:
    slides: list[Slide]
    branding: bool
    brand_label: str
    audio_enabled: bool = False
    audio_file: Path | None = None
    audio_loop: bool = True


def parse_duration(value: str, label: str) -> float:
    """Reject nonfinite numbers, extremely short and excessively long times."""
    try:
        v = float(value.strip())
    except (ValueError, AttributeError):
        raise ValueError(f'{label}: invalid duration {value!r}') from None
    if not MIN_DURATION <= v <= MAX_DURATION:  # nan fails both comparisons
        raise ValueError(f'{label}: duration must be {MIN_DURATION:g}-{MAX_DURATION:g} s')
    return v


def load_campaign(folder: Path) -> Campaign:
    """Load and strictly validate a complete campaign, without changing files.

    Default order is case-insensitive filename order. If playlist.csv exists,
    each and every PNG must occur exactly once in the listed order.
    """
    folder = Path(folder)
    files = sorted((p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() == '.png'),
                   key=lambda p: (p.name.casefold(), p.name))
    if not files:
        raise ValueError('Campaign requires at least one PNG')

    names = {p.name: p for p in files}
    if len(names) != len(files):
        raise ValueError('Duplicate PNG filenames')

    default_duration = DEFAULT_DURATION
    branding = False
    brand_label = 'Houston Display'
    audio_enabled = False
    audio_name = 'ambiance.wav'
    audio_loop = True
    ini = folder / 'settings.ini'
    if ini.exists():
        cp = configparser.ConfigParser(interpolation=None)
        with ini.open('r', encoding='utf-8-sig') as handle:
            cp.read_file(handle)
        if cp.has_section('display'):
            options = set(cp['display'])
            allowed = {'default_duration', 'show_branding', 'brand_label'}
            if options - allowed:
                raise ValueError(f'settings.ini: unknown setting(s): {sorted(options-allowed)}')
            if cp.has_option('display', 'default_duration'):
                default_duration = parse_duration(cp.get('display', 'default_duration'),
                                                  'settings.ini default_duration')
            if cp.has_option('display', 'show_branding'):
                branding = cp.getboolean('display', 'show_branding')
            if cp.has_option('display', 'brand_label'):
                brand_label = cp.get('display', 'brand_label').strip()
                if not 1 <= len(brand_label) <= 48 or '\n' in brand_label or '\r' in brand_label:
                    raise ValueError('settings.ini: brand_label must be 1-48 characters on one line')
        if cp.has_section('audio'):
            allowed_audio = {'enabled', 'file', 'loop'}
            if set(cp['audio']) - allowed_audio:
                raise ValueError('settings.ini: unknown [audio] setting')
            if cp.has_option('audio', 'enabled'):
                audio_enabled = cp.getboolean('audio', 'enabled')
            if cp.has_option('audio', 'loop'):
                audio_loop = cp.getboolean('audio', 'loop')
            if cp.has_option('audio', 'file'):
                audio_name = cp.get('audio', 'file').strip()
        if set(cp.sections()) - {'display', 'audio'}:
            raise ValueError('settings.ini: unexpected section')

    # Never allow absolute paths or traversal outside the campaign folder.
    if (not audio_name or Path(audio_name).name != audio_name or
            '/' in audio_name or '\\' in audio_name or
            Path(audio_name).suffix.lower() not in {'.wav', '.mp3'} or audio_name.startswith('.')):
        raise ValueError('settings.ini: audio file must be a local .wav or .mp3 filename')
    audio_path = folder / audio_name if audio_enabled else None
    if audio_enabled:
        if not audio_path.is_file() or audio_path.is_symlink():
            raise ValueError(f'Audio enabled but file missing: {audio_name}')
        if audio_path.suffix.lower() == '.wav':
            validate_wav(audio_path)
        else:
            validate_mp3(audio_path)

    playlist = folder / 'playlist.csv'
    if not playlist.exists():
        slides = [Slide(p, default_duration) for p in files]
        return Campaign(slides, branding, brand_label, audio_enabled, audio_path, audio_loop)

    slides: list[Slide] = []
    used: set[str] = set()
    with playlist.open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['filename', 'duration_seconds']:
            raise ValueError('playlist.csv headers must be: filename,duration_seconds')
        for row in reader:
            if None in row:
                raise ValueError('playlist.csv: too many columns')
            name = (row.get('filename') or '').strip()
            if name not in names:
                raise ValueError(f'playlist.csv: missing or unknown PNG {name!r}')
            if name in used:
                raise ValueError(f'playlist.csv: duplicate PNG {name!r}')
            duration_raw = (row.get('duration_seconds') or '').strip()
            duration = (parse_duration(duration_raw, f'playlist.csv {name}')
                        if duration_raw else default_duration)
            slides.append(Slide(names[name], duration))
            used.add(name)
    if len(slides) != len(files):
        missing = sorted(set(names) - used)
        raise ValueError(f'playlist.csv must list every PNG once; missing: {missing}')
    return Campaign(slides, branding, brand_label, audio_enabled, audio_path, audio_loop)


def validate_wav(path: Path) -> None:
    """Allow bounded, uncompressed PCM WAV for low-power ALSA playback."""
    if path.stat().st_size > 40 * 1024 * 1024:
        raise ValueError(f'{path.name}: WAV exceeds 40 MiB')
    try:
        with wave.open(str(path), 'rb') as wav:
            if wav.getcomptype() != 'NONE':
                raise ValueError(f'{path.name}: compressed WAV unsupported')
            if (wav.getnchannels() not in (1, 2) or
                    wav.getsampwidth() not in (1, 2, 3, 4) or
                    not 8000 <= wav.getframerate() <= 48000 or
                    wav.getnframes() < 1):
                raise ValueError(f'{path.name}: unsupported PCM format')
    except (EOFError, wave.Error) as exc:
        raise ValueError(f'{path.name}: invalid WAV ({exc})') from exc


def validate_mp3(path: Path) -> None:
    """Basic MP3 header sanity check without external dependencies.

    This is not a complete decoder/validator; playback is verified by ffplay.
    """
    size = path.stat().st_size
    if size < 64 or size > 40 * 1024 * 1024:
        raise ValueError(f'{path.name}: MP3 size outside permitted range')
    with path.open('rb') as stream:
        data = stream.read(min(size, 1024 * 1024))
    # A valid Layer III frame has a sync word, legal MPEG version, bitrate
    # and sample-rate indices. Seek in first MiB to allow ID3 metadata.
    for i in range(len(data) - 4):
        if data[i] != 0xFF or (data[i+1] & 0xE0) != 0xE0:
            continue
        version = (data[i+1] >> 3) & 0x03
        layer = (data[i+1] >> 1) & 0x03
        bitrate_index = (data[i+2] >> 4) & 0x0F
        sample_rate_index = (data[i+2] >> 2) & 0x03
        if (version != 0x01 and layer == 0x01 and
                1 <= bitrate_index <= 14 and sample_rate_index != 0x03):
            return
    raise ValueError(f'{path.name}: no valid MP3 frame header found')
