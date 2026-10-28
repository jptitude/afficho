#!/usr/bin/env python3
"""AFFICHO v1.2.0: offline slideshow with configurable timing.

Uses stdlib Tkinter for full-HD PNG. Stable V1.0 stays in a separate directory.
"""
from pathlib import Path
import argparse
import math
import tkinter as tk
from houston_campaign import load_campaign
from houston_import import import_media
from houston_audio import AudioLoop

SLIDES_FOLDER = Path(__file__).resolve().parent / 'slides'

try:
    from PIL import Image, ImageTk, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class HoustonDisplay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('AFFICHO v1.2.0')
        self.root.configure(bg='black')
        self.root.attributes('-fullscreen', True)
        self.root.configure(cursor='none')
        self.root.update_idletasks()
        self.w = self.root.winfo_screenwidth()
        self.h = self.root.winfo_screenheight()
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h,
                                bg='black', bd=0, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.photo = None
        self.position = 0
        self.timer = None
        self.audio = None
        self.root.bind('<Escape>', lambda event: self.close())
        self.root.bind('<Control-q>', lambda event: self.close())
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<space>', lambda event: self.advance())
        self.root.bind('<Right>', lambda event: self.advance())
        self.root.bind('r', lambda event: self.advance())
        self.campaign = load_campaign(SLIDES_FOLDER)
        if self.campaign.audio_enabled and self.campaign.audio_file:
            self.audio = AudioLoop(self.campaign.audio_file, self.campaign.audio_loop)
            self.audio.start()
        self.advance()

    def close(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.audio:
            self.audio.stop()
        self.root.destroy()

    def load_photo(self, path):
        if PIL_AVAILABLE:
            with Image.open(path) as original:
                image = original.convert('RGB')
            image = ImageOps.contain(image, (self.w, self.h),
                                     method=Image.Resampling.BILINEAR)
            return ImageTk.PhotoImage(image, master=self.root)
        photo = tk.PhotoImage(file=str(path), master=self.root)
        factor = max(1, math.ceil(photo.width() / self.w),
                     math.ceil(photo.height() / self.h))
        return photo.subsample(factor, factor) if factor > 1 else photo

    def advance(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.canvas.delete('all')
        self.photo = None
        slide = self.campaign.slides[self.position]
        self.position = (self.position + 1) % len(self.campaign.slides)
        try:
            self.photo = self.load_photo(slide.path)
            self.canvas.create_image(self.w // 2, self.h // 2,
                                     image=self.photo, anchor='center')
            if self.campaign.branding:
                margin = 28
                self.canvas.create_text(self.w - margin, self.h - margin,
                                        text=self.campaign.brand_label,
                                        fill='white', anchor='se',
                                        font=('DejaVu Sans', 14))
        except Exception as exc:
            self.canvas.create_text(self.w // 2, self.h // 2,
                                    text=f'Unable to display {slide.path.name}\n{exc}',
                                    fill='white', font=('DejaVu Sans', 16),
                                    justify='center')
        self.timer = self.root.after(round(slide.duration * 1000), self.advance)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-import', action='store_true',
                        help='Test existing dev/slides only; do not read bootfs')
    args = parser.parse_args()
    if not args.no_import:
        import_media()
    HoustonDisplay().root.mainloop()
