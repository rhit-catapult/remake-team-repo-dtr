"""
HELLSHIFT: HANGAR 9
An original 1993-style first-person shooter built entirely with Python + Pygame.

All graphics, maps, and sound effects are generated at runtime. Three bundled
CC0 music tracks provide the exploration and boss soundtrack.

Controls
--------
W / S or Up / Down     Move
A / D                  Strafe
Mouse or Left / Right  Turn
Left Click / Ctrl      Fire
R                       Reload current gun
E or Space             Use doors / exit switch
1 / 2 / 3 / 4          Select revolver / shotgun / shield / sprayer
Shift                  Run
Tab                    Automap
P                      Pause
F11                    Fullscreen
Esc                    Quit
Enter                   Restart after death or victory
"""

from __future__ import annotations

import math
import random
import sys
from array import array
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pygame


# ---------------------------------------------------------------------------
# Video and gameplay constants
# ---------------------------------------------------------------------------

# The normal window is 1.25x larger than the original 960x600 presentation.
# F11 still switches to the display's true fullscreen resolution.
SCREEN_W, SCREEN_H = 1200, 750
INTERNAL_W, INTERNAL_H = 320, 200
VIEW_H = 168
HUD_H = INTERNAL_H - VIEW_H

FOV = math.radians(70)
HALF_FOV = FOV / 2
MAX_DEPTH = 28.0
TEXTURE_SIZE = 64

PLAYER_RADIUS = 0.20
PLAYER_MAX_HEALTH = 150
PLAYER_START_HEALTH = 100
WALK_SPEED = 2.35
RUN_SPEED = 3.70
TURN_SPEED = 2.20
MOUSE_SENSITIVITY = 0.0026
BOSS_PROJECTILE_SPEED = WALK_SPEED * 3
REVIVE_SCREEN_DURATION = 1.20
REVIVE_INVINCIBILITY_DURATION = 3.0
BOSS_MAX_HEALTH = 180
SUMMONER_MAX_HEALTH = 248
OVERSEER_MAX_HEALTH = 285
NIGHTMARE_MAX_HEALTH = 530
SHIELD_MAX_DURABILITY = 50
SMALL_SHIELD_MAX_DURABILITY = 30
SHIELD_REPAIR_AMOUNT = 10
CLAW_REVEAL_TIME = 0.22
CLAW_HOLD_TIME = 5.0
FINAL_TELEPORTER_POS = (40.5, 43.5)
FINAL_ARENA_ENTRY = (57.0, 23.5)
FINAL_BOSS_POS = (66.5, 23.5)
FINAL_ARENA_EXIT = (77.0, 23.5)
DOOR_TILES = ("D", "R", "K", "G", "P")
SHOOTING_ENEMY_TYPES = frozenset(
    ("grunt", "turret", "spitter", "medic", "boss", "summoner", "overseer", "nightmare")
)
BOSS_ENEMY_TYPES = frozenset(("boss", "summoner", "overseer", "nightmare"))

WHITE = (235, 235, 225)
BLACK = (0, 0, 0)
DARK_RED = (70, 8, 8)
RED = (215, 42, 32)
GREEN = (55, 205, 85)
YELLOW = (235, 190, 55)
CYAN = (70, 190, 210)

WEAPONS = {
    "pistol": {
        "name": "REVOLVER",
        "ammo": "bullets",
        "mag_size": 26,
        "reload_time": 0.8,
        "cooldown": 0.30,
        "damage": (1, 2),
        "pellets": 1,
        "spread": 0.018,
    },
    "shotgun": {
        "name": "SHOTGUN",
        "ammo": "shells",
        "mag_size": 8,
        "reload_time": 1.5,
        "cooldown": 0.78,
        "damage": (1, 2),
        "pellets": 7,
        "spread": 0.070,
    },
    "shield": {
        "name": "SHIELD",
    },
    "sprayer": {
        "name": "SPRAYER",
        "ammo": "bullets",
        "mag_size": 80,
        "reload_time": 1.0,
        "cooldown": 0.075,
        "damage": (1, 1),
        "pellets": 1,
        "spread": 0.052,
    },
}

# Floor-pickup aura colors. Keycards retain their identifying colors, while
# armor and the one-use revive occupy distinct groups outside the requested
# healing, equipment, powerup, and ammunition colors.
PICKUP_GLOW_COLORS = {
    "medkit": (125, 255, 155),
    "megahealth": (125, 255, 155),
    "shotgun": (105, 215, 255),
    "shield": (105, 215, 255),
    "sprayer": (105, 215, 255),
    "shieldrepair": (105, 215, 255),
    "overdrive": (255, 70, 65),
    "quad": (255, 70, 65),
    "bullets": (255, 225, 70),
    "shells": (255, 225, 70),
    "ammobox": (255, 225, 70),
    "armor": (195, 125, 255),
    "redkey": (255, 75, 70),
    "bluekey": (80, 155, 255),
    "greenkey": (70, 245, 125),
    "revive": (255, 135, 225),
    "final_teleporter": (255, 105, 235),
}
DEFAULT_PICKUP_GLOW = (255, 165, 80)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def normalize_angle(angle):
    while angle > math.pi:
        angle -= math.tau
    while angle < -math.pi:
        angle += math.tau
    return angle


def shade_color(color, factor):
    factor = clamp(factor, 0.0, 1.0)
    return tuple(int(channel * factor) for channel in color)


def make_level():
    """Build a connected 24x24 map with normal, unlocked, and key-locked doors."""
    width = height = 24
    grid = [["." for _ in range(width)] for _ in range(height)]

    for x in range(width):
        grid[0][x] = "1"
        grid[height - 1][x] = "1"
    for y in range(height):
        grid[y][0] = "1"
        grid[y][width - 1] = "1"

    def hline(y, x1, x2, tile):
        for x in range(x1, x2 + 1):
            grid[y][x] = tile

    def vline(x, y1, y2, tile):
        for y in range(y1, y2 + 1):
            grid[y][x] = tile

    # Major partitions
    vline(10, 1, 14, "2")
    hline(7, 10, 22, "3")
    hline(14, 1, 17, "1")
    vline(17, 7, 18, "4")
    hline(18, 17, 22, "2")
    vline(17, 18, 22, "2")

    # Smaller rooms and decorative wall runs
    hline(3, 2, 7, "2")
    vline(7, 3, 7, "2")
    hline(7, 3, 7, "2")
    vline(3, 5, 7, "2")

    hline(3, 13, 20, "3")
    vline(13, 3, 6, "3")
    vline(20, 3, 6, "3")

    hline(11, 12, 16, "4")
    vline(12, 9, 11, "4")

    hline(16, 2, 7, "3")
    vline(7, 16, 21, "3")
    hline(21, 7, 14, "4")
    vline(14, 18, 21, "4")

    # Pillars
    for px, py, tile in (
        (5, 11, "4"),
        (8, 12, "2"),
        (13, 9, "3"),
        (20, 10, "2"),
        (21, 15, "4"),
        (3, 19, "2"),
        (11, 18, "3"),
    ):
        grid[py][px] = tile

    # Door openings
    door_tiles = {
        (10, 4): "D",
        (10, 11): "D",
        (14, 7): "D",
        (6, 14): "D",
        (13, 14): "D",
        (17, 10): "D",
        (17, 14): "D",
        (19, 18): "R",
    }
    for (x, y), tile in door_tiles.items():
        grid[y][x] = tile

    # Open passages in decorative rooms
    grid[3][5] = "."
    grid[5][7] = "."
    grid[7][5] = "."
    grid[3][16] = "."
    grid[6][18] = "."
    grid[16][5] = "."
    grid[18][7] = "."
    grid[21][10] = "."

    return tuple("".join(row) for row in grid)


LEVEL_MAP = make_level()
MAP_H = len(LEVEL_MAP)
MAP_W = len(LEVEL_MAP[0])


def make_big_level():
    """Build four 24x24 quadrants plus a disconnected 24x24 boss arena."""
    width, height = 80, 48
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # The original four-quadrant complex occupies the left 48x48 section.
    # Blank solid space to its right keeps the final arena visibly separate.
    for y in range(48):
        for x in range(48):
            grid[y][x] = "."

    # Preserve the complete original level as quadrant one.
    for y, row in enumerate(LEVEL_MAP):
        for x, tile in enumerate(row):
            grid[y][x] = tile

    # One-shot tutorial cache beside the Big-map spawn. The cracked entrance
    # at (3, 2) demonstrates breakable walls before the main campaign begins.
    grid[1][3] = "2"
    grid[2][3] = "B"
    grid[1][6] = "2"
    grid[2][6] = "2"
    grid[3][5] = "2"

    def hline(y, x1, x2, tile):
        for x in range(x1, x2 + 1):
            grid[y][x] = tile

    def vline(x, y1, y2, tile):
        for y in range(y1, y2 + 1):
            grid[y][x] = tile

    # Outer hull and the cross-shaped division between quadrants.
    hline(0, 0, 47, "1")
    hline(47, 0, 47, "1")
    vline(0, 0, 47, "1")
    vline(47, 0, 47, "1")
    vline(23, 1, 46, "2")
    hline(23, 1, 46, "2")

    # Inter-quadrant routes: keyed, breakable, and power-controlled.
    grid[10][23] = "R"
    grid[23][10] = "K"
    grid[23][18] = "B"
    grid[23][34] = "G"
    grid[36][23] = "P"

    # Quadrant two: foundry and security laboratories.
    hline(8, 25, 46, "3")
    grid[8][29] = "D"
    grid[8][42] = "."
    vline(34, 1, 22, "4")
    grid[5][34] = "."
    grid[12][34] = "P"
    grid[19][34] = "D"
    hline(16, 24, 43, "2")
    grid[16][27] = "."
    grid[16][39] = "B"
    vline(43, 9, 22, "3")
    grid[13][43] = "D"
    for x, y in ((28, 4), (39, 4), (31, 12), (38, 20), (45, 18)):
        grid[y][x] = "4"

    # Quadrant three: storage maze and the power plant.
    vline(8, 25, 46, "3")
    grid[29][8] = "D"
    grid[40][8] = "."
    hline(34, 1, 22, "4")
    grid[34][5] = "."
    grid[34][14] = "B"
    vline(16, 24, 43, "2")
    grid[28][16] = "D"
    grid[39][16] = "."
    hline(43, 9, 22, "3")
    grid[43][12] = "D"
    for x, y in ((4, 29), (12, 27), (20, 31), (4, 39), (19, 40), (13, 45)):
        grid[y][x] = "4"

    # Quadrant four: cathedral hangar and final arena.
    hline(31, 24, 46, "4")
    grid[31][28] = "D"
    grid[31][41] = "P"
    vline(34, 24, 46, "3")
    grid[27][34] = "D"
    grid[38][34] = "G"
    hline(40, 25, 46, "2")
    grid[40][30] = "B"
    grid[40][45] = "D"
    vline(43, 32, 39, "4")
    grid[36][43] = "."
    for x, y in ((27, 27), (39, 27), (29, 36), (39, 36), (27, 44), (39, 44)):
        grid[y][x] = "4"

    # The old boss chamber is now an empty teleporter hall. Remove its lone
    # interior pillar so the ornate button occupies the exact room center.
    grid[44][39] = "."

    # Separate 24x24 final arena (four times a 12x12 boss-room floor area).
    # Its six-tile void gap makes the teleport-only connection obvious on Tab.
    for y in range(12, 36):
        for x in range(55, 79):
            grid[y][x] = "."
    hline(11, 54, 79, "2")
    hline(36, 54, 79, "2")
    vline(54, 11, 36, "4")
    vline(79, 11, 36, "4")

    # Ceremonial perimeter columns frame the room without crowding supplies.
    for x, y in ((58, 15), (75, 15), (58, 32), (75, 32)):
        grid[y][x] = "3"

    # Four substantial 2x2 cover blocks provide protected reload positions.
    # Their offset layout keeps the center lane and boss navigation open.
    for block_x, block_y in ((61, 20), (61, 26), (72, 20), (72, 26)):
        for y in range(block_y, block_y + 2):
            for x in range(block_x, block_x + 2):
                grid[y][x] = "4" if (x + y) % 2 == 0 else "2"

    return tuple("".join(row) for row in grid)


BIG_LEVEL_MAP = make_big_level()


# ---------------------------------------------------------------------------
# Runtime objects
# ---------------------------------------------------------------------------

@dataclass
class Door:
    x: int
    y: int
    key: Optional[str] = None
    requires_power: bool = False
    powered: bool = True
    openness: float = 0.0
    opening: bool = False

    def update(self, dt):
        if self.opening:
            self.openness = min(1.0, self.openness + dt * 1.65)


@dataclass
class Enemy:
    x: float
    y: float
    kind: str
    hp: int
    max_hp: int = field(init=False)
    state: str = "idle"
    state_timer: float = 0.0
    attack_cooldown: float = 0.0
    special_cooldown: float = 0.0
    summons_made: int = 0
    pattern_index: int = 0
    anim_time: float = 0.0
    hurt_timer: float = 0.0
    death_time: float = 0.0
    alerted: bool = False
    path: list[tuple[float, float]] = field(default_factory=list)
    path_timer: float = 0.0
    stuck_timer: float = 0.0
    saw_player_last_frame: bool = False

    def __post_init__(self):
        self.max_hp = self.hp

    @property
    def dead(self):
        return self.state == "dead"


@dataclass
class Pickup:
    x: float
    y: float
    kind: str
    active: bool = True


@dataclass
class WorldSwitch:
    x: float
    y: float
    kind: str
    targets: tuple[tuple[int, int], ...] = ()
    activated: bool = False


@dataclass
class Projectile:
    x: float
    y: float
    dx: float
    dy: float
    speed: float
    damage: int
    kind: str
    source: Optional[Enemy] = None
    effect: str = ""
    life: float = 7.0
    delay: float = 0.0
    active: bool = True


@dataclass
class EnergyField:
    x: float
    y: float
    radius: float = 0.48
    damage: int = 5
    source: Optional[Enemy] = None
    arming_time: float = 0.9
    life: float = 7.5
    damage_cooldown: float = 0.0
    pulse: float = 0.0
    active: bool = True


@dataclass
class ClawStrike:
    x: float
    y: float
    source: Optional[Enemy] = None
    delay: float = 0.3
    age: float = 0.0
    group_time_left: float = 4.0
    damage: int = 10
    damage_done: bool = False
    active: bool = True


# ---------------------------------------------------------------------------
# Procedural assets
# ---------------------------------------------------------------------------

class Assets:
    def __init__(self):
        self.rng = random.Random(90210)
        self.textures = self._make_textures()
        self.enemy_frames = self._make_enemy_frames()
        self.pickup_frames = self._make_pickups()
        self.projectile_frames = self._make_projectiles()
        self.exit_frames = self._make_exit_frames()

    def _noise(self, surface, amount, seed):
        rng = random.Random(seed)
        width, height = surface.get_size()
        for _ in range(amount):
            x = rng.randrange(width)
            y = rng.randrange(height)
            base = surface.get_at((x, y))
            delta = rng.randint(-18, 18)
            color = (
                clamp(base.r + delta, 0, 255),
                clamp(base.g + delta, 0, 255),
                clamp(base.b + delta, 0, 255),
            )
            surface.set_at((x, y), color)

    def _make_textures(self):
        textures = {}

        # Gray stone
        stone = pygame.Surface((64, 64))
        stone.fill((102, 102, 97))
        rng = random.Random(11)
        for row in range(0, 64, 16):
            offset = 0 if (row // 16) % 2 == 0 else -12
            pygame.draw.line(stone, (47, 47, 45), (0, row), (63, row), 2)
            for x in range(offset, 64, 24):
                pygame.draw.line(stone, (53, 53, 50), (x, row), (x, min(63, row + 16)), 2)
                pygame.draw.line(stone, (145, 145, 135), (x + 2, row + 2), (x + 2, min(63, row + 14)))
        for _ in range(90):
            x, y = rng.randrange(64), rng.randrange(64)
            stone.set_at((x, y), (rng.randrange(75, 130),) * 3)
        textures["1"] = stone

        # Red brick
        brick = pygame.Surface((64, 64))
        brick.fill((114, 42, 33))
        for row in range(0, 64, 12):
            pygame.draw.line(brick, (47, 21, 20), (0, row), (63, row), 2)
            offset = 0 if (row // 12) % 2 == 0 else 10
            for x in range(offset, 64, 20):
                pygame.draw.line(brick, (55, 22, 19), (x, row), (x, min(63, row + 12)), 2)
                pygame.draw.line(brick, (157, 65, 48), (x + 2, row + 2), (x + 2, min(63, row + 10)))
        self._noise(brick, 140, 12)
        textures["2"] = brick

        # Green industrial panels
        green = pygame.Surface((64, 64))
        green.fill((45, 78, 61))
        for x in range(0, 64, 16):
            pygame.draw.rect(green, (26, 42, 35), (x, 0, 2, 64))
            pygame.draw.line(green, (77, 111, 88), (x + 3, 0), (x + 3, 63))
        for y in (8, 31, 55):
            pygame.draw.line(green, (21, 34, 29), (0, y), (63, y), 2)
            for x in range(6, 64, 16):
                pygame.draw.circle(green, (128, 137, 104), (x, y + 3), 1)
        self._noise(green, 110, 13)
        textures["3"] = green

        # Dark tech wall
        tech = pygame.Surface((64, 64))
        tech.fill((48, 50, 59))
        for x in range(0, 64, 8):
            pygame.draw.rect(tech, (25, 27, 34), (x, 0, 2, 64))
        for y in range(0, 64, 16):
            pygame.draw.line(tech, (78, 82, 93), (0, y + 1), (63, y + 1))
        pygame.draw.rect(tech, (28, 31, 38), (18, 15, 28, 35))
        pygame.draw.rect(tech, (87, 31, 26), (23, 20, 5, 17))
        pygame.draw.rect(tech, (23, 92, 68), (31, 20, 5, 17))
        pygame.draw.rect(tech, (104, 87, 31), (39, 20, 3, 17))
        self._noise(tech, 80, 14)
        textures["4"] = tech

        # Door
        door = pygame.Surface((64, 64))
        door.fill((71, 73, 76))
        pygame.draw.rect(door, (30, 31, 34), (0, 0, 64, 6))
        pygame.draw.rect(door, (30, 31, 34), (0, 58, 64, 6))
        for x in range(0, 64, 8):
            pygame.draw.line(door, (112, 114, 112), (x + 2, 7), (x + 2, 57))
            pygame.draw.line(door, (39, 41, 44), (x + 6, 7), (x + 6, 57))
        pygame.draw.rect(door, (23, 24, 27), (24, 19, 16, 26))
        pygame.draw.rect(door, (142, 100, 34), (29, 24, 6, 16))
        textures["D"] = door

        locked = door.copy()
        pygame.draw.rect(locked, (106, 22, 18), (4, 25, 56, 14))
        pygame.draw.rect(locked, (198, 43, 31), (4, 28, 56, 5))
        pygame.draw.rect(locked, (35, 10, 10), (28, 21, 8, 22))
        textures["R"] = locked

        blue_locked = door.copy()
        pygame.draw.rect(blue_locked, (24, 62, 130), (4, 25, 56, 14))
        pygame.draw.rect(blue_locked, (53, 145, 230), (4, 28, 56, 5))
        textures["K"] = blue_locked

        green_locked = door.copy()
        pygame.draw.rect(green_locked, (20, 105, 62), (4, 25, 56, 14))
        pygame.draw.rect(green_locked, (55, 220, 119), (4, 28, 56, 5))
        textures["G"] = green_locked

        power_door = door.copy()
        pygame.draw.rect(power_door, (97, 74, 14), (4, 24, 56, 16))
        pygame.draw.line(power_door, (248, 208, 61), (8, 32), (56, 32), 4)
        textures["P"] = power_door

        breakable = brick.copy()
        pygame.draw.line(breakable, (28, 17, 15), (8, 5), (31, 29), 3)
        pygame.draw.line(breakable, (28, 17, 15), (31, 29), (17, 52), 3)
        pygame.draw.line(breakable, (28, 17, 15), (31, 29), (54, 17), 3)
        pygame.draw.line(breakable, (28, 17, 15), (31, 29), (48, 59), 3)
        textures["B"] = breakable

        return textures

    def _make_enemy_frames(self):
        kinds = (
            "grunt", "fiend", "stalker", "turret", "spitter", "charger", "medic",
            "boss", "summoner", "overseer", "nightmare",
        )
        frames = {kind: {} for kind in kinds}
        for kind in frames:
            frames[kind]["walk"] = [self._enemy_sprite(kind, "walk", i) for i in range(2)]
            frames[kind]["attack"] = [self._enemy_sprite(kind, "attack", i) for i in range(2)]
            frames[kind]["hurt"] = [self._enemy_sprite(kind, "hurt", 0)]
            frames[kind]["dead"] = [self._enemy_sprite(kind, "dead", i) for i in range(4)]
        return frames

    def _enemy_sprite(self, kind, state, frame):
        surf = pygame.Surface((48, 64), pygame.SRCALPHA)
        flash = state == "hurt"

        if kind == "grunt":
            skin = (210, 156, 116) if not flash else (250, 235, 220)
            armor = (63, 102, 70) if not flash else (230, 230, 220)
            dark = (31, 34, 31)
            boot_shift = 2 if state == "walk" and frame == 1 else 0

            if state == "dead":
                stages = [
                    (12, 22, 24, 36),
                    (9, 31, 30, 27),
                    (5, 42, 38, 17),
                    (3, 50, 42, 10),
                ]
                x, y, w, h = stages[frame]
                pygame.draw.rect(surf, (88, 28, 25), (x, y, w, h))
                pygame.draw.rect(surf, armor, (x + 7, y, max(4, w - 14), max(4, h // 2)))
                return surf

            # Legs and torso
            pygame.draw.rect(surf, dark, (14, 42 + boot_shift, 8, 19 - boot_shift))
            pygame.draw.rect(surf, dark, (27, 42 - boot_shift, 8, 19 + boot_shift))
            pygame.draw.rect(surf, armor, (11, 24, 27, 24))
            pygame.draw.rect(surf, (37, 54, 40), (16, 29, 17, 15))
            pygame.draw.rect(surf, skin, (15, 10, 19, 16))
            pygame.draw.rect(surf, (50, 50, 46), (13, 7, 23, 8))
            pygame.draw.rect(surf, (25, 25, 23), (19, 16, 4, 3))
            pygame.draw.rect(surf, (25, 25, 23), (27, 16, 4, 3))

            gun_y = 30 if state != "attack" or frame == 0 else 26
            pygame.draw.rect(surf, skin, (6, 27, 8, 17))
            pygame.draw.rect(surf, skin, (36, 27, 8, 17))
            pygame.draw.rect(surf, (38, 38, 42), (16, gun_y, 28, 7))
            pygame.draw.rect(surf, (18, 18, 20), (36, gun_y + 1, 11, 4))
            if state == "attack" and frame == 1:
                pygame.draw.polygon(surf, (255, 214, 78), [(46, gun_y - 4), (47, gun_y + 3), (44, gun_y + 8), (40, gun_y + 3)])
            return surf

        # Five new regular enemies used throughout the large campaign.
        if kind in ("stalker", "turret", "spitter", "charger", "medic"):
            palettes = {
                "stalker": ((61, 45, 100), (28, 20, 48), (195, 76, 225)),
                "turret": ((77, 91, 101), (27, 32, 37), (245, 132, 38)),
                "spitter": ((54, 129, 62), (20, 55, 27), (177, 245, 62)),
                "charger": ((137, 74, 35), (62, 30, 19), (246, 187, 64)),
                "medic": ((187, 190, 174), (53, 69, 68), (67, 226, 221)),
            }
            body, dark, glow = palettes[kind]
            if flash:
                body = (245, 235, 225)
            step = 2 if state == "walk" and frame == 1 else 0
            if state == "dead":
                stages = [(9, 22, 30, 39), (6, 32, 36, 29), (3, 43, 42, 18), (2, 52, 44, 9)]
                x, y, w, h = stages[frame]
                pygame.draw.ellipse(surf, dark, (x, y, w, h))
                pygame.draw.rect(surf, body, (x + 5, y + 2, max(4, w - 10), max(4, h // 2)))
                return surf

            if kind == "turret":
                pygame.draw.rect(surf, dark, (6, 40, 36, 19))
                pygame.draw.rect(surf, body, (10, 24, 28, 25))
                pygame.draw.rect(surf, glow, (19, 29, 10, 7))
                barrel_y = 31 if state != "attack" or frame == 0 else 28
                pygame.draw.rect(surf, dark, (34, barrel_y, 14, 6))
                radius = 4 if state == "attack" and frame else 1
                pygame.draw.circle(surf, (255, 225, 115), (46, barrel_y + 3), radius)
            elif kind == "spitter":
                pygame.draw.ellipse(surf, dark, (7, 24, 34, 36))
                pygame.draw.ellipse(surf, body, (9, 10, 30, 36))
                pygame.draw.circle(surf, glow, (17, 24), 3)
                pygame.draw.circle(surf, glow, (31, 24), 3)
                pygame.draw.ellipse(surf, dark, (14, 32, 20, 8))
                if state == "attack" and frame:
                    pygame.draw.circle(surf, glow, (24, 43), 6)
            elif kind == "charger":
                pygame.draw.polygon(surf, glow, [(12, 17), (4, 2), (20, 13)])
                pygame.draw.polygon(surf, glow, [(36, 17), (44, 2), (28, 13)])
                pygame.draw.rect(surf, body, (5, 16, 38, 35))
                pygame.draw.rect(surf, dark, (8, 47 + step, 13, 16 - step))
                pygame.draw.rect(surf, dark, (27, 47 - step, 13, 16 + step))
                pygame.draw.circle(surf, glow, (18, 28), 3)
                pygame.draw.circle(surf, glow, (30, 28), 3)
            else:
                pygame.draw.rect(surf, dark, (11, 31, 27, 29))
                pygame.draw.ellipse(surf, body, (10, 9, 28, 31))
                pygame.draw.rect(surf, dark, (11, 46 + step, 9, 17 - step))
                pygame.draw.rect(surf, dark, (28, 46 - step, 9, 17 + step))
                pygame.draw.circle(surf, glow, (18, 22), 3)
                pygame.draw.circle(surf, glow, (30, 22), 3)
                if kind == "medic":
                    pygame.draw.rect(surf, glow, (21, 29, 6, 16))
                    pygame.draw.rect(surf, glow, (16, 34, 16, 6))
                else:
                    arm_y = 27 if state != "attack" or frame == 0 else 20
                    pygame.draw.rect(surf, body, (3, arm_y, 9, 25))
                    pygame.draw.rect(surf, body, (36, arm_y, 9, 25))
            return surf

        # Three increasingly extravagant bosses for the expanded campaign.
        if kind in ("summoner", "overseer", "nightmare"):
            palettes = {
                "summoner": ((117, 43, 142), (35, 12, 54), (238, 105, 255)),
                "overseer": ((34, 91, 137), (13, 28, 55), (92, 235, 255)),
                "nightmare": ((142, 20, 91), (36, 4, 35), (255, 207, 65)),
            }
            body, dark, glow = palettes[kind]
            if flash:
                body = (255, 238, 225)
            step = 2 if state == "walk" and frame == 1 else 0
            if state == "dead":
                stages = [(3, 10, 42, 53), (1, 24, 46, 39), (0, 39, 48, 24), (0, 51, 48, 12)]
                x, y, w, h = stages[frame]
                pygame.draw.ellipse(surf, dark, (x, y, w, h))
                pygame.draw.rect(surf, body, (x + 3, y + 2, max(8, w - 6), max(6, h // 2)))
                return surf
            pygame.draw.polygon(surf, glow, [(9, 17), (0, 0), (19, 12)])
            pygame.draw.polygon(surf, glow, [(39, 17), (47, 0), (29, 12)])
            pygame.draw.ellipse(surf, body, (2, 8, 44, 40))
            pygame.draw.rect(surf, dark, (4, 36, 40, 20))
            pygame.draw.rect(surf, dark, (7, 51 + step, 13, 12 - step))
            pygame.draw.rect(surf, dark, (28, 51 - step, 13, 12 + step))
            pygame.draw.circle(surf, glow, (16, 24), 4)
            pygame.draw.circle(surf, glow, (32, 24), 4)
            if kind == "summoner":
                pygame.draw.circle(surf, glow, (24, 9), 8, 2)
                pygame.draw.circle(surf, (247, 190, 255), (24, 9), 3)
                pygame.draw.arc(surf, glow, (1, 19, 18, 27), 0.4, 5.8, 2)
                pygame.draw.arc(surf, glow, (29, 19, 18, 27), 0.4, 5.8, 2)
            elif kind == "overseer":
                pygame.draw.circle(surf, glow, (24, 8), 7, 2)
                pygame.draw.line(surf, glow, (24, 1), (24, 15), 2)
            elif kind == "nightmare":
                pygame.draw.circle(surf, glow, (24, 30), 10, 2)
                pygame.draw.circle(surf, (255, 245, 190), (24, 30), 4)
                pygame.draw.line(surf, glow, (2, 18), (46, 18), 2)
            if state == "attack" and frame:
                pygame.draw.circle(surf, glow, (24, 42), 9)
            return surf

        # Hangar Warden boss
        if kind == "boss":
            body = (105, 28, 95) if not flash else (255, 235, 225)
            dark = (33, 8, 35)
            armor = (65, 68, 82) if not flash else (225, 225, 220)
            horn = (218, 179, 92)
            step = 2 if state == "walk" and frame == 1 else 0

            if state == "dead":
                stages = [
                    (5, 14, 38, 48),
                    (3, 26, 42, 36),
                    (1, 39, 46, 23),
                    (0, 51, 48, 11),
                ]
                x, y, w, h = stages[frame]
                pygame.draw.ellipse(surf, dark, (x, y, w, h))
                pygame.draw.rect(surf, body, (x + 5, y + 2, max(6, w - 10), max(5, h // 2)))
                pygame.draw.rect(surf, armor, (x + 10, y, max(5, w - 20), max(4, h // 3)))
                return surf

            pygame.draw.polygon(surf, horn, [(10, 16), (0, 0), (18, 11)])
            pygame.draw.polygon(surf, horn, [(38, 16), (47, 0), (29, 11)])
            pygame.draw.ellipse(surf, body, (5, 8, 38, 34))
            pygame.draw.rect(surf, armor, (6, 29, 36, 22))
            pygame.draw.rect(surf, dark, (9, 47 + step, 11, 16 - step))
            pygame.draw.rect(surf, dark, (28, 47 - step, 11, 16 + step))
            pygame.draw.circle(surf, (90, 245, 235), (16, 21), 4)
            pygame.draw.circle(surf, (90, 245, 235), (32, 21), 4)
            pygame.draw.rect(surf, (18, 4, 20), (15, 31, 18, 6))

            arm_y = 24 if state != "attack" or frame == 0 else 17
            pygame.draw.rect(surf, body, (0, arm_y, 9, 29))
            pygame.draw.rect(surf, body, (39, arm_y, 9, 29))
            if state == "attack" and frame == 1:
                pygame.draw.circle(surf, (80, 245, 235), (24, 36), 8)
                pygame.draw.circle(surf, WHITE, (24, 36), 3)
            return surf

        # Fiend
        body = (151, 48, 39) if not flash else (245, 230, 215)
        dark = (58, 18, 20)
        horn = (170, 150, 105)
        step = 2 if state == "walk" and frame == 1 else 0

        if state == "dead":
            stages = [
                (10, 20, 28, 41),
                (7, 30, 34, 31),
                (4, 41, 40, 20),
                (3, 51, 42, 9),
            ]
            x, y, w, h = stages[frame]
            pygame.draw.ellipse(surf, dark, (x, y, w, h))
            pygame.draw.rect(surf, body, (x + 5, y + 2, max(5, w - 10), max(4, h // 2)))
            return surf

        pygame.draw.polygon(surf, horn, [(12, 17), (3, 1), (19, 12)])
        pygame.draw.polygon(surf, horn, [(36, 17), (45, 1), (29, 12)])
        pygame.draw.ellipse(surf, body, (9, 10, 30, 29))
        pygame.draw.ellipse(surf, dark, (10, 30, 29, 25))
        pygame.draw.rect(surf, dark, (10, 44 + step, 10, 18 - step))
        pygame.draw.rect(surf, dark, (28, 44 - step, 10, 18 + step))
        pygame.draw.circle(surf, (245, 192, 42), (18, 22), 3)
        pygame.draw.circle(surf, (245, 192, 42), (30, 22), 3)
        pygame.draw.rect(surf, (42, 9, 11), (17, 29, 14, 5))

        claw_y = 23 if state != "attack" or frame == 0 else 17
        pygame.draw.rect(surf, body, (3, claw_y, 9, 25))
        pygame.draw.rect(surf, body, (36, claw_y, 9, 25))
        if state == "attack" and frame == 1:
            pygame.draw.line(surf, horn, (5, 18), (0, 10), 3)
            pygame.draw.line(surf, horn, (43, 18), (47, 10), 3)
        return surf

    def _make_pickups(self):
        pickups = {}
        kinds = (
            "bullets", "shells", "medkit", "armor", "redkey", "bluekey", "greenkey",
            "shotgun", "shield", "sprayer", "ammobox", "megahealth", "overdrive", "quad",
            "shieldrepair", "revive", "button", "power_switch", "final_teleporter",
        )
        for kind in kinds:
            surf = pygame.Surface((28, 28), pygame.SRCALPHA)

            if kind == "bullets":
                pygame.draw.rect(surf, (116, 80, 25), (4, 9, 20, 15))
                pygame.draw.rect(surf, (216, 173, 62), (4, 8, 20, 5))
                for x in (8, 13, 18):
                    pygame.draw.rect(surf, (233, 214, 128), (x, 2, 4, 12))
                    pygame.draw.polygon(surf, (136, 93, 33), [(x, 2), (x + 2, 0), (x + 4, 2)])

            elif kind == "shells":
                for x in (5, 10, 15, 20):
                    pygame.draw.rect(surf, (168, 37, 30), (x, 4, 4, 18))
                    pygame.draw.rect(surf, (213, 175, 69), (x, 19, 4, 5))

            elif kind == "medkit":
                pygame.draw.rect(surf, (203, 202, 188), (3, 5, 22, 20))
                pygame.draw.rect(surf, (80, 78, 72), (7, 2, 14, 5))
                pygame.draw.rect(surf, RED, (11, 8, 6, 14))
                pygame.draw.rect(surf, RED, (7, 12, 14, 6))

            elif kind == "armor":
                pygame.draw.polygon(surf, (50, 126, 177), [(14, 2), (25, 7), (22, 22), (14, 27), (6, 22), (3, 7)])
                pygame.draw.polygon(surf, (95, 192, 210), [(14, 5), (21, 9), (19, 19), (14, 23), (9, 19), (7, 9)])

            elif kind in ("redkey", "bluekey", "greenkey"):
                key_color = {
                    "redkey": (214, 40, 31),
                    "bluekey": (48, 132, 230),
                    "greenkey": (48, 205, 105),
                }[kind]
                pygame.draw.circle(surf, key_color, (9, 10), 6)
                pygame.draw.circle(surf, (49, 12, 11), (9, 10), 2)
                pygame.draw.rect(surf, key_color, (13, 8, 12, 5))
                pygame.draw.rect(surf, key_color, (21, 12, 4, 7))
                pygame.draw.rect(surf, key_color, (17, 12, 3, 4))

            elif kind == "shotgun":
                pygame.draw.rect(surf, (51, 52, 55), (3, 10, 22, 5))
                pygame.draw.rect(surf, (89, 55, 31), (8, 15, 12, 7))
                pygame.draw.rect(surf, (29, 29, 31), (20, 8, 7, 3))

            elif kind == "shield":
                pygame.draw.polygon(surf, (54, 61, 76), [(14, 1), (25, 6), (23, 21), (14, 27), (5, 21), (3, 6)])
                pygame.draw.polygon(surf, (121, 135, 151), [(14, 4), (22, 8), (20, 19), (14, 23), (8, 19), (6, 8)])
                pygame.draw.line(surf, (205, 178, 78), (14, 5), (14, 22), 2)
                pygame.draw.circle(surf, (67, 209, 210), (14, 13), 3)

            elif kind == "sprayer":
                pygame.draw.rect(surf, (39, 43, 51), (3, 9, 23, 7))
                pygame.draw.rect(surf, (107, 120, 130), (7, 6, 17, 6))
                pygame.draw.rect(surf, (70, 137, 148), (10, 15, 10, 10))
                pygame.draw.rect(surf, (218, 181, 72), (21, 10, 6, 4))

            elif kind == "ammobox":
                pygame.draw.rect(surf, (63, 75, 54), (2, 7, 24, 18))
                pygame.draw.rect(surf, (129, 148, 77), (2, 7, 24, 5))
                pygame.draw.rect(surf, (226, 190, 68), (11, 12, 6, 10))

            elif kind == "megahealth":
                pygame.draw.circle(surf, (55, 196, 229), (14, 14), 13)
                pygame.draw.rect(surf, WHITE, (11, 5, 6, 18))
                pygame.draw.rect(surf, WHITE, (5, 11, 18, 6))

            elif kind in ("overdrive", "quad"):
                color = (246, 132, 43) if kind == "overdrive" else (89, 93, 245)
                pygame.draw.circle(surf, color, (14, 14), 12)
                pygame.draw.circle(surf, WHITE, (14, 14), 8, 2)
                symbol = "R" if kind == "overdrive" else "X"
                glyph = pygame.font.SysFont("arial", 12, bold=True).render(symbol, True, WHITE)
                surf.blit(glyph, glyph.get_rect(center=(14, 14)))

            elif kind == "shieldrepair":
                pygame.draw.rect(surf, (49, 62, 76), (4, 5, 20, 20))
                pygame.draw.line(surf, CYAN, (7, 21), (21, 7), 4)
                pygame.draw.line(surf, CYAN, (7, 7), (21, 21), 4)

            elif kind == "revive":
                pygame.draw.circle(surf, (74, 4, 12), (14, 14), 13)
                pygame.draw.circle(surf, (238, 42, 48), (14, 14), 10, 2)
                pygame.draw.polygon(
                    surf,
                    (255, 84, 73),
                    [(14, 2), (24, 14), (14, 26), (4, 14)],
                )
                pygame.draw.rect(surf, WHITE, (12, 7, 4, 14))
                pygame.draw.rect(surf, WHITE, (8, 11, 12, 4))

            elif kind == "final_teleporter":
                # Ceremonial gold-and-void pedestal with a luminous star core.
                pygame.draw.ellipse(surf, (34, 10, 45), (1, 19, 26, 8))
                pygame.draw.ellipse(surf, (229, 181, 54), (2, 18, 24, 7), 2)
                pygame.draw.polygon(
                    surf,
                    (76, 42, 91),
                    [(5, 19), (8, 5), (20, 5), (23, 19)],
                )
                pygame.draw.polygon(
                    surf,
                    (252, 211, 84),
                    [(14, 2), (17, 9), (25, 11), (18, 15),
                     (19, 23), (14, 18), (9, 23), (10, 15),
                     (3, 11), (11, 9)],
                    2,
                )
                pygame.draw.circle(surf, (255, 82, 226), (14, 12), 6)
                pygame.draw.circle(surf, (255, 244, 180), (14, 12), 2)

            elif kind in ("button", "power_switch"):
                base = (55, 61, 68) if kind == "button" else (69, 58, 28)
                light = RED if kind == "button" else YELLOW
                pygame.draw.rect(surf, base, (4, 3, 20, 24))
                pygame.draw.rect(surf, (20, 23, 27), (7, 6, 14, 18))
                pygame.draw.circle(surf, light, (14, 13), 5)

            pickups[kind] = surf
        return pickups

    def _make_projectiles(self):
        projectiles = {}
        colors = {
            "warden_bolt": ((255, 179, 55), (255, 239, 162)),
            "rift_bolt": ((189, 62, 236), (250, 195, 255)),
            "overseer_orb": ((45, 183, 235), (198, 247, 255)),
            "nightmare_bolt": ((243, 46, 132), (255, 204, 103)),
            "poison_orb": ((93, 214, 72), (218, 255, 126)),
            "drain_orb": ((183, 45, 185), (255, 191, 240)),
        }
        for kind, (outer, inner) in colors.items():
            surf = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*outer, 70), (8, 8), 8)
            pygame.draw.circle(surf, outer, (8, 8), 5)
            pygame.draw.circle(surf, inner, (8, 8), 2)
            projectiles[kind] = surf
        return projectiles

    def _make_exit_frames(self):
        frames = []
        for frame in range(4):
            surf = pygame.Surface((40, 56), pygame.SRCALPHA)
            glow = 110 + frame * 25
            pygame.draw.rect(surf, (48, 51, 55), (4, 4, 32, 50))
            pygame.draw.rect(surf, (19, 21, 23), (8, 8, 24, 42))
            pygame.draw.rect(surf, (26, glow, 58), (12, 12, 16, 25))
            pygame.draw.rect(surf, (118, 226, 132), (15, 15, 10, 19))
            pygame.draw.rect(surf, (134, 35, 28), (12, 41, 16, 7))
            frames.append(surf)
        return frames


# ---------------------------------------------------------------------------
# Generated sound effects
# ---------------------------------------------------------------------------

class SoundBank:
    SAMPLE_RATE = 44100
    MUSIC_PATHS = {
        "ambient": Path(__file__).resolve().parent / "The 9th Circle V2.mpeg",
        "boss": Path(__file__).resolve().parent / "Quadrant Boss (3).wav",
        "final": Path(__file__).resolve().parent / "Final Boss (1).wav",
    }

    def __init__(self):
        self.enabled = False
        self.sounds = {}
        self.music = {}
        self.music_channel = None
        self.music_mode = None
        self.music_duck_until = 0
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=self.SAMPLE_RATE, size=-16, channels=2, buffer=1024)
            # Keep channel zero exclusively for music so rapid weapon sounds
            # cannot interrupt a looping track.
            pygame.mixer.set_num_channels(max(12, pygame.mixer.get_num_channels()))
            pygame.mixer.set_reserved(1)
            self.music_channel = pygame.mixer.Channel(0)
            self.enabled = True
            self.sounds = {
                "pistol": self._noise_burst(0.12, 0.50, 130),
                "shotgun": self._noise_burst(0.24, 0.78, 70),
                "sprayer": self._noise_burst(0.055, 0.28, 190),
                "pickup": self._sweep(520, 910, 0.13, 0.28),
                "door": self._sweep(110, 65, 0.38, 0.35),
                "hurt": self._noise_burst(0.10, 0.30, 210),
                "enemy": self._sweep(150, 85, 0.20, 0.27),
                "switch": self._sweep(310, 160, 0.16, 0.30),
                "nightmare_transform": self._nightmare_stinger(),
            }
            self.music = self._load_music()
        except pygame.error:
            self.enabled = False

    def _sound(self, samples):
        # Generated sound effects are mono waveforms. Duplicate each sample
        # across the stereo mixer so both speakers receive the same effect.
        if pygame.mixer.get_init() and pygame.mixer.get_init()[2] == 2:
            stereo_samples = array("h")
            for sample in samples:
                stereo_samples.extend((sample, sample))
            return pygame.mixer.Sound(buffer=stereo_samples.tobytes())
        return pygame.mixer.Sound(buffer=array("h", samples).tobytes())

    def _load_music(self):
        """Load the bundled CC0 songs, retaining synthesis as a safe fallback."""
        tracks = {}
        for mode, path in self.MUSIC_PATHS.items():
            try:
                tracks[mode] = pygame.mixer.Sound(str(path))
            except (FileNotFoundError, pygame.error):
                tracks[mode] = self._music_loop(mode)
        return tracks

    def _noise_burst(self, duration, volume, tone):
        total = int(self.SAMPLE_RATE * duration)
        rng = random.Random(int(duration * 10000 + tone))
        samples = []
        for i in range(total):
            t = i / self.SAMPLE_RATE
            envelope = (1.0 - i / total) ** 2
            noise = rng.uniform(-1.0, 1.0)
            wave = math.sin(math.tau * tone * t)
            value = (noise * 0.70 + wave * 0.30) * envelope * volume
            samples.append(int(clamp(value, -1, 1) * 32767))
        return self._sound(samples)

    def _sweep(self, start_freq, end_freq, duration, volume):
        total = int(self.SAMPLE_RATE * duration)
        samples = []
        phase = 0.0
        for i in range(total):
            t = i / max(1, total - 1)
            freq = lerp(start_freq, end_freq, t)
            phase += math.tau * freq / self.SAMPLE_RATE
            envelope = math.sin(math.pi * t) ** 0.7
            value = math.sin(phase) * envelope * volume
            samples.append(int(clamp(value, -1, 1) * 32767))
        return self._sound(samples)

    def _nightmare_stinger(self):
        """Create a four-second horror sting synchronized to the mode merge."""
        duration = 4.0
        total = int(self.SAMPLE_RATE * duration)
        rng = random.Random(9666)
        samples = []
        low_phase = 0.0
        shriek_phase = 0.0
        for i in range(total):
            t = i / self.SAMPLE_RATE
            progress = t / duration

            low_frequency = lerp(76.0, 34.0, progress)
            low_phase += math.tau * low_frequency / self.SAMPLE_RATE
            rumble = (
                math.sin(low_phase)
                + 0.45 * math.sin(low_phase * 0.503)
            ) * (0.13 + progress * 0.16)

            # The dissonant rise peaks when NIGHTMARE appears on screen.
            rise = clamp(t / 2.35, 0.0, 1.0)
            shriek_frequency = lerp(145.0, 690.0, rise ** 1.7)
            shriek_phase += math.tau * shriek_frequency / self.SAMPLE_RATE
            shriek = (
                math.sin(shriek_phase)
                + 0.55 * math.sin(shriek_phase * 1.037)
            ) * (rise ** 1.4) * 0.17

            heartbeat = 0.0
            for beat_time in (0.42, 1.08, 1.72):
                beat_age = t - beat_time
                if 0.0 <= beat_age < 0.22:
                    beat_env = (1.0 - beat_age / 0.22) ** 2
                    heartbeat += math.sin(math.tau * 58.0 * beat_age) * beat_env * 0.42

            impact = 0.0
            impact_age = t - 2.34
            if 0.0 <= impact_age < 0.70:
                impact_env = (1.0 - impact_age / 0.70) ** 2
                impact_noise = rng.uniform(-1.0, 1.0)
                impact = (
                    impact_noise * 0.45
                    + math.sin(math.tau * 47.0 * impact_age) * 0.55
                ) * impact_env * 0.78

            hiss = rng.uniform(-1.0, 1.0) * (0.025 + rise * 0.055)
            fade_out = clamp((duration - t) / 0.55, 0.0, 1.0)
            value = (rumble + shriek + heartbeat + impact + hiss) * fade_out
            samples.append(int(clamp(value, -1, 1) * 32767))
        return self._sound(samples)

    def _music_loop(self, mode):
        """Synthesize a short, seamless industrial track for each danger tier."""
        if mode == "ambient":
            step_time = 0.50
            notes = (55.0, 0, 65.4, 0, 49.0, 0, 73.4, 65.4,
                     55.0, 0, 49.0, 0)
            base_volume, drone_volume = 0.125, 0.055
            kick_period, hat_period = 1.0, 0.50
        elif mode == "boss":
            step_time = 0.25
            notes = (55.0, 55.0, 65.4, 55.0, 73.4, 65.4, 49.0, 55.0,
                     55.0, 82.4, 73.4, 65.4, 49.0, 55.0, 65.4, 49.0)
            base_volume, drone_volume = 0.165, 0.060
            kick_period, hat_period = 0.50, 0.25
        else:
            step_time = 0.125
            notes = (55.0, 65.4, 73.4, 82.4, 55.0, 73.4, 98.0, 82.4,
                     49.0, 65.4, 73.4, 98.0, 55.0, 82.4, 110.0, 73.4,
                     55.0, 73.4, 82.4, 110.0, 49.0, 65.4, 98.0, 82.4,
                     55.0, 82.4, 98.0, 123.5, 49.0, 73.4, 110.0, 65.4)
            base_volume, drone_volume = 0.205, 0.065
            kick_period, hat_period = 0.25, 0.125

        duration = step_time * len(notes)
        total = int(self.SAMPLE_RATE * duration)
        samples = []
        track_gain = {"ambient": 2.20, "boss": 2.00, "final": 1.85}[mode]
        for i in range(total):
            t = i / self.SAMPLE_RATE
            step_index = min(len(notes) - 1, int(t / step_time))
            local = t - step_index * step_time
            note = notes[step_index]

            # Short attack/release on every note avoids clicks while retaining
            # the clipped pulse of a 1990s industrial soundtrack.
            note_edge = min(1.0, local / 0.018, (step_time - local) / 0.028)
            bass = 0.0
            if note:
                fundamental = math.sin(math.tau * note * t)
                # Laptop speakers often cannot reproduce the bass fundamental.
                # These octave harmonics keep the same melody clearly audible.
                octave = math.sin(math.tau * note * 2.0 * t)
                upper = math.sin(math.tau * note * 4.0 * t)
                bass = (
                    fundamental * 0.48 + octave * 0.36 + upper * 0.16
                ) * note_edge * base_volume

            drone = (
                math.sin(math.tau * 55.0 * t)
                + 0.45 * math.sin(math.tau * 82.4 * t)
            ) * drone_volume

            kick_local = t % kick_period
            kick = 0.0
            if kick_local < 0.105:
                kick_env = (1.0 - kick_local / 0.105) ** 2
                kick_freq = 92.0 - 48.0 * (kick_local / 0.105)
                kick = math.sin(math.tau * kick_freq * kick_local) * kick_env * 0.16

            hat_local = t % hat_period
            hat = 0.0
            if mode != "ambient" and hat_local < 0.035:
                hat_env = (1.0 - hat_local / 0.035) ** 3
                noise = (((i * 1103515245 + 12345) >> 8) & 65535) / 32767.5 - 1.0
                hat = noise * hat_env * (0.030 if mode == "boss" else 0.045)

            # Fade only the track edges very slightly for a clean loop point.
            loop_edge = min(1.0, t / 0.025, (duration - t) / 0.025)
            value = (bass + drone + kick + hat) * loop_edge * track_gain
            samples.append(int(clamp(value, -1, 1) * 32767))
        return self._sound(samples)

    def play(self, name):
        if self.enabled and name in self.sounds:
            if name == "nightmare_transform":
                # Let the transformation dominate without permanently changing
                # the user's normal exploration-music volume.
                self.music_duck_until = pygame.time.get_ticks() + 4000
            self.sounds[name].play()

    def set_music(self, mode):
        """Switch music only when the active encounter tier changes."""
        if not self.enabled or self.music_channel is None or mode not in self.music:
            return
        volume = {"ambient": 0.90, "boss": 0.96, "final": 1.00}[mode]
        if pygame.time.get_ticks() < self.music_duck_until:
            volume *= 0.28
        self.music_channel.set_volume(volume)
        if self.music_mode == mode and self.music_channel.get_busy():
            return
        self.music_mode = mode
        self.music_channel.play(self.music[mode], loops=-1, fade_ms=350)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.init()
        pygame.display.set_caption("HELLSHIFT: HANGAR 9")

        self.fullscreen = False
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.canvas = pygame.Surface((INTERNAL_W, INTERNAL_H))
        self.clock = pygame.time.Clock()

        self.font6 = pygame.font.SysFont("consolas", 7, bold=True)
        self.font8 = pygame.font.SysFont("consolas", 9, bold=True)
        self.font12 = pygame.font.SysFont("consolas", 13, bold=True)
        self.font24 = pygame.font.SysFont("consolas", 25, bold=True)
        # Clean antialiased fonts used only by the title menu.
        self.menu_title_font = pygame.font.SysFont("arial", 30, bold=True)
        self.menu_subtitle_font = pygame.font.SysFont("arial", 14, bold=True)
        self.menu_text_font = pygame.font.SysFont("arial", 9, bold=True)
        self.menu_prompt_font = pygame.font.SysFont("arial", 11, bold=True)
        # Plain antialiased fonts keep the information-heavy instruction page
        # readable while the in-game HUD retains its deliberate pixel style.
        self.instructions_font = pygame.font.SysFont("arial", 7)
        self.instructions_small_font = pygame.font.SysFont("arial", 7)
        self._hud_font_cache_key = None
        self._hud_screen_fonts = {}
        # Exact-result rendering caches avoid recreating identical Pygame
        # surfaces. They change neither the source art nor its final pixels.
        self._wall_column_cache = OrderedDict()
        self._scaled_sprite_cache = OrderedDict()
        self._pickup_aura_cache = OrderedDict()
        self._low_health_surface = pygame.Surface(
            (INTERNAL_W, VIEW_H), pygame.SRCALPHA
        )
        self._damage_flash_surface = pygame.Surface(
            (INTERNAL_W, VIEW_H), pygame.SRCALPHA
        )

        self.assets = Assets()
        self.sounds = SoundBank()

        self.show_map = False
        self.show_fps = False
        self.paused = False
        self.running = True
        self.mouse_captured = False
        self.selected_difficulty = "easy"
        self.selected_map_size = "small"
        self.nightmare_anim_start = 0
        self.reset()
        self.state = "menu"
        self.sounds.set_music("ambient")
        self.set_mouse_capture(False)

    def reset(self):
        template = BIG_LEVEL_MAP if self.selected_map_size == "big" else LEVEL_MAP
        self.map_data = [list(row) for row in template]
        self.map_h = len(self.map_data)
        self.map_w = len(self.map_data[0])
        self.doors = {}
        self.breakable_walls = {}
        self.switches = []
        for y, row in enumerate(self.map_data):
            for x, tile in enumerate(row):
                if tile in DOOR_TILES:
                    key = {"R": "red", "K": "blue", "G": "green"}.get(tile)
                    requires_power = tile == "P"
                    self.doors[(x, y)] = Door(
                        x,
                        y,
                        key=key,
                        requires_power=requires_power,
                        powered=not requires_power,
                    )
                elif tile == "B":
                    tutorial_wall = self.selected_map_size == "big" and (x, y) == (3, 2)
                    self.breakable_walls[(x, y)] = 1 if tutorial_wall else 6

        self.player_x = 1.8
        self.player_y = 1.8
        self.player_angle = 0.12
        self.health = PLAYER_START_HEALTH
        self.armor = 0
        # Ammo stored here is reserve ammunition. The revolver begins loaded,
        # preserving the original total of 50 starting bullets (26 + 24).
        self.ammo = {"bullets": 24, "shells": 0}
        self.magazines = {"pistol": 26, "shotgun": 0, "sprayer": 0}
        self.reloading_weapon = None
        self.reload_timer = 0.0
        self.reload_duration = 0.0
        self.has_shotgun = False
        self.has_shield = False
        self.has_sprayer = False
        self.has_red_key = False
        self.has_blue_key = False
        self.has_green_key = False
        self.has_revive = False
        self.weapon = "pistol"
        self.projectiles = []
        self.energy_fields = []
        self.claw_strikes = []
        self.weapon_cooldown = 0.0
        self.weapon_anim = 0.0
        self.muzzle_timer = 0.0
        self.shield_flash = 0.0
        self.shield_hits = 0
        self.shield_max_durability = (
            SMALL_SHIELD_MAX_DURABILITY
            if self.selected_map_size == "small"
            else SHIELD_MAX_DURABILITY
        )
        self.damage_flash = 0.0
        self.face_hurt_timer = 0.0
        self.bob_time = 0.0
        self.moving = False
        self.score = 0
        self.score_multiplier = {
            ("small", "easy"): 1.0,
            ("small", "hard"): 1.5,
            ("big", "easy"): 2.0,
            ("big", "hard"): 3.0,
        }[(self.selected_map_size, self.selected_difficulty)]
        self.kills = 0
        self.total_kills = 0
        self.elapsed = 0.0
        self.overdrive_timer = 0.0
        self.quad_timer = 0.0
        self.poison_timer = 0.0
        self.poison_tick = 0.0
        self.revive_screen_timer = 0.0
        self.invincibility_timer = 0.0
        self.state = "playing"

        self.message = "Tip: You can switch between items with number keys"
        self.message_timer = 5.0

        enemy_spawns = [
            # Original 13 hostiles.
            (5.5, 5.0, "grunt", 3),
            (8.5, 2.2, "grunt", 3),
            (12.5, 5.2, "fiend", 5),
            (18.0, 5.3, "grunt", 3),
            (21.2, 9.5, "fiend", 5),
            (14.7, 10.0, "grunt", 3),
            (7.8, 12.2, "fiend", 5),
            (3.2, 12.0, "grunt", 3),
            (4.2, 18.8, "fiend", 5),
            (9.7, 18.5, "grunt", 3),
            (15.6, 16.4, "fiend", 5),
            (20.7, 16.0, "grunt", 3),
            (20.8, 21.2, "fiend", 6),
            # 13 reinforcements: 26 hostiles total.
            (6.3, 5.3, "grunt", 3),
            (7.6, 2.4, "grunt", 3),
            (11.7, 5.6, "fiend", 5),
            (19.0, 5.5, "grunt", 3),
            (20.4, 9.2, "fiend", 5),
            (15.5, 9.8, "grunt", 3),
            (6.8, 12.6, "fiend", 5),
            (4.2, 12.7, "grunt", 3),
            (5.2, 19.2, "fiend", 5),
            (10.5, 19.4, "grunt", 3),
            (14.8, 15.5, "fiend", 5),
            (21.7, 16.4, "grunt", 3),
            (21.8, 22.0, "fiend", 6),
            # The Hangar Warden guards the exit in the final locked room.
            (20.4, 20.2, "boss", BOSS_MAX_HEALTH),
        ]
        if self.selected_map_size == "small":
            if self.selected_difficulty == "easy":
                enemy_spawns = [spawn for spawn in enemy_spawns if spawn[2] != "boss"]
            else:
                # Small Hard has 1.5x regular opposition while keeping one boss.
                enemy_spawns.extend(self.small_hard_reinforcements(enemy_spawns))
        else:
            big_regular_spawns = self.big_enemy_spawns()
            enemy_spawns.extend(big_regular_spawns)
            if self.selected_difficulty == "easy":
                enemy_spawns = [spawn for spawn in enemy_spawns if spawn[2] != "boss"]
                enemy_spawns.append((*FINAL_BOSS_POS, "boss", BOSS_MAX_HEALTH))
            else:
                # Nightmare raises Q2/Q3 opposition to 1.5x and Q4 to 2x.
                enemy_spawns.extend(
                    self.nightmare_quadrant_reinforcements(big_regular_spawns)
                )
                enemy_spawns.extend(
                    [
                        (40.0, 20.5, "summoner", SUMMONER_MAX_HEALTH),
                        (12.0, 40.0, "overseer", OVERSEER_MAX_HEALTH),
                        (*FINAL_BOSS_POS, "nightmare", NIGHTMARE_MAX_HEALTH),
                    ]
                )

        boss_kinds = ("boss", "summoner", "overseer", "nightmare")
        enemy_spawns = [
            (
                x,
                y,
                kind,
                hp if kind in boss_kinds else hp + self.quadrant_health_bonus(x, y),
            )
            for x, y, kind, hp in enemy_spawns
        ]
        self.enemies = [Enemy(*spawn) for spawn in enemy_spawns]
        self.final_boss = (
            next(
                (
                    enemy for enemy in self.enemies
                    if math.hypot(
                        enemy.x - FINAL_BOSS_POS[0],
                        enemy.y - FINAL_BOSS_POS[1],
                    ) < 0.1
                ),
                None,
            )
            if self.selected_map_size == "big"
            else None
        )
        self.total_kills = len(self.enemies)

        self.pickups = [
            # The shotgun is now found deep in the lower complex.
            Pickup(12.5, 16.8, "shotgun"),
            Pickup(6.2, 5.6, "shells"),
            Pickup(8.3, 8.5, "medkit"),
            Pickup(12.0, 2.0, "bullets"),
            Pickup(15.5, 5.0, "armor"),
            Pickup(18.4, 5.4, "shells"),
            Pickup(14.6, 12.2, "redkey"),
            Pickup(2.7, 17.7, "medkit"),
            Pickup(10.5, 16.8, "bullets"),
            # Defensive equipment found shortly before the final approach.
            Pickup(18.8, 16.5, "shield"),
            Pickup(16.0, 20.5, "shells"),
            Pickup(21.5, 12.4, "medkit"),
        ]

        if self.selected_map_size == "big":
            self.pickups.extend(self.big_pickups())
            self.switches = [
                WorldSwitch(42.5, 5.5, "button", ((34, 12),)),
                WorldSwitch(12.5, 39.5, "power_switch"),
                WorldSwitch(*FINAL_TELEPORTER_POS, "final_teleporter"),
            ]
            self.exit_x, self.exit_y = FINAL_ARENA_EXIT
        else:
            # The one-use revive is exclusive to the expanded campaign.
            self.pickups = [
                pickup for pickup in self.pickups if pickup.kind != "revive"
            ]
            self.exit_x = 21.0
            self.exit_y = 21.1

        self.set_mouse_capture(True)

    def small_hard_reinforcements(self, current_spawns):
        """Add 13 reinforcements: 26 regular enemies become 39."""
        offsets = (
            (0.38, 0.0), (-0.38, 0.0), (0.0, 0.38), (0.0, -0.38),
            (0.30, 0.30), (-0.30, 0.30), (0.30, -0.30), (-0.30, -0.30),
        )
        reinforcements = []
        occupied = [(spawn[0], spawn[1]) for spawn in current_spawns]
        regular_spawns = [
            spawn for spawn in current_spawns if spawn[2] != "boss"
        ][::2]
        for index, (x, y, kind, hp) in enumerate(regular_spawns):
            placed = None
            for attempt in range(len(offsets)):
                offset_x, offset_y = offsets[(index + attempt) % len(offsets)]
                candidate_x = x + offset_x
                candidate_y = y + offset_y
                separated = all(
                    math.hypot(candidate_x - other_x, candidate_y - other_y) >= 0.24
                    for other_x, other_y in occupied
                )
                if separated and self.can_stand(candidate_x, candidate_y, 0.18):
                    placed = (candidate_x, candidate_y, kind, hp)
                    break
            if placed is None:
                placed = (x, y, kind, hp)
            reinforcements.append(placed)
            occupied.append((placed[0], placed[1]))
        return reinforcements

    @staticmethod
    def quadrant_health_bonus(x, y):
        """Return the regular-enemy health bonus for a spawn quadrant."""
        if x >= 24 and y >= 24:
            return 4
        if x >= 24 or y >= 24:
            return 2
        return 1

    def big_enemy_spawns(self):
        """Regular opposition spread across the three expanded quadrants."""
        return [
            # Quadrant two: foundry.
            (26.5, 3.5, "stalker", 5), (31.0, 5.5, "turret", 8),
            (38.0, 3.5, "spitter", 7), (44.5, 5.5, "charger", 10),
            (27.5, 11.5, "medic", 8), (32.0, 14.0, "turret", 8),
            (37.5, 11.0, "stalker", 5), (41.0, 14.0, "spitter", 7),
            (27.0, 19.0, "charger", 10), (32.0, 20.0, "medic", 8),
            (40.0, 18.5, "turret", 8), (45.0, 21.0, "stalker", 5),
            # Quadrant three: power plant.
            (3.0, 27.0, "stalker", 5), (6.0, 31.0, "turret", 8),
            (11.0, 29.0, "spitter", 7), (14.0, 31.0, "charger", 10),
            (19.0, 27.0, "medic", 8), (3.0, 37.0, "charger", 10),
            (7.0, 42.0, "spitter", 7), (11.0, 38.0, "turret", 8),
            (15.0, 41.0, "stalker", 5), (20.0, 37.0, "medic", 8),
            (5.0, 45.0, "charger", 10), (19.0, 45.0, "turret", 8),
            # Quadrant four: cathedral hangar.
            (26.0, 26.0, "turret", 8), (31.0, 28.0, "stalker", 5),
            (37.0, 26.0, "spitter", 7), (44.0, 28.0, "charger", 10),
            (27.0, 34.0, "medic", 8), (32.0, 36.0, "turret", 8),
            (38.0, 34.0, "stalker", 5), (45.0, 35.0, "spitter", 7),
            (26.0, 42.0, "charger", 10), (32.0, 44.0, "medic", 8),
            # These two formerly occupied the boss room; keeping them above
            # its entrance leaves the new teleporter hall completely empty.
            (36.0, 38.0, "turret", 8), (45.0, 38.0, "stalker", 5),
        ]

    def nightmare_quadrant_reinforcements(self, big_spawns):
        """Spread Nightmare-only reinforcements across quadrants two to four."""
        groups = {
            2: [spawn for spawn in big_spawns if spawn[0] >= 24 and spawn[1] < 24],
            3: [spawn for spawn in big_spawns if spawn[0] < 24 and spawn[1] >= 24],
            4: [spawn for spawn in big_spawns if spawn[0] >= 24 and spawn[1] >= 24],
        }
        additions = {2: len(groups[2]) // 2, 3: len(groups[3]) // 2, 4: len(groups[4])}
        bounds = {
            2: (24, 48, 0, 24),
            3: (0, 24, 24, 48),
            4: (24, 48, 24, 48),
        }
        reinforcements = []

        for quadrant in (2, 3, 4):
            source_group = groups[quadrant]
            min_x, max_x, min_y, max_y = bounds[quadrant]
            occupied = [(spawn[0], spawn[1]) for spawn in source_group]
            candidates = []
            for tile_y in range(min_y + 1, max_y - 1):
                for tile_x in range(min_x + 1, max_x - 1):
                    candidate_x = tile_x + 0.5
                    candidate_y = tile_y + 0.5
                    if self.tile_at(candidate_x, candidate_y) != ".":
                        continue
                    if not self.can_stand(candidate_x, candidate_y, 0.18):
                        continue
                    # Preserve the intentionally empty final-teleporter hall.
                    if quadrant == 4 and tile_x >= 34 and tile_y >= 40:
                        continue
                    candidates.append((candidate_x, candidate_y))

            for index in range(additions[quadrant]):
                separated_candidates = [
                    candidate for candidate in candidates
                    if all(
                        math.hypot(candidate[0] - other_x, candidate[1] - other_y) >= 1.15
                        for other_x, other_y in occupied
                    )
                ]
                available = separated_candidates or candidates
                if not available:
                    break

                # Farthest-point placement distributes reinforcements through
                # rooms and hallways instead of clustering beside old spawns.
                chosen = max(
                    available,
                    key=lambda candidate: min(
                        math.hypot(candidate[0] - other_x, candidate[1] - other_y)
                        for other_x, other_y in occupied
                    ),
                )
                source = source_group[index % len(source_group)]
                reinforcements.append((chosen[0], chosen[1], source[2], source[3]))
                occupied.append(chosen)
                candidates.remove(chosen)

        return reinforcements

    def big_pickups(self):
        """Extra weapons, keys, supplies, and timed powerups for the large map."""
        return [
            # Immediate tutorial cache behind the one-shot breakable wall.
            Pickup(4.4, 1.5, "ammobox"), Pickup(5.3, 2.3, "medkit"),
            # Big-only healing covers the far ends of the original quadrant.
            Pickup(16.5, 2.5, "medkit"), Pickup(18.5, 21.5, "medkit"),
            # One-use revive reward in the otherwise empty dead-end nook.
            Pickup(13.5, 10.5, "revive"),
            # Quadrant two supplies and blue progression key.
            Pickup(26.5, 5.5, "ammobox"), Pickup(31.0, 13.0, "shells"),
            Pickup(37.5, 6.0, "sprayer"), Pickup(27.5, 4.5, "medkit"),
            Pickup(43.5, 4.5, "medkit"), Pickup(25.5, 18.5, "medkit"),
            Pickup(29.5, 11.5, "medkit"), Pickup(37.5, 22.5, "medkit"),
            Pickup(40.0, 12.0, "bluekey"),
            Pickup(44.5, 19.5, "megahealth"),
            Pickup(46.0, 21.5, "medkit"),
            Pickup(40.5, 22.0, "medkit"),
            Pickup(41.0, 20.0, "quad"), Pickup(36.5, 20.0, "shieldrepair"),
            # Quadrant three supplies, powerups, and green progression key.
            Pickup(3.0, 31.5, "ammobox"), Pickup(12.0, 31.0, "shells"),
            Pickup(19.0, 29.0, "greenkey"), Pickup(1.5, 26.5, "medkit"),
            Pickup(13.5, 29.5, "medkit"), Pickup(3.5, 44.5, "medkit"),
            Pickup(6.5, 38.5, "medkit"), Pickup(18.5, 33.5, "medkit"),
            Pickup(12.0, 37.0, "overdrive"), Pickup(12.5, 38.5, "megahealth"),
            Pickup(21.5, 44.5, "megahealth"),
            Pickup(10.0, 45.0, "armor"), Pickup(18.5, 45.0, "shieldrepair"),
            Pickup(10.5, 41.5, "medkit"),
            Pickup(21.5, 41.5, "medkit"),
            # Extra late-quadrant ammunition before the route into the final arena.
            Pickup(20.5, 38.5, "ammobox"),
            # Final-quadrant healing is split across every arena section.
            Pickup(26.0, 29.0, "ammobox"), Pickup(31.5, 34.0, "shells"),
            Pickup(25.5, 27.5, "medkit"), Pickup(45.0, 30.0, "shield"),
            Pickup(35.5, 29.5, "medkit"),
            Pickup(41.5, 26.5, "medkit"), Pickup(26.5, 36.5, "medkit"),
            Pickup(41.5, 34.5, "medkit"),
            Pickup(29.5, 45.5, "megahealth"),
            # Final-arena supplies are distributed around its perimeter. Four
            # came from now-excessive quadrant-four caches, with bullets and
            # shells added so every firearm can be replenished for the boss.
            Pickup(58.5, 31.5, "overdrive"), Pickup(76.5, 17.5, "quad"),
            Pickup(60.5, 14.5, "shieldrepair"),
            Pickup(74.5, 14.5, "megahealth"), Pickup(57.5, 17.5, "megahealth"),
            Pickup(73.5, 31.5, "medkit"), Pickup(76.5, 29.5, "medkit"),
            Pickup(57.5, 29.5, "ammobox"),
            Pickup(64.5, 13.5, "bullets"), Pickup(68.5, 34.5, "shells"),
        ]

    # ------------------------------------------------------------------
    # Map and collision
    # ------------------------------------------------------------------

    def tile_at(self, x, y):
        tx, ty = int(x), int(y)
        if tx < 0 or ty < 0 or tx >= self.map_w or ty >= self.map_h:
            return "1"
        return self.map_data[ty][tx]

    def tile_blocks(self, tx, ty):
        if tx < 0 or ty < 0 or tx >= self.map_w or ty >= self.map_h:
            return True
        tile = self.map_data[ty][tx]
        if tile == ".":
            return False
        if tile in DOOR_TILES:
            door = self.doors[(tx, ty)]
            return door.openness < 0.88
        return True

    def can_stand(self, x, y, radius=PLAYER_RADIUS):
        left = int(x - radius)
        right = int(x + radius)
        top = int(y - radius)
        bottom = int(y + radius)
        if self.tile_blocks(left, top):
            return False
        if right != left and self.tile_blocks(right, top):
            return False
        if bottom != top:
            if self.tile_blocks(left, bottom):
                return False
            if right != left and self.tile_blocks(right, bottom):
                return False
        for field in self.energy_fields:
            if (
                field.active
                and field.arming_time <= 0
                and math.hypot(x - field.x, y - field.y) < radius + field.radius
            ):
                return False
        return True

    def line_of_sight(self, x1, y1, x2, y2):
        distance = math.hypot(x2 - x1, y2 - y1)
        steps = max(2, int(distance / 0.06))
        for i in range(1, steps):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            if self.tile_blocks(int(x), int(y)):
                return False
        return True

    def clear_enemy_shot(self, x1, y1, x2, y2):
        """Use three tightly spaced rays so enemies cannot fire through corners."""
        dx = x2 - x1
        dy = y2 - y1
        distance = math.hypot(dx, dy)
        if distance < 0.08:
            return True

        perpendicular_x = -dy / distance
        perpendicular_y = dx / distance
        steps = max(2, int(distance / 0.025))
        # Neighboring samples overwhelmingly occupy the same map tile. Check
        # each unique tile once; tile state cannot change during this call.
        checked_tiles = set()
        tile_blocks = self.tile_blocks
        for index in range(1, steps):
            t = index / steps
            center_x = x1 + dx * t
            center_y = y1 + dy * t
            for offset in (-0.04, 0.0, 0.04):
                sample_x = center_x + perpendicular_x * offset
                sample_y = center_y + perpendicular_y * offset
                tile = (int(sample_x), int(sample_y))
                if tile in checked_tiles:
                    continue
                checked_tiles.add(tile)
                if tile_blocks(*tile):
                    return False
        return True

    def spawn_boss_projectile(
        self,
        enemy,
        kind,
        damage,
        effect="",
        spread=0.0,
        angle_offset=0.0,
        delay=0.0,
    ):
        """Launch one aimed projectile, optionally offset or delayed for patterns."""
        aim_angle = math.atan2(self.player_y - enemy.y, self.player_x - enemy.x)
        aim_angle += angle_offset + random.uniform(-spread, spread)
        direction_x = math.cos(aim_angle)
        direction_y = math.sin(aim_angle)
        self.projectiles.append(
            Projectile(
                enemy.x + direction_x * 0.38,
                enemy.y + direction_y * 0.38,
                direction_x,
                direction_y,
                BOSS_PROJECTILE_SPEED,
                damage,
                kind,
                source=enemy,
                effect=effect,
                delay=delay,
            )
        )

    def spawn_radial_burst(self, enemy, kind, damage_range, count, effect=""):
        """Fire a full circular nova with one lane aimed directly at the player."""
        for index in range(count):
            self.spawn_boss_projectile(
                enemy,
                kind,
                random.randint(*damage_range),
                effect=effect,
                angle_offset=math.tau * index / count,
            )

    def spawn_claw_line(self, enemy):
        """Telegraph sequential ground claws from the Overseer to the next wall."""
        aim_angle = math.atan2(self.player_y - enemy.y, self.player_x - enemy.x)
        direction_x = math.cos(aim_angle)
        direction_y = math.sin(aim_angle)
        new_claws = []
        index = 0
        while True:
            distance = 0.85 + index * 0.58
            claw_x = enemy.x + direction_x * distance
            claw_y = enemy.y + direction_y * distance
            if self.tile_blocks(int(claw_x), int(claw_y)):
                break
            new_claws.append(
                ClawStrike(
                    claw_x,
                    claw_y,
                    source=enemy,
                    delay=0.28 + index * 0.085,
                )
            )
            index += 1

        if not new_claws:
            return 0

        # The line has no claw-count or range cap: the wall determines its
        # length. It remains dangerous for five seconds after the final claw
        # has finished emerging, then every segment vanishes together.
        group_lifetime = (
            new_claws[-1].delay + CLAW_REVEAL_TIME + CLAW_HOLD_TIME
        )
        for claw in new_claws:
            claw.group_time_left = group_lifetime
        self.claw_strikes.extend(new_claws)
        return len(new_claws)

    def spawn_energy_field(self, enemy):
        """Place a telegraphed, temporary rift sphere near the player."""
        active_fields = [
            field
            for field in self.energy_fields
            if field.active and field.source is enemy
        ]
        if len(active_fields) >= 4:
            return False

        aim_angle = math.atan2(self.player_y - enemy.y, self.player_x - enemy.x)
        side = 1 if enemy.pattern_index % 2 == 0 else -1
        angle_offsets = (side * math.pi / 2, -side * math.pi / 2, math.pi, 0.0)
        for distance in (1.05, 1.40):
            for offset in angle_offsets:
                field_x = self.player_x + math.cos(aim_angle + offset) * distance
                field_y = self.player_y + math.sin(aim_angle + offset) * distance
                if self.tile_at(field_x, field_y) != ".":
                    continue
                if math.hypot(field_x - self.exit_x, field_y - self.exit_y) < 1.3:
                    continue
                overlaps_field = any(
                    field.active
                    and math.hypot(field_x - field.x, field_y - field.y)
                    < field.radius + 0.70
                    for field in self.energy_fields
                )
                if overlaps_field:
                    continue
                if not self.can_stand(field_x, field_y, 0.52):
                    continue
                self.energy_fields.append(
                    EnergyField(field_x, field_y, source=enemy)
                )
                return True
        return False

    def update_projectiles(self, dt):
        """Move boss projectiles, stop them at walls, and resolve impacts."""
        for projectile in self.projectiles:
            if not projectile.active:
                continue

            if projectile.delay > 0:
                projectile.delay = max(0.0, projectile.delay - dt)
                continue

            projectile.life -= dt
            if projectile.life <= 0:
                projectile.active = False
                continue

            travel = projectile.speed * dt
            steps = max(1, int(travel / 0.045) + 1)
            step_x = projectile.dx * travel / steps
            step_y = projectile.dy * travel / steps
            for _ in range(steps):
                next_x = projectile.x + step_x
                next_y = projectile.y + step_y
                if self.tile_blocks(int(next_x), int(next_y)):
                    projectile.active = False
                    break

                projectile.x = next_x
                projectile.y = next_y
                if math.hypot(
                    projectile.x - self.player_x,
                    projectile.y - self.player_y,
                ) >= 0.30:
                    continue

                projectile.active = False
                if self.shield_blocks_projectile(projectile, 2):
                    break

                if projectile.effect == "overseer":
                    self.armor = max(0, self.armor - random.randint(3, 7))

                self.damage_player(projectile.damage)
                source = projectile.source
                if projectile.effect == "poison":
                    self.poison_timer = max(self.poison_timer, 2.5)
                elif projectile.effect == "drain":
                    if source is not None and not source.dead:
                        source.hp = min(
                            NIGHTMARE_MAX_HEALTH,
                            source.hp + projectile.damage,
                        )
                elif projectile.effect == "overseer":
                    if source is not None and not source.dead:
                        source.hp = min(OVERSEER_MAX_HEALTH, source.hp + 2)
                break

        self.projectiles = [
            projectile for projectile in self.projectiles if projectile.active
        ]

    def update_energy_fields(self, dt):
        """Arm, pulse, damage on contact, and expire Summoner rift spheres."""
        for field in self.energy_fields:
            if not field.active:
                continue

            field.pulse += dt
            field.arming_time = max(0.0, field.arming_time - dt)
            field.life -= dt
            field.damage_cooldown = max(0.0, field.damage_cooldown - dt)
            if field.source is not None and field.source.dead:
                field.life = min(field.life, 0.8)
            if field.life <= 0:
                field.active = False
                continue

            touching = math.hypot(
                self.player_x - field.x,
                self.player_y - field.y,
            ) < field.radius + PLAYER_RADIUS + 0.06
            if field.arming_time <= 0 and touching and field.damage_cooldown <= 0:
                self.damage_player(field.damage)
                field.damage_cooldown = 0.75

        self.energy_fields = [field for field in self.energy_fields if field.active]

    def update_claw_strikes(self, dt):
        """Advance warnings and damage the player once per erupted claw."""
        for claw in self.claw_strikes:
            if not claw.active:
                continue
            if claw.source is not None and claw.source.dead:
                claw.active = False
                continue

            claw.group_time_left = max(0.0, claw.group_time_left - dt)
            if claw.group_time_left <= 0:
                claw.active = False
                continue
            if claw.delay > 0:
                claw.delay = max(0.0, claw.delay - dt)
                continue

            claw.age += dt
            touching = math.hypot(
                self.player_x - claw.x,
                self.player_y - claw.y,
            ) < 0.42
            if claw.age >= 0.08 and touching and not claw.damage_done:
                claw.damage_done = True
                self.damage_player(claw.damage)

        self.claw_strikes = [claw for claw in self.claw_strikes if claw.active]

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def set_mouse_capture(self, captured):
        """Capture and center the pointer for unlimited mouse turning."""
        self.mouse_captured = captured
        pygame.event.set_grab(captured)
        pygame.mouse.set_visible(not captured)
        if captured:
            pygame.mouse.set_pos(self.screen.get_rect().center)
        # Throw away movement caused by capturing or warping the pointer.
        pygame.mouse.get_rel()

    def internal_mouse_pos(self, position):
        width, height = self.screen.get_size()
        return int(position[0] * INTERNAL_W / width), int(position[1] * INTERNAL_H / height)

    def setup_rects(self):
        return {
            "easy": pygame.Rect(34, 57, 112, 30),
            "hard": pygame.Rect(174, 57, 112, 30),
            "small": pygame.Rect(34, 111, 112, 30),
            "big": pygame.Rect(174, 111, 112, 30),
            "start": pygame.Rect(103, 161, 114, 25),
        }

    def set_game_option(self, difficulty=None, map_size=None):
        was_nightmare = self.selected_difficulty == "hard" and self.selected_map_size == "big"
        if difficulty is not None:
            self.selected_difficulty = difficulty
        if map_size is not None:
            self.selected_map_size = map_size
        is_nightmare = self.selected_difficulty == "hard" and self.selected_map_size == "big"
        if is_nightmare and not was_nightmare:
            self.nightmare_anim_start = pygame.time.get_ticks()
            self.sounds.play("nightmare_transform")
        elif not is_nightmare:
            self.nightmare_anim_start = 0

    def nightmare_animation_active(self):
        if not (self.selected_difficulty == "hard" and self.selected_map_size == "big"):
            return False
        return pygame.time.get_ticks() - self.nightmare_anim_start < 4000

    def request_game_start(self):
        if self.nightmare_animation_active():
            return
        if self.selected_difficulty == "hard" and self.selected_map_size == "big":
            self.state = "nightmare_confirm"
            self.set_mouse_capture(False)
        else:
            self.reset()

    def handle_setup_click(self, position):
        point = self.internal_mouse_pos(position)
        rects = self.setup_rects()
        if rects["easy"].collidepoint(point):
            self.set_game_option(difficulty="easy")
        elif rects["hard"].collidepoint(point):
            self.set_game_option(difficulty="hard")
        elif rects["small"].collidepoint(point):
            self.set_game_option(map_size="small")
        elif rects["big"].collidepoint(point):
            self.set_game_option(map_size="big")
        elif rects["start"].collidepoint(point):
            self.request_game_start()

    def handle_events(self):
        fire = False
        use = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "nightmare_confirm":
                        self.state = "setup"
                    elif self.state == "setup":
                        self.state = "instructions"
                    elif self.state == "instructions":
                        self.state = "menu"
                    else:
                        self.running = False
                elif self.state == "menu":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.state = "instructions"
                        self.set_mouse_capture(False)
                elif self.state == "instructions":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.state = "setup"
                        self.set_mouse_capture(False)
                elif self.state == "setup":
                    if event.key == pygame.K_e:
                        self.set_game_option(difficulty="easy")
                    elif event.key == pygame.K_h:
                        self.set_game_option(difficulty="hard")
                    elif event.key == pygame.K_s:
                        self.set_game_option(map_size="small")
                    elif event.key == pygame.K_b:
                        self.set_game_option(map_size="big")
                    elif event.key == pygame.K_RETURN:
                        self.request_game_start()
                elif self.state == "nightmare_confirm":
                    if event.key in (pygame.K_RETURN, pygame.K_y):
                        self.reset()
                    elif event.key in (pygame.K_n, pygame.K_BACKSPACE):
                        self.state = "setup"
                elif event.key == pygame.K_TAB:
                    self.show_map = not self.show_map
                elif event.key == pygame.K_F3:
                    self.show_fps = not self.show_fps
                elif event.key == pygame.K_p and self.state == "playing":
                    self.paused = not self.paused
                    self.set_mouse_capture(not self.paused)
                elif event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif event.key == pygame.K_r:
                    self.begin_reload()
                elif event.key == pygame.K_1:
                    self.select_weapon("pistol")
                elif event.key == pygame.K_2 and self.has_shotgun:
                    self.select_weapon("shotgun")
                elif event.key == pygame.K_3 and self.has_shield:
                    self.select_weapon("shield")
                elif event.key == pygame.K_4 and self.has_sprayer:
                    self.select_weapon("sprayer")
                elif event.key in (pygame.K_e, pygame.K_SPACE):
                    use = True
                elif event.key in (pygame.K_LCTRL, pygame.K_RCTRL):
                    fire = True
                elif event.key == pygame.K_RETURN and self.state in ("dead", "won"):
                    self.reset()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "menu":
                    self.state = "instructions"
                    self.set_mouse_capture(False)
                elif self.state == "instructions":
                    self.state = "setup"
                    self.set_mouse_capture(False)
                elif self.state == "setup":
                    self.handle_setup_click(event.pos)
                elif self.state == "nightmare_confirm":
                    mx, my = self.internal_mouse_pos(event.pos)
                    if pygame.Rect(42, 145, 105, 28).collidepoint(mx, my):
                        self.reset()
                    elif pygame.Rect(173, 145, 105, 28).collidepoint(mx, my):
                        self.state = "setup"
                else:
                    if self.state == "playing" and not self.paused and not self.mouse_captured:
                        self.set_mouse_capture(True)
                    fire = True

            elif event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                self.set_mouse_capture(False)

            elif event.type == getattr(pygame, "WINDOWFOCUSGAINED", -1):
                if self.state == "playing" and not self.paused:
                    self.set_mouse_capture(True)

        mouse_dx, _ = pygame.mouse.get_rel()
        if self.state == "playing" and not self.paused and self.mouse_captured:
            self.player_angle = (self.player_angle + mouse_dx * MOUSE_SENSITIVITY) % math.tau

            # Some window managers ignore the first Pygame grab request. Keeping
            # the pointer centered prevents it from ever reaching a screen edge,
            # so turning remains unlimited even in that case.
            center = self.screen.get_rect().center
            if pygame.mouse.get_pos() != center:
                pygame.mouse.set_pos(center)
                pygame.mouse.get_rel()

            if self.weapon == "sprayer":
                keys = pygame.key.get_pressed()
                mouse_down = pygame.mouse.get_pressed()[0]
                ctrl_down = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
                fire = fire or mouse_down or ctrl_down

        return fire, use

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        size = (0, 0) if self.fullscreen else (SCREEN_W, SCREEN_H)
        self.screen = pygame.display.set_mode(size, flags)
        if self.state == "playing" and not self.paused:
            self.set_mouse_capture(True)

    # ------------------------------------------------------------------
    # Player movement and interaction
    # ------------------------------------------------------------------

    def remaining_teleporter_hostiles(self):
        """Count every living enemy except the unreachable final-arena boss."""
        return sum(
            not enemy.dead and enemy is not self.final_boss
            for enemy in self.enemies
        )

    def update_player(self, dt):
        keys = pygame.key.get_pressed()

        turn = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        self.player_angle = (self.player_angle + turn * TURN_SPEED * dt) % math.tau

        forward = (
            int(keys[pygame.K_w] or keys[pygame.K_UP])
            - int(keys[pygame.K_s] or keys[pygame.K_DOWN])
        )
        strafe = int(keys[pygame.K_d]) - int(keys[pygame.K_a])

        magnitude = math.hypot(forward, strafe)
        self.moving = magnitude > 0

        if magnitude:
            forward /= magnitude
            strafe /= magnitude
            running = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            speed = RUN_SPEED if running else WALK_SPEED

            cos_a = math.cos(self.player_angle)
            sin_a = math.sin(self.player_angle)
            dx = (cos_a * forward - sin_a * strafe) * speed * dt
            dy = (sin_a * forward + cos_a * strafe) * speed * dt

            if self.can_stand(self.player_x + dx, self.player_y):
                self.player_x += dx
            if self.can_stand(self.player_x, self.player_y + dy):
                self.player_y += dy

            self.bob_time += dt * speed * 4.2
        else:
            self.bob_time += dt * 1.2

    def use_action(self):
        best = None
        best_distance = 999.0

        for switch in self.switches:
            dx = switch.x - self.player_x
            dy = switch.y - self.player_y
            distance = math.hypot(dx, dy)
            angle = abs(normalize_angle(math.atan2(dy, dx) - self.player_angle))
            if distance < 1.45 and angle < math.radians(65) and distance < best_distance:
                best = switch
                best_distance = distance

        for door in self.doors.values():
            dx = door.x + 0.5 - self.player_x
            dy = door.y + 0.5 - self.player_y
            distance = math.hypot(dx, dy)
            angle = abs(normalize_angle(math.atan2(dy, dx) - self.player_angle))
            if distance < 1.55 and angle < math.radians(65) and distance < best_distance:
                best = door
                best_distance = distance

        if best is not None:
            if isinstance(best, WorldSwitch):
                if best.kind == "final_teleporter":
                    if best.activated:
                        self.set_message("The final teleporter has already fired.", 1.0)
                        return
                    remaining = self.remaining_teleporter_hostiles()
                    if remaining:
                        self.set_message(
                            f"TELEPORT LOCKED: {remaining} quadrant hostile"
                            f"{'s' if remaining != 1 else ''} remain.",
                            2.0,
                        )
                        self.sounds.play("switch")
                        return

                    best.activated = True
                    self.player_x, self.player_y = FINAL_ARENA_ENTRY
                    self.player_angle = 0.0
                    self.projectiles.clear()
                    self.energy_fields.clear()
                    self.claw_strikes.clear()
                    self.poison_timer = 0.0
                    self.poison_tick = 0.0
                    self.set_message("FINAL ARENA TRANSMISSION COMPLETE.", 2.0)
                    self.sounds.play("door")
                    return

                if best.activated:
                    self.set_message("The switch is already active.", 1.0)
                    return
                best.activated = True
                if best.kind == "power_switch":
                    for door in self.doors.values():
                        if door.requires_power:
                            door.powered = True
                    self.set_message("MAIN POWER RESTORED.", 2.2)
                else:
                    for target in best.targets:
                        door = self.doors.get(target)
                        if door is not None:
                            door.powered = True
                            door.opening = True
                    self.set_message("REMOTE SECURITY DOOR OPENED.", 2.0)
                self.sounds.play("switch")
                return

            key_owned = {
                "red": self.has_red_key,
                "blue": self.has_blue_key,
                "green": self.has_green_key,
            }
            if best.requires_power and not best.powered:
                self.set_message("NO POWER. Find a button or power switch.", 1.8)
                self.sounds.play("switch")
            elif best.key and not key_owned[best.key]:
                self.set_message(f"The door requires a {best.key.upper()} keycard.", 1.8)
                self.sounds.play("switch")
            else:
                if not best.opening:
                    best.opening = True
                    self.sounds.play("door")
                    self.set_message("Door opening.", 0.9)
            return

        distance_to_exit = math.hypot(self.exit_x - self.player_x, self.exit_y - self.player_y)
        if distance_to_exit < 1.3:
            living = sum(not enemy.dead for enemy in self.enemies)
            if living:
                self.set_message(f"Exit denied: {living} hostile{'s' if living != 1 else ''} remain.", 1.8)
                self.sounds.play("switch")
            else:
                self.state = "won"
                self.sounds.play("switch")
                self.set_mouse_capture(False)
            return

        self.set_message("Nothing to use.", 0.7)

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------

    def cancel_reload(self):
        self.reloading_weapon = None
        self.reload_timer = 0.0
        self.reload_duration = 0.0

    def select_weapon(self, weapon_name):
        """Select an owned weapon and cancel any reload in progress."""
        owned = {
            "pistol": True,
            "shotgun": self.has_shotgun,
            "shield": self.has_shield,
            "sprayer": self.has_sprayer,
        }
        if not owned.get(weapon_name, False):
            return
        if self.weapon != weapon_name:
            self.cancel_reload()
        self.weapon = weapon_name
        if weapon_name == "shield":
            self.weapon_anim = 0.0

    def transfer_ammo_to_magazine(self, weapon_name):
        """Move as much reserve ammunition as possible into one magazine."""
        weapon = WEAPONS[weapon_name]
        ammo_type = weapon["ammo"]
        needed = weapon["mag_size"] - self.magazines[weapon_name]
        loaded = min(needed, self.ammo[ammo_type])
        self.magazines[weapon_name] += loaded
        self.ammo[ammo_type] -= loaded
        return loaded

    def begin_reload(self):
        """Start a timed reload for the currently selected firearm."""
        if self.state != "playing" or self.paused or self.weapon == "shield":
            return False
        if self.reloading_weapon is not None:
            return False

        weapon = WEAPONS[self.weapon]
        ammo_type = weapon["ammo"]
        if self.magazines[self.weapon] >= weapon["mag_size"]:
            self.set_message("Magazine already full.", 0.8)
            return False
        if self.ammo[ammo_type] <= 0:
            self.set_message(f"No reserve {ammo_type}.", 1.0)
            return False

        self.reloading_weapon = self.weapon
        self.reload_duration = weapon["reload_time"]
        self.reload_timer = self.reload_duration
        self.weapon_anim = 0.0
        self.muzzle_timer = 0.0
        self.set_message(f"RELOADING {weapon['name']}...", self.reload_duration)
        self.sounds.play("switch")
        return True

    def update_reload(self, dt):
        """Advance a reload and fill the magazine when its timer expires."""
        if self.reloading_weapon is None:
            return
        self.reload_timer = max(0.0, self.reload_timer - dt)
        if self.reload_timer > 0:
            return

        weapon_name = self.reloading_weapon
        weapon = WEAPONS[weapon_name]
        self.transfer_ammo_to_magazine(weapon_name)
        current = self.magazines[weapon_name]
        capacity = weapon["mag_size"]
        self.cancel_reload()
        self.set_message(f"{weapon['name']} RELOADED: {current}/{capacity}", 1.0)
        self.sounds.play("pickup")

    def fire_weapon(self):
        if self.state != "playing" or self.paused or self.weapon_cooldown > 0:
            return

        if self.weapon == "shield":
            self.set_message("Shield raised. Press 1, 2, or 4 to fire.", 0.8)
            return

        if self.reloading_weapon is not None:
            return

        weapon = WEAPONS[self.weapon]
        ammo_type = weapon["ammo"]

        if self.magazines[self.weapon] <= 0:
            if self.ammo[ammo_type] > 0:
                self.begin_reload()
            else:
                self.set_message(f"Out of {ammo_type}.", 1.0)
                self.weapon_cooldown = 0.18
            return

        self.magazines[self.weapon] -= 1
        cooldown = weapon["cooldown"] * (0.55 if self.overdrive_timer > 0 else 1.0)
        self.weapon_cooldown = cooldown
        self.weapon_anim = cooldown
        self.muzzle_timer = 0.08
        self.sounds.play(self.weapon)

        pellets = weapon["pellets"]
        hit_anything = False
        boss_killed = None
        wall_hit = False
        wall_broken = False

        for _ in range(pellets):
            shot_angle = self.player_angle + random.uniform(-weapon["spread"], weapon["spread"])
            target = self.find_target_for_ray(shot_angle)
            if target is not None:
                damage = random.randint(*weapon["damage"])
                if self.quad_timer > 0:
                    damage *= 2
                target.hp -= damage
                target.hurt_timer = 0.13
                target.alerted = True
                target.state = "hurt"
                target.state_timer = 0.12
                hit_anything = True

                if target.hp <= 0 and not target.dead:
                    target.state = "dead"
                    target.death_time = 0.0
                    self.kills += 1
                    boss_types = ("boss", "summoner", "overseer", "nightmare")
                    base_points = 1500 if target.kind in boss_types else 100
                    self.score += int(base_points * self.score_multiplier)
                    self.sounds.play("enemy")
                    if target.kind in boss_types:
                        boss_killed = target.kind
                else:
                    self.score += int(10 * self.score_multiplier)
            else:
                wall = self.find_breakable_wall_for_ray(shot_angle)
                if wall is not None:
                    wall_hit = True
                    self.breakable_walls[wall] -= 1
                    if self.breakable_walls[wall] <= 0:
                        wall_broken = True
                        del self.breakable_walls[wall]
                        self.map_data[wall[1]][wall[0]] = "."

        if boss_killed:
            boss_name = {
                "boss": "HANGAR WARDEN",
                "summoner": "FOUNDRY SUMMONER",
                "overseer": "VOID OVERSEER",
                "nightmare": "NIGHTMARE SOVEREIGN",
            }[boss_killed]
            self.set_message(f"THE {boss_name} IS DEAD.", 3.0)
        elif wall_broken:
            self.set_message("BREAKABLE WALL DESTROYED.", 1.4)
            self.sounds.play("door")
        elif hit_anything:
            self.set_message("Hit.", 0.30)
        elif wall_hit:
            self.set_message("The wall is cracking!", 0.45)

    def find_target_for_ray(self, shot_angle):
        best = None
        best_dist = MAX_DEPTH

        for enemy in self.enemies:
            if enemy.dead:
                continue

            dx = enemy.x - self.player_x
            dy = enemy.y - self.player_y
            distance = math.hypot(dx, dy)
            angle = abs(normalize_angle(math.atan2(dy, dx) - shot_angle))
            body_radius = {
                "boss": 0.43,
                "summoner": 0.48,
                "overseer": 0.48,
                "nightmare": 0.72,
            }.get(enemy.kind, 0.28)
            body_width = body_radius / max(distance, 0.2)

            if angle < body_width and distance < best_dist:
                if self.line_of_sight(self.player_x, self.player_y, enemy.x, enemy.y):
                    best = enemy
                    best_dist = distance

        return best

    def find_breakable_wall_for_ray(self, shot_angle):
        """Trace a short weapon ray and return the first breakable wall hit."""
        ray_dx = math.cos(shot_angle)
        ray_dy = math.sin(shot_angle)
        for step in range(1, 181):
            distance = step * 0.05
            tx = int(self.player_x + ray_dx * distance)
            ty = int(self.player_y + ray_dy * distance)
            tile = self.tile_at(tx, ty)
            if tile == "B":
                return (tx, ty)
            if tile != ".":
                if tile in DOOR_TILES and not self.tile_blocks(tx, ty):
                    continue
                return None
        return None

    def damage_player(self, amount):
        if self.state != "playing":
            return
        if self.invincibility_timer > 0:
            return

        absorbed = min(self.armor, max(1, int(amount * 0.35)))
        self.armor -= absorbed
        self.health -= amount - absorbed
        self.damage_flash = 0.22
        self.face_hurt_timer = 0.55
        self.sounds.play("hurt")

        if self.health <= 0:
            self.health = 0
            self.cancel_reload()
            if self.has_revive:
                self.has_revive = False
                self.state = "reviving"
                self.revive_screen_timer = REVIVE_SCREEN_DURATION
                self.poison_timer = 0.0
                self.poison_tick = 0.0
            else:
                self.state = "dead"
            self.set_mouse_capture(False)

    def finish_revive(self):
        """Return the player at full health with brief, counted invincibility."""
        self.health = PLAYER_MAX_HEALTH
        self.state = "playing"
        self.invincibility_timer = REVIVE_INVINCIBILITY_DURATION
        self.damage_flash = 0.0
        self.face_hurt_timer = 0.0
        self.poison_timer = 0.0
        self.poison_tick = 0.0

        # Never revive inside a solid rift sphere that would prevent escape.
        for field in self.energy_fields:
            if math.hypot(self.player_x - field.x, self.player_y - field.y) < (
                field.radius + PLAYER_RADIUS + 0.15
            ):
                field.active = False
        self.energy_fields = [field for field in self.energy_fields if field.active]

        self.set_message("REVIVED - INVINCIBLE FOR 3 SECONDS!", 1.8)
        self.sounds.play("pickup")
        self.set_mouse_capture(True)

    def shield_blocks_from_angle(self, attacker_angle, durability_damage=1):
        """Resolve one attack arriving from an already-calculated direction."""
        if self.weapon != "shield" or not self.has_shield:
            return False

        relative = abs(normalize_angle(attacker_angle - self.player_angle))
        if relative > math.radians(75):
            return False

        self.shield_hits += max(1, durability_damage)
        self.shield_flash = 0.18
        self.sounds.play("switch")
        if self.shield_hits >= self.shield_max_durability:
            self.shield_hits = self.shield_max_durability
            self.has_shield = False
            self.select_weapon("shotgun" if self.has_shotgun else "pistol")
            self.set_message("THE SHIELD HAS BROKEN!", 2.0)
        else:
            remaining = self.shield_max_durability - self.shield_hits
            self.set_message(
                f"BULLET BLOCKED - SHIELD {remaining}/{self.shield_max_durability}",
                0.55,
            )
        return True

    def shield_blocks_bullet(self, attacker_x, attacker_y, durability_damage=1):
        """Return True when the raised shield faces a hitscan attacker."""
        attacker_angle = math.atan2(attacker_y - self.player_y, attacker_x - self.player_x)
        return self.shield_blocks_from_angle(attacker_angle, durability_damage)

    def shield_blocks_projectile(self, projectile, durability_damage=2):
        """Block using flight direction, even if a projectile crosses the player center."""
        attacker_angle = math.atan2(-projectile.dy, -projectile.dx)
        return self.shield_blocks_from_angle(attacker_angle, durability_damage)

    # ------------------------------------------------------------------
    # Enemies
    # ------------------------------------------------------------------

    @staticmethod
    def enemy_collision_radius(enemy):
        if enemy.kind in ("boss", "summoner", "overseer", "nightmare"):
            return 0.30
        return 0.18

    def clear_enemy_path(self, x1, y1, x2, y2, radius):
        """Check the full width of an enemy's route instead of a center ray."""
        distance = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(math.ceil(distance / 0.10)))
        can_stand = self.can_stand
        for index in range(1, steps + 1):
            amount = index / steps
            x = x1 + (x2 - x1) * amount
            y = y1 + (y2 - y1) * amount
            if not can_stand(x, y, radius):
                return False
        return True

    def find_enemy_path(self, enemy, radius):
        """Find a short tile-center route through open doors and around walls."""
        start = (int(enemy.x), int(enemy.y))
        goal = (int(self.player_x), int(self.player_y))
        if start == goal:
            return []

        frontier = [start]
        frontier_index = 0
        came_from = {start: None}
        can_stand = self.can_stand

        while frontier_index < len(frontier):
            current = frontier[frontier_index]
            frontier_index += 1
            if current == goal:
                break

            cx, cy = current
            neighbors = ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1))
            neighbors = sorted(
                neighbors,
                key=lambda point: abs(point[0] - goal[0]) + abs(point[1] - goal[1]),
            )
            for neighbor in neighbors:
                if neighbor in came_from:
                    continue
                nx, ny = neighbor
                if not can_stand(nx + 0.5, ny + 0.5, radius):
                    continue
                came_from[neighbor] = current
                frontier.append(neighbor)

        if goal not in came_from:
            return []

        tiles = []
        current = goal
        while current != start:
            tiles.append((current[0] + 0.5, current[1] + 0.5))
            current = came_from[current]
        tiles.reverse()
        return tiles

    def move_enemy_toward(self, enemy, target_x, target_y, speed, dt, radius):
        """Move toward a waypoint, trying both axes and both wall-slide directions."""
        dx = target_x - enemy.x
        dy = target_y - enemy.y
        distance = math.hypot(dx, dy)
        if distance <= 0.001:
            return False

        nx = dx / distance
        ny = dy / distance
        step = min(speed * dt, distance)
        move_x = nx * step
        move_y = ny * step

        candidates = [(move_x, move_y)]
        if abs(move_x) >= abs(move_y):
            candidates.extend(((move_x, 0.0), (0.0, move_y)))
        else:
            candidates.extend(((0.0, move_y), (move_x, 0.0)))
        candidates.extend(
            (
                (-ny * step, nx * step),
                (ny * step, -nx * step),
            )
        )

        for offset_x, offset_y in candidates:
            next_x = enemy.x + offset_x
            next_y = enemy.y + offset_y
            if self.can_stand(next_x, next_y, radius):
                enemy.x = next_x
                enemy.y = next_y
                return True
        return False

    def update_enemies(self, dt):
        pending_summons = []
        for enemy in self.enemies:
            enemy.anim_time += dt

            if enemy.dead:
                enemy.death_time += dt
                continue

            enemy.attack_cooldown = max(0.0, enemy.attack_cooldown - dt)
            enemy.special_cooldown = max(0.0, enemy.special_cooldown - dt)
            enemy.hurt_timer = max(0.0, enemy.hurt_timer - dt)
            enemy.state_timer = max(0.0, enemy.state_timer - dt)
            enemy.path_timer = max(0.0, enemy.path_timer - dt)

            dx = self.player_x - enemy.x
            dy = self.player_y - enemy.y
            distance = math.hypot(dx, dy)
            sight_range = MAX_DEPTH if enemy.kind in SHOOTING_ENEMY_TYPES else 10.5
            sees_player = (
                distance < sight_range
                and self.clear_enemy_shot(enemy.x, enemy.y, self.player_x, self.player_y)
            )
            gained_line_of_sight = sees_player and not enemy.saw_player_last_frame
            enemy.saw_player_last_frame = sees_player
            if gained_line_of_sight and enemy.kind in SHOOTING_ENEMY_TYPES:
                # Ranged enemies react quickly but still give the player a
                # brief warning window after first sight or reappearing. Bosses
                # keep the slightly longer, randomized tell; regular shooters
                # fire after a flat half-second.
                if enemy.kind in BOSS_ENEMY_TYPES:
                    enemy.attack_cooldown = random.uniform(0.5, 0.75)
                else:
                    enemy.attack_cooldown = 0.5

            newly_alerted = sees_player and not enemy.alerted
            if sees_player:
                enemy.alerted = True
                boss_names = {
                    "boss": "THE HANGAR WARDEN AWAKENS!",
                    "summoner": "THE FOUNDRY SUMMONER OPENS A RIFT!",
                    "overseer": "THE VOID OVERSEER SEES YOU!",
                    "nightmare": "THE NIGHTMARE SOVEREIGN DESCENDS!",
                }
                if newly_alerted and enemy.kind in boss_names:
                    self.set_message(boss_names[enemy.kind], 2.5)
                    self.sounds.play("enemy")

            if enemy.state == "hurt" and enemy.state_timer > 0:
                continue

            if not enemy.alerted:
                enemy.state = "idle"
                continue

            if enemy.kind == "grunt":
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.23
                    enemy.attack_cooldown = random.uniform(1.0, 1.5)
                    accuracy = clamp(0.86 - distance * 0.075, 0.24, 0.78)
                    if random.random() < accuracy:
                        if not self.shield_blocks_bullet(enemy.x, enemy.y):
                            self.damage_player(random.randint(6, 11))
                    continue
                move_speed = 1.08
                desired_distance = 3.6
            elif enemy.kind == "fiend":
                if sees_player and distance < 0.82 and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.30
                    enemy.attack_cooldown = 0.85
                    self.damage_player(random.randint(10, 16))
                    continue
                move_speed = 1.50
                desired_distance = 0.65
            elif enemy.kind == "stalker":
                if distance < 0.72 and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.22
                    enemy.attack_cooldown = 0.52
                    self.damage_player(random.randint(7, 11))
                    continue
                move_speed = 2.52
                desired_distance = 0.55
            elif enemy.kind == "turret":
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.18
                    enemy.attack_cooldown = random.uniform(0.38, 0.52)
                    if random.random() < 0.72 and not self.shield_blocks_bullet(enemy.x, enemy.y):
                        self.damage_player(random.randint(5, 8))
                move_speed = 0.0
                desired_distance = 99.0
            elif enemy.kind == "spitter":
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.30
                    enemy.attack_cooldown = random.uniform(1.15, 1.45)
                    if random.random() < 0.78:
                        if not self.shield_blocks_bullet(enemy.x, enemy.y):
                            self.damage_player(random.randint(4, 6))
                            self.poison_timer = max(self.poison_timer, 3.5)
                    continue
                move_speed = 0.93
                desired_distance = 4.2
            elif enemy.kind == "charger":
                if distance < 0.90 and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.34
                    enemy.attack_cooldown = 1.05
                    self.damage_player(random.randint(15, 22))
                    continue
                move_speed = 3.075
                desired_distance = 0.65
            elif enemy.kind == "medic":
                healable_kinds = {
                    "grunt", "fiend", "stalker", "turret",
                    "spitter", "charger", "medic",
                }
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.attack_cooldown = 1.25
                    if random.random() < 0.66 and not self.shield_blocks_bullet(enemy.x, enemy.y):
                        self.damage_player(random.randint(5, 7))
                    continue
                wounded = next(
                    (
                        ally for ally in self.enemies
                        if ally is not enemy and not ally.dead and ally.kind in healable_kinds
                        and ally.hp < ally.max_hp
                        and math.hypot(ally.x - enemy.x, ally.y - enemy.y) < 4.2
                    ),
                    None,
                )
                if wounded is not None and enemy.attack_cooldown <= 0:
                    wounded.hp = min(wounded.max_hp, wounded.hp + 2)
                    enemy.state = "attack"
                    enemy.attack_cooldown = 1.55
                    continue
                move_speed = 1.05
                desired_distance = 4.0
            elif enemy.kind == "boss":
                # The Warden fires while advancing and crushes players who get close.
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.32
                    if distance < 1.15:
                        self.damage_player(random.randint(18, 27))
                        enemy.attack_cooldown = random.uniform(0.62, 0.82)
                    else:
                        accuracy = clamp(0.94 - distance * 0.035, 0.62, 0.90)
                        if random.random() < accuracy:
                            for angle_offset in (-0.18, 0.0, 0.18):
                                self.spawn_boss_projectile(
                                    enemy,
                                    "warden_bolt",
                                    random.randint(10, 18),
                                    angle_offset=angle_offset,
                                )
                        enemy.attack_cooldown = random.uniform(0.90, 1.12)
                    continue
                move_speed = 1.68
                desired_distance = 0.82
            elif enemy.kind == "summoner":
                if sees_player and distance < 1.08 and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.34
                    enemy.attack_cooldown = random.uniform(0.72, 0.92)
                    self.damage_player(random.randint(14, 21))
                    continue
                if sees_player and enemy.special_cooldown <= 0 and enemy.summons_made < 8:
                    enemy.state = "attack"
                    enemy.state_timer = 0.55
                    enemy.special_cooldown = 4.2
                    summon_kinds = ("stalker", "spitter", "charger", "medic")
                    summon_hp = {"stalker": 5, "spitter": 7, "charger": 10, "medic": 8}
                    for angle_offset in (-0.95, 0.95):
                        angle = math.atan2(dy, dx) + angle_offset
                        spawn_x = enemy.x + math.cos(angle) * 0.95
                        spawn_y = enemy.y + math.sin(angle) * 0.95
                        if self.can_stand(spawn_x, spawn_y, 0.18):
                            kind_index = enemy.summons_made % len(summon_kinds)
                            summoned_kind = summon_kinds[kind_index]
                            summoned = Enemy(
                                spawn_x,
                                spawn_y,
                                summoned_kind,
                                summon_hp[summoned_kind]
                                + self.quadrant_health_bonus(spawn_x, spawn_y),
                            )
                            summoned.alerted = True
                            pending_summons.append(summoned)
                            enemy.summons_made += 1
                    self.set_message("THE SUMMONER TEARS OPEN A RIFT!", 1.5)
                    self.sounds.play("enemy")
                    continue
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.42
                    enemy.pattern_index += 1
                    placed_field = False
                    if enemy.pattern_index % 2 == 1:
                        placed_field = self.spawn_energy_field(enemy)
                    if placed_field:
                        enemy.attack_cooldown = random.uniform(2.10, 2.45)
                        self.set_message("RIFT SPHERE FORMING - MOVE!", 1.1)
                    else:
                        for angle_offset in (-0.12, 0.12):
                            self.spawn_boss_projectile(
                                enemy,
                                "rift_bolt",
                                random.randint(7, 12),
                                angle_offset=angle_offset,
                            )
                        enemy.attack_cooldown = random.uniform(1.35, 1.65)
                    continue
                move_speed = 0.99
                desired_distance = 0.84
            elif enemy.kind == "overseer":
                if sees_player and distance < 1.12 and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.32
                    enemy.attack_cooldown = random.uniform(0.68, 0.86)
                    self.damage_player(random.randint(17, 24))
                    continue
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.55
                    enemy.pattern_index += 1
                    claw_attack = enemy.pattern_index % 2 == 0
                    if claw_attack and self.spawn_claw_line(enemy) > 0:
                        enemy.state_timer = 0.70
                        enemy.attack_cooldown = random.uniform(2.05, 2.35)
                        self.set_message("VOID CLAWS - STEP ASIDE!", 1.2)
                        self.sounds.play("enemy")
                    else:
                        for index, angle_offset in enumerate((-0.28, -0.14, 0.0, 0.14, 0.28)):
                            self.spawn_boss_projectile(
                                enemy,
                                "overseer_orb",
                                random.randint(8, 14),
                                effect="overseer",
                                angle_offset=angle_offset,
                                delay=index * 0.10,
                            )
                        enemy.attack_cooldown = random.uniform(1.45, 1.75)
                    continue
                move_speed = 1.38
                desired_distance = 0.86
            else:  # Nightmare Sovereign
                if sees_player and enemy.attack_cooldown <= 0:
                    enemy.state = "attack"
                    enemy.state_timer = 0.32
                    if distance < 1.8:
                        self.damage_player(random.randint(25, 36))
                        enemy.attack_cooldown = random.uniform(0.62, 0.82)
                        continue

                    cycle = enemy.pattern_index % 3
                    enemy.pattern_index += 1
                    if cycle == 0:
                        self.spawn_radial_burst(
                            enemy,
                            "nightmare_bolt",
                            (11, 17),
                            12,
                        )
                        enemy.attack_cooldown = random.uniform(1.00, 1.20)
                    elif cycle == 1:
                        for angle_offset in (-0.36, -0.18, 0.0, 0.18, 0.36):
                            self.spawn_boss_projectile(
                                enemy,
                                "poison_orb",
                                random.randint(9, 15),
                                effect="poison",
                                angle_offset=angle_offset,
                            )
                        enemy.attack_cooldown = random.uniform(1.10, 1.30)
                    else:
                        for index, angle_offset in enumerate((-0.15, 0.0, 0.15)):
                            self.spawn_boss_projectile(
                                enemy,
                                "drain_orb",
                                random.randint(8, 13),
                                effect="drain",
                                angle_offset=angle_offset,
                                delay=index * 0.08,
                            )
                        enemy.attack_cooldown = random.uniform(0.90, 1.10)
                    continue
                move_speed = 1.77
                desired_distance = 0.92

            # Ranged enemies must keep repositioning if a wall or doorway
            # blocks their shot, even when the player is already within their
            # preferred combat distance. This prevents safe corner exploits.
            if move_speed > 0 and (not sees_player or distance > desired_distance):
                enemy.state = "walk"
                enemy_radius = self.enemy_collision_radius(enemy)
                target_x, target_y = self.player_x, self.player_y

                direct_route = self.clear_enemy_path(
                    enemy.x,
                    enemy.y,
                    self.player_x,
                    self.player_y,
                    enemy_radius,
                )
                if direct_route:
                    # Open rooms still use natural direct pursuit.
                    enemy.path.clear()
                else:
                    # Recalculate often enough to notice opening doors and
                    # destroyed walls without running a search every frame.
                    if enemy.path_timer <= 0:
                        enemy.path = self.find_enemy_path(enemy, enemy_radius)
                        enemy.path_timer = 0.40

                    while enemy.path and math.hypot(
                        enemy.path[0][0] - enemy.x,
                        enemy.path[0][1] - enemy.y,
                    ) < 0.16:
                        enemy.path.pop(0)

                    if enemy.path:
                        target_x, target_y = enemy.path[0]
                    else:
                        # Centering frees enemies already pressed against a
                        # doorway edge while they wait for a route to open.
                        target_x = int(enemy.x) + 0.5
                        target_y = int(enemy.y) + 0.5

                if enemy.kind == "stalker" and direct_route:
                    chase_x = target_x - enemy.x
                    chase_y = target_y - enemy.y
                    chase_distance = max(0.001, math.hypot(chase_x, chase_y))
                    chase_x /= chase_distance
                    chase_y /= chase_distance
                    weave = math.sin(enemy.anim_time * 7.0) * 0.30
                    target_x = enemy.x + chase_x - chase_y * weave
                    target_y = enemy.y + chase_y + chase_x * weave

                moved = self.move_enemy_toward(
                    enemy,
                    target_x,
                    target_y,
                    move_speed,
                    dt,
                    enemy_radius,
                )
                if moved:
                    enemy.stuck_timer = 0.0
                else:
                    enemy.stuck_timer += dt
                    if enemy.stuck_timer >= 0.25:
                        enemy.path.clear()
                        enemy.path_timer = 0.0
                        enemy.stuck_timer = 0.0

        if pending_summons:
            self.enemies.extend(pending_summons)
            self.total_kills += len(pending_summons)

    # ------------------------------------------------------------------
    # Pickups and doors
    # ------------------------------------------------------------------

    def update_pickups(self):
        for pickup in self.pickups:
            if not pickup.active:
                continue
            if math.hypot(pickup.x - self.player_x, pickup.y - self.player_y) > 0.50:
                continue

            pickup.active = False
            self.sounds.play("pickup")

            if pickup.kind == "bullets":
                self.ammo["bullets"] += 30
                self.set_message("Bullets: +30 reserve ammo.", 1.1)

            elif pickup.kind == "shells":
                self.ammo["shells"] += 10
                self.set_message("Shotgun shells: +10 reserve ammo.", 1.1)

            elif pickup.kind == "medkit":
                gained = max(0, min(50, PLAYER_MAX_HEALTH - self.health))
                self.health += gained
                self.set_message(f"Medkit: +{gained} health.", 1.1)

            elif pickup.kind == "armor":
                gained = min(75, 100 - self.armor)
                self.armor += gained
                self.set_message(f"Security armor: +{gained}.", 1.1)

            elif pickup.kind == "redkey":
                self.has_red_key = True
                self.set_message("RED KEYCARD ACQUIRED.", 2.0)

            elif pickup.kind == "bluekey":
                self.has_blue_key = True
                self.set_message("BLUE KEYCARD ACQUIRED.", 2.0)

            elif pickup.kind == "greenkey":
                self.has_green_key = True
                self.set_message("GREEN KEYCARD ACQUIRED.", 2.0)

            elif pickup.kind == "shotgun":
                self.has_shotgun = True
                # The original 10-shell weapon grant is rounded up after its
                # 1.25x increase so ammunition always remains a whole number.
                self.ammo["shells"] += 13
                self.magazines["shotgun"] = 0
                self.transfer_ammo_to_magazine("shotgun")
                self.select_weapon("shotgun")
                self.set_message("Combat shotgun acquired: 8-shell magazine.", 1.7)

            elif pickup.kind == "shield":
                self.has_shield = True
                self.shield_hits = 0
                self.select_weapon("shield")
                self.set_message("Riot shield acquired. Press 3 to raise it.", 2.2)

            elif pickup.kind == "sprayer":
                self.has_sprayer = True
                self.ammo["bullets"] += 100
                self.magazines["sprayer"] = 0
                self.transfer_ammo_to_magazine("sprayer")
                self.select_weapon("sprayer")
                self.set_message("Bullet sprayer acquired. Hold FIRE and press 4 to select.", 2.5)

            elif pickup.kind == "ammobox":
                self.ammo["bullets"] += 100
                self.ammo["shells"] += 15
                self.set_message("Ammo box: +100 bullets, +15 shells.", 1.5)

            elif pickup.kind == "megahealth":
                gained = min(75, PLAYER_MAX_HEALTH - self.health)
                self.health += gained
                self.set_message(f"MEGA HEALTH: +{gained}.", 1.7)

            elif pickup.kind == "revive":
                self.has_revive = True
                self.set_message("REVIVE ITEM COLLECTED.", 2.2)

            elif pickup.kind == "overdrive":
                self.overdrive_timer = 20.0
                self.set_message("OVERDRIVE: rapid fire for 20 seconds!", 2.0)

            elif pickup.kind == "quad":
                self.quad_timer = 20.0
                self.set_message("QUAD DAMAGE for 20 seconds!", 2.0)

            elif pickup.kind == "shieldrepair":
                self.has_shield = True
                self.shield_hits = max(0, self.shield_hits - SHIELD_REPAIR_AMOUNT)
                remaining = self.shield_max_durability - self.shield_hits
                self.set_message(
                    f"Shield repaired: {remaining}/{self.shield_max_durability}.",
                    1.5,
                )

    def set_message(self, text, duration):
        self.message = text
        self.message_timer = duration

    # ------------------------------------------------------------------
    # Raycasting
    # ------------------------------------------------------------------

    def cast_scene(self):
        self.draw_floor_and_ceiling()
        zbuffer = [MAX_DEPTH] * INTERNAL_W

        for screen_x in range(INTERNAL_W):
            camera = (screen_x / INTERNAL_W - 0.5) * FOV
            ray_angle = self.player_angle + camera
            ray_dx = math.cos(ray_angle)
            ray_dy = math.sin(ray_angle)

            map_x = int(self.player_x)
            map_y = int(self.player_y)

            delta_x = abs(1.0 / ray_dx) if abs(ray_dx) > 1e-9 else 1e30
            delta_y = abs(1.0 / ray_dy) if abs(ray_dy) > 1e-9 else 1e30

            if ray_dx < 0:
                step_x = -1
                side_x = (self.player_x - map_x) * delta_x
            else:
                step_x = 1
                side_x = (map_x + 1.0 - self.player_x) * delta_x

            if ray_dy < 0:
                step_y = -1
                side_y = (self.player_y - map_y) * delta_y
            else:
                step_y = 1
                side_y = (map_y + 1.0 - self.player_y) * delta_y

            side = 0
            tile = "1"

            for _ in range(64):
                if side_x < side_y:
                    side_x += delta_x
                    map_x += step_x
                    side = 0
                else:
                    side_y += delta_y
                    map_y += step_y
                    side = 1

                if map_x < 0 or map_y < 0 or map_x >= self.map_w or map_y >= self.map_h:
                    tile = "1"
                    break

                tile = self.map_data[map_y][map_x]
                if tile == ".":
                    continue
                if tile in DOOR_TILES and self.doors[(map_x, map_y)].openness >= 0.88:
                    continue
                break

            if side == 0:
                distance = (map_x - self.player_x + (1 - step_x) / 2) / max(abs(ray_dx), 1e-9)
                wall_hit = self.player_y + distance * ray_dy
            else:
                distance = (map_y - self.player_y + (1 - step_y) / 2) / max(abs(ray_dy), 1e-9)
                wall_hit = self.player_x + distance * ray_dx

            distance = abs(distance)
            corrected = max(0.001, distance * math.cos(camera))
            zbuffer[screen_x] = corrected

            line_height = max(1, int(VIEW_H / corrected))
            draw_start = VIEW_H // 2 - line_height // 2

            door_lift = 0.0
            if tile in DOOR_TILES:
                door_lift = self.doors[(map_x, map_y)].openness
                draw_start -= int(line_height * door_lift)

            tex_x = int((wall_hit % 1.0) * TEXTURE_SIZE)
            if (side == 0 and ray_dx > 0) or (side == 1 and ray_dy < 0):
                tex_x = TEXTURE_SIZE - tex_x - 1

            texture = self.assets.textures.get(tile, self.assets.textures["1"])
            shade = clamp(1.10 - corrected / 14.0, 0.24, 1.0)
            if side == 1:
                shade *= 0.72
            shade_byte = int(255 * shade)
            column_key = (id(texture), tex_x, line_height, shade_byte)
            scaled = self._wall_column_cache.pop(column_key, None)
            if scaled is None:
                column = texture.subsurface((tex_x, 0, 1, TEXTURE_SIZE)).copy()
                column.fill(
                    (shade_byte, shade_byte, shade_byte),
                    special_flags=pygame.BLEND_RGB_MULT,
                )
                scaled = pygame.transform.scale(column, (1, line_height))
                if len(self._wall_column_cache) >= 4096:
                    self._wall_column_cache.popitem(last=False)
            self._wall_column_cache[column_key] = scaled
            self.canvas.blit(scaled, (screen_x, draw_start))

        return zbuffer

    def draw_floor_and_ceiling(self):
        self.canvas.fill((23, 25, 33), (0, 0, INTERNAL_W, VIEW_H // 2))

        horizon = VIEW_H // 2
        for y in range(horizon):
            t = y / max(1, horizon - 1)
            color = (
                int(18 + 22 * t),
                int(20 + 20 * t),
                int(28 + 17 * t),
            )
            pygame.draw.line(self.canvas, color, (0, y), (INTERNAL_W, y))

        for y in range(horizon, VIEW_H):
            t = (y - horizon) / max(1, VIEW_H - horizon)
            color = (
                int(48 - 22 * t),
                int(42 - 21 * t),
                int(38 - 20 * t),
            )
            pygame.draw.line(self.canvas, color, (0, y), (INTERNAL_W, y))

        # Horizontal floor bands imply texture while remaining fast.
        for y in range(horizon + 8, VIEW_H, 9):
            shade = max(14, 38 - (y - horizon) // 3)
            pygame.draw.line(self.canvas, (shade, shade - 3, shade - 6), (0, y), (INTERNAL_W, y))

    # ------------------------------------------------------------------
    # Sprite projection
    # ------------------------------------------------------------------

    def project(self, world_x, world_y):
        dx = world_x - self.player_x
        dy = world_y - self.player_y
        distance = math.hypot(dx, dy)
        relative = normalize_angle(math.atan2(dy, dx) - self.player_angle)

        if abs(relative) > HALF_FOV + 0.40 or distance < 0.05:
            return None

        corrected = distance * math.cos(relative)
        if corrected <= 0.02:
            return None

        center_x = int((0.5 + relative / FOV) * INTERNAL_W)
        height = int(VIEW_H / corrected)
        return center_x, height, corrected, distance

    def draw_sprite_occluded(self, sprite, center_x, bottom_y, depth, zbuffer):
        x0 = center_x - sprite.get_width() // 2
        y0 = bottom_y - sprite.get_height()
        left = max(0, x0)
        right = min(INTERNAL_W, x0 + sprite.get_width())

        for x in range(left, right):
            if depth < zbuffer[x] + 0.06:
                source_x = x - x0
                self.canvas.blit(sprite, (x, y0), (source_x, 0, 1, sprite.get_height()))

    def draw_pickup_aura(self, pickup, center_x, bottom_y, depth, size, zbuffer):
        """Draw a strong pulsing aura around a pickup without shining through walls."""
        color = PICKUP_GLOW_COLORS.get(pickup.kind, DEFAULT_PICKUP_GLOW)
        phase = self.elapsed * 4.2 + pickup.x * 0.37 + pickup.y * 0.23
        pulse = 0.5 + 0.5 * math.sin(phase)
        aura_size = max(10, int(size * (1.70 + pulse * 0.22)))
        circle_alpha = 125 + int(pulse * 55)
        ellipse_alpha = 155 + int(pulse * 70)
        aura_key = (color, aura_size, circle_alpha, ellipse_alpha)
        aura = self._pickup_aura_cache.pop(aura_key, None)
        if aura is None:
            aura = pygame.Surface((aura_size, aura_size), pygame.SRCALPHA)
            center = (aura_size // 2, aura_size // 2)

            # Layered translucent discs read as a glow even with
            # nearest-neighbor scaling, and the bright ellipse anchors the
            # item to the floor.
            for radius_scale, alpha in ((0.48, 28), (0.37, 48), (0.25, 78)):
                radius = max(2, int(aura_size * radius_scale))
                pygame.draw.circle(aura, (*color, alpha), center, radius)
            pygame.draw.circle(
                aura,
                (*color, circle_alpha),
                center,
                max(2, int(aura_size * 0.43)),
                1,
            )
            ring_height = max(2, aura_size // 7)
            pygame.draw.ellipse(
                aura,
                (*color, ellipse_alpha),
                (2, aura_size - ring_height - 2, aura_size - 4, ring_height),
                1,
            )
            if len(self._pickup_aura_cache) >= 192:
                self._pickup_aura_cache.popitem(last=False)
        self._pickup_aura_cache[aura_key] = aura

        # Shift the larger aura down slightly so its center aligns with the
        # pickup sprite while leaving a visible pool of light on the floor.
        aura_bottom = bottom_y + (aura_size - size) // 2
        self.draw_sprite_occluded(aura, center_x, aura_bottom, depth, zbuffer)

    def enemy_frame(self, enemy):
        if enemy.dead:
            frame = min(3, int(enemy.death_time / 0.13))
            return self.assets.enemy_frames[enemy.kind]["dead"][frame]

        if enemy.hurt_timer > 0:
            return self.assets.enemy_frames[enemy.kind]["hurt"][0]

        if enemy.state == "attack":
            frame = int(enemy.anim_time * 9) % 2
            return self.assets.enemy_frames[enemy.kind]["attack"][frame]

        frame = int(enemy.anim_time * 5) % 2
        return self.assets.enemy_frames[enemy.kind]["walk"][frame]

    def claw_strike_frame(self, claw):
        """Create the warning sigil or raised spectral talons for one strike."""
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        if claw.delay > 0:
            pulse = 0.5 + 0.5 * math.sin(self.elapsed * 16.0 + claw.x + claw.y)
            alpha = 115 + int(pulse * 90)
            pygame.draw.ellipse(surface, (70, 205, 255, alpha), (8, 47, 48, 11), 2)
            pygame.draw.ellipse(surface, (198, 96, 255, alpha), (17, 50, 30, 6), 1)
            pygame.draw.line(surface, (225, 190, 255, alpha), (20, 55), (44, 50), 1)
            return surface

        extension = clamp(claw.age / CLAW_REVEAL_TIME, 0.0, 1.0)
        claw_height = max(4, int(45 * extension))
        base_y = 57
        pygame.draw.ellipse(surface, (24, 4, 38, 180), (7, 49, 50, 12))
        pygame.draw.ellipse(surface, (105, 36, 145, 210), (11, 51, 42, 8), 2)
        for base_x, lean in ((18, -7), (32, 0), (46, 7)):
            tip_x = base_x + lean
            tip_y = base_y - claw_height
            talon = (
                (base_x - 6, base_y),
                (tip_x - 2, tip_y + 7),
                (tip_x, tip_y),
                (tip_x + 3, tip_y + 8),
                (base_x + 6, base_y),
            )
            pygame.draw.polygon(surface, (63, 187, 225, 235), talon)
            pygame.draw.lines(surface, (220, 153, 255, 255), False, talon, 2)
        return surface

    def scale_sprite_cached(self, source, width, height):
        """Return an identical scaled sprite while avoiding repeat transforms."""
        key = (id(source), width, height)
        sprite = self._scaled_sprite_cache.pop(key, None)
        if sprite is None:
            sprite = pygame.transform.scale(source, (width, height))
            if len(self._scaled_sprite_cache) >= 2048:
                self._scaled_sprite_cache.popitem(last=False)
        self._scaled_sprite_cache[key] = sprite
        return sprite

    def draw_sprites(self, zbuffer):
        entries = []

        for enemy in self.enemies:
            projection = self.project(enemy.x, enemy.y)
            if projection:
                entries.append(("enemy", enemy, projection))

        for pickup in self.pickups:
            if pickup.active:
                projection = self.project(pickup.x, pickup.y)
                if projection:
                    entries.append(("pickup", pickup, projection))

        for switch in self.switches:
            projection = self.project(switch.x, switch.y)
            if projection:
                entries.append(("switch", switch, projection))

        for projectile in self.projectiles:
            if projectile.active and projectile.delay <= 0:
                projection = self.project(projectile.x, projectile.y)
                if projection:
                    entries.append(("projectile", projectile, projection))

        for field in self.energy_fields:
            if field.active:
                projection = self.project(field.x, field.y)
                if projection:
                    entries.append(("energy_field", field, projection))

        for claw in self.claw_strikes:
            if claw.active:
                projection = self.project(claw.x, claw.y)
                if projection:
                    entries.append(("claw_strike", claw, projection))

        projection = self.project(self.exit_x, self.exit_y)
        if projection:
            entries.append(("exit", None, projection))

        entries.sort(key=lambda entry: entry[2][2], reverse=True)

        for kind, obj, projection in entries:
            center_x, height, depth, _ = projection
            bottom = VIEW_H // 2 + height // 2

            if kind == "enemy":
                source = self.enemy_frame(obj)
                scale_factor = {
                    "boss": 1.28,
                    "summoner": 1.42,
                    "overseer": 1.38,
                    "nightmare": 2.05,
                }.get(obj.kind, 0.90)
                sprite_h = clamp(int(height * scale_factor), 5, VIEW_H * 2)
                sprite_w = max(3, int(sprite_h * source.get_width() / source.get_height()))
                sprite = self.scale_sprite_cached(source, sprite_w, sprite_h)
                self.draw_sprite_occluded(sprite, center_x, bottom, depth, zbuffer)

            elif kind == "pickup":
                source = self.assets.pickup_frames[obj.kind]
                size = clamp(int(height * 0.34), 4, 55)
                sprite = self.scale_sprite_cached(source, size, size)
                self.draw_pickup_aura(obj, center_x, bottom, depth, size, zbuffer)
                self.draw_sprite_occluded(sprite, center_x, bottom, depth, zbuffer)

            elif kind == "switch":
                source = self.assets.pickup_frames[obj.kind]
                if obj.kind == "final_teleporter":
                    pulse = 1.0 + math.sin(self.elapsed * 5.5) * 0.08
                    size = clamp(int(height * 0.68 * pulse), 10, 88)
                    self.draw_pickup_aura(
                        obj,
                        center_x,
                        bottom,
                        depth,
                        size,
                        zbuffer,
                    )
                else:
                    size = clamp(int(height * 0.42), 5, 64)
                sprite = self.scale_sprite_cached(source, size, size)
                if obj.activated:
                    sprite = sprite.copy()
                    sprite.set_alpha(145)
                self.draw_sprite_occluded(sprite, center_x, bottom, depth, zbuffer)

            elif kind == "projectile":
                source = self.assets.projectile_frames[obj.kind]
                size = clamp(int(height * 0.18), 5, 38)
                sprite = self.scale_sprite_cached(source, size, size)
                projectile_bottom = VIEW_H // 2 + size // 2
                self.draw_sprite_occluded(
                    sprite,
                    center_x,
                    projectile_bottom,
                    depth,
                    zbuffer,
                )

            elif kind == "energy_field":
                source = self.assets.projectile_frames["rift_bolt"]
                pulse = 1.0 + math.sin(obj.pulse * 8.0) * 0.16
                size = clamp(int(height * 0.38 * pulse), 8, 72)
                sprite = self.scale_sprite_cached(source, size, size).copy()
                sprite.set_alpha(105 if obj.arming_time > 0 else 235)
                self.draw_sprite_occluded(sprite, center_x, bottom, depth, zbuffer)

            elif kind == "claw_strike":
                source = self.claw_strike_frame(obj)
                size = clamp(int(height * 0.46), 9, 82)
                sprite = pygame.transform.scale(source, (size, size))
                self.draw_sprite_occluded(sprite, center_x, bottom, depth, zbuffer)

            else:
                frame = int(self.elapsed * 7) % len(self.assets.exit_frames)
                source = self.assets.exit_frames[frame]
                sprite_h = clamp(int(height * 0.72), 8, 110)
                sprite_w = max(5, int(sprite_h * source.get_width() / source.get_height()))
                sprite = self.scale_sprite_cached(source, sprite_w, sprite_h)
                self.draw_sprite_occluded(sprite, center_x, bottom, depth, zbuffer)

    # ------------------------------------------------------------------
    # Weapon and HUD
    # ------------------------------------------------------------------

    def draw_weapon(self):
        bob_x = int(math.sin(self.bob_time * 0.50) * 3) if self.moving else 0
        bob_y = int(abs(math.sin(self.bob_time)) * 3) if self.moving else 0

        # A compact lower-and-sway motion makes the timed reload visible while
        # keeping the hand-drawn weapon art simple and readable.
        if self.reloading_weapon == self.weapon and self.reload_duration > 0:
            progress = clamp(1.0 - self.reload_timer / self.reload_duration, 0.0, 1.0)
            bob_y += int(math.sin(progress * math.pi) * 34)
            bob_x += int(math.sin(progress * math.tau) * 5)

        if self.weapon == "shield":
            x = INTERNAL_W // 2 - 100 + bob_x
            y = VIEW_H - 88 + bob_y
            edge = (115, 245, 245) if self.shield_flash > 0 else (103, 118, 137)
            face = (103, 120, 136) if self.shield_flash > 0 else (50, 57, 70)
            outer = [
                (x + 18, y),
                (x + 182, y),
                (x + 198, y + 18),
                (x + 180, y + 82),
                (x + 100, y + 91),
                (x + 20, y + 82),
                (x + 2, y + 18),
            ]
            inner = [
                (x + 24, y + 7),
                (x + 176, y + 7),
                (x + 189, y + 22),
                (x + 172, y + 75),
                (x + 100, y + 83),
                (x + 28, y + 75),
                (x + 11, y + 22),
            ]
            pygame.draw.polygon(self.canvas, (24, 28, 35), outer)
            pygame.draw.polygon(self.canvas, edge, outer, 3)
            pygame.draw.polygon(self.canvas, face, inner)
            pygame.draw.line(self.canvas, (24, 30, 39), (x + 100, y + 8), (x + 100, y + 82), 3)
            pygame.draw.rect(self.canvas, (13, 18, 24), (x + 63, y + 18, 74, 13))
            pygame.draw.rect(self.canvas, (89, 195, 198), (x + 68, y + 21, 64, 6), 1)
            pygame.draw.circle(self.canvas, (211, 181, 74), (x + 100, y + 52), 8, 2)
            cracks = (
                (11, (100, 52), (82, 38)), (20, (100, 52), (119, 34)),
                (31, (82, 38), (67, 24)), (40, (119, 34), (139, 22)),
                (51, (100, 52), (78, 69)), (60, (100, 52), (126, 70)),
                (71, (78, 69), (54, 77)), (80, (126, 70), (153, 76)),
                (91, (67, 24), (48, 10)), (97, (139, 22), (164, 8)),
            )
            for threshold, start, end in cracks:
                damage_threshold = math.ceil(
                    self.shield_max_durability * threshold / 100
                )
                if self.shield_hits >= damage_threshold:
                    pygame.draw.line(
                        self.canvas,
                        (13, 17, 22),
                        (x + start[0], y + start[1]),
                        (x + end[0], y + end[1]),
                        2,
                    )
            return

        recoil = 0.0
        if self.weapon_anim > 0:
            total = WEAPONS[self.weapon]["cooldown"]
            progress = 1.0 - self.weapon_anim / total
            recoil = math.sin(progress * math.pi) * 10

        if self.weapon == "pistol":
            x = INTERNAL_W // 2 - 19 + bob_x
            y = VIEW_H - 48 + bob_y + int(recoil)

            pygame.draw.rect(self.canvas, (117, 74, 47), (x + 1, y + 31, 10, 16))
            pygame.draw.rect(self.canvas, (117, 74, 47), (x + 27, y + 31, 10, 16))
            pygame.draw.rect(self.canvas, (40, 41, 46), (x + 8, y + 13, 22, 35))
            pygame.draw.rect(self.canvas, (78, 81, 88), (x + 11, y + 4, 16, 26))
            pygame.draw.rect(self.canvas, (20, 21, 24), (x + 14, y, 10, 9))
            pygame.draw.line(self.canvas, (122, 124, 129), (x + 13, y + 9), (x + 25, y + 9), 2)
            muzzle_x, muzzle_y = x + 19, y - 1

        elif self.weapon == "shotgun":
            x = INTERNAL_W // 2 - 48 + bob_x
            y = VIEW_H - 52 + bob_y + int(recoil)

            pygame.draw.rect(self.canvas, (122, 77, 48), (x + 3, y + 35, 20, 17))
            pygame.draw.rect(self.canvas, (122, 77, 48), (x + 73, y + 35, 20, 17))
            pygame.draw.rect(self.canvas, (42, 43, 46), (x + 17, y + 19, 62, 28))
            pygame.draw.rect(self.canvas, (88, 91, 94), (x + 29, y + 7, 38, 27))
            pygame.draw.rect(self.canvas, (20, 21, 23), (x + 35, y, 26, 13))
            pygame.draw.rect(self.canvas, (110, 68, 39), (x + 31, y + 32, 34, 12))
            pygame.draw.line(self.canvas, (143, 146, 146), (x + 33, y + 9), (x + 63, y + 9), 2)
            muzzle_x, muzzle_y = x + 48, y - 1

        else:  # Automatic bullet sprayer
            x = INTERNAL_W // 2 - 42 + bob_x
            y = VIEW_H - 48 + bob_y + int(recoil)
            pygame.draw.rect(self.canvas, (47, 51, 59), (x + 12, y + 14, 60, 30))
            pygame.draw.rect(self.canvas, (100, 114, 124), (x + 20, y + 7, 44, 19))
            pygame.draw.rect(self.canvas, (24, 27, 32), (x + 28, y, 28, 13))
            pygame.draw.rect(self.canvas, (64, 132, 145), (x + 27, y + 29, 30, 15))
            pygame.draw.rect(self.canvas, (117, 75, 43), (x + 3, y + 34, 18, 14))
            pygame.draw.rect(self.canvas, (117, 75, 43), (x + 63, y + 34, 18, 14))
            pygame.draw.rect(self.canvas, (21, 23, 27), (x + 34, y - 5, 16, 9))
            pygame.draw.line(self.canvas, (224, 186, 72), (x + 24, y + 10), (x + 60, y + 10), 2)
            muzzle_x, muzzle_y = x + 42, y - 6

        if self.muzzle_timer > 0:
            points = [
                (muzzle_x, muzzle_y - 22),
                (muzzle_x - 5, muzzle_y - 8),
                (muzzle_x - 18, muzzle_y - 12),
                (muzzle_x - 9, muzzle_y),
                (muzzle_x - 16, muzzle_y + 10),
                (muzzle_x, muzzle_y + 5),
                (muzzle_x + 16, muzzle_y + 10),
                (muzzle_x + 9, muzzle_y),
                (muzzle_x + 18, muzzle_y - 12),
                (muzzle_x + 5, muzzle_y - 8),
            ]
            pygame.draw.polygon(self.canvas, (252, 185, 45), points)
            pygame.draw.circle(self.canvas, (255, 241, 172), (muzzle_x, muzzle_y - 4), 5)

    def draw_face(self):
        x, y = INTERNAL_W // 2 - 13, VIEW_H + 4
        hurt = self.face_hurt_timer > 0

        skin = (194, 137, 99)
        pygame.draw.rect(self.canvas, (41, 23, 20), (x + 4, y, 18, 5))
        pygame.draw.rect(self.canvas, skin, (x + 2, y + 4, 22, 22))
        pygame.draw.rect(self.canvas, (91, 47, 35), (x, y + 8, 4, 12))
        pygame.draw.rect(self.canvas, (91, 47, 35), (x + 22, y + 8, 4, 12))

        eye_y = y + 11
        if hurt:
            pygame.draw.line(self.canvas, BLACK, (x + 6, eye_y - 2), (x + 10, eye_y + 2), 2)
            pygame.draw.line(self.canvas, BLACK, (x + 16, eye_y + 2), (x + 20, eye_y - 2), 2)
            pygame.draw.rect(self.canvas, DARK_RED, (x + 8, y + 18, 10, 4))
        elif self.health < 30:
            pygame.draw.rect(self.canvas, BLACK, (x + 6, eye_y, 4, 2))
            pygame.draw.rect(self.canvas, BLACK, (x + 16, eye_y, 4, 2))
            pygame.draw.line(self.canvas, DARK_RED, (x + 8, y + 21), (x + 18, y + 18), 2)
        else:
            look = int(math.sin(self.elapsed * 1.7) * 1.5)
            pygame.draw.rect(self.canvas, BLACK, (x + 7 + look, eye_y, 3, 3))
            pygame.draw.rect(self.canvas, BLACK, (x + 16 + look, eye_y, 3, 3))
            pygame.draw.rect(self.canvas, (74, 32, 29), (x + 9, y + 19, 8, 2))

    def draw_hud(self):
        pygame.draw.rect(self.canvas, (38, 34, 31), (0, VIEW_H, INTERNAL_W, HUD_H))
        pygame.draw.line(self.canvas, (111, 96, 75), (0, VIEW_H), (INTERNAL_W, VIEW_H), 2)

        self.draw_face()

        armor_color = (72, 160, 210)
        # A drawn icon is clearer than a font-dependent shield character and
        # keeps armor visually distinct from the health/max-health readout.
        shield_x, shield_y = 74, VIEW_H + 7
        shield_points = (
            (shield_x + 6, shield_y),
            (shield_x + 12, shield_y + 2),
            (shield_x + 11, shield_y + 9),
            (shield_x + 6, shield_y + 14),
            (shield_x + 1, shield_y + 9),
            (shield_x, shield_y + 2),
        )
        pygame.draw.polygon(self.canvas, (31, 64, 84), shield_points)
        pygame.draw.polygon(self.canvas, armor_color, shield_points, 1)
        pygame.draw.line(
            self.canvas,
            (120, 205, 230),
            (shield_x + 6, shield_y + 3),
            (shield_x + 6, shield_y + 10),
            1,
        )
        if self.has_red_key:
            pygame.draw.rect(self.canvas, (198, 35, 27), (202, VIEW_H + 6, 6, 7))
        if self.has_blue_key:
            pygame.draw.rect(self.canvas, (48, 132, 230), (211, VIEW_H + 6, 6, 7))
        if self.has_green_key:
            pygame.draw.rect(self.canvas, (48, 205, 105), (220, VIEW_H + 6, 6, 7))

        # Crosshair is hidden while the defensive shield is raised.
        if self.weapon != "shield":
            cx, cy = INTERNAL_W // 2, VIEW_H // 2
            pygame.draw.line(self.canvas, (215, 210, 190), (cx - 4, cy), (cx - 1, cy))
            pygame.draw.line(self.canvas, (215, 210, 190), (cx + 1, cy), (cx + 4, cy))
            pygame.draw.line(self.canvas, (215, 210, 190), (cx, cy - 4), (cx, cy - 1))
            pygame.draw.line(self.canvas, (215, 210, 190), (cx, cy + 1), (cx, cy + 4))

        boss_types = ("boss", "summoner", "overseer", "nightmare")
        boss = next(
            (enemy for enemy in self.enemies if enemy.kind in boss_types and not enemy.dead and enemy.alerted),
            None,
        )
        if boss is not None:
            boss_data = {
                "boss": ("HANGAR WARDEN", BOSS_MAX_HEALTH, (220, 55, 176)),
                "summoner": ("FOUNDRY SUMMONER", SUMMONER_MAX_HEALTH, (206, 75, 235)),
                "overseer": ("VOID OVERSEER", OVERSEER_MAX_HEALTH, (65, 180, 235)),
                "nightmare": ("NIGHTMARE SOVEREIGN", NIGHTMARE_MAX_HEALTH, (245, 52, 152)),
            }
            _, boss_max, boss_color = boss_data[boss.kind]
            bar_w = 142
            bar_x = (INTERNAL_W - bar_w) // 2
            ratio = clamp(boss.hp / boss_max, 0.0, 1.0)
            pygame.draw.rect(self.canvas, (25, 8, 22), (bar_x - 2, 11, bar_w + 4, 9))
            pygame.draw.rect(self.canvas, (75, 20, 67), (bar_x, 13, bar_w, 5))
            pygame.draw.rect(self.canvas, boss_color, (bar_x, 13, int(bar_w * ratio), 5))

    def draw_crisp_hud_text(self):
        """Draw HUD words at display resolution so small labels stay sharp."""
        display_w, display_h = self.screen.get_size()
        scale_x = display_w / INTERNAL_W
        scale_y = display_h / INTERNAL_H
        font_scale = min(scale_x, scale_y)
        cache_key = (display_w, display_h)
        if self._hud_font_cache_key != cache_key:
            self._hud_font_cache_key = cache_key
            self._hud_screen_fonts = {
                "large": pygame.font.SysFont(
                    "arial", max(18, int(11 * font_scale)), bold=True
                ),
                "medium": pygame.font.SysFont(
                    "arial", max(14, int(7.5 * font_scale)), bold=True
                ),
                "small": pygame.font.SysFont(
                    "arial", max(12, int(6 * font_scale)), bold=True
                ),
            }

        fonts = self._hud_screen_fonts

        def position(x, y):
            return round(x * scale_x), round(y * scale_y)

        def draw(text, font, color, x, y):
            label = font.render(text, True, color)
            self.screen.blit(label, position(x, y))

        draw(
            f"{self.health:03d}/{PLAYER_MAX_HEALTH}",
            fonts["large"],
            (235, 68, 54),
            8,
            VIEW_H + 7,
        )
        draw(f"{self.armor:03d}", fonts["large"], (85, 185, 235), 90, VIEW_H + 7)
        draw(
            f"BULLETS {self.ammo['bullets']:03d}",
            fonts["medium"],
            (245, 230, 180),
            229,
            VIEW_H + 3,
        )
        draw(
            f"SHELLS {self.ammo['shells']:02d}",
            fonts["medium"],
            (245, 230, 180),
            229,
            VIEW_H + 15,
        )
        draw(f"SCORE {self.score:05d}", fonts["small"], YELLOW, 8, VIEW_H + 23)
        draw(
            f"KILLS {self.kills}/{self.total_kills}",
            fonts["small"],
            WHITE,
            139,
            VIEW_H + 23,
        )

        weapon_label = WEAPONS[self.weapon]["name"]
        if self.weapon == "shield":
            remaining = self.shield_max_durability - self.shield_hits
            weapon_label += f" {remaining}/{self.shield_max_durability}"
        else:
            magazine = self.magazines[self.weapon]
            capacity = WEAPONS[self.weapon]["mag_size"]
            if self.reloading_weapon == self.weapon:
                weapon_label = f"RELOAD {magazine}/{capacity}"
            else:
                weapon_label += f" {magazine}/{capacity}"
        draw(weapon_label, fonts["small"], YELLOW, 139, VIEW_H + 2)

        effects = []
        if self.has_revive:
            effects.append("REVIVE")
        if self.invincibility_timer > 0:
            effects.append(f"INV {self.invincibility_timer:.1f}")
        if self.quad_timer > 0:
            effects.append(f"QUAD {int(self.quad_timer):02d}")
        if self.overdrive_timer > 0:
            effects.append(f"RAPID {int(self.overdrive_timer):02d}")
        if effects:
            draw(" ".join(effects), fonts["small"], CYAN, 139, VIEW_H + 12)

        boss_types = ("boss", "summoner", "overseer", "nightmare")
        boss = next(
            (
                enemy
                for enemy in self.enemies
                if enemy.kind in boss_types and not enemy.dead and enemy.alerted
            ),
            None,
        )
        if boss is not None:
            boss_names = {
                "boss": "HANGAR WARDEN",
                "summoner": "FOUNDRY SUMMONER",
                "overseer": "VOID OVERSEER",
                "nightmare": "NIGHTMARE SOVEREIGN",
            }
            boss_label = fonts["small"].render(
                boss_names[boss.kind], True, (245, 215, 135)
            )
            self.screen.blit(
                boss_label,
                boss_label.get_rect(midtop=(display_w // 2, round(2 * scale_y))),
            )

        if self.message_timer > 0:
            message = fonts["medium"].render(self.message, True, WHITE)
            message_y = 23 if boss is not None else 5
            message_rect = message.get_rect(
                midtop=(display_w // 2, round(message_y * scale_y))
            )
            background_padding = max(4, round(3 * font_scale))
            pygame.draw.rect(
                self.screen,
                (0, 0, 0),
                message_rect.inflate(background_padding * 2, background_padding),
            )
            self.screen.blit(message, message_rect)

        if self.show_fps:
            fps = fonts["small"].render(
                f"{self.clock.get_fps():04.1f} FPS", True, WHITE
            )
            self.screen.blit(
                fps,
                (display_w - fps.get_width() - round(4 * scale_x), round(4 * scale_y)),
            )

    def draw_automap(self):
        if not self.show_map:
            return

        overlay = pygame.Surface((INTERNAL_W, VIEW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))

        scale = 3 if self.map_w > 24 else 6
        origin_x = INTERNAL_W // 2 - self.map_w * scale // 2
        origin_y = VIEW_H // 2 - self.map_h * scale // 2

        for y, row in enumerate(self.map_data):
            for x, tile in enumerate(row):
                if tile not in (".", " "):
                    color = {
                        "1": (110, 110, 105),
                        "2": (160, 62, 48),
                        "3": (63, 125, 88),
                        "4": (75, 80, 103),
                        "D": (190, 160, 90),
                        "R": (210, 45, 35),
                        "K": (55, 135, 225),
                        "G": (55, 205, 105),
                        "P": (235, 193, 55),
                        "B": (198, 91, 54),
                    }.get(tile, WHITE)
                    pygame.draw.rect(
                        overlay,
                        color,
                        (origin_x + x * scale, origin_y + y * scale, scale, scale),
                        1,
                    )

        # The ceremonial diamond is the ultimate exploration goal. It changes
        # from locked gold to ready cyan when every quadrant hostile is dead.
        for switch in self.switches:
            if switch.kind != "final_teleporter":
                continue
            goal_x = int(origin_x + switch.x * scale)
            goal_y = int(origin_y + switch.y * scale)
            goal_color = (
                (80, 240, 245)
                if self.remaining_teleporter_hostiles() == 0
                else (250, 195, 55)
            )
            radius = max(4, scale + 2)
            pygame.draw.polygon(
                overlay,
                goal_color,
                (
                    (goal_x, goal_y - radius),
                    (goal_x + radius, goal_y),
                    (goal_x, goal_y + radius),
                    (goal_x - radius, goal_y),
                ),
                2,
            )
            pygame.draw.circle(overlay, goal_color, (goal_x, goal_y), 2)
            goal_label = self.font6.render("GOAL", False, goal_color)
            overlay.blit(goal_label, goal_label.get_rect(midbottom=(goal_x, goal_y - radius - 1)))

        for enemy in self.enemies:
            if not enemy.dead:
                radius = max(5, scale + 2) if enemy is self.final_boss else 1
                pygame.draw.circle(
                    overlay,
                    RED,
                    (int(origin_x + enemy.x * scale), int(origin_y + enemy.y * scale)),
                    radius,
                )
                if enemy is self.final_boss:
                    pygame.draw.circle(
                        overlay,
                        (255, 175, 70),
                        (int(origin_x + enemy.x * scale), int(origin_y + enemy.y * scale)),
                        radius + 2,
                        1,
                    )

        for field in self.energy_fields:
            if field.active:
                pygame.draw.circle(
                    overlay,
                    (205, 75, 235),
                    (int(origin_x + field.x * scale), int(origin_y + field.y * scale)),
                    max(1, scale // 3),
                )

        px = int(origin_x + self.player_x * scale)
        py = int(origin_y + self.player_y * scale)
        pygame.draw.circle(overlay, WHITE, (px, py), 2)
        pygame.draw.line(
            overlay,
            WHITE,
            (px, py),
            (
                int(px + math.cos(self.player_angle) * 6),
                int(py + math.sin(self.player_angle) * 6),
            ),
            1,
        )

        title = self.font8.render("AUTOMAP", False, WHITE)
        overlay.blit(title, (4, 4))
        self.canvas.blit(overlay, (0, 0))

    def draw_menu(self):
        """Draw a clean title-only opening screen."""
        for y in range(INTERNAL_H):
            heat = max(0, y - 115)
            color = (14 + heat // 5, 10 + heat // 15, 18 + heat // 20)
            pygame.draw.line(self.canvas, color, (0, y), (INTERNAL_W, y))

        # Industrial frame and warning stripes.
        pygame.draw.rect(self.canvas, (66, 63, 65), (7, 6, INTERNAL_W - 14, INTERNAL_H - 12), 2)
        pygame.draw.rect(self.canvas, (102, 23, 22), (11, 10, INTERNAL_W - 22, INTERNAL_H - 20), 1)
        for x in range(12, INTERNAL_W - 15, 16):
            pygame.draw.line(self.canvas, (132, 89, 29), (x, 139), (x + 7, 139), 2)

        title_shadow = self.menu_title_font.render("HELLSHIFT", True, BLACK)
        title = self.menu_title_font.render("HELLSHIFT", True, (241, 65, 48))
        subtitle = self.menu_subtitle_font.render("HANGAR 9", True, (245, 213, 119))
        self.canvas.blit(title_shadow, title_shadow.get_rect(center=(INTERNAL_W // 2 + 2, 77)))
        self.canvas.blit(title, title.get_rect(center=(INTERNAL_W // 2, 75)))
        self.canvas.blit(subtitle, subtitle.get_rect(center=(INTERNAL_W // 2, 108)))

        prompt_color = YELLOW if int(pygame.time.get_ticks() / 450) % 2 == 0 else WHITE
        prompt = self.menu_prompt_font.render("PRESS ENTER TO BEGIN", True, prompt_color)
        self.canvas.blit(prompt, prompt.get_rect(center=(INTERNAL_W // 2, 164)))

    def draw_instructions(self):
        """Explain progression and survival rules before mission setup."""
        self.canvas.fill((10, 13, 20))
        for y in range(0, INTERNAL_H, 4):
            color = (15 + y // 22, 18 + y // 28, 28 + y // 18)
            pygame.draw.line(self.canvas, color, (0, y), (INTERNAL_W, y))
        pygame.draw.rect(self.canvas, (112, 38, 40), (7, 6, INTERNAL_W - 14, INTERNAL_H - 12), 2)

        title = self.menu_subtitle_font.render("HOW TO PLAY", True, (250, 220, 130))
        subtitle = self.menu_text_font.render(
            "CONTROLS AND HUD REFERENCE",
            True,
            WHITE,
        )
        self.canvas.blit(title, title.get_rect(center=(INTERNAL_W // 2, 16)))
        self.canvas.blit(subtitle, subtitle.get_rect(center=(INTERNAL_W // 2, 32)))

        left_panel = pygame.Rect(10, 41, 145, 116)
        right_panel = pygame.Rect(165, 41, 145, 116)
        for panel in (left_panel, right_panel):
            pygame.draw.rect(self.canvas, (18, 22, 31), panel)
            pygame.draw.rect(self.canvas, (70, 82, 98), panel, 1)

        controls_heading = self.menu_text_font.render("CONTROLS", True, (250, 191, 63))
        hud_heading = self.menu_text_font.render("HUD", True, (90, 215, 235))
        self.canvas.blit(controls_heading, controls_heading.get_rect(center=(82, 49)))
        self.canvas.blit(hud_heading, hud_heading.get_rect(center=(237, 49)))

        control_lines = (
            "W / S / UP / DOWN: Move",
            "A / D: Strafe",
            "Mouse / LEFT / RIGHT: Turn",
            "Click / Ctrl: Fire",
            "E / Space: Use",
            "1 / 2 / 3 / 4: Select gear",
            "Shift: Run",
            "R: Reload",
            "Tab: Automap",
            "P: Pause",
            "F11: Fullscreen",
            "Esc: Quit",
        )
        hud_lines = (
            "LEFT: health / 150.",
            "Shield icon: armor points.",
            "CENTER: weapon + magazine.",
            "Raised shield: durability.",
            "RIGHT: reserve ammo.",
            "Bottom: score + kills.",
            "Keys/effects: beside weapon.",
            "Top bar: boss health.",
            "Red pulse: below 25 HP.",
            "Floor glows identify loot.",
        )
        for index, line in enumerate(control_lines):
            text = self.instructions_font.render(line, True, (224, 224, 216))
            self.canvas.blit(text, (15, 57 + index * 8))
        for index, line in enumerate(hud_lines):
            text = self.instructions_font.render(line, True, (224, 224, 216))
            self.canvas.blit(text, (170, 57 + index * 8))

        pygame.draw.rect(self.canvas, (36, 13, 27), (10, 162, 300, 33))
        pygame.draw.rect(self.canvas, (175, 42, 75), (10, 162, 300, 33), 1)
        recommendation = self.instructions_small_font.render(
            "RECOMMENDED TO PLAY: HARD / BIG",
            True,
            (255, 92, 180),
        )
        continue_text = self.instructions_small_font.render(
            "ENTER / CLICK TO CONTINUE",
            True,
            (255, 224, 100),
        )
        for text, y in (
            (recommendation, 173),
            (continue_text, 187),
        ):
            self.canvas.blit(text, text.get_rect(center=(INTERNAL_W // 2, y)))

    def draw_crisp_instructions(self):
        """Draw instructions at native window resolution so text is never scaled."""
        surface = self.screen
        width, height = surface.get_size()
        scale_x = width / INTERNAL_W
        scale_y = height / INTERNAL_H
        font_scale = min(scale_x, scale_y)

        def px(value):
            return int(round(value * scale_x))

        def py(value):
            return int(round(value * scale_y))

        def logical_rect(x, y, w, h):
            return pygame.Rect(px(x), py(y), px(w), py(h))

        cache_key = (width, height)
        if getattr(self, "_instruction_font_cache_key", None) != cache_key:
            self._instruction_font_cache_key = cache_key
            self._instruction_screen_fonts = {
                "title": pygame.font.SysFont("arial", max(14, int(14 * font_scale)), bold=True),
                "subtitle": pygame.font.SysFont("arial", max(9, int(9 * font_scale)), bold=True),
                "heading": pygame.font.SysFont("arial", max(9, int(9 * font_scale)), bold=True),
                "body": pygame.font.SysFont("arial", max(7, int(7 * font_scale))),
                "mode": pygame.font.SysFont("arial", max(7, int(6.5 * font_scale))),
            }
        fonts = self._instruction_screen_fonts

        surface.fill((10, 13, 20))
        for logical_y in range(0, INTERNAL_H, 4):
            color = (
                15 + logical_y // 22,
                18 + logical_y // 28,
                28 + logical_y // 18,
            )
            pygame.draw.rect(
                surface,
                color,
                logical_rect(0, logical_y, INTERNAL_W, 4),
            )
        pygame.draw.rect(
            surface,
            (112, 38, 40),
            logical_rect(7, 6, INTERNAL_W - 14, INTERNAL_H - 12),
            max(2, int(2 * font_scale)),
        )

        title = fonts["title"].render("HOW TO PLAY", True, (250, 220, 130))
        subtitle = fonts["subtitle"].render(
            "CONTROLS AND HUD REFERENCE", True, WHITE
        )
        surface.blit(title, title.get_rect(center=(px(INTERNAL_W / 2), py(16))))
        surface.blit(subtitle, subtitle.get_rect(center=(px(INTERNAL_W / 2), py(32))))

        panels = (logical_rect(10, 41, 145, 116), logical_rect(165, 41, 145, 116))
        for panel in panels:
            pygame.draw.rect(surface, (18, 22, 31), panel)
            pygame.draw.rect(surface, (70, 82, 98), panel, max(1, int(font_scale)))

        controls_heading = fonts["heading"].render("CONTROLS", True, (250, 191, 63))
        hud_heading = fonts["heading"].render("HUD", True, (90, 215, 235))
        surface.blit(controls_heading, controls_heading.get_rect(center=(px(82), py(49))))
        surface.blit(hud_heading, hud_heading.get_rect(center=(px(237), py(49))))

        control_lines = (
            "W / S / UP / DOWN: Move",
            "A / D: Strafe",
            "Mouse / LEFT / RIGHT: Turn",
            "Click / Ctrl: Fire",
            "E / Space: Use",
            "1 / 2 / 3 / 4: Select gear",
            "Shift: Run",
            "R: Reload",
            "Tab: Automap",
            "P: Pause",
            "F11: Fullscreen",
            "Esc: Quit",
        )
        hud_lines = (
            "LEFT: health / 150.",
            "Shield icon: armor points.",
            "CENTER: weapon + magazine.",
            "Raised shield: durability.",
            "RIGHT: reserve ammo.",
            "Bottom: score + kills.",
            "Keys/effects: beside weapon.",
            "Top bar: boss health.",
            "Red pulse: below 25 HP.",
            "Floor glows identify loot.",
        )
        for index, line in enumerate(control_lines):
            text = fonts["body"].render(line, True, (224, 224, 216))
            surface.blit(text, (px(15), py(57 + index * 8)))
        for index, line in enumerate(hud_lines):
            text = fonts["body"].render(line, True, (224, 224, 216))
            surface.blit(text, (px(170), py(57 + index * 8)))

        mode_panel = logical_rect(10, 162, 300, 33)
        pygame.draw.rect(surface, (36, 13, 27), mode_panel)
        pygame.draw.rect(surface, (175, 42, 75), mode_panel, max(1, int(font_scale)))
        mode_lines = (
            ("RECOMMENDED TO PLAY: HARD / BIG", (255, 92, 180), 173),
            ("ENTER / CLICK TO CONTINUE", (255, 224, 100), 187),
        )
        for line, color, logical_y in mode_lines:
            text = fonts["mode"].render(line, True, color)
            surface.blit(text, text.get_rect(center=(px(INTERNAL_W / 2), py(logical_y))))

    def draw_setup_menu(self):
        """Draw difficulty and map-size selection with clickable controls."""
        self.canvas.fill((13, 15, 22))
        for y in range(0, INTERNAL_H, 4):
            pygame.draw.line(self.canvas, (18 + y // 18, 20, 29), (0, y), (INTERNAL_W, y))
        pygame.draw.rect(self.canvas, (93, 32, 31), (8, 7, INTERNAL_W - 16, INTERNAL_H - 14), 2)

        title = self.menu_subtitle_font.render("MISSION SETUP", True, WHITE)
        self.canvas.blit(title, title.get_rect(center=(INTERNAL_W // 2, 21)))
        rects = self.setup_rects()

        difficulty = self.menu_text_font.render("DIFFICULTY", True, (215, 199, 150))
        map_label = self.menu_text_font.render("MAP SIZE", True, (215, 199, 150))
        self.canvas.blit(difficulty, difficulty.get_rect(center=(INTERNAL_W // 2, 45)))
        self.canvas.blit(map_label, map_label.get_rect(center=(INTERNAL_W // 2, 99)))

        button_data = (
            ("easy", "EASY", "Fewer bosses"),
            ("hard", "HARD", "Full challenge"),
            ("small", "SMALL", "24 x 24"),
            ("big", "BIG", "48 x 48"),
        )
        for key, label, detail in button_data:
            selected = key in (self.selected_difficulty, self.selected_map_size)
            rect = rects[key]
            fill = (109, 38, 35) if selected else (37, 42, 53)
            edge = YELLOW if selected else (104, 111, 123)
            pygame.draw.rect(self.canvas, fill, rect)
            pygame.draw.rect(self.canvas, edge, rect, 2)
            name = self.menu_prompt_font.render(label, True, WHITE)
            sub = self.menu_text_font.render(detail, True, (196, 201, 204))
            self.canvas.blit(name, name.get_rect(center=(rect.centerx, rect.centery - 5)))
            self.canvas.blit(sub, sub.get_rect(center=(rect.centerx, rect.centery + 8)))

        animating = self.nightmare_animation_active()
        start_rect = rects["start"]
        pygame.draw.rect(self.canvas, (72, 95, 67) if not animating else (58, 58, 61), start_rect)
        pygame.draw.rect(self.canvas, GREEN if not animating else (105, 105, 108), start_rect, 2)
        start_label = "START" if not animating else "TRANSFORMING..."
        start_text = self.menu_prompt_font.render(start_label, True, WHITE)
        self.canvas.blit(start_text, start_text.get_rect(center=start_rect.center))

        if animating:
            elapsed = (pygame.time.get_ticks() - self.nightmare_anim_start) / 4000.0
            overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
            overlay.fill((8, 0, 10, int(105 + elapsed * 90)))
            self.canvas.blit(overlay, (0, 0))
            merge = clamp(elapsed / 0.68, 0.0, 1.0)
            hard_x = int(lerp(72, 132, merge))
            big_x = int(lerp(248, 188, merge))
            hard = self.font24.render("HARD", False, (239, 61, 44))
            big = self.font24.render("BIG", False, (73, 168, 232))
            self.canvas.blit(hard, hard.get_rect(center=(hard_x, 91)))
            self.canvas.blit(big, big.get_rect(center=(big_x, 91)))
            if elapsed > 0.58:
                pulse = 180 + int(70 * abs(math.sin(elapsed * 18)))
                nightmare = self.menu_title_font.render("NIGHTMARE", True, (pulse, 35, 92))
                self.canvas.blit(nightmare, nightmare.get_rect(center=(INTERNAL_W // 2, 126)))
                warning = self.menu_text_font.render("HARD + BIG COMBINED", True, YELLOW)
                self.canvas.blit(warning, warning.get_rect(center=(INTERNAL_W // 2, 151)))
        elif self.selected_difficulty == "hard" and self.selected_map_size == "big":
            nightmare = self.menu_subtitle_font.render("NIGHTMARE MODE", True, (242, 49, 110))
            self.canvas.blit(nightmare, nightmare.get_rect(center=(INTERNAL_W // 2, 151)))

    def draw_nightmare_confirm(self):
        self.canvas.fill((15, 0, 8))
        for radius in range(145, 15, -18):
            shade = max(20, 145 - radius)
            pygame.draw.circle(self.canvas, (shade, 5, 25), (INTERNAL_W // 2, 88), radius, 2)
        title = self.menu_title_font.render("WARNING", True, (248, 45, 58))
        self.canvas.blit(title, title.get_rect(center=(INTERNAL_W // 2, 35)))
        line1 = self.menu_subtitle_font.render("NIGHTMARE IS REALLY, REALLY HARD.", True, WHITE)
        line2 = self.menu_text_font.render("Are you sure you want to proceed?", True, (235, 208, 154))
        self.canvas.blit(line1, line1.get_rect(center=(INTERNAL_W // 2, 78)))
        self.canvas.blit(line2, line2.get_rect(center=(INTERNAL_W // 2, 103)))
        yes_rect = pygame.Rect(42, 145, 105, 28)
        no_rect = pygame.Rect(173, 145, 105, 28)
        pygame.draw.rect(self.canvas, (116, 29, 32), yes_rect)
        pygame.draw.rect(self.canvas, RED, yes_rect, 2)
        pygame.draw.rect(self.canvas, (45, 55, 65), no_rect)
        pygame.draw.rect(self.canvas, (145, 155, 165), no_rect, 2)
        yes = self.menu_prompt_font.render("YES - PROCEED", True, WHITE)
        no = self.menu_prompt_font.render("NO - GO BACK", True, WHITE)
        self.canvas.blit(yes, yes.get_rect(center=yes_rect.center))
        self.canvas.blit(no, no.get_rect(center=no_rect.center))
        keys = self.menu_text_font.render("ENTER / Y = YES     N / ESC = NO", True, (210, 210, 205))
        self.canvas.blit(keys, keys.get_rect(center=(INTERNAL_W // 2, 187)))

    def draw_end_screen(self):
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 205))
        self.canvas.blit(overlay, (0, 0))

        if self.state == "won":
            title = self.font24.render("AREA SECURED", False, GREEN)
            subtitle = f"TIME {int(self.elapsed // 60):02d}:{int(self.elapsed % 60):02d}   KILLS {self.kills}/{self.total_kills}"
            score_summary = f"SCORE {self.score:05d}"
        else:
            title = self.font24.render("MISSION FAILED", False, RED)
            subtitle = f"SCORE {self.score:05d}   KILLS {self.kills}/{self.total_kills}"
            score_summary = None

        sub = self.font8.render(subtitle, False, WHITE)
        restart = self.font8.render("PRESS ENTER TO RESTART", False, WHITE)

        self.canvas.blit(title, title.get_rect(center=(INTERNAL_W // 2, 78)))
        self.canvas.blit(sub, sub.get_rect(center=(INTERNAL_W // 2, 106)))
        if score_summary is not None:
            score_text = self.font8.render(score_summary, False, YELLOW)
            self.canvas.blit(score_text, score_text.get_rect(center=(INTERNAL_W // 2, 120)))
        restart_y = 140 if score_summary is not None else 132
        self.canvas.blit(restart, restart.get_rect(center=(INTERNAL_W // 2, restart_y)))

    def draw_revive_screen(self):
        """Display the automatic one-use revival transition."""
        pulse = int(25 * abs(math.sin(pygame.time.get_ticks() * 0.013)))
        self.canvas.fill((125 + pulse, 0, 8))
        for y in range(0, INTERNAL_H, 8):
            pygame.draw.line(self.canvas, (82, 0, 5), (0, y), (INTERNAL_W, y), 1)
        pygame.draw.rect(self.canvas, (245, 42, 38), (8, 8, INTERNAL_W - 16, INTERNAL_H - 16), 3)
        title = self.menu_title_font.render("REVIVE", True, WHITE)
        subtitle = self.menu_subtitle_font.render("SECOND CHANCE ACTIVATED", True, (255, 210, 165))
        reboot = self.menu_text_font.render("RESTORING LIFE SIGNAL...", True, WHITE)
        self.canvas.blit(title, title.get_rect(center=(INTERNAL_W // 2, 74)))
        self.canvas.blit(subtitle, subtitle.get_rect(center=(INTERNAL_W // 2, 112)))
        self.canvas.blit(reboot, reboot.get_rect(center=(INTERNAL_W // 2, 140)))

    def draw_pause(self):
        overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.canvas.blit(overlay, (0, 0))
        text = self.font24.render("PAUSED", False, WHITE)
        help_text = self.font8.render("P TO RESUME", False, WHITE)
        self.canvas.blit(text, text.get_rect(center=(INTERNAL_W // 2, 85)))
        self.canvas.blit(help_text, help_text.get_rect(center=(INTERNAL_W // 2, 112)))

    # ------------------------------------------------------------------
    # Update and render
    # ------------------------------------------------------------------

    def update(self, dt, fire, use):
        self.update_music()
        self.message_timer = max(0.0, self.message_timer - dt)
        self.weapon_cooldown = max(0.0, self.weapon_cooldown - dt)
        self.weapon_anim = max(0.0, self.weapon_anim - dt)
        self.muzzle_timer = max(0.0, self.muzzle_timer - dt)
        self.shield_flash = max(0.0, self.shield_flash - dt)
        self.damage_flash = max(0.0, self.damage_flash - dt)
        self.face_hurt_timer = max(0.0, self.face_hurt_timer - dt)
        self.overdrive_timer = max(0.0, self.overdrive_timer - dt)
        self.quad_timer = max(0.0, self.quad_timer - dt)
        if self.state == "playing" and not self.paused:
            self.invincibility_timer = max(0.0, self.invincibility_timer - dt)

        if self.state == "reviving":
            self.revive_screen_timer = max(0.0, self.revive_screen_timer - dt)
            if self.revive_screen_timer <= 0:
                self.finish_revive()
            return

        if self.state != "playing" or self.paused:
            return

        self.update_reload(dt)

        if self.poison_timer > 0:
            self.poison_timer = max(0.0, self.poison_timer - dt)
            self.poison_tick += dt
            if self.poison_tick >= 0.75:
                self.poison_tick = 0.0
                self.damage_player(2)
                if self.state != "playing":
                    return

        self.elapsed += dt
        self.update_player(dt)

        if fire:
            self.fire_weapon()
        if use:
            self.use_action()

        for door in self.doors.values():
            door.update(dt)

        self.update_enemies(dt)
        self.update_projectiles(dt)
        self.update_energy_fields(dt)
        self.update_claw_strikes(dt)
        self.update_pickups()

    def update_music(self):
        """Choose exploration, quadrant-boss, or final-boss music."""
        music_mode = "ambient"
        if self.state == "playing":
            active_bosses = [
                enemy for enemy in self.enemies
                if enemy.kind in ("boss", "summoner", "overseer", "nightmare")
                and enemy.alerted
                and not enemy.dead
            ]
            if any(enemy is self.final_boss for enemy in active_bosses):
                music_mode = "final"
            elif active_bosses:
                music_mode = "boss"
        self.sounds.set_music(music_mode)

    def draw_low_health_warning(self):
        """Pulse the 3D view red without obscuring the HUD."""
        if self.state != "playing" or self.health >= 25:
            return
        pulse = (math.sin(pygame.time.get_ticks() * 0.012) + 1.0) * 0.5
        warning = self._low_health_surface
        warning.fill((205, 8, 8, int(22 + pulse * 52)))
        self.canvas.blit(warning, (0, 0))

    def render_frame(self):
        # The gameplay view is intentionally rendered at 320x200, but scaling
        # small text from that resolution makes it fuzzy. Instructions bypass
        # the retro canvas and render directly to the real display instead.
        if self.state == "instructions":
            self.draw_crisp_instructions()
            pygame.display.flip()
            return

        if self.state == "menu":
            self.draw_menu()
        elif self.state == "setup":
            self.draw_setup_menu()
        elif self.state == "nightmare_confirm":
            self.draw_nightmare_confirm()
        elif self.state == "reviving":
            self.draw_revive_screen()
        else:
            zbuffer = self.cast_scene()
            self.draw_sprites(zbuffer)
            self.draw_weapon()
            self.draw_automap()
            self.draw_low_health_warning()

            if self.damage_flash > 0:
                # Damage feedback belongs to the world view; the HUD must
                # remain readable even during repeated hits.
                flash = self._damage_flash_surface
                alpha = int(110 * self.damage_flash / 0.22)
                flash.fill((210, 15, 10, alpha))
                self.canvas.blit(flash, (0, 0))

            # Draw the HUD after every warning/flash overlay so neither can
            # tint its panels, icons, or fallback text.
            self.draw_hud()

            if self.paused:
                self.draw_pause()
            elif self.state in ("dead", "won"):
                self.draw_end_screen()

        display_size = self.screen.get_size()
        # Scale directly into the display instead of allocating and blitting a
        # new 1200x750 surface every frame.
        pygame.transform.scale(self.canvas, display_size, self.screen)
        if self.state not in (
            "menu",
            "instructions",
            "setup",
            "nightmare_confirm",
            "reviving",
        ):
            self.draw_crisp_hud_text()
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            fire, use = self.handle_events()
            self.update(dt, fire, use)
            self.render_frame()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
