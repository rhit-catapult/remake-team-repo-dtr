"""Patrolling monsters: spawning, movement, hitboxes, and rendering."""
import math

import pygame

from config import *

next_monster_spawn_x = 420


def reset_monsters():
    """Reset the spawn cursor for a fresh run."""
    global next_monster_spawn_x
    next_monster_spawn_x = 420


def spawn_island_monster(monster_list, island, offset=0.0):
    """Put a killable monster patrolling across the top of a floating island.

    `offset` shifts its start position (and varies its size/heading) so several
    monsters can share one island without stacking on the same spot.
    """
    seed = int(island["x"] * 0.05 + island["y"] + offset)
    width = 28 + (seed % 3) * 4
    height = 24 + (seed % 2) * 4
    lo = island["x"] + 4
    right = island["x"] + island["width"] - 4
    if right - lo < width + 8:
        return  # island too narrow to patrol
    mid = (lo + right - width) / 2
    spawn_x = min(max(mid + offset, lo), right - width)
    monster_list.append(
        {
            "x": float(spawn_x),
            "y": float(island["y"] - height),   # standing on the island top
            "width": width,
            "height": height,
            "direction": 1 if seed % 2 else -1,
            "speed": 1.0 + (seed % 3) * 0.2,
            "phase": seed * 0.35,
            "patrol_left": float(lo),
            "patrol_right": float(right),
        }
    )


def spawn_monsters(monster_list, camera_x, monster_max):
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


def update_monsters(monster_list, camera_x, monster_max):
    """Move monsters in a lively patrol loop and keep the list trimmed to the active view."""
    spawn_monsters(monster_list, camera_x, monster_max)
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
