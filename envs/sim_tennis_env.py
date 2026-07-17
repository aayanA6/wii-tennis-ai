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

MAX_RUN_SPEED = 8.0  # m/s either side auto-runs at -- caps how far it can close in one step

# A swing only connects if the ball is within this box around whoever's side
# it's on (checked against player_x/Y_PLAYER or opponent_x/Y_OPPONENT).
HIT_Y_TOLERANCE = 1.0
HIT_X_TOLERANCE = 1.3
HIT_Z_MAX = 2.2

# A swing (hit or whiff) locks out further swings for this many frames --
# real racket recovery time. Without this, "swing every frame" trivially
# covers the hit window and beats the environment by brute force, which
# would make the random-action baseline nearly perfect and leave nothing
# for a trained policy to improve on. Player and opponent recover on
# independent cooldowns.
SWING_COOLDOWN_FRAMES = 18

BASELINE_MISS_MARGIN = 1.5  # ball this far past a baseline, uncontested = that side's error
MAX_STEPS = 600  # 10 seconds at 60fps -- safety net so a stuck episode can't loop forever

SWING_X_OFFSET = {SWING_CENTER: 0.0, SWING_LEFT: -4.0, SWING_RIGHT: 4.0}

# Rule-based CPU: always returns the ball when it's in reach and off cooldown
# (no shot selection/strategy beyond that), aimed into whichever half of the
# court the player isn't currently standing in -- simple, but enough to
# force the player to actually move instead of camping center.
CPU_AIM_FRACTION = 0.8  # aim toward the court edge, not dead on the sideline


class SimTennisEnv(gym.Env):
    """Simplified tennis rally standing in for real Wii Sports Tennis.

    One ball is served toward the player per episode. Both the player's and
    opponent's x positions auto-track the ball (mirroring the real game's Mii
    auto-run -- you don't control movement, only swing timing and direction),
    so the only decision each step is which of the 4 actions to take. Whoever
    the ball isn't currently heading toward is on "auto" -- the opponent side
    is always the simple rule-based CPU described above `CPU_AIM_FRACTION`.

    A rally continues, alternating sides, until either side fails to return
    the ball (double bounce or it sails past their baseline uncontested).
    `terminated` fires only then: +1 if the opponent failed, -1 if the player
    did. A successful return that keeps the rally alive is reward 0,
    non-terminal.
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(low=OBS_LOW, high=OBS_HIGH, dtype=np.float32)
        self.action_space = spaces.Discrete(4)
        self._state = None
        self._step_count = 0
        self._bounced = False
        self._player_cooldown = 0
        self._opponent_cooldown = 0

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
        self._player_cooldown = 0
        self._opponent_cooldown = 0
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
            "opponent_x": 0.0,
            "time_since_bounce": 0.0,
        }
        return self._obs(), {}

    def step(self, action):
        assert self.action_space.contains(action), f"invalid action {action}"
        s = self._state
        self._step_count += 1

        # Both sides auto-run toward the ball's current x position, at a
        # capped speed -- this is what makes swing *timing* matter: if the
        # ball is moving fast sideways, whoever it's headed toward might not
        # get there in time.
        max_step = MAX_RUN_SPEED * DT
        s["player_x"] += float(np.clip(s["ball_x"] - s["player_x"], -max_step, max_step))
        s["opponent_x"] += float(np.clip(s["ball_x"] - s["opponent_x"], -max_step, max_step))

        # Cooldowns recover every frame regardless of which side the ball is
        # currently on -- a racket's recovery time doesn't care about that.
        if self._player_cooldown > 0:
            self._player_cooldown -= 1
        if self._opponent_cooldown > 0:
            self._opponent_cooldown -= 1

        heading_to_player = s["ball_vy"] < 0

        if heading_to_player:
            can_swing = self._player_cooldown == 0
            in_reach = (
                abs(s["ball_y"] - Y_PLAYER) < HIT_Y_TOLERANCE
                and abs(s["ball_x"] - s["player_x"]) < HIT_X_TOLERANCE
                and s["ball_z"] < HIT_Z_MAX
            )
            if action != WAIT and can_swing:
                self._player_cooldown = SWING_COOLDOWN_FRAMES
            if action != WAIT and can_swing and in_reach:
                # Legal return: send the ball back toward the opponent.
                s["ball_vy"] = self.np_random.uniform(9.0, 14.0)  # positive = toward the opponent
                s["ball_vz"] = self.np_random.uniform(3.0, 5.0)
                s["ball_vx"] = SWING_X_OFFSET[action] + self.np_random.uniform(-1.0, 1.0)
                self._bounced = False  # fresh leg, now headed to the opponent
                return self._obs(), 0.0, False, False, {"outcome": "player_hit"}
        else:
            can_swing = self._opponent_cooldown == 0
            in_reach = (
                abs(s["ball_y"] - Y_OPPONENT) < HIT_Y_TOLERANCE
                and abs(s["ball_x"] - s["opponent_x"]) < HIT_X_TOLERANCE
                and s["ball_z"] < HIT_Z_MAX
            )
            # Rule-based CPU: no decision to make, it always swings when it
            # can connect, aimed away from the player's current position.
            if can_swing and in_reach:
                self._opponent_cooldown = SWING_COOLDOWN_FRAMES
                sign = -1.0 if s["player_x"] >= 0 else 1.0
                aim_x = sign * COURT_HALF_WIDTH * CPU_AIM_FRACTION
                s["ball_vy"] = -self.np_random.uniform(9.0, 14.0)  # negative = toward the player
                s["ball_vz"] = self.np_random.uniform(3.0, 5.0)
                s["ball_vx"] = aim_x + self.np_random.uniform(-1.0, 1.0)
                self._bounced = False  # fresh leg, now headed to the player
                return self._obs(), 0.0, False, False, {"outcome": "opponent_hit"}

        # Nobody swung this frame (wait, whiff, or the CPU couldn't reach it
        # -- whiffing/missing a swing attempt has no penalty by itself, only
        # failing to return the ball before it's lost does): advance physics.
        s["ball_vz"] -= GRAVITY * DT
        s["ball_x"] += s["ball_vx"] * DT
        s["ball_y"] += s["ball_vy"] * DT
        s["ball_z"] += s["ball_vz"] * DT

        if s["ball_z"] <= 0.0:
            s["ball_z"] = 0.0
            if self._bounced:
                # Second bounce before whoever it was headed to returned it.
                if heading_to_player:
                    return self._obs(), -1.0, True, False, {"outcome": "player_double_bounce"}
                return self._obs(), 1.0, True, False, {"outcome": "opponent_double_bounce"}
            self._bounced = True
            s["ball_vz"] = -s["ball_vz"] * 0.75  # lose some energy on the bounce
            s["time_since_bounce"] = 0.0
        else:
            s["time_since_bounce"] += DT

        if heading_to_player and s["ball_y"] < Y_PLAYER - BASELINE_MISS_MARGIN:
            return self._obs(), -1.0, True, False, {"outcome": "player_past_baseline"}
        if not heading_to_player and s["ball_y"] > Y_OPPONENT + BASELINE_MISS_MARGIN:
            return self._obs(), 1.0, True, False, {"outcome": "opponent_past_baseline"}

        truncated = self._step_count >= MAX_STEPS
        return self._obs(), 0.0, False, truncated, {}
