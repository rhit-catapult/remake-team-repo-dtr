"""Ground spikes and moving spiked-ball obstacles (damage on contact)."""
import math

import pygame

from config import *
from terrain import *
from enemies import spawn_island_monster

next_spike_spawn_x = 700
next_obstacle_spawn_x = 900
# Islands that have already been considered for an obstacle (keyed by world x),
# so each one is seeded exactly once as it scrolls into view.
_seeded_islands = set()


def reset_hazards():
    """Reset the spike/obstacle spawn cursors for a fresh run."""
    global next_spike_spawn_x, next_obstacle_spawn_x
    next_spike_spawn_x = 700
    next_obstacle_spawn_x = 900
    _seeded_islands.clear()


def spawn_spikes(spike_list, camera_x, spike_gap):
    """Place periodic ground spikes ahead of the camera, spaced by difficulty."""
    global next_spike_spawn_x
    while next_spike_spawn_x < camera_x + SCREEN_W + 400:
        seed = int(next_spike_spawn_x * 0.11)
        count = 1 + (seed % 3)  # a small cluster of 1-3 spikes
        for c in range(count):
            sx = next_spike_spawn_x + c * (SPIKE_WIDTH + 2)
            spike_list.append({"x": float(sx), "count": 1})
        next_spike_spawn_x += spike_gap + (seed % 4) * 40 + count * (SPIKE_WIDTH + 2)


def update_spikes(spike_list, camera_x, spike_gap):
    """Drop spikes that have scrolled well behind the player."""
    spawn_spikes(spike_list, camera_x, spike_gap)
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


def spawn_obstacles(obstacle_list, camera_x, obstacle_gap):
    """Spawn moving obstacles over the ground ahead of the camera; spacing by difficulty."""
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


def spawn_island_obstacles(obstacle_list, monster_list, camera_x):
    """Seed most floating islands with a hazard as they appear.

    Each island is seeded once (tracked in `_seeded_islands`). Islands get a mix
    of spiked balls and killable patrolling monsters; roughly a quarter stay
    clear as safe platforms.
    """
    for island in get_active_islands(camera_x, SCREEN_W):
        key = int(island["x"])
        # Seed just-behind the camera to a little ahead of it. Stay well inside
        # the monster cull-ahead band (camera + SCREEN_W + 600) so an island
        # monster isn't removed the frame after it spawns.
        if island["x"] + island["width"] < camera_x - 100:
            continue
        if island["x"] > camera_x + SCREEN_W + 200:
            continue
        if key in _seeded_islands:
            continue
        _seeded_islands.add(key)

        # Leave roughly a fifth of islands clear so there are safe platforms
        seed = int(island["x"] * 0.05 + island["y"])
        if seed % 5 == 0:
            continue

        # Most hazardous islands get killable monsters; only some get a ball.
        if seed % 4 != 0:
            spawn_island_monster(monster_list, island)
            # Some wide islands get a second monster so they feel busier
            if island["width"] >= 118 and seed % 3 == 0:
                spawn_island_monster(monster_list, island, offset=-42)
            continue

        lo = island["x"] + 4
        hi = island["x"] + island["width"] - OBSTACLE_SIZE - 4
        if hi <= lo:
            continue  # island too narrow to patrol
        obstacle_list.append({
            "x": float(lo), "axis": "x",
            "pos": (lo + hi) / 2.0, "lo": float(lo), "hi": float(hi),
            "dir": 1 if seed % 2 else -1, "phase": seed * 0.3,
            "y": float(island["y"] - OBSTACLE_SIZE - 2),
        })

    # Keep the seeded-island set from growing without bound as the world scrolls
    if len(_seeded_islands) > 200:
        cutoff = camera_x - 2 * CHUNK_WIDTH
        _seeded_islands.difference_update(
            {k for k in _seeded_islands if k < cutoff}
        )


def update_obstacles(obstacle_list, camera_x, obstacle_gap, obstacle_speed, monster_list):
    """Move obstacles along their axis and cull ones left far behind."""
    spawn_obstacles(obstacle_list, camera_x, obstacle_gap)
    spawn_island_obstacles(obstacle_list, monster_list, camera_x)
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


def obstacle_size(ob):
    """Side length of an obstacle (boss orbs carry a larger custom size)."""
    return ob.get("size", OBSTACLE_SIZE)


def obstacle_hitbox(ob):
    """World rect for a moving obstacle."""
    size = obstacle_size(ob)
    return pygame.Rect(int(obstacle_x(ob)) + 3, int(obstacle_y(ob)) + 3,
                       size - 6, size - 6)


def draw_obstacle(surface, ob, camera_x, camera_y, time_ms):
    """Draw a spiked metal ball (buzz-hazard) that spins as it moves."""
    size = obstacle_size(ob)
    ox = obstacle_x(ob) - camera_x
    oy = obstacle_y(ob) - camera_y
    cx = int(ox + size / 2)
    cy = int(oy + size / 2)
    r = size // 2
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
