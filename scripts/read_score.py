"""Read the Wii Sports Tennis on-screen score via screenshot + OCR.

Captures the Dolphin window region showing "XX - XX" and OCRs it. Built to
close the loop on RAM scanning without relying on a human narrating score
changes over chat -- see notes/02-ram-scanning.md.

Crop coordinates were hand-calibrated against a 1920x1080 capture with the
Dolphin window docked on the right half of the screen. Re-calibrate if the
window moves/resizes (see the `--calibrate` flag).
"""

import argparse
import subprocess
import tempfile
import os

from PIL import Image, ImageFilter
import pytesseract

CROP_BOX = (1350, 405, 1510, 435)  # (left, top, right, bottom) in full-screen pixels


def grab_screen(path):
    subprocess.run(["grim", path], check=True)


def read_score(screenshot_path=None):
    tmp_path = screenshot_path
    cleanup = False
    if tmp_path is None:
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        cleanup = True

    try:
        grab_screen(tmp_path)
        im = Image.open(tmp_path)
        crop = im.crop(CROP_BOX).convert("L")
        thresh = crop.point(lambda p: 255 if p > 200 else 0)
        big = thresh.resize((thresh.width * 8, thresh.height * 8), Image.LANCZOS)
        dilated = big.filter(ImageFilter.MaxFilter(5))
        text = pytesseract.image_to_string(
            dilated, config="--psm 7 -c tessedit_char_whitelist=0123456789-"
        ).strip()
        return text
    finally:
        if cleanup:
            os.remove(tmp_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate", action="store_true", help="save a full screenshot for re-cropping")
    args = parser.parse_args()

    if args.calibrate:
        grab_screen("/tmp/calibrate.png")
        print("Saved /tmp/calibrate.png -- find the score's pixel box and update CROP_BOX.")
        return

    print(read_score())


if __name__ == "__main__":
    main()
