#!/usr/bin/env python3
"""Houston Display V1.2-dev: transactional campaign import from bootfs.

Only full-HD PNG files are supported without extra Python packages.
No network access, no root permissions, and no shell commands are used.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import struct
import time
import zlib
from houston_campaign import load_campaign

SOURCE_DIR = Path('/boot/firmware/HOUSTON_V12_MEDIA')
PROJECT_DIR = Path(__file__).resolve().parent
DEST_DIR = PROJECT_DIR / 'slides'
STAGE_DIR = PROJECT_DIR / '.slides_staging'
BACKUP_DIR = PROJECT_DIR / '.slides_backup'
STATE_FILE = PROJECT_DIR / '.houston_media_sha256'
LOG_FILE = PROJECT_DIR / 'houston_import.log'
EXPECTED_WIDTH = 1920
EXPECTED_HEIGHT = 1080
MAX_FILES = 30
MAX_FILE_SIZE = 12 * 1024 * 1024
MAX_TOTAL_SIZE = 180 * 1024 * 1024
MAX_AUDIO_SIZE = 40 * 1024 * 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def log(message: str) -> str:
    entry = time.strftime('%Y-%m-%d %H:%M:%S') + ' | ' + message
    print(entry)
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 200_000:
            LOG_FILE.write_text('Historique tronque.\n', encoding='utf-8')
        with LOG_FILE.open('a', encoding='utf-8') as handle:
            handle.write(entry + '\n')
    except OSError:
        pass
    return message


def valid_png(path: Path) -> None:
    """Validate structure, CRCs, and dimensions of a PNG before adopting it."""
    has_idat = False
    has_iend = False
    width = height = None
    with path.open('rb') as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise ValueError(f'{path.name}: not a PNG')
        first = True
        while True:
            header = handle.read(8)
            if len(header) != 8:
                raise ValueError(f'{path.name}: missing IEND')
            length, kind = struct.unpack('>I4s', header)
            if length > MAX_FILE_SIZE:
                raise ValueError(f'{path.name}: excessive chunk size')
            payload = handle.read(length)
            crc_bytes = handle.read(4)
            if len(payload) != length or len(crc_bytes) != 4:
                raise ValueError(f'{path.name}: truncated PNG')
            expected_crc = struct.unpack('>I', crc_bytes)[0]
            actual_crc = zlib.crc32(payload, zlib.crc32(kind)) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                raise ValueError(f'{path.name}: PNG checksum mismatch')
            if first:
                if kind != b'IHDR' or length != 13:
                    raise ValueError(f'{path.name}: invalid PNG header')
                width, height = struct.unpack('>II', payload[:8])
                first = False
            if kind == b'IDAT':
                has_idat = True
            if kind == b'IEND':
                has_iend = True
                if handle.read(1):
                    raise ValueError(f'{path.name}: trailing bytes')
                break
    if not has_iend or not has_idat:
        raise ValueError(f'{path.name}: incomplete PNG')
    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise ValueError(f'{path.name}: {width}x{height}, expected 1920x1080')


def fingerprint(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for source in files:
        digest.update(source.name.encode('utf-8'))
        digest.update(b'\x00')
        with source.open('rb') as handle:
            for block in iter(lambda: handle.read(128 * 1024), b''):
                digest.update(block)
    return digest.hexdigest()


def import_media(source_dir: Path = SOURCE_DIR, dest_dir: Path = DEST_DIR,
                 stage_dir: Path = STAGE_DIR, backup_dir: Path = BACKUP_DIR,
                 state_file: Path = STATE_FILE) -> str:
    """Replace the entire slide set, only when all replacement images pass checks.

    Missing or empty HOUSTON_MEDIA never clears the current slideshow.
    A prior interrupted swap is repaired from the backup on next launch.
    """
    try:
        # Clean up or recover from an interrupted prior import.
        if not dest_dir.exists() and backup_dir.exists():
            os.replace(backup_dir, dest_dir)
            state_file.unlink(missing_ok=True)
            log('Recovered previous slides after interrupted update')
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        if backup_dir.exists() and dest_dir.exists():
            shutil.rmtree(backup_dir)
        if not source_dir.is_dir():
            return log('No HOUSTON_MEDIA folder: keeping current images')
        files = sorted((p for p in source_dir.iterdir()
                        if p.is_file() and p.suffix.lower() == '.png'),
                       key=lambda p: (p.name.casefold(), p.name))
        if not files:
            return log('No PNG images in HOUSTON_MEDIA: keeping current images')
        if len(files) > MAX_FILES:
            return log(f'IMPORT REJECTED: more than {MAX_FILES} PNG files')
        sizes = [p.stat().st_size for p in files]
        if any(s > MAX_FILE_SIZE for s in sizes) or sum(sizes) > MAX_TOTAL_SIZE:
            return log('IMPORT REJECTED: PNG file(s) exceed size limits')
        audio_files = sorted((p for p in source_dir.iterdir()
                              if p.is_file() and p.suffix.lower() in {'.wav', '.mp3'}),
                             key=lambda p: p.name.casefold())
        if len(audio_files) > 1:
            return log('IMPORT REJECTED: only one audio file (WAV or MP3) permitted per campaign')
        if any(p.stat().st_size > MAX_AUDIO_SIZE for p in audio_files):
            return log('IMPORT REJECTED: audio file exceeds 40 MiB')
        if sum(sizes) + sum(p.stat().st_size for p in audio_files) > MAX_TOTAL_SIZE:
            return log('IMPORT REJECTED: campaign exceeds total size limit')
        # Optional configuration is part of the campaign identity.
        config_files = [source_dir / name for name in ('playlist.csv', 'settings.ini')
                        if (source_dir / name).is_file()]
        # Reject invalid campaign BEFORE replacing the previous one.
        load_campaign(source_dir)
        # Do not copy or erase anything when the source has not changed.
        new_fingerprint = fingerprint(files + audio_files + config_files)
        if (dest_dir.is_dir() and any(dest_dir.glob('*.png'))
                and state_file.exists()
                and state_file.read_text(encoding='ascii').strip() == new_fingerprint):
            return log(f'Unchanged media: {len(files)} images')
        stage_dir.mkdir(parents=True, exist_ok=False)
        for source in files:
            target = stage_dir / source.name
            shutil.copyfile(source, target)
            valid_png(target)
        for source in audio_files:
            shutil.copyfile(source, stage_dir / source.name)
        for source in config_files:
            shutil.copyfile(source, stage_dir / source.name)
        load_campaign(stage_dir)  # Validates copied configuration as well.
        # Stage complete: replace the previous image set using atomic renames.
        if dest_dir.exists():
            os.replace(dest_dir, backup_dir)
        try:
            os.replace(stage_dir, dest_dir)
        except BaseException:
            if backup_dir.exists() and not dest_dir.exists():
                os.replace(backup_dir, dest_dir)
            raise
        temp_state = state_file.with_suffix('.tmp')
        temp_state.write_text(new_fingerprint + '\n', encoding='ascii')
        os.replace(temp_state, state_file)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        return log(f'IMPORT OK: {len(files)} full-HD images + campaign settings/audio installed')
    except Exception as exc:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        if not dest_dir.exists() and backup_dir.exists():
            try:
                os.replace(backup_dir, dest_dir)
            except OSError:
                pass
        return log(f'IMPORT FAILED ({type(exc).__name__}): {exc}; old images retained')


if __name__ == '__main__':
    import_media()
