"""Automatic RAM scanner: narrows candidates in lockstep with real input events.

memory_scan.py requires the player to act, then switch to the terminal and
type a filter command -- the gap between "I moved" and "I typed c" adds slop
that lets false positives survive. This watches the keyboard/trackpad/mouse
devices directly (via evdev) and applies the filter itself the instant it
sees activity (or the instant a still period elapses), so the changed/
unchanged boundary lines up with the real input, not with typing speed.

Runs a full fresh baseline scan (same region/dtype as memory_scan.py) rather
than resuming from a prior candidate list -- a full 24MiB MEM1 read takes
~55ms, well within the poll interval, so there's no need to hand-carry
candidates between sessions.
"""

import argparse
import os
import select
import sys
import time

import dolphin_memory_engine as dme
import evdev

sys.path.insert(0, os.path.dirname(__file__))
from memory_scan import REGIONS, MemoryScanner  # noqa: E402

INPUT_DEVICES = ["/dev/input/event3", "/dev/input/event12", "/dev/input/event13"]

POLL_INTERVAL = 0.15  # seconds between filter steps
LIST_THRESHOLD = 60  # print full candidate list once the count drops below this


def open_devices(paths):
    devices = []
    for p in paths:
        try:
            devices.append(evdev.InputDevice(p))
        except OSError as e:
            print(f"skipping {p}: {e}")
    return devices


def had_activity(devices, timeout):
    """Drain any pending events from the given devices; return True if any arrived."""
    if not devices:
        time.sleep(timeout)
        return False
    ready, _, _ = select.select(devices, [], [], timeout)
    activity = False
    for dev in ready:
        for _ in dev.read():
            activity = True
    return activity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", choices=REGIONS, default="mem1")
    parser.add_argument("--dtype", default="float32")
    args = parser.parse_args()

    dme.hook()
    if not dme.is_hooked():
        print("Could not attach to Dolphin. Make sure the native build is running with the game loaded.")
        return

    devices = open_devices(INPUT_DEVICES)
    print(f"Watching {len(devices)} input device(s): {[d.name for d in devices]}")

    start, end = REGIONS[args.region]
    print(f"Baseline scan of {args.region} ({(end - start) / 2**20:.0f} MiB) as {args.dtype} ...")
    scanner = MemoryScanner(dme.read_bytes, start, end, args.dtype)
    last_count = int(scanner.mask.sum())
    print(f"Baseline: {last_count:,} candidates. Play normally -- Ctrl+C to stop.\n")

    try:
        while True:
            active = had_activity(devices, POLL_INTERVAL)
            scanner.rescan("changed" if active else "unchanged")
            count = int(scanner.mask.sum())

            if count != last_count:
                tag = "ACTIVE" if active else "idle"
                print(f"[{tag}] {count:,} candidates remain.")
                if count == 0:
                    print("All candidates eliminated -- Ctrl+C and reconsider the approach.")
                    break
                if count < LIST_THRESHOLD:
                    for addr, val in scanner.candidates(limit=LIST_THRESHOLD):
                        print(f"  0x{addr:08X}  {val}")
                last_count = count
    except KeyboardInterrupt:
        pass

    print("\nFinal candidates:")
    for addr, val in scanner.candidates(limit=LIST_THRESHOLD):
        print(f"  0x{addr:08X}  {val}")


if __name__ == "__main__":
    main()
