# Step 1: the environment contract

`envs/sim_tennis_env.py` returns fake, fixed data on purpose -- the goal was to
get the *shape* of the environment right before any tennis logic exists.

- `observation_space` / `action_space` aren't documentation, they're queried by
  code later (e.g. `PolicyNetwork` will read `env.observation_space.shape[0]`
  instead of hardcoding 9). That's the mechanism that lets `DolphinTennisEnv`
  swap in later without touching the network or training loop.
- `reset(seed, options) -> (obs, info)` and
  `step(action) -> (obs, reward, terminated, truncated, info)` are gymnasium's
  fixed signatures (the modern 5-tuple `step`, not old `gym`'s 4-tuple).
- `terminated` = episode ended because of something in the game (point won or
  lost). `truncated` = cut off for an external reason (e.g. a step limit).
  They get treated differently in return calculations later.

State vector order (must match everywhere): `[ball_x, ball_y, ball_z, ball_vx,
ball_vy, ball_vz, player_x, opponent_x, time_since_bounce]`. Units: meters,
real gravity -- chosen so debug numbers map to real-world intuition.
