"""The boss: a flying dragon that weaves around the slime, swooping to bite.

It hovers high most of the time, dips toward the player to attack, damages on
contact, and can be defeated by a well-timed stomp from above.
"""
import math

import pygame

from config import GROUND_TOP

DRAGON_W = 96
DRAGON_H = 48


def spawn_dragon(world_x):
    """Create the boss dragon, entering from high in the air ahead of the slime."""
    return {"x": float(world_x), "y": float(GROUND_TOP - 340),
            "phase": 0.0, "facing": -1, "breathing": False}


def update_dragon(dragon, player_x, player_y, time_ms):
    """Weave the dragon around the player, swooping down to attack periodically."""
    if dragon.get("fleeing"):
        # Cleared the zone: soar up and forward off the top of the screen
        dragon["x"] += 7
        dragon["y"] -= 9
        dragon["facing"] = 1
        dragon["breathing"] = False
        return

    t = time_ms * 0.001
    target_x = player_x + 150 + math.sin(t * 0.8 + dragon["phase"]) * 240
    swoop = math.sin(t * 0.6 + dragon["phase"]) > 0.55
    if swoop:
        target_y = player_y - 10
    else:
        target_y = (GROUND_TOP - 300) + math.sin(t * 1.6) * 80

    dragon["x"] += (target_x - dragon["x"]) * 0.05
    dragon["y"] += (target_y - dragon["y"]) * 0.06
    dragon["breathing"] = swoop
    dragon["facing"] = -1 if player_x < dragon["x"] else 1


def dragon_hitbox(dragon):
    """World-space collision box covering the dragon's body and head."""
    return pygame.Rect(int(dragon["x"] - DRAGON_W / 2),
                       int(dragon["y"] - DRAGON_H / 2),
                       DRAGON_W, DRAGON_H)


def draw_dragon(surface, dragon, camera_x, camera_y, time_ms):
    """Draw a flying dragon: flapping wings, horned head, spiked tail, and fire."""
    cx = int(dragon["x"] - camera_x)
    cy = int(dragon["y"] - camera_y)
    f = dragon["facing"]  # -1 faces left (toward a chasing player), +1 faces right
    flap = math.sin(time_ms * 0.012 + dragon["phase"])

    body = (140, 40, 48)
    body_dark = (95, 24, 32)
    belly = (210, 150, 90)
    membrane = (180, 70, 80)
    membrane_edge = (110, 30, 45)

    # --- Far wing (behind the body) ---
    wing_y = cy - 6 - int(flap * 10)
    pygame.draw.polygon(surface, membrane_edge, [
        (cx, cy - 6),
        (cx - f * 40, wing_y - 26),
        (cx - f * 8, wing_y - 4),
    ])

    # --- Tail sweeping out behind (opposite the facing direction) ---
    tail_sway = math.sin(time_ms * 0.006 + dragon["phase"]) * 10
    tx = cx + f * 44
    ty = cy + 4
    pygame.draw.polygon(surface, body_dark, [
        (cx + f * 20, cy - 6), (cx + f * 20, cy + 10),
        (tx, ty + tail_sway),
    ])
    # Tail-tip barb
    pygame.draw.polygon(surface, (240, 220, 120), [
        (tx, ty + tail_sway - 8),
        (tx + f * 16, ty + tail_sway),
        (tx, ty + tail_sway + 8),
    ])

    # --- Body ---
    body_rect = pygame.Rect(cx - DRAGON_W // 2 + 18, cy - DRAGON_H // 2 + 8,
                            DRAGON_W - 36, DRAGON_H - 16)
    pygame.draw.ellipse(surface, body, body_rect)
    pygame.draw.ellipse(surface, belly,
                        (body_rect.x + 4, body_rect.centery, body_rect.width - 8, body_rect.height // 2 - 2))

    # Back ridge spikes
    for i in range(-1, 3):
        rx = cx + f * (-i * 10)
        pygame.draw.polygon(surface, (240, 220, 120), [
            (rx - 4, cy - 8), (rx + 4, cy - 8), (rx, cy - 18),
        ])

    # --- Neck + head (toward the facing direction) ---
    hx = cx - f * 42
    hy = cy - 6
    pygame.draw.polygon(surface, body, [
        (cx - f * 6, cy - 8), (cx - f * 6, cy + 8),
        (hx + f * 6, hy + 8), (hx + f * 6, hy - 8),
    ])
    head = pygame.Rect(0, 0, 30, 22)
    head.center = (hx, hy)
    pygame.draw.ellipse(surface, body, head)
    # Snout
    pygame.draw.polygon(surface, body_dark, [
        (hx - f * 4, hy - 4), (hx - f * 22, hy + 2), (hx - f * 4, hy + 8),
    ])
    # Horns
    pygame.draw.polygon(surface, (240, 220, 120), [
        (hx + f * 6, hy - 8), (hx + f * 12, hy - 24), (hx + f * 12, hy - 8),
    ])
    # Eye
    pygame.draw.circle(surface, (255, 230, 90), (int(hx - f * 4), hy - 3), 3)
    pygame.draw.circle(surface, (30, 10, 10), (int(hx - f * 5), hy - 3), 1)

    # --- Fire breath while swooping ---
    if dragon["breathing"]:
        mouthx = hx - f * 20
        for i in range(3):
            flick = math.sin(time_ms * 0.03 + i) * 5
            length = 26 + i * 10
            col = [(255, 220, 80), (255, 150, 40), (230, 70, 30)][i]
            pygame.draw.polygon(surface, col, [
                (mouthx, hy - 6 + flick),
                (mouthx - f * length, hy + flick),
                (mouthx, hy + 6 + flick),
            ])

    # --- Near wing (in front of the body), flaps opposite the far wing ---
    nwing_y = cy - 6 + int(flap * 12)
    pygame.draw.polygon(surface, membrane, [
        (cx, cy - 4),
        (cx - f * 52, nwing_y - 34),
        (cx - f * 4, nwing_y + 2),
    ])
    pygame.draw.polygon(surface, membrane_edge, [
        (cx, cy - 4),
        (cx - f * 52, nwing_y - 34),
        (cx - f * 30, nwing_y - 30),
    ])
