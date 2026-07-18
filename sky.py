"""Day/night sky: a cycling gradient backdrop, a sun/moon that arcs across, a
star field that fades in at night, and a dimming veil for the whole scene.

Everything here is driven purely by elapsed time (a fixed cycle length), so the
sky is independent of the player's position.
"""
import math

import pygame

from config import SCREEN_W, SCREEN_H, GROUND_TOP

DAY_NIGHT_MS = 80000  # length of one full day -> night -> day cycle

DAY_TOP = (96, 176, 246)
DAY_BOTTOM = (198, 244, 255)
NIGHT_TOP = (7, 9, 30)
NIGHT_BOTTOM = (26, 30, 62)

_STARS = None


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def daylight(time_ms):
    """Brightness of the sky: 0 at deep night, 1 at midday (smooth cosine)."""
    phase = (time_ms % DAY_NIGHT_MS) / DAY_NIGHT_MS
    return (math.cos(phase * 2 * math.pi) + 1) * 0.5


def _star_field(count=80):
    """Deterministic star positions in screen space (upper sky only)."""
    stars = []
    for i in range(count):
        fx = (math.sin(i * 12.9898) * 43758.5453) % 1.0
        fy = (math.sin(i * 78.233) * 12543.123) % 1.0
        radius = 1 + int(((math.sin(i * 3.1) * 0.5 + 0.5)) * 1.6)
        stars.append((int(fx * SCREEN_W), int(fy * GROUND_TOP * 0.8), radius, i))
    return stars


def draw_sky(surface, time_ms):
    """Fill the sky with the current day/night gradient, stars, and sun/moon."""
    global _STARS
    b = daylight(time_ms)
    top = _lerp(NIGHT_TOP, DAY_TOP, b)
    bottom = _lerp(NIGHT_BOTTOM, DAY_BOTTOM, b)

    # Banded vertical gradient (cheap and smooth enough)
    bands = 48
    band_h = SCREEN_H / bands
    for i in range(bands):
        t = i / (bands - 1)
        color = tuple(int(top[j] + (bottom[j] - top[j]) * t) for j in range(3))
        pygame.draw.rect(surface, color, (0, int(i * band_h), SCREEN_W, int(band_h) + 1))

    # Stars fade in as the sky darkens
    if b < 0.55:
        if _STARS is None:
            _STARS = _star_field()
        base_alpha = (0.55 - b) / 0.55 * 255
        twinkle = time_ms * 0.005
        for sx, sy, radius, i in _STARS:
            flicker = 0.6 + 0.4 * math.sin(twinkle + i)
            alpha = max(0, min(255, int(base_alpha * flicker)))
            if alpha <= 0:
                continue
            dot = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (255, 255, 245, alpha), (radius + 1, radius + 1), radius)
            surface.blit(dot, (sx, sy))

    _draw_celestial(surface, time_ms, b)


def _draw_celestial(surface, time_ms, b):
    """Draw the sun (day) or moon (night) arcing across the sky."""
    phase = (time_ms % DAY_NIGHT_MS) / DAY_NIGHT_MS
    horizon = GROUND_TOP - 10
    arc = GROUND_TOP * 0.72

    # Offset from noon (phase 0) and from midnight (phase 0.5), in [-0.5, 0.5)
    sun_off = phase if phase <= 0.5 else phase - 1.0
    moon_off = phase - 0.5

    if abs(sun_off) < 0.25:
        across = (sun_off + 0.25) / 0.5           # 0..1 left to right
        cx = int(SCREEN_W * across)
        cy = int(horizon - math.sin(across * math.pi) * arc)
        _draw_sun(surface, cx, cy)
    if abs(moon_off) < 0.25:
        across = (moon_off + 0.25) / 0.5
        cx = int(SCREEN_W * across)
        cy = int(horizon - math.sin(across * math.pi) * arc)
        _draw_moon(surface, cx, cy)


def _draw_sun(surface, cx, cy):
    glow = pygame.Surface((180, 180), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 236, 160, 70), (90, 90), 80)
    pygame.draw.circle(glow, (255, 240, 180, 90), (90, 90), 52)
    surface.blit(glow, (cx - 90, cy - 90))
    pygame.draw.circle(surface, (255, 226, 120), (cx, cy), 30)
    pygame.draw.circle(surface, (255, 244, 190), (cx - 6, cy - 6), 14)


def _draw_moon(surface, cx, cy):
    glow = pygame.Surface((150, 150), pygame.SRCALPHA)
    pygame.draw.circle(glow, (210, 220, 255, 60), (75, 75), 62)
    surface.blit(glow, (cx - 75, cy - 75))
    pygame.draw.circle(surface, (232, 236, 250), (cx, cy), 26)
    # A few craters for character
    pygame.draw.circle(surface, (205, 210, 228), (cx - 8, cy - 6), 6)
    pygame.draw.circle(surface, (205, 210, 228), (cx + 9, cy + 4), 4)
    pygame.draw.circle(surface, (205, 210, 228), (cx + 2, cy + 11), 3)


def draw_night_veil(surface, time_ms):
    """Dim the whole scene toward night. Draw after the world, before the HUD."""
    b = daylight(time_ms)
    if b >= 0.9:
        return
    alpha = int((0.9 - b) / 0.9 * 135)
    if alpha <= 0:
        return
    veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    veil.fill((10, 14, 42, alpha))
    surface.blit(veil, (0, 0))
