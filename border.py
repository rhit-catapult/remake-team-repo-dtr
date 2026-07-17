"""A lethal 'void' border that trails far behind the slime.

It only ever advances (never retreats), so it stays offscreen to the left during
normal forward play. Backtracking, though, runs the slime straight into it.
"""
import math

import pygame

from config import SCREEN_W, SCREEN_H

BORDER_TRAIL = int(SCREEN_W * 1.6)   # how far behind the slime the edge sits
BORDER_DAMAGE = 34                   # damage per hit while caught in the void
BORDER_KNOCKBACK = 22.0              # forward shove back out of the void


def advance_border(border_x, player_x):
    """Trail the player by BORDER_TRAIL, never retreating."""
    return max(border_x, player_x - BORDER_TRAIL)


def draw_border(surface, border_x, camera_x, time_ms):
    """Draw the creeping void wall filling everything left of border_x."""
    edge = int(border_x - camera_x)
    if edge < 0:
        return  # wholly offscreen to the left

    fill_w = min(edge, SCREEN_W) + 2
    void = pygame.Surface((fill_w, SCREEN_H), pygame.SRCALPHA)
    void.fill((18, 3, 28, 215))
    # Faint vertical energy streaks drifting inside the void
    for i in range(6):
        sx = int((i + 0.5) / 6 * fill_w + math.sin(time_ms * 0.002 + i) * 8)
        pygame.draw.line(void, (60, 15, 90, 120), (sx, 0), (sx, SCREEN_H), 2)
    surface.blit(void, (0, 0))

    ex = min(edge, SCREEN_W)
    # Jagged glowing leading edge
    pts = [(ex + math.sin(time_ms * 0.006 + y * 0.05) * 12, y)
           for y in range(0, SCREEN_H + 24, 24)]
    pygame.draw.lines(surface, (170, 60, 220), False, pts, 4)
    pygame.draw.line(surface, (225, 140, 255), (ex, 0), (ex, SCREEN_H), 2)
    # Sparks skittering along the edge
    for i in range(10):
        sy = int((math.sin(i * 45.2 + time_ms * 0.003) * 0.5 + 0.5) * SCREEN_H)
        r = 2 + (i % 2)
        px = ex + int(math.sin(time_ms * 0.01 + i) * 6)
        pygame.draw.circle(surface, (230, 170, 255), (px, sy), r)
