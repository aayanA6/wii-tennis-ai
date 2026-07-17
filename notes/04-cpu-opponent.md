# Step 3: rule-based CPU opponent

`envs/sim_tennis_env.py` previously ended the episode the moment the player's
swing connected (+1) -- that's not actually "winning the point" per
`notes/01-gymnasium-contract.md`'s own definition of `terminated`, just
returning the ball once. This step turns it into a real rally.

## What changed

- Both `player_x` and `opponent_x` now auto-track the ball every frame (only
  `player_x` did before; `opponent_x` was a dead field waiting for this step).
- Player and opponent each have an independent swing cooldown (was a single
  shared `_swing_cooldown`, meaningless once there are two swingers).
- Which side is "in play" is just `ball_vy`'s sign: negative heads toward the
  player (their action matters that frame), positive heads toward the
  opponent (the CPU acts, the passed-in `action` is ignored that frame).
- The CPU has no strategy beyond "always swing back when in reach and off
  cooldown," aimed at whichever half of the court the player isn't currently
  standing in (`CPU_AIM_FRACTION`). That's enough to force movement without
  needing anything smarter for a first pass.
- `terminated` now only fires when a side actually fails: double bounce, or
  the ball sails past their baseline uncontested. Successful returns by
  either side are `reward=0.0`, non-terminal -- the rally keeps going.
  Reward is still +1/-1 from the player's perspective (opponent's failure
  is a player win).

## Random-baseline check

Same practice as step 2 (`notes/03-ball-physics-baseline.md`): run the
random-action baseline before writing any learning code, so a trained
policy's improvement is measured against a real number, not a guess.

3000 episodes, random actions vs. the CPU:
- **Player win rate: ~18%** (down from the old single-shot design's ~50.8%
  "hit rate," which is expected and correct -- winning a whole rally against
  an opponent that always returns compounds the player's failure probability
  across multiple exchanges, instead of the episode ending after one swing).
- Dominant loss mode: `player_past_baseline` (~55%), i.e. random actions
  mostly fail to swing inside the ~15-frame hit window on a fast incoming
  ball -- expected given 3 of 4 actions are a swing but timing has to line up.
- ~2% of episodes hit the 600-step (`MAX_STEPS`) truncation cap from long
  back-and-forth rallies -- the safety net is doing its job, not a bug.
- Sanity check: `WAIT`-only play loses 200/200 episodes, always attributed
  to the player's side (`player_past_baseline` / `player_double_bounce`,
  never misattributed to the opponent) -- confirms the win/loss sign
  convention didn't get flipped anywhere in the two-sided rewrite.

18% leaves plenty of room for step 6's "beat the random baseline" milestone
to mean something, same reasoning as step 2's note.
