"""The player slime's rendering: body, eyes, shadow, death melt, and the
enclose-the-enemy consume animation."""
import math

import pygame

from config import *
from terrain import get_support_surface_y, world_to_screen, _ground_crest_y


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
