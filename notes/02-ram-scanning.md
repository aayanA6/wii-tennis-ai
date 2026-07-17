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

## 2026-07-13 session: live scanning attempt, score abandoned for now

Got the native Dolphin build attached and ran the scanner against a live
Wii Sports Tennis match. Score-hunting ate the whole session and was
ultimately set aside in favor of a plan split (see "Plan going forward"
below). Findings, in case we revisit:

**Environment gotchas (will recur every session, not one-time fixes):**
- `ptrace_scope` resets to `1` (restricted) on every reboot -- memory reads
  fail with `RuntimeError: Could not read memory at ...` until you run
  `sudo sysctl kernel.yama.ptrace_scope=0` again. Not persistent by design;
  redo it each session.
- The dolphin-memory-engine hook can go stale mid-session (observed after
  Dolphin briefly showed the game list instead of gameplay -- reloading a
  game likely reallocates the MEM1 host buffer, invalidating the old
  hook's cached pointer). Symptom: a long-running scanner process starts
  failing with the same "Could not read memory" error even though Dolphin
  is fine and a *fresh* `dme.hook()` call works immediately. Fix: kill and
  restart the scanner process (re-hook) any time reads start failing.
- When driving `memory_scan.py` interactively from a script/agent rather
  than a human at a terminal: don't `pkill -f "memory_scan.py"` from
  within a shell command that *also* contains the literal string
  `memory_scan.py` later on (e.g. the next line that launches it) --
  `pkill -f` matches the invoking shell's own command text and kills
  itself before it reaches the launch line. Kill by exact PID instead.

**Score encoding (byte-level, in MEM1):**
- The displayed score text ("15", "30", "40", "Deuce", "Advantage") is
  *not* the literal stored value. Confirmed by direct test: filtered
  candidates for "equals 15" then "equals 30" using the correct dtype
  (`uint8`) and got zero survivors both times. The raw byte is a small
  point-index (0/1/2/3/...) that the game maps to display text, not the
  literal number.
- Deuce/advantage make the index model murkier still -- in-game evidence
  was inconsistent about whether a player's raw index keeps incrementing
  past 3 through advantage exchanges or whether advantage is tracked as a
  separate shared flag. Multiple `unchanged`/`increased` filter chains
  that looked like they were converging (down to single digits of
  candidates) unexpectedly zeroed out right at deuce/advantage/game-end
  transitions. Never got a fully confirmed address.
- Root difficulty: score is a *low-entropy* value (~5 possible states) that
  only changes on a rare, rule-governed event (a scored point). Both
  properties are close to worst-case for unknown-initial-value scanning --
  low entropy means lots of coincidental false-positive matches survive
  each filter, and rare/rule-bound changes mean every mistake (a missed
  intermediate state, a misjudged deuce transition) costs a full round
  with no way to double-check except after the fact.

**Screen-reading side effort (this actually worked well):**
- Built `scripts/read_score.py`: `grim` screenshot -> crop the on-screen
  "XX - XX" region -> grayscale threshold -> upscale 8x -> `ImageFilter.
  MaxFilter(5)` to fill in the hollow-outline digit font -> `pytesseract`
  with `--psm 7` and a digit/dash whitelist. Works, but not perfectly:
  occasionally misreads a digit (saw "3" -> "2" and a stray extra digit
  once) -- worth a visual double-check via a saved crop when a reading
  looks like an invalid tennis score.
- Important environment note: this machine runs Hyprland (Wayland). `mss`
  and `xwd`/plain X11 grabs return solid black (Wayland compositors block
  arbitrary X11 screen capture for security) even though `DISPLAY` is set
  and `xdpyinfo` works. `grim` (wlroots screenshot tool) is what actually
  works here. Don't waste time on X11 grab tools on this box.

## Plan going forward

Split the problem instead of finding everything via blind RAM scanning:
- **Score / reward signal / episode boundaries:** use `scripts/
  read_score.py` (OCR) directly as the source of truth. It's a low-
  frequency, discrete signal (once per point) -- exactly what OCR is good
  at, and sidesteps the low-entropy-byte problem entirely.
- **Ball / paddle position (and anything else read at observation
  frequency):** use RAM scanning, but expect this to go *better* than
  score did, not worse -- these are float32s (high entropy, few
  coincidental matches) that the player directly and continuously
  controls, so the standard "hold still -> unchanged; move one direction
  -> increased/decreased" technique applies cleanly without any of
  score's rule-governed-event or low-entropy problems.
