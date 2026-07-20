"""Pickups and the hotbar inventory: health potions (auto-heal) and star
power-ups (stored in the hotbar, used with F for long invincibility)."""
import math

import pygame

from config import *

next_potion_spawn_x = 320
next_star_spawn_x = 600
next_sprint_spawn_x = 460
# Hotbar inventory: one entry per slot, None (empty) or an item id like "star".
hotbar_items = [None] * hotbar_slots


def reset_pickups():
    """Reset spawn cursors and empty the hotbar for a fresh run."""
    global next_potion_spawn_x, next_star_spawn_x, next_sprint_spawn_x
    next_potion_spawn_x = 320
    next_star_spawn_x = 600
    next_sprint_spawn_x = 460
    hotbar_items[:] = [None] * hotbar_slots


def spawn_potions(potion_list, camera_x, spikes):
    """Scatter floating health potions ahead of the camera as the world scrolls.

    Potions are only placed within the range spikes have already been seeded
    (SCREEN_W + 400 ahead), and any spot that would sit on a spike is skipped so
    a potion never lands on top of a hazard.
    """
    global next_potion_spawn_x
    max_potions = 8
    while len(potion_list) < max_potions and next_potion_spawn_x < camera_x + SCREEN_W + 400:
        seed = int(next_potion_spawn_x * 0.13)
        px = next_potion_spawn_x
        # Skip spots overlapping a spike (with a little clearance on each side)
        on_spike = any(
            px < s["x"] + SPIKE_WIDTH + 30 and px + POTION_WIDTH + 30 > s["x"]
            for s in spikes
        )
        if not on_spike:
            potion_list.append(
                {
                    "x": float(px),
                    "base_y": float(GROUND_TOP - POTION_HEIGHT - 10),
                    "width": POTION_WIDTH,
                    "height": POTION_HEIGHT,
                    "phase": seed * 0.7,
                }
            )
        # Uneven spacing so pickups don't feel like a metronome
        next_potion_spawn_x += 520 + (seed % 5) * 90


def update_potions(potion_list, camera_x, player_world_rect, health_bar, spikes):
    """Spawn, cull, and collect potions. True if one was consumed or stowed.

    If the slime is hurt the potion heals immediately; only at full HP is it
    stowed in the hotbar to save for later.
    """
    spawn_potions(potion_list, camera_x, spikes)
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
        if not potion_rect.colliderect(player_world_rect):
            continue
        if health_bar.hp < health_bar.max_hp:
            health_bar.heal(POTION_HEAL_AMOUNT)   # hurt: drink it right away
            potion_list.remove(potion)
            picked_up = True
        elif add_item_to_hotbar("potion"):        # full HP: stow it for later
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


def spawn_sprint_pots(pot_list, camera_x, spikes):
    """Scatter blue sprint potions ahead of the camera (they refill stamina)."""
    global next_sprint_spawn_x
    max_pots = 6
    while len(pot_list) < max_pots and next_sprint_spawn_x < camera_x + SCREEN_W + 400:
        seed = int(next_sprint_spawn_x * 0.11)
        px = next_sprint_spawn_x
        on_spike = any(
            px < s["x"] + SPIKE_WIDTH + 30 and px + POTION_WIDTH + 30 > s["x"]
            for s in spikes
        )
        if not on_spike:
            pot_list.append(
                {
                    "x": float(px),
                    "base_y": float(GROUND_TOP - POTION_HEIGHT),   # bolt sits on the ground
                    "width": POTION_WIDTH,
                    "height": POTION_HEIGHT,
                    "phase": seed * 0.6,
                }
            )
        next_sprint_spawn_x += 640 + (seed % 5) * 80


def update_sprint_pots(pot_list, camera_x, player_world_rect, spikes):
    """Spawn, cull, and collect lightning-bolt stamina pickups.

    Always collected on contact (regardless of current stamina); returns how many
    were grabbed this frame so the caller can refill (capped at max).
    """
    spawn_sprint_pots(pot_list, camera_x, spikes)
    grabbed = 0
    for pot in list(pot_list):
        if pot["x"] + pot["width"] < camera_x - 400:
            pot_list.remove(pot)
            continue
        rect = pygame.Rect(int(pot["x"]), int(pot["base_y"]), pot["width"], pot["height"])
        if rect.colliderect(player_world_rect):
            pot_list.remove(pot)
            grabbed += 1
    return grabbed


def draw_sprint_pot(surface, pot, camera_x, camera_y, time_ms):
    """Draw a glowing lightning bolt sitting on the ground."""
    bob = math.sin(time_ms * 0.005 + pot["phase"]) * 2
    x = pot["x"] - camera_x
    y = pot["base_y"] - camera_y + bob
    w = pot["width"]
    h = pot["height"]
    cx = x + w / 2

    # Pulsing yellow glow halo
    glow_r = int(w)
    glow = pygame.Surface((glow_r * 4, glow_r * 4), pygame.SRCALPHA)
    pulse = int(45 + (math.sin(time_ms * 0.006 + pot["phase"]) + 1) * 30)
    pygame.draw.circle(glow, (255, 235, 110, pulse), (glow_r * 2, glow_r * 2), glow_r)
    pygame.draw.circle(glow, (255, 250, 190, pulse), (glow_r * 2, glow_r * 2), glow_r // 2)
    surface.blit(glow, (int(cx - glow_r * 2), int(y + h / 2 - glow_r * 2)))

    # Lightning bolt filling the box, pointing down to the ground
    bolt = [
        (cx + 3, y),
        (cx - 6, y + h * 0.52),
        (cx,     y + h * 0.52),
        (cx - 4, y + h),
        (cx + 7, y + h * 0.42),
        (cx + 1, y + h * 0.42),
        (cx + 6, y),
    ]
    pygame.draw.polygon(surface, (150, 110, 20), [(px + 1, py + 1) for px, py in bolt])  # shadow
    pygame.draw.polygon(surface, (255, 232, 70), bolt)                                    # body
    pygame.draw.polygon(surface, (255, 252, 200),
                        [(cx + 3, y), (cx - 3, y + h * 0.5), (cx + 1, y + h * 0.5)])       # highlight


def add_item_to_hotbar(item):
    """Drop an item into the first empty hotbar slot; True if it fit."""
    for slot in range(hotbar_slots):
        if hotbar_items[slot] is None:
            hotbar_items[slot] = item
            return True
    return False


def use_selected_item(selected_slot):
    """Consume the item in the given hotbar slot.

    Returns a (kind, amount) tuple describing the effect for the caller to apply
    ("star" -> invincibility ms, "potion" -> heal amount), or None if the slot
    was empty.
    """
    item = hotbar_items[selected_slot]
    if item == "star":
        hotbar_items[selected_slot] = None
        return ("star", STAR_INVINCIBILITY_MS)
    if item == "potion":
        hotbar_items[selected_slot] = None
        return ("potion", POTION_HEAL_AMOUNT)
    if item == "sprint":
        hotbar_items[selected_slot] = None
        return ("sprint", SPRINT_REFILL)
    return None


def draw_star_shape(surface, cx, cy, radius, color=(255, 225, 80), rot=0.0):
    """Draw a filled five-point star centered at (cx, cy)."""
    points = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        a = rot - math.pi / 2 + i * math.pi / 5
        points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    pygame.draw.polygon(surface, color, points)


def spawn_stars(star_list, camera_x):
    """Scatter occasional star power-ups far ahead of the camera."""
    global next_star_spawn_x
    max_stars = 4
    while len(star_list) < max_stars and next_star_spawn_x < camera_x + SCREEN_W + 1400:
        seed = int(next_star_spawn_x * 0.07)
        star_list.append(
            {
                "x": float(next_star_spawn_x),
                "base_y": float(GROUND_TOP - STAR_SIZE - 16),
                "phase": seed * 0.5,
            }
        )
        # Rare and unevenly spaced so a star feels like a find
        next_star_spawn_x += 1600 + (seed % 5) * 240


def update_stars(star_list, camera_x, player_world_rect):
    """Spawn, cull, and collect stars into the hotbar. True if one was picked up."""
    spawn_stars(star_list, camera_x)
    picked_up = False
    for star in list(star_list):
        if star["x"] + STAR_SIZE < camera_x - 400:
            star_list.remove(star)
            continue
        star_rect = pygame.Rect(int(star["x"]), int(star["base_y"]), STAR_SIZE, STAR_SIZE)
        if star_rect.colliderect(player_world_rect) and add_item_to_hotbar("star"):
            star_list.remove(star)
            picked_up = True
    return picked_up


def draw_star(surface, star, camera_x, camera_y, time_ms):
    """Draw a spinning, glowing gold star that bobs in place."""
    bob = math.sin(time_ms * 0.004 + star["phase"]) * 4
    cx = int(star["x"] - camera_x + STAR_SIZE / 2)
    cy = int(star["base_y"] - camera_y + STAR_SIZE / 2 + bob)

    glow = pygame.Surface((STAR_SIZE * 4, STAR_SIZE * 4), pygame.SRCALPHA)
    pulse = int(45 + (math.sin(time_ms * 0.005 + star["phase"]) + 1) * 22)
    pygame.draw.circle(glow, (255, 235, 120, pulse), (STAR_SIZE * 2, STAR_SIZE * 2), STAR_SIZE)
    pygame.draw.circle(glow, (255, 250, 200, pulse), (STAR_SIZE * 2, STAR_SIZE * 2), STAR_SIZE // 2)
    surface.blit(glow, (cx - STAR_SIZE * 2, cy - STAR_SIZE * 2))

    rot = time_ms * 0.002 + star["phase"]
    draw_star_shape(surface, cx, cy, STAR_SIZE / 2, (255, 200, 40), rot)
    draw_star_shape(surface, cx, cy, STAR_SIZE / 2 * 0.98, (255, 232, 90), rot)
    draw_star_shape(surface, cx, cy, STAR_SIZE / 2 * 0.55, (255, 255, 205), rot)
