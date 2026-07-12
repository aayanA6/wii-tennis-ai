"""Interactive Cheat-Engine-style RAM scanner for a running native Dolphin instance.

Finds addresses in the Wii's emulated memory (score, ball position, paddle
position, ...) by repeatedly narrowing a set of candidate addresses: read the
whole region once as a baseline, have the user do something in-game, read it
again, and keep only the addresses whose value changed the way the user
describes (increased, decreased, became a specific value, ...).

Nothing here is Wii-Sports-Tennis-specific -- this is a general tool. The
addresses it finds should get recorded in a small mapping module once known
(that module doesn't exist yet -- it's the next step after this).
"""

import argparse

import numpy as np

# The Wii has two RAM regions visible to games. Most gameplay state (scores,
# entity positions, timers) tends to live in MEM1, so that's the default.
MEM1_START, MEM1_END = 0x80000000, 0x81800000  # 24 MiB, "low" main memory
MEM2_START, MEM2_END = 0x90000000, 0x94000000  # 64 MiB, "high" main memory

REGIONS = {"mem1": (MEM1_START, MEM1_END), "mem2": (MEM2_START, MEM2_END)}

CHUNK_SIZE = 4 * 1024 * 1024  # read in 4 MiB pieces rather than one huge call

CONDITIONS = {"c": "changed", "u": "unchanged", "i": "increased", "d": "decreased"}

HELP = """
Commands (do something in-game, THEN type a command and press enter):
  c        keep candidates whose value CHANGED since the last scan
  u        keep candidates whose value stayed UNCHANGED
  i        keep candidates whose value INCREASED
  d        keep candidates whose value DECREASED
  e VALUE  keep candidates now EQUAL to VALUE (e.g. "e 15")
  l        list current surviving candidates
  r        reset and start over from a fresh baseline
  q        quit and print final candidates
"""


class MemoryScanner:
    """Narrows a set of candidate addresses over successive scans.

    Takes a `read_bytes(address, size) -> bytes` function rather than talking
    to Dolphin directly, so the scanning logic can be exercised against a fake
    reader in tests without a real emulator attached.
    """

    def __init__(self, read_bytes, start, end, dtype):
        self.read_bytes = read_bytes
        self.start = start
        self.dtype = np.dtype(dtype)
        region_len = end - start
        self.addresses = np.arange(start, end, self.dtype.itemsize, dtype=np.uint32)
        self.values = self._read_region(region_len)
        self.mask = np.ones(len(self.addresses), dtype=bool)

    def _read_region(self, region_len):
        chunks = []
        offset = 0
        while offset < region_len:
            size = min(CHUNK_SIZE, region_len - offset)
            chunks.append(self.read_bytes(self.start + offset, size))
            offset += size
        raw = b"".join(chunks)
        return np.frombuffer(raw, dtype=self.dtype)

    def rescan(self, condition, value=None, tolerance=1e-3):
        new_values = self._read_region(len(self.values) * self.dtype.itemsize)
        old = self.values[self.mask]
        new = new_values[self.mask]

        if condition == "changed":
            keep = new != old
        elif condition == "unchanged":
            keep = new == old
        elif condition == "increased":
            keep = new > old
        elif condition == "decreased":
            keep = new < old
        elif condition == "equals":
            if np.issubdtype(self.dtype, np.floating):
                keep = np.abs(new - value) <= tolerance
            else:
                keep = new == value
        else:
            raise ValueError(f"unknown condition {condition!r}")

        surviving_indices = np.flatnonzero(self.mask)
        self.mask[surviving_indices] = keep
        self.values = new_values
        return int(self.mask.sum())

    def candidates(self, limit=50):
        idx = np.flatnonzero(self.mask)[:limit]
        return [(int(self.addresses[i]), self.values[i].item()) for i in idx]


def run(read_bytes, region, dtype):
    start, end = REGIONS[region]
    print(f"Scanning {region} ({(end - start) / 2**20:.0f} MiB) as {dtype} ...")
    scanner = MemoryScanner(read_bytes, start, end, dtype)
    print(f"Baseline captured: {scanner.mask.sum():,} candidate addresses.")
    print(HELP)

    while True:
        cmd = input("> ").strip()
        if not cmd:
            continue
        if cmd == "q":
            break
        if cmd == "r":
            scanner = MemoryScanner(read_bytes, start, end, dtype)
            print(f"Reset. Baseline: {scanner.mask.sum():,} candidates.")
            continue
        if cmd == "l":
            for addr, val in scanner.candidates():
                print(f"  0x{addr:08X}  {val}")
            print(f"{scanner.mask.sum():,} total candidates")
            continue
        if cmd.startswith("e "):
            raw_value = cmd[2:].strip()
            try:
                value = float(raw_value) if "float" in dtype else int(raw_value)
            except ValueError:
                print(f"couldn't parse {raw_value!r} as a value for dtype {dtype}")
                continue
            n = scanner.rescan("equals", value=value)
        elif cmd in CONDITIONS:
            n = scanner.rescan(CONDITIONS[cmd])
        else:
            print(f"unrecognized command {cmd!r} -- see the command list above")
            continue
        print(f"{n:,} candidates remain.")

    print("\nFinal candidates:")
    for addr, val in scanner.candidates():
        print(f"  0x{addr:08X}  {val}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", choices=REGIONS, default="mem1")
    parser.add_argument("--dtype", default="float32", help="numpy dtype to scan as, e.g. float32, int32, uint8")
    args = parser.parse_args()

    import dolphin_memory_engine as dme

    dme.hook()
    if not dme.is_hooked():
        print(
            "Could not attach to Dolphin. Make sure the NATIVE (non-Flatpak) build "
            "is running with Wii Sports Tennis loaded, then try again."
        )
        return

    run(dme.read_bytes, args.region, args.dtype)


if __name__ == "__main__":
    main()
