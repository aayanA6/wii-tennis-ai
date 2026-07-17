# wii-tennis-ai

An RL agent that learns to play Wii Sports Tennis, built step by step to
learn the ML/RL from the ground up rather than dropping in a finished
solution. See `notes/` for a running log of what each step does and why, in
build order.

## Status

**Phase A (simulator + hand-rolled RL):**
- [x] Step 1: repo skeleton + dummy `SimTennisEnv` (gymnasium contract)
- [x] Step 2: real ball physics + random-agent baseline (random hit rate ~51%)
- [x] Step 3: rule-based CPU opponent (random-vs-CPU win rate ~18%)
- [ ] Step 4: PyTorch `PolicyNetwork`
- [ ] Step 5: rollout collection + Monte Carlo returns
- [ ] Step 6: REINFORCE training loop (milestone: beats random baseline)
- [ ] Steps 7-11: reward-to-go -> baseline -> actor-critic -> GAE -> PPO

**Phase B groundwork (real Dolphin, in parallel):**
- [x] Found the installed Dolphin was Flatpak (sandboxed, blocks the
      `ptrace`-based memory hooking this project needs) -- switching to a
      native AUR build (`yay -S dolphin-emu`)
- [x] `scripts/memory_scan.py`: from-scratch RAM address scanner, validated
      against a fake memory buffer
- [ ] Run the scanner against the live game to find score/ball/paddle
      addresses, record them in `envs/memory_map.py`
- [ ] `envs/dolphin_tennis_env.py` matching `SimTennisEnv`'s interface

## Setup

```
python3 -m venv .venv
.venv/bin/pip install -e .
```
