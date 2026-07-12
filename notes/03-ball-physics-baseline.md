# Step 2: ball physics + the random-baseline sanity check

`envs/sim_tennis_env.py` now simulates one served ball per episode: real
gravity, a bounce, and a player whose x position auto-tracks the ball (Mii
auto-run) at a capped speed. The agent's only decision each frame is
`{wait, swing_center, swing_left, swing_right}`. Episode ends the moment a
swing connects (+1) or the ball is clearly missed (-1): flew past the
baseline, or bounced twice.

## The bug the random-baseline check caught

First version had no cost to swinging: any frame, 3 of the 4 actions are a
swing, and a swing landed inside a ~15-frame hit window connected
immediately. Running 2000 episodes of pure random actions gave a **99.8%**
hit rate. That's a broken environment for RL purposes -- if random play
already wins almost every time, there is no room to demonstrate a trained
policy is better, and the eventual REINFORCE milestone (step 6: "beat the
random baseline") would be meaningless.

**Fix:** added `SWING_COOLDOWN_FRAMES` (18 frames, ~0.3s) -- any swing
attempt, hit or whiff, locks out further swings until it expires, modeling
real racket recovery time. Also narrowed `HIT_Y_TOLERANCE` (1.5m -> 1.0m).
Spamming swings every frame now risks using up the one real attempt on a
premature whiff and being on cooldown when the ball actually arrives.

Re-ran the same 3000-episode random check after the fix: **hit rate ~50.8%**,
mean reward ~0.015. That's the number step 6's trained policy needs to beat
by a wide margin for the milestone to mean anything.

**Lesson:** always run the random-baseline check *before* writing any
learning code, not after -- it's what caught this, and it would have been
much harder to tell "the policy learned something" from "the environment was
never hard to begin with" once a network was in the loop too.
