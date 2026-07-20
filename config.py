"""Static configuration and tuning for the slime platformer.

Everything here is a constant: window size, physics, entity sizes, difficulty
presets, and animation timings. Mutable game state (player position, score,
the live difficulty values) lives in slimemain.py instead.
"""

# --- Window / world -----------------------------------------------------------
SCREEN_W = 960
SCREEN_H = 850

# One map chunk of islands; repeated infinitely as the world scrolls
CHUNK_WIDTH = 960
# Raised, taller platforms with stepping-stone heights so there's more room to
# climb: low steps lead up to the tall platforms near the top of the play area.
ISLAND_TEMPLATES = [
    {"x": 150, "y": 560, "width": 130, "height": 80},
    {"x": 430, "y": 430, "width": 120, "height": 75},
    {"x": 700, "y": 525, "width": 140, "height": 85},
    {"x": 250, "y": 300, "width": 110, "height": 72},
    {"x": 600, "y": 235, "width": 125, "height": 80},
]

platform_height = 170
GROUND_TOP = SCREEN_H - platform_height
GROUND_DEPTH = max(platform_height + 40, SCREEN_H - GROUND_TOP + 80)
# One seamless ground tile: grass + dirt + rock + plants all scroll together
GROUND_TILE_WIDTH = 480

# --- Player physics / animation ----------------------------------------------
square_size = 40
speed = 5                 # horizontal speed while airborne
half_ellipse_speed = 3.5  # horizontal speed on the ground
gravity = 0.5
jump_strength = -12
# Tail wiggle: full stretch-retract cycle period (ms) and max extra width (px)
tail_cycle_ms = 920
tail_max_stretch = 6.0
bob_amplitude = 4
bob_frequency = 0.5
BLINK_INTERVAL_MS = 3000
BLINK_DURATION_MS = 140

# --- Stamina / hotbar ---------------------------------------------------------
sprint_ticks = 500
SPRINT_REFILL = 250   # stamina restored per sprint potion (no auto-regen)
hotbar_slots = 5

# --- Enemies / combat ---------------------------------------------------------
monster_attack_cooldown_ms = 700
MONSTER_DAMAGE = 24
MONSTER_KNOCKBACK = 15.0   # horizontal shove (px/frame) away from the enemy
KNOCKBACK_DECAY = 0.80     # how quickly the shove fades each frame
# Enclose animation duration when the slime consumes an enemy
CONSUME_ANIM_MS = 1000
# Two flavors of invincibility (both tracked by `invincible_until`):
#  - a brief mercy window right after a consume, so a stomp isn't punished
#  - a long window granted by using a picked-up star item from the hotbar
CONSUME_IFRAME_MS = 450
STAR_INVINCIBILITY_MS = 6000

# --- Pickups ------------------------------------------------------------------
POTION_WIDTH = 20
POTION_HEIGHT = 30
POTION_HEAL_AMOUNT = 25
STAR_SIZE = 26

# --- Death / run stats --------------------------------------------------------
PIXELS_PER_METER = 50.0   # world pixels that count as one "meter"
DEATH_ANIM_MS = 900       # slime melt animation duration

# --- Boss level ---------------------------------------------------------------
# The dragon returns in every [200n, 200n+25] m window; each return hits harder.
BOSS_METERS = 200         # boss windows recur every this many meters
BOSS_END_METERS = 250     # end of each boss window (BOSS_METERS + 50 -> a 50 m zone)
DRAGON_DAMAGE_STEP = 12   # extra dragon contact damage per return

# --- Difficulty ---------------------------------------------------------------
# Chosen on the start screen with keys 1/2/3. Higher levels pack in more
# hazards that move faster.
DIFFICULTY_SETTINGS = {
    1: {"name": "EASY", "spike_gap": 950, "obstacle_gap": 1500,
        "obstacle_speed": 1.6, "monster_max": 14, "obstacle_dmg": 18, "spike_dmg": 16},
    2: {"name": "NORMAL", "spike_gap": 620, "obstacle_gap": 1000,
        "obstacle_speed": 2.6, "monster_max": 22, "obstacle_dmg": 24, "spike_dmg": 22},
    3: {"name": "HARD", "spike_gap": 400, "obstacle_gap": 640,
        "obstacle_speed": 3.6, "monster_max": 30, "obstacle_dmg": 30, "spike_dmg": 28},
}

# --- Hazards ------------------------------------------------------------------
HAZARD_COOLDOWN_MS = 700   # min time between hazard hits so damage isn't per-frame
SPIKE_WIDTH = 26
SPIKE_HEIGHT = 30
OBSTACLE_SIZE = 34

# --- Clouds -------------------------------------------------------------------
CLOUD_STRIP_WIDTH = 900
CLOUD_TEMPLATES = [
    {"x": 80, "y": 48, "scale": 1.15},
    {"x": 280, "y": 28, "scale": 0.85},
    {"x": 460, "y": 70, "scale": 1.35},
    {"x": 680, "y": 36, "scale": 1.0},
    {"x": 820, "y": 88, "scale": 0.75},
]
