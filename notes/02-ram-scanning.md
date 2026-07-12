# Phase B groundwork: RAM address scanning

`scripts/memory_scan.py` is a from-scratch "unknown initial value" scanner,
the same technique Cheat Engine / Dolphin Memory Engine use, built on the
`dolphin-memory-engine` PyPI library's `read_bytes(console_address, size)`.

Why build our own instead of using the standalone Dolphin Memory Engine GUI:
it's ours to read, and the whole technique is short enough to be worth owning
rather than treating as a black box.

How it works:
1. Read an entire memory region (default: MEM1, `0x80000000`-`0x81800000`,
   24 MiB -- where Wii games usually keep gameplay state) once as a baseline,
   parsed as a numpy array of a chosen dtype (float32 for positions, uint8/
   int32 for counters like score).
2. You do something in-game (e.g. score a point), then tell the tool what you
   expect (`i` = increased, `e 1` = now equals 1, etc).
3. It re-reads the whole region and keeps only the addresses whose value
   changed the way you described -- vectorized with numpy comparisons rather
   than looping in Python, since MEM1 alone is millions of addresses.
4. Repeat with a different action each time (score again, watch it become 2,
   etc) until only a handful of addresses survive.

Validated against a fake in-memory buffer (no real Dolphin needed) -- planted
a single byte that behaves like a score counter, confirmed the scanner narrows
1024 candidates down to exactly that one address.

**Blocker found and fixed:** the installed Dolphin was a Flatpak build.
Flatpak sandboxes block `ptrace`, which memory-hooking depends on -- a
sandboxed Dolphin cannot be attached to. Fix: install the native AUR package
(`yay -S dolphin-emu`) and run the game from that build instead.

**Not done yet:** actually running the scanner against the live game --
waiting on the native Dolphin build to finish installing. Once addresses for
score / ball position / paddle position are found, they get recorded in a new
`envs/memory_map.py` (doesn't exist yet).
