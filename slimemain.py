"""Slime side-scrolling platformer — horizontal camera; full ground scrolls together."""
import math
import sys
from asyncio import wait

import pygame
from healthbar import HealthBar


pygame.init()
screen = pygame.display.set_mode((960, 850))
pygame.display.set_caption("Slime Platformer")
clock = pygame.time.Clock()
SCREEN_W = screen.get_width()
SCREEN_H = screen.get_height()
HEALTH_FONT = pygame.font.SysFont("Pixel Code", 24)
DEATH_FONT_BIG = pygame.font.SysFont("Pixel Code", 84, bold=True)
DEATH_FONT_MED = pygame.font.SysFont("Pixel Code", 34)
health_bar = HealthBar(
    HEALTH_FONT,
    x=SCREEN_W // 2 - 200,
    y=SCREEN_H - 60,
    width=400,
    height=24,
    max_hp=100,
)

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

square_size = 40
speed = 5              # horizontal speed while airborne
half_ellipse_speed = 3.5  # horizontal speed on the ground
gravity = 0.5
jump_strength = -12
vertical_velocity = 0
jumps_used = 0
second_jump_started_at = 0

platform_height = 170
GROUND_TOP = SCREEN_H - platform_height
GROUND_DEPTH = max(platform_height + 40, SCREEN_H - GROUND_TOP + 80)
# One seamless ground tile: grass + dirt + rock + plants all scroll together
GROUND_TILE_WIDTH = 480
_ground_tile_surf = None  # built lazily on first draw
# Player lives in world space; camera centers them on screen
x = 0.0
y = float(GROUND_TOP - square_size)
on_ground = True
landing_squash_frames = 0
# Tail wiggle: full stretch–retract cycle period (ms) and max extra width (px)
tail_cycle_ms = 920
tail_max_stretch = 6.0
bob_amplitude = 4
bob_frequency = 0.5

sprint_ticks = 500
green_ticks = sprint_ticks
last_stamina_regen_time = pygame.time.get_ticks()
hotbar_slots = 5
selected_hotbar_slot = 0
monster_attack_cooldown_ms = 700
last_monster_attack_time = 0
next_monster_spawn_x = 420
monsters = []
# Enemy combat: solid hitbox that hurts and knocks the slime back on contact
MONSTER_DAMAGE = 24
MONSTER_KNOCKBACK = 15.0      # horizontal shove (px/frame) away from the enemy
KNOCKBACK_DECAY = 0.80       # how quickly the shove fades each frame
knockback_velocity_x = 0.0
# Enclose animation: the slime squishes and its bottom curves around the enemy,
# closing in over it. `consuming` holds the active enclose, or None.
CONSUME_ANIM_MS = 1000
consuming = None  # {"start": ms, "ew": w, "eh": h, "ecolor": (r, g, b)}

# Health potions scattered along the world; picked up by walking over them
POTION_WIDTH = 20
POTION_HEIGHT = 30
POTION_HEAL_AMOUNT = 25
potions = []
next_potion_spawn_x = 320

# Death / run stats
PIXELS_PER_METER = 50.0   # world pixels that count as one "meter"
DEATH_ANIM_MS = 900       # slime melt animation duration
max_distance = 0.0        # furthest distance from spawn reached (world px)
game_over = False
death_time = 0            # tick when the slime died

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
game_state = "menu"   # "menu" while choosing difficulty, then "playing"
difficulty = 2
# Live difficulty-driven values (set by start_run)
spike_gap = DIFFICULTY_SETTINGS[difficulty]["spike_gap"]
obstacle_gap = DIFFICULTY_SETTINGS[difficulty]["obstacle_gap"]
obstacle_speed = DIFFICULTY_SETTINGS[difficulty]["obstacle_speed"]
monster_max = DIFFICULTY_SETTINGS[difficulty]["monster_max"]
obstacle_damage = DIFFICULTY_SETTINGS[difficulty]["obstacle_dmg"]
spike_damage = DIFFICULTY_SETTINGS[difficulty]["spike_dmg"]

# Periodic ground spikes and moving obstacles (both damage on contact)
HAZARD_COOLDOWN_MS = 700   # min time between hazard hits so damage isn't per-frame
last_hazard_hit_time = 0
SPIKE_WIDTH = 26
SPIKE_HEIGHT = 30
spikes = []
next_spike_spawn_x = 700
OBSTACLE_SIZE = 34
obstacles = []
next_obstacle_spawn_x = 900


def get_active_islands(camera_x, view_width):
    """Build island instances for map chunks near the camera."""
    margin = CHUNK_WIDTH
    left = camera_x - margin
    right = camera_x + view_width + margin
    first_chunk = math.floor(left / CHUNK_WIDTH) - 1
    last_chunk = math.floor(right / CHUNK_WIDTH) + 1
    active = []
    for chunk_i in range(first_chunk, last_chunk + 1):
        # Slight vertical variety per chunk so repeats feel less identical
        y_shift = int(math.sin(chunk_i * 2.17) * 20)
        for template in ISLAND_TEMPLATES:
            active.append(
                {
                    "x": template["x"] + chunk_i * CHUNK_WIDTH,
                    "y": template["y"] + y_shift,
                    "width": template["width"],
                    "height": template["height"],
                }
            )
    return active


def world_to_screen(wx, wy, camera_x, camera_y):
    """Convert world coordinates to screen coordinates."""
    return wx - camera_x, wy - camera_y


def _island_tip_x(island):
    """World x of the inverted-triangle's bottom point (matches draw_island)."""
    seed = int(island["x"] * 7 + island["y"] * 13)
    return island["x"] + island["width"] * (0.42 + _pseudo_rand(seed, 0) * 0.16)


def island_solid_span(island, world_y):
    """Left/right x of the solid triangle at a given world y (point at the tip)."""
    height = island["height"]
    t = (world_y - island["y"]) / height if height else 0.0
    t = max(0.0, min(1.0, t))
    tip_x = _island_tip_x(island)
    left = island["x"] + (tip_x - island["x"]) * t
    right = (island["x"] + island["width"]) + (tip_x - island["x"] - island["width"]) * t
    return left, right


def get_stamina_bar_rect():
    """Return the smaller stamina bar in the top-right corner."""
    bar_width = 200
    bar_height = 20
    return pygame.Rect(screen.get_width() - bar_width - 15, 15, bar_width, bar_height)


def draw_slime(surface, rectangle, color=(0, 200, 0)):
    """Draw a rounded dome with softly rounded bottom corners."""
    w = rectangle.width
    h = rectangle.height
    cx = rectangle.centerx
    bottom = rectangle.bottom
    left = cx - w / 2
    right = cx + w / 2
    # Corner fillet radius, clamped so it never exceeds the body
    r = max(2, int(min(w, h) * 0.22))
    r = min(r, w // 2, h // 2)

    points = []
    # Dome sits on a baseline r above the bottom so corners have room to curve
    steps = 24
    for step in range(steps + 1):
        angle = math.pi - (math.pi * step / steps)
        px = cx + (w / 2) * math.cos(angle)
        py = (bottom - r) - (h - r) * math.sin(angle)
        points.append((round(px), round(py)))
    # Rounded bottom-right corner: (right, bottom-r) -> (right-r, bottom)
    rc_x, rc_y = right - r, bottom - r
    for step in range(1, 7):
        a = (math.pi / 2) * step / 6
        points.append((round(rc_x + r * math.cos(a)), round(rc_y + r * math.sin(a))))
    # Straight bottom edge is implied here, then rounded bottom-left corner
    lc_x, lc_y = left + r, bottom - r
    for step in range(0, 7):
        a = math.pi / 2 + (math.pi / 2) * step / 6
        points.append((round(lc_x + r * math.cos(a)), round(lc_y + r * math.sin(a))))
    pygame.draw.polygon(surface, color, points)


def draw_dead_slime(surface, rect, progress):
    """Melt the slime into a puddle with X'd-out eyes as it dies."""
    p = max(0.0, min(1.0, progress))
    ease = p * p * (3 - 2 * p)  # smoothstep

    base_cx = rect.centerx
    base_bottom = rect.bottom

    # Spreading puddle underneath that grows and darkens
    puddle_w = int(rect.width * (0.7 + 1.7 * ease))
    puddle_h = int(7 + 12 * ease)
    puddle = pygame.Surface((puddle_w, puddle_h), pygame.SRCALPHA)
    pygame.draw.ellipse(puddle, (18, 120, 30, 150), puddle.get_rect())
    pygame.draw.ellipse(
        puddle, (30, 160, 45, 190),
        (puddle_w // 6, puddle_h // 4, puddle_w * 2 // 3, puddle_h // 2),
    )
    surface.blit(puddle, (base_cx - puddle_w // 2, base_bottom - puddle_h // 2))

    # Deflating body: shrinks in height, spreads in width, colour goes sickly
    body_h = int(rect.height * (1 - 0.85 * ease))
    body_w = int(rect.width * (1 + 0.8 * ease))
    body_color = (
        int(0 + 60 * ease),
        int(200 - 90 * ease),
        int(0 + 55 * ease),
    )
    if body_h > 4:
        dome = pygame.Rect(base_cx - body_w // 2, base_bottom - body_h, body_w, body_h)
        draw_slime(surface, dome, body_color)

        # X'd-out eyes near the top of the shrinking dome (fade as it flattens)
        if ease < 0.75:
            eye_y = int(base_bottom - body_h * 0.55)
            reach = max(2, int(4 * (1 - ease)))
            for eye_x in (int(base_cx - body_w * 0.22), int(base_cx + body_w * 0.22)):
                pygame.draw.line(surface, (20, 40, 20),
                                 (eye_x - reach, eye_y - reach),
                                 (eye_x + reach, eye_y + reach), 2)
                pygame.draw.line(surface, (20, 40, 20),
                                 (eye_x - reach, eye_y + reach),
                                 (eye_x + reach, eye_y - reach), 2)


def draw_death_screen(surface, meters):
    """'YOU DIED', distance travelled, and a restart hint over the frozen scene."""
    def centered(font, text, color, cy, shadow=(0, 0, 0)):
        sh = font.render(text, True, shadow)
        tx = font.render(text, True, color)
        rect = tx.get_rect(center=(SCREEN_W // 2, cy))
        surface.blit(sh, (rect.x + 2, rect.y + 2))
        surface.blit(tx, rect)

    centered(DEATH_FONT_BIG, "YOU DIED", (215, 55, 55), SCREEN_H // 2 - 70)
    centered(DEATH_FONT_MED, f"Distance travelled: {meters} m", (240, 240, 245), SCREEN_H // 2 + 10)
    centered(HEALTH_FONT, "R to try again    M for difficulty menu", (200, 205, 215), SCREEN_H // 2 + 70)


def get_support_surface_y(player_x, player_bottom, square_size, islands, ground_top):
    """Y of the nearest platform top at or below the slime's feet (world space)."""
    surface_y = ground_top
    left = player_x
    right = player_x + square_size
    for island in islands:
        if right > island["x"] and left < island["x"] + island["width"]:
            top = island["y"]
            if top >= player_bottom - 4:
                surface_y = min(surface_y, top)
    return surface_y


def resolve_island_x(x, y, prev_x, square_size, islands):
    """Block horizontal movement into the solid inverted-triangle body."""
    for island in islands:
        top = island["y"]
        bottom = island["y"] + island["height"]
        # Vertical overlap first (Y has not changed this step)
        if y + square_size <= top or y >= bottom:
            continue
        # Solid width at the highest overlapping row — the triangle is widest
        # there, so this matches the sprite instead of a full rectangle.
        left, right = island_solid_span(island, max(y, top))
        if x + square_size <= left or x >= right:
            continue
        # Came from the left side of the island
        if prev_x + square_size <= left:
            x = left - square_size
        # Came from the right side of the island
        elif prev_x >= right:
            x = right
        # Already overlapping: push out along the smaller horizontal penetration
        else:
            push_left = (x + square_size) - left
            push_right = right - x
            if push_left < push_right:
                x = left - square_size
            else:
                x = right
    return x


def resolve_island_y(x, y, prev_y, square_size, vertical_velocity, islands):
    """
    Block vertical movement into solid islands.
    Lands on tops, bounces off undersides, and stops tunneling through the body.
    Returns (y, vertical_velocity, landed_on_island).
    """
    landed = False
    for island in islands:
        top = island["y"]
        bottom = island["y"] + island["height"]

        # Solid width where the player's column meets the triangle (widest at
        # the top overlap row); the flat top stays full width for landing.
        left, right = island_solid_span(island, max(y, top))
        if x + square_size <= left or x >= right:
            continue

        prev_bottom = prev_y + square_size
        prev_top = prev_y
        cur_bottom = y + square_size
        cur_top = y

        # Landing: feet crossed or rest on the island top while falling
        crossed_top = prev_bottom <= top and cur_bottom >= top
        resting_on_top = (
            cur_bottom >= top
            and cur_bottom <= top + max(vertical_velocity, 0) + 2
            and prev_bottom <= top + 1
        )
        if vertical_velocity >= 0 and (crossed_top or resting_on_top):
            y = top - square_size
            vertical_velocity = 0
            landed = True
            continue

        # Ceiling: head crossed or entered the underside while rising
        crossed_bottom = prev_top >= bottom and cur_top <= bottom
        hit_underside = cur_top < bottom and cur_bottom > top and prev_top >= bottom - 1
        if vertical_velocity < 0 and (crossed_bottom or hit_underside):
            y = bottom
            vertical_velocity = 0
            continue

        # Still inside the solid body (e.g. high speed / side entry): push out
        if cur_bottom > top and cur_top < bottom:
            dist_up = cur_bottom - top
            dist_down = bottom - cur_top
            if dist_up <= dist_down:
                y = top - square_size
                if vertical_velocity > 0:
                    vertical_velocity = 0
                landed = True
            else:
                y = bottom
                if vertical_velocity < 0:
                    vertical_velocity = 0

    return y, vertical_velocity, landed


def draw_slime_shadow(
    surface,
    player_x,
    player_y,
    square_size,
    islands,
    ground_top,
    camera_x,
    camera_y,
    crouching=False,
    landing_squash=False,
):
    """Draw a soft oval shadow under the slime, cast onto the surface below."""
    feet_y = player_y + square_size
    support_y = get_support_surface_y(
        player_x, feet_y, square_size, islands, ground_top
    )
    height_above = max(0, support_y - feet_y)

    # Wider when squashed/crouching; shrinks and fades while airborne
    base_w = 48 if (crouching or landing_squash) else 38
    base_h = 14 if (crouching or landing_squash) else 11
    scale = max(0.4, 1.0 - height_above / 260)
    shadow_w = max(16, int(base_w * scale))
    shadow_h = max(5, int(base_h * scale))
    alpha = int(100 * scale)

    world_cx = player_x + square_size / 2
    if support_y >= ground_top - 1:
        world_cy = _ground_crest_y(ground_top, world_cx) + shadow_h * 0.25
    else:
        world_cy = support_y + shadow_h * 0.3
    center_x, center_y = world_to_screen(world_cx, world_cy, camera_x, camera_y)
    center_x, center_y = int(center_x), int(center_y)

    shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surf, (20, 40, 25, alpha), shadow_surf.get_rect())
    surface.blit(
        shadow_surf,
        (center_x - shadow_w // 2, center_y - shadow_h // 2),
    )

    # Darker core when close to the ground so it reads under the feet
    if scale > 0.7:
        inner_w = max(10, int(shadow_w * 0.55))
        inner_h = max(4, int(shadow_h * 0.5))
        inner = pygame.Surface((inner_w, inner_h), pygame.SRCALPHA)
        pygame.draw.ellipse(inner, (15, 30, 20, int(alpha * 0.85)), inner.get_rect())
        surface.blit(
            inner,
            (center_x - inner_w // 2, center_y - inner_h // 2 + 1),
        )


BLINK_INTERVAL_MS = 3000
BLINK_DURATION_MS = 140


def is_blinking(current_time_ms):
    """True for a short window at the start of every blink interval."""
    return (current_time_ms % BLINK_INTERVAL_MS) < BLINK_DURATION_MS


def draw_eyes(surface, rectangle, look_x, look_y, vertical_offset=0, blink=False):
    """Draw eyes whose pupils look in the slime's movement direction."""
    eye_radius = 5
    pupil_radius = 2
    eye_y = rectangle.y + round(rectangle.height * 0.58) - vertical_offset
    eye_positions = (
        (rectangle.x + round(rectangle.width * 0.35), eye_y),
        (rectangle.x + round(rectangle.width * 0.65), eye_y),
    )
    for eye_x, eye_y in eye_positions:
        if blink:
            # Closed lids: thin dark line with a slight green curve
            pygame.draw.line(
                surface,
                (15, 90, 25),
                (eye_x - eye_radius, eye_y),
                (eye_x + eye_radius, eye_y),
                2,
            )
            pygame.draw.line(
                surface,
                (10, 70, 20),
                (eye_x - eye_radius + 1, eye_y + 1),
                (eye_x + eye_radius - 1, eye_y + 1),
                1,
            )
        else:
            pygame.draw.circle(surface, (255, 255, 255), (eye_x, eye_y), eye_radius)
            pygame.draw.circle(
                surface, (20, 20, 20), (eye_x + look_x, eye_y + look_y), pupil_radius
            )


def draw_hotbar(surface, selected_slot):
    """Draw a five-slot hotbar below the stamina bar."""
    slot_size = 32
    gap = 4
    start_x = 15
    start_y = 15

    for slot in range(hotbar_slots):
        slot_rect = pygame.Rect(start_x + slot * (slot_size + gap), start_y, slot_size, slot_size)
        border_color = (255, 220, 40) if slot == selected_slot else (255, 255, 255)
        pygame.draw.rect(surface, (45, 45, 55), slot_rect, border_radius=4)
        pygame.draw.rect(surface, border_color, slot_rect, 2, border_radius=4)


def spawn_monsters(monster_list, camera_x):
    """Spawn new monsters ahead of the camera so enemies appear as the world scrolls."""
    global next_monster_spawn_x
    max_monsters = monster_max
    # Spawn just ahead of the view; stays inside the cull-ahead band below so
    # freshly spawned enemies are kept and the world stays densely populated.
    spawn_ahead = camera_x + SCREEN_W + 300
    while len(monster_list) < max_monsters and next_monster_spawn_x < spawn_ahead:
        seed = int(next_monster_spawn_x * 0.17)
        width = 28 + (seed % 3) * 4
        # Occasionally drop a tight cluster of enemies for busier stretches
        cluster = 1 + (seed % 3 == 0) + (seed % 5 == 0)
        for c in range(cluster):
            offset = c * (width + 30)
            spawn_x = next_monster_spawn_x + offset
            monster_list.append(
                {
                    "x": float(spawn_x),
                    "y": float(GROUND_TOP - (24 + (seed % 2) * 4)),
                    "width": width,
                    "height": 24 + (seed % 2) * 4,
                    "direction": 1 if (seed + c) % 2 == 0 else -1,
                    "speed": 1.0 + (seed % 3) * 0.2,
                    "phase": seed * 0.35 + c * 0.6,
                    "patrol_left": float(spawn_x - 90),
                    "patrol_right": float(spawn_x + 90),
                }
            )
        # Tighter spacing than before → more enemies as you scroll
        next_monster_spawn_x += 90 + (seed % 4) * 30 + (cluster - 1) * (width + 30)


def update_monsters(monster_list, camera_x, current_time_ms):
    """Move monsters in a lively patrol loop and keep the list trimmed to the active view."""
    spawn_monsters(monster_list, camera_x)
    for monster in list(monster_list):
        monster["x"] += monster["direction"] * monster["speed"]
        if monster["x"] <= monster["patrol_left"]:
            monster["x"] = monster["patrol_left"]
            monster["direction"] = 1
        elif monster["x"] + monster["width"] >= monster["patrol_right"]:
            monster["x"] = monster["patrol_right"] - monster["width"]
            monster["direction"] = -1

        if monster["x"] + monster["width"] < camera_x - 400 or monster["x"] > camera_x + SCREEN_W + 600:
            monster_list.remove(monster)


def get_monster_hitbox(monster):
    """World-space collision box, raised a little to cover the head/bob."""
    return pygame.Rect(
        int(monster["x"]),
        int(monster["y"] - 8),
        int(monster["width"]),
        int(monster["height"] + 8),
    )


def draw_monster(surface, monster, camera_x, camera_y, time_ms):
    """Draw a more detailed monster with a walk cycle and physical limbs."""
    screen_x = monster["x"] - camera_x
    screen_y = monster["y"] - camera_y
    rect = pygame.Rect(int(screen_x), int(screen_y), monster["width"], monster["height"])
    bob = math.sin(time_ms * 0.006 + monster["phase"]) * 1.8
    body_y = int(rect.y + 3 + bob)
    body_rect = pygame.Rect(rect.x + 4, body_y, rect.width - 8, rect.height - 8)
    body_color = (80, 140, 70)
    shadow_color = (45, 90, 45)

    pygame.draw.ellipse(surface, shadow_color, (body_rect.x + 2, body_rect.y + 2, body_rect.width, body_rect.height))
    pygame.draw.ellipse(surface, body_color, body_rect)
    pygame.draw.ellipse(surface, (120, 190, 95), (body_rect.x + 3, body_rect.y + 3, body_rect.width - 6, body_rect.height - 8))

    head_rect = pygame.Rect(rect.x + rect.width // 2 - 7, body_y - 7, 14, 12)
    pygame.draw.ellipse(surface, (95, 160, 80), head_rect)
    pygame.draw.circle(surface, (255, 255, 255), (head_rect.x + 4, head_rect.y + 4), 2)
    pygame.draw.circle(surface, (255, 255, 255), (head_rect.x + 10, head_rect.y + 4), 2)
    pygame.draw.circle(surface, (20, 20, 20), (head_rect.x + 4 + int(monster["direction"] * 1), head_rect.y + 4), 1)
    pygame.draw.circle(surface, (20, 20, 20), (head_rect.x + 10 + int(monster["direction"] * 1), head_rect.y + 4), 1)

    for side in (-1, 1):
        stride = math.sin(time_ms * 0.009 + monster["phase"] + side * 0.7) * 4
        leg_x = rect.x + 8 + side * 6
        leg_y = rect.y + rect.height - 4 + int(abs(stride) * 0.3)
        pygame.draw.line(surface, (60, 110, 55), (rect.x + 10, rect.y + rect.height - 6), (leg_x, leg_y), 3)
        pygame.draw.line(surface, (60, 110, 55), (rect.x + rect.width - 10, rect.y + rect.height - 6), (rect.x + rect.width - 10 + side * 6, leg_y), 3)
        pygame.draw.circle(surface, (80, 130, 70), (int(leg_x), int(leg_y)), 3)

    arm_phase = math.sin(time_ms * 0.008 + monster["phase"]) * 3
    pygame.draw.line(surface, (80, 130, 70), (rect.x + 6, body_y + 8), (rect.x + 2 + int(arm_phase), body_y + 14), 3)
    pygame.draw.line(surface, (80, 130, 70), (rect.x + rect.width - 6, body_y + 8), (rect.x + rect.width - 2 - int(arm_phase), body_y + 14), 3)

    pygame.draw.rect(surface, (35, 55, 30), (rect.x + 7, rect.y + rect.height - 5, rect.width - 14, 4), border_radius=2)


def draw_consuming(surface, rect, t, enemy_w, enemy_h, enemy_color, slime_color=(0, 200, 0)):
    """Slime squishes and its bottom curves around the enemy, closing in to enclose it."""
    ease = t * t * (3 - 2 * t)  # smoothstep for a slow, soft close
    open_amt = 1 - ease

    cx = rect.centerx
    bottom = rect.bottom  # slime rests on the ground here

    # Body squishes a little wider and shorter as it works
    W = rect.width * (1 + 0.32 * ease)
    H = rect.height * (1 - 0.1 * ease)
    left = cx - W / 2
    right = cx + W / 2
    r = max(2, int(min(W, H) * 0.22))
    r = min(r, int(W // 2), int(H // 2))

    # A soft, shallow dimple in the bottom that cradles the enemy — not a deep
    # concave mouth — so the absorb reads as gentle and natural.
    cavity_hw = (enemy_w / 2 + 3) * open_amt
    cavity_h = (enemy_h * 0.35 + 3) * open_amt

    # --- Enemy being absorbed: peeks at the base, is drawn up into the body,
    # shrinks, and fades late so the absorb stays visible ---
    e_scale = max(0.12, 1 - 0.8 * ease)
    ew = max(3, int(enemy_w * e_scale))
    eh = max(3, int(enemy_h * e_scale))
    e_cy = (bottom + eh * 0.25) - ease * (eh * 0.25 + H * 0.4)
    alpha = int(255 * min(1.0, 2.0 * (1 - ease)))
    if alpha > 4:
        blob = pygame.Surface((ew + 2, eh + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(blob, enemy_color + (alpha,), (1, 1, ew, eh))
        hi = (
            min(255, enemy_color[0] + 40),
            min(255, enemy_color[1] + 45),
            min(255, enemy_color[2] + 30),
        )
        pygame.draw.ellipse(blob, hi + (alpha,), (2, 2, max(1, ew - 3), max(1, eh // 2)))
        surface.blit(blob, (int(cx - ew / 2), int(e_cy - eh / 2)))

    # --- Slime silhouette with the closing bottom arch ---
    points = []
    steps = 22
    # Rounded top dome, left -> right, baseline r above the ground
    for step in range(steps + 1):
        a = math.pi - (math.pi * step / steps)
        px = cx + (W / 2) * math.cos(a)
        py = (bottom - r) - (H - r) * math.sin(a)
        points.append((px, py))
    # Rounded bottom-right corner: (right, bottom-r) -> (right-r, bottom)
    rc_x, rc_y = right - r, bottom - r
    for step in range(1, 6):
        a = (math.pi / 2) * step / 5
        points.append((rc_x + r * math.cos(a), rc_y + r * math.sin(a)))
    # Along the ground to the right lip of the arch
    points.append((cx + cavity_hw, bottom))
    # Arch up and over the enemy (right lip -> peak -> left lip)
    arch_steps = 16
    for step in range(1, arch_steps):
        a = math.pi * step / arch_steps
        points.append((cx + cavity_hw * math.cos(a), bottom - cavity_h * math.sin(a)))
    # Left lip, then along the ground to the rounded bottom-left corner
    points.append((cx - cavity_hw, bottom))
    lc_x, lc_y = left + r, bottom - r
    for step in range(0, 6):
        a = math.pi / 2 + (math.pi / 2) * step / 5
        points.append((lc_x + r * math.cos(a), lc_y + r * math.sin(a)))
    pygame.draw.polygon(surface, slime_color, [(round(px), round(py)) for px, py in points])

    # Eyes on the dome, peering down at the meal
    eye_y = int(bottom - H * 0.5)
    for sx in (-0.2, 0.2):
        ex = int(cx + W * sx)
        pygame.draw.circle(surface, (255, 255, 255), (ex, eye_y), 5)
        pygame.draw.circle(surface, (20, 20, 20), (ex, eye_y + 2), 2)


def spawn_potions(potion_list, camera_x):
    """Scatter floating health potions ahead of the camera as the world scrolls."""
    global next_potion_spawn_x
    max_potions = 8
    while len(potion_list) < max_potions and next_potion_spawn_x < camera_x + SCREEN_W + 1200:
        seed = int(next_potion_spawn_x * 0.13)
        base_y = float(GROUND_TOP - POTION_HEIGHT - 10)
        potion_list.append(
            {
                "x": float(next_potion_spawn_x),
                "base_y": base_y,
                "width": POTION_WIDTH,
                "height": POTION_HEIGHT,
                "phase": seed * 0.7,
            }
        )
        # Uneven spacing so pickups don't feel like a metronome
        next_potion_spawn_x += 520 + (seed % 5) * 90


def update_potions(potion_list, camera_x, player_world_rect, health_bar):
    """Spawn, cull, and collect potions. Returns True if one was picked up."""
    spawn_potions(potion_list, camera_x)
    picked_up = False
    for potion in list(potion_list):
        # Drop potions that have scrolled well behind the player
        if potion["x"] + potion["width"] < camera_x - 400:
            potion_list.remove(potion)
            continue
        potion_rect = pygame.Rect(
            int(potion["x"]),
            int(potion["base_y"]),
            potion["width"],
            potion["height"],
        )
        if potion_rect.colliderect(player_world_rect) and health_bar.hp < health_bar.max_hp:
            health_bar.heal(POTION_HEAL_AMOUNT)
            potion_list.remove(potion)
            picked_up = True
    return picked_up


def draw_potion(surface, potion, camera_x, camera_y, time_ms):
    """Draw a glowing red-liquid flask that bobs gently in place."""
    bob = math.sin(time_ms * 0.004 + potion["phase"]) * 4
    left = potion["x"] - camera_x
    top = potion["base_y"] - camera_y + bob
    w = potion["width"]
    h = potion["height"]
    cx = int(left + w / 2)

    # Soft glow halo behind the bottle
    glow_r = w
    glow = pygame.Surface((glow_r * 4, glow_r * 4), pygame.SRCALPHA)
    pulse = int(40 + (math.sin(time_ms * 0.005 + potion["phase"]) + 1) * 18)
    pygame.draw.circle(glow, (255, 90, 100, pulse), (glow_r * 2, glow_r * 2), glow_r)
    pygame.draw.circle(glow, (255, 150, 160, pulse), (glow_r * 2, glow_r * 2), glow_r // 2)
    surface.blit(glow, (cx - glow_r * 2, int(top + h / 2) - glow_r * 2))

    body_r = w // 2 + 1
    body_cy = int(top + h - body_r)

    # Cork and neck
    neck_w = 7
    neck_h = 7
    neck_x = cx - neck_w // 2
    neck_top = body_cy - body_r - neck_h + 3
    pygame.draw.rect(surface, (215, 228, 240), (neck_x, neck_top, neck_w, neck_h + 2), border_radius=2)
    pygame.draw.rect(surface, (150, 96, 48), (neck_x - 1, neck_top - 6, neck_w + 2, 7), border_radius=2)
    pygame.draw.rect(surface, (176, 120, 66), (neck_x, neck_top - 5, neck_w, 3), border_radius=1)

    # Glass body
    pygame.draw.circle(surface, (232, 240, 250), (cx, body_cy), body_r)
    # Red liquid, sitting a little below the rim so glass shows on top
    pygame.draw.circle(surface, (206, 44, 54), (cx, body_cy + 2), body_r - 3)
    pygame.draw.circle(surface, (236, 92, 98), (cx - 2, body_cy + 4), max(2, (body_r - 3) // 2))
    # Liquid surface line
    pygame.draw.ellipse(
        surface, (250, 190, 195),
        (cx - (body_r - 4), body_cy - body_r + 6, (body_r - 4) * 2, 5),
    )
    # Little bubbles
    pygame.draw.circle(surface, (250, 200, 205), (cx + 2, body_cy + 5), 1)
    pygame.draw.circle(surface, (250, 200, 205), (cx - 3, body_cy - 1), 1)
    # Glass shine and outline
    pygame.draw.ellipse(surface, (255, 255, 255), (cx - body_r + 3, body_cy - body_r + 4, 4, 8))
    pygame.draw.circle(surface, (255, 255, 255), (cx, body_cy), body_r, 1)


def spawn_spikes(spike_list, camera_x):
    """Place periodic ground spikes ahead of the camera, spaced by difficulty."""
    global next_spike_spawn_x
    while next_spike_spawn_x < camera_x + SCREEN_W + 400:
        seed = int(next_spike_spawn_x * 0.11)
        count = 1 + (seed % 3)  # a small cluster of 1-3 spikes
        for c in range(count):
            sx = next_spike_spawn_x + c * (SPIKE_WIDTH + 2)
            spike_list.append({"x": float(sx), "count": 1})
        next_spike_spawn_x += spike_gap + (seed % 4) * 40 + count * (SPIKE_WIDTH + 2)


def update_spikes(spike_list, camera_x):
    """Drop spikes that have scrolled well behind the player."""
    spawn_spikes(spike_list, camera_x)
    spike_list[:] = [s for s in spike_list if s["x"] > camera_x - 300]


def spike_hitbox(spike):
    """World rect for a spike, a little slimmer than the sprite so grazing is fair."""
    return pygame.Rect(
        int(spike["x"] + 4), int(GROUND_TOP - SPIKE_HEIGHT + 6),
        SPIKE_WIDTH - 8, SPIKE_HEIGHT - 6,
    )


def draw_spike(surface, spike, camera_x, camera_y):
    """Draw a metal ground spike (triangle blade with a base)."""
    base_y = GROUND_TOP - camera_y
    left = spike["x"] - camera_x
    cx = left + SPIKE_WIDTH / 2
    tip_y = base_y - SPIKE_HEIGHT
    # Blade
    pygame.draw.polygon(surface, (150, 155, 165),
                        [(left + 2, base_y), (left + SPIKE_WIDTH - 2, base_y), (cx, tip_y)])
    # Shaded right half + bright edge
    pygame.draw.polygon(surface, (110, 115, 128),
                        [(cx, base_y), (left + SPIKE_WIDTH - 2, base_y), (cx, tip_y)])
    pygame.draw.line(surface, (225, 230, 240), (left + 4, base_y - 2), (cx, tip_y + 3), 2)
    # Little base plate
    pygame.draw.rect(surface, (80, 84, 95),
                    (int(left), int(base_y - 4), SPIKE_WIDTH, 6), border_radius=2)


def spawn_obstacles(obstacle_list, camera_x):
    """Spawn moving obstacles ahead of the camera; spacing set by difficulty."""
    global next_obstacle_spawn_x
    while next_obstacle_spawn_x < camera_x + SCREEN_W + 600:
        seed = int(next_obstacle_spawn_x * 0.09)
        vertical = seed % 2 == 0
        if vertical:
            # Bobs up and down over the ground
            low = GROUND_TOP - OBSTACLE_SIZE - 6
            high = GROUND_TOP - OBSTACLE_SIZE - 150
            obstacle_list.append({
                "x": float(next_obstacle_spawn_x), "axis": "y",
                "pos": float(low), "lo": float(high), "hi": float(low),
                "dir": -1, "phase": seed * 0.3,
            })
        else:
            # Sweeps left and right across a stretch of ground
            span = 130 + (seed % 3) * 40
            base = float(next_obstacle_spawn_x)
            obstacle_list.append({
                "x": base, "axis": "x",
                "pos": base, "lo": base - span, "hi": base + span,
                "dir": 1 if seed % 3 else -1, "phase": seed * 0.3,
                "y": float(GROUND_TOP - OBSTACLE_SIZE - 4),
            })
        next_obstacle_spawn_x += obstacle_gap + (seed % 5) * 60


def update_obstacles(obstacle_list, camera_x):
    """Move obstacles along their axis and cull ones left far behind."""
    spawn_obstacles(obstacle_list, camera_x)
    for ob in obstacle_list:
        ob["pos"] += ob["dir"] * obstacle_speed
        if ob["pos"] <= ob["lo"]:
            ob["pos"] = ob["lo"]
            ob["dir"] = 1
        elif ob["pos"] >= ob["hi"]:
            ob["pos"] = ob["hi"]
            ob["dir"] = -1
    obstacle_list[:] = [o for o in obstacle_list if obstacle_x(o) > camera_x - 300]


def obstacle_x(ob):
    """World x of an obstacle (moving axis or fixed)."""
    return ob["pos"] if ob["axis"] == "x" else ob["x"]


def obstacle_y(ob):
    """World y of an obstacle (moving axis or fixed)."""
    return ob["pos"] if ob["axis"] == "y" else ob["y"]


def obstacle_hitbox(ob):
    """World rect for a moving obstacle."""
    return pygame.Rect(int(obstacle_x(ob)) + 3, int(obstacle_y(ob)) + 3,
                       OBSTACLE_SIZE - 6, OBSTACLE_SIZE - 6)


def draw_obstacle(surface, ob, camera_x, camera_y, time_ms):
    """Draw a spiked metal ball (buzz-hazard) that spins as it moves."""
    ox = obstacle_x(ob) - camera_x
    oy = obstacle_y(ob) - camera_y
    cx = int(ox + OBSTACLE_SIZE / 2)
    cy = int(oy + OBSTACLE_SIZE / 2)
    r = OBSTACLE_SIZE // 2
    spin = time_ms * 0.006 + ob["phase"]
    # Spikes radiating out
    for i in range(8):
        a = spin + i * math.tau / 8
        pygame.draw.polygon(surface, (90, 95, 108), [
            (cx + math.cos(a) * (r + 6), cy + math.sin(a) * (r + 6)),
            (cx + math.cos(a + 0.28) * r, cy + math.sin(a + 0.28) * r),
            (cx + math.cos(a - 0.28) * r, cy + math.sin(a - 0.28) * r),
        ])
    # Core ball
    pygame.draw.circle(surface, (70, 74, 86), (cx, cy), r)
    pygame.draw.circle(surface, (120, 126, 140), (cx, cy), r, 2)
    pygame.draw.circle(surface, (170, 176, 190), (cx - r // 3, cy - r // 3), max(2, r // 4))


# Cloud band templates: local x within a repeat strip, y, and scale
CLOUD_STRIP_WIDTH = 900
CLOUD_TEMPLATES = [
    {"x": 80, "y": 48, "scale": 1.15},
    {"x": 280, "y": 28, "scale": 0.85},
    {"x": 460, "y": 70, "scale": 1.35},
    {"x": 680, "y": 36, "scale": 1.0},
    {"x": 820, "y": 88, "scale": 0.75},
]


def draw_cloud(surface, cx, cy, scale=1.0):
    """Draw a soft puffy cloud from layered ellipses (center at cx, cy)."""
    # Shadow/base puffs slightly below, then bright tops for volume
    puffs = (
        # (dx, dy, w, h, color)
        (-28, 6, 52, 28, (210, 230, 245)),
        (22, 8, 48, 26, (210, 230, 245)),
        (-6, 10, 60, 30, (200, 220, 240)),
        (-34, -2, 44, 30, (245, 252, 255)),
        (30, 0, 40, 28, (245, 252, 255)),
        (-4, -12, 50, 36, (255, 255, 255)),
        (12, -6, 36, 28, (255, 255, 255)),
        (-18, -4, 34, 26, (250, 254, 255)),
    )
    for dx, dy, w, h, color in puffs:
        rw = max(8, int(w * scale))
        rh = max(6, int(h * scale))
        rect = pygame.Rect(
            int(cx + dx * scale - rw / 2),
            int(cy + dy * scale - rh / 2),
            rw,
            rh,
        )
        pygame.draw.ellipse(surface, color, rect)


def draw_clouds(surface, camera_x, time_ms=0):
    """Draw a parallax cloud band across the top of the sky."""
    # Drift slowly with the camera (parallax) plus a gentle idle drift
    parallax = camera_x * 0.18
    idle_drift = (time_ms * 0.012) % CLOUD_STRIP_WIDTH
    scroll = (parallax + idle_drift) % CLOUD_STRIP_WIDTH

    # Cover the screen with enough strips for the view width
    screen_w = surface.get_width()
    start = -CLOUD_STRIP_WIDTH - int(scroll)
    x_base = start
    while x_base < screen_w + CLOUD_STRIP_WIDTH:
        for i, cloud in enumerate(CLOUD_TEMPLATES):
            # Soft vertical bob so clouds feel alive
            bob = math.sin(time_ms * 0.0011 + i * 1.7) * 3.5
            cx = x_base + cloud["x"] + scroll
            cy = cloud["y"] + bob
            # Skip far off-screen clouds
            if cx < -120 or cx > screen_w + 120:
                continue
            draw_cloud(surface, cx, cy, cloud["scale"])
        x_base += CLOUD_STRIP_WIDTH


def _pseudo_rand(seed, index):
    """Deterministic 0..1 value so island details stay stable every frame."""
    value = math.sin(seed * 12.9898 + index * 78.233) * 43758.5453
    return value - math.floor(value)


def _draw_grass_tuft(surface, base_x, base_y, scale=1.0, seed=0):
    """Small cluster of grass blades along a surface."""
    blade_color = (46, 160, 55)
    highlight = (90, 200, 80)
    for i in range(4):
        offset = (i - 1.5) * 3 * scale
        height = (6 + _pseudo_rand(seed, i) * 5) * scale
        lean = (_pseudo_rand(seed, i + 4) - 0.5) * 4 * scale
        tip = (base_x + offset + lean, base_y - height)
        left = (base_x + offset - 1.5 * scale, base_y + 1)
        right = (base_x + offset + 1.5 * scale, base_y + 1)
        color = highlight if i % 2 == 0 else blade_color
        pygame.draw.polygon(surface, color, [left, tip, right])


def _draw_rock(surface, center_x, center_y, size, seed=0):
    """Irregular pebble / boulder on top of an island."""
    points = []
    for i in range(6):
        angle = (math.pi * 2 * i / 6) + _pseudo_rand(seed, i) * 0.4
        radius = size * (0.65 + _pseudo_rand(seed, i + 10) * 0.45)
        points.append(
            (
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius * 0.7,
            )
        )
    pygame.draw.polygon(surface, (105, 100, 92), points)
    # Soft highlight and shadow for volume
    pygame.draw.polygon(
        surface,
        (145, 138, 125),
        [
            points[0],
            points[1],
            (
                center_x - size * 0.15,
                center_y - size * 0.1,
            ),
        ],
    )
    pygame.draw.polygon(
        surface,
        (70, 66, 60),
        [
            points[3],
            points[4],
            (
                center_x + size * 0.1,
                center_y + size * 0.15,
            ),
        ],
    )


def _draw_flower(surface, x, y, seed=0):
    """Tiny flower for top-of-island decoration."""
    petal = (
        (220, 80, 100)
        if _pseudo_rand(seed, 1) < 0.5
        else (240, 210, 70)
    )
    for angle in (0, 90, 180, 270):
        rad = math.radians(angle)
        px = x + math.cos(rad) * 3
        py = y + math.sin(rad) * 2
        pygame.draw.circle(surface, petal, (int(px), int(py)), 2)
    pygame.draw.circle(surface, (255, 230, 90), (int(x), int(y)), 2)


def _draw_bush(surface, x, y, width=16):
    """Rounded leafy bush on the island surface."""
    pygame.draw.ellipse(surface, (28, 110, 40), (x - width // 2, y - 10, width, 14))
    pygame.draw.ellipse(surface, (40, 145, 55), (x - width // 2 + 2, y - 12, width - 4, 12))
    pygame.draw.ellipse(surface, (55, 170, 65), (x - 4, y - 11, 8, 8))


def draw_island(surface, island, camera_x=0, camera_y=0):
    """Draw a floating island as an inverted triangle with layers, shading, and props."""
    width = island["width"]
    height = island["height"]
    seed = int(island["x"] * 7 + island["y"] * 13)
    x = island["x"] - camera_x
    y = island["y"] - camera_y

    # Tip sits near the center, slightly offset for a more natural rock mass
    tip_x = x + width * (0.42 + _pseudo_rand(seed, 0) * 0.16)
    tip_y = y + height
    top_left = (x, y)
    top_right = (x + width, y)
    tip = (tip_x, tip_y)

    # Main stone body — classic upside-down triangle
    body = [top_left, top_right, tip]
    pygame.draw.polygon(surface, (112, 105, 95), body)

    # Right-side shade (away from light)
    shade_mid = (
        x + width * 0.55,
        y + height * 0.35,
    )
    pygame.draw.polygon(
        surface,
        (78, 72, 65),
        [top_right, tip, shade_mid],
    )

    # Left-side highlight
    highlight_mid = (
        x + width * 0.28,
        y + height * 0.32,
    )
    pygame.draw.polygon(
        surface,
        (138, 130, 118),
        [top_left, highlight_mid, tip],
    )

    # Dirt band under the grass cap (trapezoid tapering down)
    dirt_depth = height * 0.28
    dirt_inset = width * 0.08
    dirt_shape = [
        (x + 2, y + 4),
        (x + width - 2, y + 4),
        (x + width - dirt_inset, y + dirt_depth),
        (x + dirt_inset, y + dirt_depth),
    ]
    pygame.draw.polygon(surface, (120, 78, 42), dirt_shape)
    # Dirt shade on the right half
    pygame.draw.polygon(
        surface,
        (95, 58, 30),
        [
            (x + width * 0.55, y + 4),
            (x + width - 2, y + 4),
            (x + width - dirt_inset, y + dirt_depth),
            (x + width * 0.5, y + dirt_depth),
        ],
    )

    # Deeper stone core for the lower half of the triangle
    core_top = y + dirt_depth * 0.85
    core = [
        (x + width * 0.18, core_top),
        (x + width * 0.82, core_top),
        tip,
    ]
    pygame.draw.polygon(surface, (95, 90, 82), core)
    pygame.draw.polygon(
        surface,
        (68, 64, 58),
        [
            (x + width * 0.55, core_top),
            (x + width * 0.82, core_top),
            tip,
        ],
    )

    # Rock cracks / strata lines for texture
    for i in range(4):
        t = 0.2 + i * 0.18
        line_y = y + height * t
        left_x = x + (tip_x - x) * t
        right_x = x + width - (x + width - tip_x) * t
        # Slightly wavy strata
        mid_x = (left_x + right_x) / 2
        mid_y = line_y + (_pseudo_rand(seed, 20 + i) - 0.5) * 4
        color = (60, 55, 50) if i % 2 == 0 else (125, 118, 108)
        pygame.draw.lines(
            surface,
            color,
            False,
            [
                (left_x + 4, line_y),
                (mid_x, mid_y),
                (right_x - 4, line_y),
            ],
            1,
        )

    # Speckles / pebbles embedded in the rock face
    for i in range(8):
        t = 0.25 + _pseudo_rand(seed, 30 + i) * 0.55
        across = 0.15 + _pseudo_rand(seed, 40 + i) * 0.7
        left_edge = x + (tip_x - x) * t
        right_edge = x + width - (x + width - tip_x) * t
        px = left_edge + (right_edge - left_edge) * across
        py = y + height * t
        radius = 1 + int(_pseudo_rand(seed, 50 + i) * 2)
        speck = (55, 50, 45) if _pseudo_rand(seed, 60 + i) < 0.5 else (140, 132, 120)
        pygame.draw.circle(surface, speck, (int(px), int(py)), radius)

    # Moss patches clinging to the lower rock
    for i in range(3):
        t = 0.55 + _pseudo_rand(seed, 70 + i) * 0.3
        across = 0.25 + _pseudo_rand(seed, 80 + i) * 0.5
        left_edge = x + (tip_x - x) * t
        right_edge = x + width - (x + width - tip_x) * t
        mx = left_edge + (right_edge - left_edge) * across
        my = y + height * t
        pygame.draw.ellipse(
            surface,
            (55, 120, 50),
            (int(mx - 5), int(my - 3), 10, 6),
        )

    # Hanging roots / vines from the underside of the dirt band
    for i in range(3):
        root_x = x + width * (0.25 + i * 0.22 + _pseudo_rand(seed, 90 + i) * 0.05)
        root_top = y + dirt_depth
        root_len = 10 + _pseudo_rand(seed, 100 + i) * 14
        pygame.draw.line(
            surface,
            (90, 60, 35),
            (root_x, root_top),
            (root_x + (_pseudo_rand(seed, 110 + i) - 0.5) * 6, root_top + root_len),
            2,
        )

    # Grass cap — slightly raised, softly uneven top edge
    grass_points = []
    steps = max(6, int(width // 10))
    for i in range(steps + 1):
        t = i / steps
        gx = x + width * t
        wave = math.sin(t * math.pi * 2 + seed) * 1.5
        grass_points.append((gx, y - 3 + wave))
    # Drop grass sides slightly down the triangle for thickness
    grass_points.append((x + width - 3, y + 10))
    grass_points.append((x + 3, y + 10))
    pygame.draw.polygon(surface, (42, 145, 48), grass_points)

    # Grass highlight strip near the front-left
    highlight_grass = []
    for i in range(steps // 2 + 1):
        t = i / max(1, steps // 2) * 0.55
        gx = x + width * t
        wave = math.sin(t * math.pi * 2 + seed) * 1.5
        highlight_grass.append((gx, y - 3 + wave))
    highlight_grass.append((x + width * 0.55, y + 7))
    highlight_grass.append((x + 4, y + 7))
    pygame.draw.polygon(surface, (70, 175, 70), highlight_grass)

    # Dark grass edge along the right / back for depth
    pygame.draw.line(
        surface,
        (28, 100, 35),
        (x + width * 0.5, y - 2),
        (x + width - 2, y + 1),
        2,
    )

    # Surface props: tufts, rocks, flowers, bushes (deterministic)
    _draw_grass_tuft(surface, x + width * 0.18, y - 1, 0.9, seed + 1)
    _draw_grass_tuft(surface, x + width * 0.4, y - 2, 1.1, seed + 2)
    _draw_grass_tuft(surface, x + width * 0.72, y - 1, 0.85, seed + 3)

    if _pseudo_rand(seed, 120) > 0.35:
        _draw_rock(
            surface,
            x + width * (0.3 + _pseudo_rand(seed, 121) * 0.2),
            y + 2,
            5 + _pseudo_rand(seed, 122) * 3,
            seed + 5,
        )
    if _pseudo_rand(seed, 123) > 0.4:
        _draw_rock(
            surface,
            x + width * (0.65 + _pseudo_rand(seed, 124) * 0.15),
            y + 3,
            4 + _pseudo_rand(seed, 125) * 2,
            seed + 6,
        )

    if _pseudo_rand(seed, 130) > 0.45:
        _draw_flower(
            surface,
            x + width * (0.25 + _pseudo_rand(seed, 131) * 0.2),
            y - 5,
            seed + 7,
        )
    if _pseudo_rand(seed, 132) > 0.5:
        _draw_flower(
            surface,
            x + width * (0.55 + _pseudo_rand(seed, 133) * 0.2),
            y - 4,
            seed + 8,
        )

    if width >= 110 and _pseudo_rand(seed, 140) > 0.3:
        _draw_bush(surface, x + width * 0.78, y - 1, int(14 + _pseudo_rand(seed, 141) * 6))
    elif width >= 100:
        _draw_bush(surface, x + width * 0.22, y, 12)

    # Sharp tip accent so the inverted triangle reads clearly
    pygame.draw.polygon(
        surface,
        (55, 52, 48),
        [
            (tip_x - 6, tip_y - 8),
            (tip_x + 6, tip_y - 8),
            tip,
        ],
    )
    pygame.draw.circle(surface, (70, 66, 60), (int(tip_x), int(tip_y - 2)), 3)


def _ground_crest_y(top, gx):
    """Uneven grass height; matches the tiled ground strip (periodic)."""
    lx = gx % GROUND_TILE_WIDTH
    wave = (
        math.sin(lx * (2 * math.pi * 2 / GROUND_TILE_WIDTH)) * 5
        + math.sin(lx * (2 * math.pi * 5 / GROUND_TILE_WIDTH) + 1.2) * 3
        + math.sin(lx * (2 * math.pi * 8 / GROUND_TILE_WIDTH)) * 1.5
    )
    return top - 1 - abs(wave) * 0.45


def draw_island_ground_shadows(surface, islands, ground_top, camera_x, camera_y):
    """Cast each island's shadow onto the ground platform (world → screen)."""
    for island in islands:
        ix = island["x"]
        iy = island["y"]
        width = island["width"]
        seed = int(ix * 7 + iy * 13)

        # Same tip x as draw_island so the shadow sits under the rock mass
        tip_x = ix + width * (0.42 + _pseudo_rand(seed, 0) * 0.16)
        center_x = ix + width * 0.5

        # Higher islands cast slightly larger, softer shadows
        height_above = max(40, ground_top - iy)
        size_scale = 0.9 + min(0.55, height_above / 500)
        shadow_w = max(36, int(width * 1.15 * size_scale))
        shadow_h = max(12, int(18 * size_scale))

        # Light from upper-left → nudge shadow a bit right/down on the ground
        world_cx = center_x * 0.45 + tip_x * 0.55 + width * 0.08
        world_cy = _ground_crest_y(ground_top, world_cx) + shadow_h * 0.35
        shadow_cx, shadow_cy = world_to_screen(world_cx, world_cy, camera_x, camera_y)
        shadow_cx, shadow_cy = int(shadow_cx), int(shadow_cy)

        # Skip if far off-screen
        if shadow_cx < -shadow_w or shadow_cx > surface.get_width() + shadow_w:
            continue
        if shadow_cy < -shadow_h or shadow_cy > surface.get_height() + shadow_h:
            continue

        outer = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(outer, (25, 45, 30, 70), outer.get_rect())
        surface.blit(outer, (shadow_cx - shadow_w // 2, shadow_cy - shadow_h // 2))

        inner_w = max(20, int(shadow_w * 0.62))
        inner_h = max(8, int(shadow_h * 0.55))
        inner = pygame.Surface((inner_w, inner_h), pygame.SRCALPHA)
        pygame.draw.ellipse(inner, (20, 35, 25, 95), inner.get_rect())
        surface.blit(inner, (shadow_cx - inner_w // 2, shadow_cy - inner_h // 2 + 1))


def build_ground_tile(ground_top):
    """
    Bake one seamless ground strip: grass, dirt, gray rock, plants, pebbles.
    The whole strip is blitted with a camera offset so every layer scrolls together.
    """
    width = GROUND_TILE_WIDTH
    # Tile is only as tall as the ground stack; y=0 is the top of the walkable crest area
    height = GROUND_DEPTH + 24
    tile = pygame.Surface((width, height), pygame.SRCALPHA)
    # Local coords: crest near y=12 so plants above crest still fit on the tile
    local_top = 12
    step = 12

    def period_wave(lx, cycles, phase=0.0):
        """Wave that matches at lx=0 and lx=width so tiles join seamlessly."""
        return math.sin(lx * (2 * math.pi * cycles / width) + phase)

    def crest_local(lx):
        wave = (
            period_wave(lx, 2) * 5
            + period_wave(lx, 5, 1.2) * 3
            + period_wave(lx, 8) * 1.5
        )
        return local_top - 1 - abs(wave) * 0.45

    # --- Grass ---
    grass_top_points = [(gx, crest_local(gx)) for gx in range(0, width, step)]
    grass_top_points.append((width, crest_local(0)))  # matches left edge for seamless tiling
    grass_depth = 38
    grass_poly = list(grass_top_points)
    grass_poly.append((width, local_top + grass_depth))
    grass_poly.append((0, local_top + grass_depth))
    pygame.draw.polygon(tile, (40, 140, 48), grass_poly)

    light_grass = list(grass_top_points)
    for gx in range(width, -1, -step):
        wave = period_wave(gx if gx < width else 0, 2) * 5 + period_wave(gx if gx < width else 0, 5, 1.2) * 3
        light_grass.append((gx, local_top + 14 + wave * 0.3))
    pygame.draw.polygon(tile, (62, 168, 62), light_grass)

    soil_edge = []
    for gx in range(0, width + step, step):
        lx = 0 if gx >= width else gx
        wave = period_wave(lx, 3, 0.5) * 3
        soil_edge.append((gx, local_top + grass_depth - 4 + wave))
    soil_edge.append((width, local_top + grass_depth + 8))
    soil_edge.append((0, local_top + grass_depth + 8))
    pygame.draw.polygon(tile, (28, 95, 32), soil_edge)

    # --- Dirt ---
    dirt_top = local_top + grass_depth - 2
    dirt_bottom = local_top + 105
    dirt_poly = []
    for gx in range(0, width + step, step):
        lx = 0 if gx >= width else gx
        wave = period_wave(lx, 2, 2) * 4
        dirt_poly.append((gx, dirt_top + wave))
    for gx in range(width, -1, -step):
        lx = 0 if gx >= width else gx
        wave = period_wave(lx, 1, 0) * 5
        dirt_poly.append((gx, dirt_bottom + wave))
    pygame.draw.polygon(tile, (118, 76, 40), dirt_poly)

    for band in range(3):
        band_y = dirt_top + 18 + band * 18
        shade = (100 - band * 8, 62 - band * 5, 32 - band * 3)
        points = []
        for gx in range(0, width + step, step):
            lx = 0 if gx >= width else gx
            wave = period_wave(lx, 2, band) * 3
            points.append((gx, band_y + wave))
        for gx in range(width, -1, -step):
            lx = 0 if gx >= width else gx
            wave = period_wave(lx, 2, band) * 3
            points.append((gx, band_y + 12 + wave))
        pygame.draw.polygon(tile, shade, points)

    for gx in range(0, width, 28):
        cell = gx // 28
        sy = dirt_top + 10 + _pseudo_rand(cell, 240) * (dirt_bottom - dirt_top - 20)
        color = (90, 55, 28) if _pseudo_rand(cell, 280) < 0.5 else (145, 100, 55)
        pygame.draw.circle(
            tile,
            color,
            (int(gx + _pseudo_rand(cell, 200) * 20), int(sy)),
            1 + int(_pseudo_rand(cell, 300) * 2),
        )

    # --- Gray rock (same tile → must scroll with grass) ---
    stone_top = dirt_bottom - 8
    stone_poly = []
    for gx in range(0, width + 20, 20):
        jagged = (_pseudo_rand(gx // 20, 400) - 0.5) * 12
        stone_poly.append((gx, stone_top + jagged))
    stone_poly.append((width, height))
    stone_poly.append((0, height))
    pygame.draw.polygon(tile, (115, 108, 98), stone_poly)

    for i in range(5):
        band_y = stone_top + 20 + i * 16
        shade = (95 - i * 6, 90 - i * 5, 82 - i * 4)
        pygame.draw.rect(tile, shade, (0, int(band_y), width, 10))

    # Distinct vertical cracks so rock motion is obvious while scrolling
    for gx in range(30, width, 70):
        cell = gx // 70
        cx = gx + (_pseudo_rand(cell, 500) - 0.5) * 16
        top_y = stone_top + 4 + _pseudo_rand(cell, 510) * 12
        pygame.draw.line(
            tile,
            (70, 65, 58),
            (cx, top_y),
            (cx + (_pseudo_rand(cell, 520) - 0.5) * 8, height - 8),
            2,
        )
        # Extra darker groove for visibility
        pygame.draw.line(
            tile,
            (55, 50, 45),
            (cx + 3, top_y + 10),
            (cx + 2, height - 20),
            1,
        )

    for gx in range(40, width, 90):
        cell = gx // 90
        bx = gx + _pseudo_rand(cell, 530) * 20
        by = stone_top + 20 + _pseudo_rand(cell, 540) * 50
        _draw_rock(tile, bx, by, 6 + _pseudo_rand(cell, 541) * 5, cell + 50)

    # --- Plants & surface pebbles (baked into the same scrolling tile) ---
    for gx in range(8, width, 48):
        cell = gx // 48
        tx = gx + _pseudo_rand(cell, 600) * 12
        ty = crest_local(tx)
        _draw_grass_tuft(tile, tx, ty, 0.9 + _pseudo_rand(cell, 610) * 0.5, cell)

    for gx in range(50, width, 140):
        cell = gx // 140
        fx = gx + _pseudo_rand(cell, 700) * 30
        _draw_flower(tile, fx, crest_local(fx) - 4, cell + 20)

    for gx in range(90, width, 200):
        cell = gx // 200
        bx = gx + _pseudo_rand(cell, 720) * 25
        _draw_bush(tile, bx, crest_local(bx) - 2, int(16 + _pseudo_rand(cell, 730) * 8))

    for gx in range(70, width, 160):
        cell = gx // 160
        rx = gx + _pseudo_rand(cell, 740) * 25
        _draw_rock(tile, rx, crest_local(rx) + 4, 5 + _pseudo_rand(cell, 750) * 3, cell + 30)

    for i in range(len(grass_top_points) - 1):
        pygame.draw.line(
            tile,
            (95, 195, 85),
            grass_top_points[i],
            grass_top_points[i + 1],
            2,
        )

    return tile


def draw_ground_platform(surface, ground_top, camera_x, camera_y):
    """Tile the ground strip across the view; offset by camera so the whole stack scrolls."""
    global _ground_tile_surf
    if _ground_tile_surf is None:
        _ground_tile_surf = build_ground_tile(ground_top)

    tile = _ground_tile_surf
    tile_w = tile.get_width()
    # Local crest sits at y=12 inside the tile; align that to world ground_top on screen
    tile_draw_y = int(ground_top - camera_y - 12)

    # Screen x of world x=0 is -camera_x; tile repeats every tile_w world units
    scroll = -int(round(camera_x)) % tile_w
    # Start one tile early so the left edge is always covered
    start_x = scroll - tile_w
    if scroll == 0:
        start_x = -tile_w

    x_pos = start_x
    screen_w = surface.get_width()
    while x_pos < screen_w:
        surface.blit(tile, (x_pos, tile_draw_y))
        x_pos += tile_w


def start_run(level):
    """Apply a difficulty level and (re)initialize a fresh run."""
    global difficulty, spike_gap, obstacle_gap, obstacle_speed, monster_max
    global obstacle_damage, spike_damage, game_state
    global x, y, vertical_velocity, on_ground, jumps_used, second_jump_started_at
    global landing_squash_frames, knockback_velocity_x, consuming
    global monsters, potions, spikes, obstacles
    global next_monster_spawn_x, next_potion_spawn_x, next_spike_spawn_x, next_obstacle_spawn_x
    global green_ticks, last_monster_attack_time, last_stamina_regen_time, last_hazard_hit_time
    global max_distance, game_over, death_time

    difficulty = level
    cfg = DIFFICULTY_SETTINGS[level]
    spike_gap = cfg["spike_gap"]
    obstacle_gap = cfg["obstacle_gap"]
    obstacle_speed = cfg["obstacle_speed"]
    monster_max = cfg["monster_max"]
    obstacle_damage = cfg["obstacle_dmg"]
    spike_damage = cfg["spike_dmg"]

    health_bar.reset()
    x = 0.0
    y = float(GROUND_TOP - square_size)
    vertical_velocity = 0
    on_ground = True
    jumps_used = 0
    second_jump_started_at = 0
    landing_squash_frames = 0
    knockback_velocity_x = 0.0
    consuming = None
    monsters.clear()
    potions.clear()
    spikes.clear()
    obstacles.clear()
    next_monster_spawn_x = 420
    next_potion_spawn_x = 320
    next_spike_spawn_x = 700
    next_obstacle_spawn_x = 900
    green_ticks = sprint_ticks
    last_monster_attack_time = 0
    last_hazard_hit_time = 0
    last_stamina_regen_time = pygame.time.get_ticks()
    max_distance = 0.0
    game_over = False
    death_time = 0
    game_state = "playing"


def draw_menu(surface, time_ms):
    """Difficulty select screen: press 1, 2, or 3."""
    surface.fill((26, 30, 46))
    # Subtle scrolling ground strip at the bottom for flavor
    draw_ground_platform(surface, GROUND_TOP, (time_ms * 0.05) % 480, 0)

    def centered(font, text, color, cy, shadow=(0, 0, 0)):
        sh = font.render(text, True, shadow)
        tx = font.render(text, True, color)
        rect = tx.get_rect(center=(SCREEN_W // 2, cy))
        surface.blit(sh, (rect.x + 2, rect.y + 2))
        surface.blit(tx, rect)

    # Bobbing slime mascot
    bob = int(math.sin(time_ms * 0.004) * 8)
    draw_slime(surface, pygame.Rect(SCREEN_W // 2 - 34, 150 + bob, 68, 54))
    draw_eyes(surface, pygame.Rect(SCREEN_W // 2 - 34, 150 + bob, 68, 54), 0, 0)

    centered(DEATH_FONT_BIG, "SLIME RUN", (120, 230, 120), 90)
    centered(DEATH_FONT_MED, "Choose a difficulty", (235, 235, 245), 260)

    y0 = 330
    for level in (1, 2, 3):
        cfg = DIFFICULTY_SETTINGS[level]
        selected = level == difficulty
        color = (255, 220, 90) if selected else (215, 220, 230)
        label = f"[{level}]  {cfg['name']}"
        centered(DEATH_FONT_MED, label, color, y0 + (level - 1) * 60)

    centered(HEALTH_FONT, "Press 1, 2, or 3 to start", (190, 200, 215), y0 + 210)
    centered(HEALTH_FONT, "Move: A/D or Arrows   Jump: W/Up   Stomp enemies from above",
             (150, 160, 180), y0 + 245)


DIFFICULTY_KEYS = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}

while True:
    jump_requested = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        if game_state == "menu":
            # Difficulty select: 1 / 2 / 3 starts the run
            if event.type == pygame.KEYDOWN and event.key in DIFFICULTY_KEYS:
                start_run(DIFFICULTY_KEYS[event.key])
            continue
        if game_over and event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            start_run(difficulty)  # restart at the same difficulty
            continue
        if game_over and event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            game_state = "menu"    # back to difficulty select
            continue
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_w) and not game_over:
            jump_requested = True
        if event.type == pygame.KEYDOWN and pygame.K_1 <= event.key <= pygame.K_5:
            selected_hotbar_slot = event.key - pygame.K_1
        if event.type == pygame.MOUSEWHEEL:
            selected_hotbar_slot = (selected_hotbar_slot - event.y) % hotbar_slots

    if game_state == "menu":
        draw_menu(screen, pygame.time.get_ticks())
        pygame.display.update()
        clock.tick(60)
        continue

    pressed_keys = pygame.key.get_pressed()
    moving_left = pressed_keys[pygame.K_LEFT] or pressed_keys[pygame.K_a]
    moving_right = pressed_keys[pygame.K_RIGHT] or pressed_keys[pygame.K_d]
    crouching = pressed_keys[pygame.K_DOWN] or pressed_keys[pygame.K_s]
    if game_over:
        # Freeze all control once the slime dies
        moving_left = moving_right = crouching = False
        jump_requested = False
    current_speed = speed if not on_ground else half_ellipse_speed
    if pressed_keys[pygame.K_SPACE] & (pressed_keys[pygame.K_UP] or pressed_keys[pygame.K_LEFT] or pressed_keys[pygame.K_RIGHT]) and green_ticks > 0:
        current_speed = speed * 1.05
        green_ticks -= 1

    # Snapshot before movement so we know which face of an island was entered
    prev_x, prev_y = x, y
    current_time = pygame.time.get_ticks()
    camera_x = x + square_size / 2 - SCREEN_W / 2
    camera_y = 0
    if not game_over:
        update_monsters(monsters, camera_x, current_time)
        update_spikes(spikes, camera_x)
        update_obstacles(obstacles, camera_x)

    if moving_left:
        x -= current_speed
    if moving_right:
        x += current_speed
    # Enemy knockback shove decays over a few frames
    x += knockback_velocity_x
    knockback_velocity_x *= KNOCKBACK_DECAY
    if abs(knockback_velocity_x) < 0.3:
        knockback_velocity_x = 0.0
    # World is endless horizontally — no screen edge clamp

    # Islands near the player (world continues as you explore)
    islands = get_active_islands(x + square_size / 2 - SCREEN_W / 2, SCREEN_W)

    # Solid islands: stop walking/jumping sideways through their bodies
    x = resolve_island_x(x, y, prev_x, square_size, islands)

    if jump_requested and jumps_used < 2:
        vertical_velocity = jump_strength
        on_ground = False
        jumps_used += 1
        if jumps_used == 2:
            second_jump_started_at = pygame.time.get_ticks()

    vertical_velocity += gravity
    y += vertical_velocity

    # Check collision with main platform (world ground top)
    if y + square_size >= GROUND_TOP:
        if not on_ground and vertical_velocity > 0:
            landing_squash_frames = 6
        y = GROUND_TOP - square_size
        vertical_velocity = 0
        on_ground = True
        jumps_used = 0
        second_jump_started_at = 0
    else:
        # Solid islands: land on top, hit underside when jumping, never pass through
        was_airborne = not on_ground
        y, vertical_velocity, landed_on_island = resolve_island_y(
            x, y, prev_y, square_size, vertical_velocity, islands
        )
        if landed_on_island:
            if was_airborne:
                landing_squash_frames = 6
            on_ground = True
            jumps_used = 0
            second_jump_started_at = 0
        else:
            on_ground = False

    # Enemy hitboxes: stomp from above to consume; side/below contact hurts
    player_world_rect = pygame.Rect(int(x), int(y), square_size, square_size)
    hit_monster = None
    for monster in monsters:
        if player_world_rect.colliderect(get_monster_hitbox(monster)):
            hit_monster = monster
            break
    if hit_monster is not None and not game_over:
        # Stomp: falling onto the enemy from above (feet were above its top)
        feet_prev = prev_y + square_size
        is_stomp = vertical_velocity > 0 and feet_prev <= hit_monster["y"] + 10
        if is_stomp:
            # Consume the enemy: settle on the ground (no bounce) and start the
            # enclose animation — the slime's bottom curves around and closes in.
            consuming = {
                "start": current_time,
                "ew": hit_monster["width"],
                "eh": hit_monster["height"],
                "ecolor": (85, 150, 75),
            }
            monsters.remove(hit_monster)
            y = float(GROUND_TOP - square_size)
            vertical_velocity = 0
            on_ground = True
            jumps_used = 0
            landing_squash_frames = 0
        else:
            player_center = x + square_size / 2
            monster_center = hit_monster["x"] + hit_monster["width"] / 2
            push_dir = -1 if player_center < monster_center else 1
            # Shove the slime backwards (away from the enemy), not upward
            knockback_velocity_x = push_dir * MONSTER_KNOCKBACK
            if current_time - last_monster_attack_time >= monster_attack_cooldown_ms:
                health_bar.damage(MONSTER_DAMAGE)
                last_monster_attack_time = current_time

    # Horizontal camera only: map (grass, plants, rock, islands) scrolls together
    camera_x = x + square_size / 2 - SCREEN_W / 2
    camera_y = 0

    # Potions: collect any the slime is now overlapping (heals + green "+" popup)
    if not game_over:
        player_world_rect = pygame.Rect(int(x), int(y), square_size, square_size)
        update_potions(potions, camera_x, player_world_rect, health_bar)
        # Track furthest distance from spawn for the run's meter count
        max_distance = max(max_distance, abs(x))

        # Hazards: spikes and moving obstacles hurt and shove the slime backwards
        hit_hazard = False
        hazard_center = None
        for spike in spikes:
            if player_world_rect.colliderect(spike_hitbox(spike)):
                hit_hazard, hazard_center = True, spike["x"] + SPIKE_WIDTH / 2
                hazard_dmg = spike_damage
                break
        if not hit_hazard:
            for ob in obstacles:
                if player_world_rect.colliderect(obstacle_hitbox(ob)):
                    hit_hazard, hazard_center = True, obstacle_x(ob) + OBSTACLE_SIZE / 2
                    hazard_dmg = obstacle_damage
                    break
        if hit_hazard:
            push_dir = -1 if (x + square_size / 2) < hazard_center else 1
            knockback_velocity_x = push_dir * MONSTER_KNOCKBACK
            if current_time - last_hazard_hit_time >= HAZARD_COOLDOWN_MS:
                health_bar.damage(hazard_dmg)
                last_hazard_hit_time = current_time

    # Screen-space rect (centered horizontally; vertical position is true world Y)
    player_screen_x, player_screen_y = world_to_screen(x, y, camera_x, camera_y)
    player_rect = pygame.Rect(
        int(player_screen_x), int(player_screen_y), square_size, square_size
    )

    current_time = pygame.time.get_ticks()
    elapsed_seconds = (current_time - last_stamina_regen_time) // 1000
    if elapsed_seconds > 0:
        green_ticks = min(sprint_ticks, green_ticks + elapsed_seconds * 5)
        last_stamina_regen_time += elapsed_seconds * 1000

    # Trigger the death sequence the moment HP hits zero
    if health_bar.is_dead and not game_over:
        game_over = True
        death_time = current_time
        knockback_velocity_x = 0.0
        vertical_velocity = 0

    screen.fill((184, 254, 255))
    draw_clouds(screen, camera_x, current_time)
    draw_ground_platform(screen, GROUND_TOP, camera_x, camera_y)
    # Shadows land on the ground under each island, then islands draw above
    draw_island_ground_shadows(screen, islands, GROUND_TOP, camera_x, camera_y)

    for island in islands:
        # Only draw islands near the view for a bit of extra performance
        sx = island["x"] - camera_x
        if sx + island["width"] < -50 or sx > SCREEN_W + 50:
            continue
        draw_island(screen, island, camera_x, camera_y)

    for spike in spikes:
        sx = spike["x"] - camera_x
        if sx + SPIKE_WIDTH < -20 or sx > SCREEN_W + 20:
            continue
        draw_spike(screen, spike, camera_x, camera_y)

    for monster in monsters:
        draw_monster(screen, monster, camera_x, camera_y, current_time)

    for ob in obstacles:
        sx = obstacle_x(ob) - camera_x
        if sx + OBSTACLE_SIZE < -40 or sx > SCREEN_W + 40:
            continue
        draw_obstacle(screen, ob, camera_x, camera_y, current_time)

    for potion in potions:
        sx = potion["x"] - camera_x
        if sx + potion["width"] < -60 or sx > SCREEN_W + 60:
            continue
        draw_potion(screen, potion, camera_x, camera_y, current_time)

    draw_slime_shadow(
        screen,
        x,
        y,
        square_size,
        islands,
        GROUND_TOP,
        camera_x,
        camera_y,
        crouching=crouching,
        landing_squash=landing_squash_frames > 0,
    )

    if game_over:
        # Draw the melting death animation, then park the live-slime rect off
        # screen so the normal slime/eyes drawing below renders invisibly.
        death_progress = (current_time - death_time) / DEATH_ANIM_MS
        draw_dead_slime(screen, player_rect, death_progress)
        player_rect = pygame.Rect(-9999, -9999, square_size, square_size)
    elif consuming is not None:
        consume_t = (current_time - consuming["start"]) / CONSUME_ANIM_MS
        if consume_t >= 1:
            consuming = None  # animation done; slime stays put where it ate
        else:
            # Draw the enclosing slime and park the normal rect off screen
            draw_consuming(
                screen, player_rect, consume_t,
                consuming["ew"], consuming["eh"], consuming["ecolor"],
            )
            player_rect = pygame.Rect(-9999, -9999, square_size, square_size)

    display_player_rect = player_rect.copy()
    display_player_rect.x -= 4
    display_player_rect.y += 5
    display_player_rect.width += 8
    display_player_rect.height -= 5
    if not on_ground:
        second_jump_elapsed = pygame.time.get_ticks() - second_jump_started_at
        is_intermediate_frame = second_jump_started_at and (
            second_jump_elapsed < 16 or 31 <= second_jump_elapsed < 47
        )
        is_wide_second_jump = second_jump_started_at and 16 <= second_jump_elapsed < 31

        if is_wide_second_jump:
            # Second jump: flip the first-jump proportions into a wide, flat ellipse.
            display_player_rect.x -= 3
            display_player_rect.y += 4
            display_player_rect.width += 6
            display_player_rect.height -= 8
        elif is_intermediate_frame:
            # Midpoint between the tall and wide ellipse poses.
            display_player_rect.x += 2
            display_player_rect.width -= 4
        else:
            # First jump: use a taller ellipse with an 8-pixel smaller horizontal radius.
            display_player_rect.x += 8
            display_player_rect.y -= 4
            display_player_rect.width -= 16
            display_player_rect.height += 8
        display_player_rect.x -= 5
        display_player_rect.y -= 5
        display_player_rect.width += 10
        display_player_rect.height += 10
        pygame.draw.ellipse(screen, (0, 200, 0), display_player_rect)
    elif landing_squash_frames > 0:
        # Landing: keep the bottom fixed while briefly spreading out.
        display_player_rect.x -= 6
        display_player_rect.y += 10
        display_player_rect.width += 12
        display_player_rect.height -= 10
        draw_slime(screen, display_player_rect)
    elif crouching:
        # Keep the bottom fixed while making the player shorter and wider.
        display_player_rect.x -= 7
        display_player_rect.y += 15
        display_player_rect.width += 14
        display_player_rect.height -= 15
        draw_slime(screen, display_player_rect)
    else:
        # Apply bobbing animation when moving on the ground
        bob_offset = 0
        if on_ground and (moving_left or moving_right):
            bob_offset = round(math.sin(current_time * bob_frequency * 0.01) * bob_amplitude)
        
        # Bobbing: keep bottom fixed, top bounces up and down
        display_player_rect.y -= bob_offset
        display_player_rect.height += bob_offset

        # Smooth tail stretch: sine ease between 0 and max (no hard on/off toggle)
        if moving_left and not moving_right or moving_right and not moving_left:
            phase = (current_time % tail_cycle_ms) / tail_cycle_ms * math.pi * 2
            # (sin + 1) / 2 → 0..1 with soft ease at both ends
            stretch = (math.sin(phase) + 1) * 0.5 * tail_max_stretch
            stretch_px = round(stretch)
            if moving_left and not moving_right:
                display_player_rect.width += stretch_px
            else:
                display_player_rect.x -= stretch_px
                display_player_rect.width += stretch_px
        draw_slime(screen, display_player_rect)

    look_x = 0
    look_y = 0
    if moving_left and not moving_right:
        look_x = -2
    elif moving_right and not moving_left:
        look_x = 2
    if vertical_velocity < 0:
        look_y = -2
    elif vertical_velocity > 0:
        look_y = 2
    draw_eyes(
        screen,
        display_player_rect,
        look_x,
        look_y,
        6 if not on_ground else 0,
        blink=is_blinking(current_time),
    )

    if landing_squash_frames > 0:
        landing_squash_frames -= 1

    health_bar.update()
    health_bar.draw(screen)
    bar_rect = get_stamina_bar_rect()
    green_width = bar_rect.width * green_ticks // sprint_ticks
    pygame.draw.rect(screen, (255, 255, 255), bar_rect, border_radius=6)
    pygame.draw.rect(
        screen,
        (0, 200, 0),
        (bar_rect.x, bar_rect.y, green_width, bar_rect.height),
        border_radius=6,
    )
    pygame.draw.rect(screen, (255, 255, 255), bar_rect, 2, border_radius=6)
    draw_hotbar(screen, selected_hotbar_slot)

    if game_over:
        meters = int(max_distance / PIXELS_PER_METER)
        draw_death_screen(screen, meters)

    pygame.display.update()
    clock.tick(60)
