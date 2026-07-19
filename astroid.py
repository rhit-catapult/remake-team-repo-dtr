import sys
import pygame
import random

BLOCK = 5  # pixel size of each chunk inside an asteroid
ROCK_PALETTE = [
    (78, 72, 66), (96, 90, 82), (120, 112, 102), (138, 128, 116),
    (60, 55, 50), (104, 84, 64), (88, 70, 54),
]


def _draw_asteroid(surf, cx, cy, radius, rng):
    """Draw one pixelated, roughly-round asteroid centered at (cx, cy)."""
    base = rng.choice(ROCK_PALETTE)
    dark = (max(0, base[0] - 26), max(0, base[1] - 24), max(0, base[2] - 22))
    darker = (max(0, base[0] - 45), max(0, base[1] - 42), max(0, base[2] - 38))
    light = (min(255, base[0] + 34), min(255, base[1] + 31), min(255, base[2] + 27))

    top = int(cy - radius - BLOCK)
    bottom = int(cy + radius + BLOCK)
    left = int(cx - radius - BLOCK)
    right = int(cx + radius + BLOCK)
    for by in range(top, bottom, BLOCK):
        for bx in range(left, right, BLOCK):
            dx = (bx + BLOCK / 2) - cx
            dy = (by + BLOCK / 2) - cy
            dist = (dx * dx + dy * dy) ** 0.5
            wobble = radius * (0.80 + 0.20 * rng.random())   # irregular, lumpy edge
            if dist > wobble:
                continue
            if dist > wobble - BLOCK:      # dark rim so each rock reads as separate
                color = darker
            elif dist > wobble * 0.55:
                color = dark
            else:
                color = base
            pygame.draw.rect(surf, color, (bx, by, BLOCK, BLOCK))

    # A couple of craters and a highlight for texture
    for _ in range(rng.randint(1, 3)):
        crx = cx + rng.uniform(-radius * 0.45, radius * 0.45)
        cry = cy + rng.uniform(-radius * 0.45, radius * 0.45)
        pygame.draw.rect(surf, darker, (int(crx), int(cry), BLOCK, BLOCK))
    pygame.draw.rect(surf, light, (int(cx - radius * 0.35), int(cy - radius * 0.4), BLOCK, BLOCK))


def make_belt_surface(width, height):
    """Build a column made of several separate pixelated asteroids."""
    height = max(0, int(height))
    surf = pygame.Surface((width, max(1, height)), pygame.SRCALPHA)  # transparent gaps = space
    rng = random.Random()   # local stream so belt art doesn't disturb the game's randomness

    # Main chain of asteroids running down the column (slight overlap keeps it a barrier)
    y = 0
    started = False
    while y < height + 6:
        radius = rng.randint(11, 18)
        if not started:
            y = radius          # first rock: top just meets the edge, so it isn't clipped flat
            started = True
        cx = width // 2 + rng.randint(-9, 9)
        _draw_asteroid(surf, cx, y, radius, rng)
        y += rng.randint(radius, radius + 7)

    # A few smaller asteroids off to the sides to widen and vary the belt
    for _ in range(max(1, height // 45)):
        r = rng.randint(6, 11)
        cx = rng.randint(r, max(r + 1, width - r))
        cy = rng.randint(r, max(r + 1, height - r))
        _draw_asteroid(surf, cx, cy, r, rng)

    return surf


class Astroid:
    def __init__(self, x, gap):
        self.velo = 2
        self.point = True
        self.x = x
        self.gap = gap
        self.upperGap = random.randint(0, 480 - self.gap)
        self.lowergap = self.upperGap + self.gap
        self.lowerRectangle = pygame.Rect(self.x, 0, 50, 480 - self.lowergap)
        self.lowerRectangle.bottom = 480
        self.upperRectangle = pygame.Rect(self.x, 0, 50, self.upperGap)
        self.upperRectangle.top = 0
        # Pre-render the belts once (heights are fixed for this pipe)
        self.upperSurf = make_belt_surface(50, self.upperGap)
        self.lowerSurf = make_belt_surface(50, 480 - self.lowergap)
        # Masks matching the actual asteroid pixels (so collision ignores the gaps)
        self.upperMask = pygame.mask.from_surface(self.upperSurf)
        self.lowerMask = pygame.mask.from_surface(self.lowerSurf)

    def update(self, screen):
        self.x -= self.velo

        self.lowerRectangle = pygame.Rect(self.x, 0, 50, 480 - self.lowergap)
        self.lowerRectangle.bottom = 480
        self.upperRectangle = pygame.Rect(self.x, 0, 50, self.upperGap)
        self.upperRectangle.top = 0

        # Draw the belt of separate pixelated asteroids
        screen.blit(self.upperSurf, self.upperRectangle.topleft)
        screen.blit(self.lowerSurf, self.lowerRectangle.topleft)
