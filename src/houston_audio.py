#!/usr/bin/env python3
"""Optional offline WAV/MP3 playback without extra Python dependencies.

WAV uses ALSA aplay; MP3 uses existing ffplay. Playback runs outside
Tkinter and never blocks the slideshow. Terminate the child on exit.
"""
from pathlib import Path
import shutil
import subprocess
import threading


class AudioLoop:
    def __init__(self, file_path, loop=True):
        self.path = str(file_path)
        self.loop = bool(loop)
        self.stop_signal = threading.Event()
        self.process = None
        self.worker = None

    def build_command(self):
        suffix = Path(self.path).suffix.lower()
        if suffix == '.wav':
            if not shutil.which('aplay'):
                return None
            return ['aplay', '-q', self.path]
        if suffix == '.mp3':
            if not shutil.which('ffplay'):
                return None
            # ffplay -loop 0 = endless loop; -autoexit = once and exit.
            base = ['ffplay', '-nodisp', '-loglevel', 'error',
                    '-volume', '35']
            return base + (['-loop', '0'] if self.loop else ['-autoexit']) + [self.path]
        return None

    def start(self):
        command = self.build_command()
        if command is None:
            print('[Houston Audio] Missing player/unsupported format; slideshow continues')
            return
        self.worker = threading.Thread(target=self._run, args=(command,), daemon=True)
        self.worker.start()

    def _run(self, command):
        # MP3 looping is managed by ffplay itself. WAV by restarting aplay.
        is_mp3 = Path(self.path).suffix.lower() == '.mp3'
        while not self.stop_signal.is_set():
            try:
                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                result = self.process.wait()
                self.process = None
                if self.stop_signal.is_set():
                    break
                if result != 0:
                    print('[Houston Audio] Playback failed; slideshow continues')
                    break
                if is_mp3 or not self.loop:
                    break
                if self.stop_signal.wait(0.05):
                    break
            except (OSError, ValueError) as exc:
                print(f'[Houston Audio] {exc}; slideshow continues')
                break

    def stop(self):
        self.stop_signal.set()
        p = self.process
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    p.kill()
                    p.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
