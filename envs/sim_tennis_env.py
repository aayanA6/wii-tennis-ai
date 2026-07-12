import numpy as np
import gymnasium as gym
from gymnasium import spaces

# Order matters: this is the exact vector the policy network will receive.
# [ball_x, ball_y, ball_z, ball_vx, ball_vy, ball_vz, player_x, opponent_x, time_since_bounce]
OBS_LOW = np.array([-5, -12, 0, -20, -20, -20, -5, -5, 0], dtype=np.float32)
OBS_HIGH = np.array([5, 12, 5, 20, 20, 20, 5, 5, 10], dtype=np.float32)

WAIT, SWING_CENTER, SWING_LEFT, SWING_RIGHT = 0, 1, 2, 3

# All distances in meters, matching real-world tennis court scale (roughly --
# not exact regulation numbers) so debug output maps to real-world intuition.
DT = 1.0 / 60.0  # one physics step per Wii-like 60fps frame
GRAVITY = 9.8

COURT_HALF_LENGTH = 10.0  # net-to-baseline distance
COURT_HALF_WIDTH = 4.0
Y_PLAYER = -COURT_HALF_LENGTH
Y_OPPONENT = COURT_HALF_LENGTH

MAX_PLAYER_SPEED = 8.0  # m/s the Mii auto-runs at -- caps how far it can close in one step

# A swing only connects if the ball is within this box around the player.
HIT_Y_TOLERANCE = 1.0
HIT_X_TOLERANCE = 1.3
HIT_Z_MAX = 2.2

# A swing (hit or whiff) locks out further swings for this many frames --
# real racket recovery time. Without this, "swing every frame" trivially
# covers the hit window and beats the environment by brute force, which
# would make the random-action baseline nearly perfect and leave nothing
# for a trained policy to improve on.
SWING_COOLDOWN_FRAMES = 18

BASELINE_MISS_MARGIN = 1.5  # ball this far past the player's baseline = definitely missed
MAX_STEPS = 600  # 10 seconds at 60fps -- safety net so a stuck episode can't loop forever

SWING_X_OFFSET = {SWING_CENTER: 0.0, SWING_LEFT: -4.0, SWING_RIGHT: 4.0}


class SimTennisEnv(gym.Env):
    """Simplified single-shot tennis rally standing in for real Wii Sports Tennis.

    One ball is served toward the player per episode. The player's x position
    auto-tracks the ball (mirroring the real game's Mii auto-run -- you don't
    control movement, only swing timing and direction), so the only decision
    each step is which of the 4 actions to take. The episode ends the moment
    the player connects with a legal swing (+1) or clearly misses (-1).
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(low=OBS_LOW, high=OBS_HIGH, dtype=np.float32)
        self.action_space = spaces.Discrete(4)
        self._state = None
        self._step_count = 0
        self._bounced = False
        self._swing_cooldown = 0

    def _obs(self):
        s = self._state
        return np.array(
            [s["ball_x"], s["ball_y"], s["ball_z"], s["ball_vx"], s["ball_vy"], s["ball_vz"],
             s["player_x"], s["opponent_x"], s["time_since_bounce"]],
            dtype=np.float32,
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._step_count = 0
        self._bounced = False
        # Serve toward the player from the opponent's side, with enough
        # randomness (start position, speed, spin-ish sideways drift) that a
        # policy can't just memorize one fixed trajectory.
        self._state = {
            "ball_x": self.np_random.uniform(-2.0, 2.0),
            "ball_y": Y_OPPONENT * 0.8,
            "ball_z": 3.0,
            "ball_vx": self.np_random.uniform(-2.0, 2.0),
            "ball_vy": -self.np_random.uniform(9.0, 14.0),  # negative = toward the player
            "ball_vz": self.np_random.uniform(-1.0, 1.0),
            "player_x": 0.0,
            "opponent_x": 0.0,  # not driven by any logic yet -- arrives in step 3's CPU opponent
            "time_since_bounce": 0.0,
        }
        return self._obs(), {}

    def step(self, action):
        assert self.action_space.contains(action), f"invalid action {action}"
        s = self._state
        self._step_count += 1

        # The Mii auto-runs toward the ball's current x position, at a capped
        # speed -- this is what makes swing *timing* matter: if the ball is
        # moving fast sideways, the player might not get there in time.
        dx = s["ball_x"] - s["player_x"]
        max_step = MAX_PLAYER_SPEED * DT
        s["player_x"] += float(np.clip(dx, -max_step, max_step))

        # A swing attempt is only possible if the racket has recovered from
        # the last one -- during cooldown, any action is forced to behave
        # like WAIT.
        can_swing = self._swing_cooldown == 0
        if self._swing_cooldown > 0:
            self._swing_cooldown -= 1
        elif action != WAIT:
            self._swing_cooldown = SWING_COOLDOWN_FRAMES

        in_reach = (
            abs(s["ball_y"] - Y_PLAYER) < HIT_Y_TOLERANCE
            and abs(s["ball_x"] - s["player_x"]) < HIT_X_TOLERANCE
            and s["ball_z"] < HIT_Z_MAX
        )

        if action != WAIT and can_swing and in_reach:
            # Legal return: send the ball back toward the opponent's side.
            s["ball_vy"] = self.np_random.uniform(9.0, 14.0)  # positive = toward the opponent
            s["ball_vz"] = self.np_random.uniform(3.0, 5.0)
            s["ball_vx"] = SWING_X_OFFSET[action] + self.np_random.uniform(-1.0, 1.0)
            return self._obs(), 1.0, True, False, {"outcome": "hit"}

        # No swing connected this frame (either WAIT, or a swing that missed
        # -- whiffing has no penalty, only failing to return the ball does):
        # advance the physics by one frame.
        s["ball_vz"] -= GRAVITY * DT
        s["ball_x"] += s["ball_vx"] * DT
        s["ball_y"] += s["ball_vy"] * DT
        s["ball_z"] += s["ball_vz"] * DT

        if s["ball_z"] <= 0.0:
            s["ball_z"] = 0.0
            if self._bounced:
                # Second bounce before the player returned it -- point lost.
                return self._obs(), -1.0, True, False, {"outcome": "double_bounce"}
            self._bounced = True
            s["ball_vz"] = -s["ball_vz"] * 0.75  # lose some energy on the bounce
            s["time_since_bounce"] = 0.0
        else:
            s["time_since_bounce"] += DT

        if s["ball_y"] < Y_PLAYER - BASELINE_MISS_MARGIN:
            return self._obs(), -1.0, True, False, {"outcome": "past_baseline"}

        truncated = self._step_count >= MAX_STEPS
        return self._obs(), 0.0, False, truncated, {}
