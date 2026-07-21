"""Impossible Square - a World's Hardest Game-inspired Pygame challenge.

All graphics are drawn with Pygame, so no external assets are required.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable

import pygame

import scores


SCREEN_W = 960
SCREEN_H = 640
HUD_H = 64
TILE = 32
GRID_W = SCREEN_W // TILE
GRID_H = (SCREEN_H - HUD_H) // TILE
FPS = 60

INK = (31, 35, 48)
INK_SOFT = (75, 81, 101)
WALL = (164, 178, 235)
WALL_DARK = (132, 150, 222)
FLOOR_A = (250, 250, 255)
FLOOR_B = (236, 239, 250)
SAFE_A = (183, 239, 153)
SAFE_B = (158, 222, 124)
RED = (232, 56, 76)
RED_DARK = (174, 30, 49)
BLUE = (36, 91, 224)
BLUE_DARK = (20, 54, 154)
GOLD = (255, 210, 58)
GOLD_DARK = (189, 131, 17)
WHITE = (255, 255, 255)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def grid_point(x: float, y: float) -> pygame.Vector2:
    """Convert grid coordinates (where integers are tile edges) to pixels."""
    return pygame.Vector2(x * TILE, HUD_H + y * TILE)


def circle_hits_rect(center: pygame.Vector2, radius: float, rect: pygame.Rect) -> bool:
    closest_x = clamp(center.x, rect.left, rect.right)
    closest_y = clamp(center.y, rect.top, rect.bottom)
    dx = center.x - closest_x
    dy = center.y - closest_y
    return dx * dx + dy * dy < radius * radius


@dataclass
class EnemySpec:
    start: tuple[float, float]
    end: tuple[float, float]
    speed: float = 145.0
    radius: int = 10
    phase: float = 0.0
    direction: int = 1


@dataclass
class LevelSpec:
    name: str
    hint: str
    floor: set[tuple[int, int]]
    safe: set[tuple[int, int]]
    checkpoints: set[tuple[int, int]]
    start: tuple[float, float]
    goal: set[tuple[int, int]]
    coins: list[tuple[float, float]]
    enemies: list[EnemySpec]


class LevelBuilder:
    def __init__(self, name: str, hint: str) -> None:
        self.name = name
        self.hint = hint
        self.floor: set[tuple[int, int]] = set()
        self.safe: set[tuple[int, int]] = set()
        self.checkpoints: set[tuple[int, int]] = set()
        self.goal: set[tuple[int, int]] = set()
        self.coins: list[tuple[float, float]] = []
        self.enemies: list[EnemySpec] = []
        self.start = (2.5, 8.5)

    def rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        safe: bool = False,
        checkpoint: bool = False,
        goal: bool = False,
    ) -> "LevelBuilder":
        cells = {
            (tx, ty)
            for tx in range(x, x + w)
            for ty in range(y, y + h)
            if 0 <= tx < GRID_W and 0 <= ty < GRID_H
        }
        self.floor.update(cells)
        if safe or checkpoint or goal:
            self.safe.update(cells)
        if checkpoint:
            self.checkpoints.update(cells)
        if goal:
            self.goal.update(cells)
        return self

    def remove_rect(self, x: int, y: int, w: int, h: int) -> "LevelBuilder":
        cells = {(tx, ty) for tx in range(x, x + w) for ty in range(y, y + h)}
        self.floor.difference_update(cells)
        self.safe.difference_update(cells)
        self.checkpoints.difference_update(cells)
        self.goal.difference_update(cells)
        return self

    def spawn(self, x: float, y: float) -> "LevelBuilder":
        self.start = (x, y)
        return self

    def coin(self, x: float, y: float) -> "LevelBuilder":
        self.coins.append((x, y))
        return self

    def enemy(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        speed: float = 145.0,
        radius: int = 10,
        phase: float = 0.0,
        direction: int = 1,
    ) -> "LevelBuilder":
        self.enemies.append(EnemySpec((x1, y1), (x2, y2), speed, radius, phase, direction))
        return self

    def build(self) -> LevelSpec:
        if not self.goal:
            raise ValueError(f"Level {self.name!r} has no goal")
        return LevelSpec(
            self.name,
            self.hint,
            self.floor,
            self.safe,
            self.checkpoints,
            self.start,
            self.goal,
            self.coins,
            self.enemies,
        )


def build_levels() -> list[LevelSpec]:
    levels: list[LevelSpec] = []

    # Level 1: a clean introduction to alternating vertical lanes.
    b = LevelBuilder("FIRST STEPS", "Move between the red orbs. Green zones are safe.")
    b.rect(1, 7, 4, 4, safe=True).rect(5, 4, 20, 10).rect(25, 7, 4, 4, goal=True)
    b.spawn(2.5, 9).coin(9.5, 9).coin(15.5, 9).coin(21.5, 9)
    for i, x in enumerate((7.5, 10.5, 13.5, 16.5, 19.5, 22.5)):
        b.enemy(x, 4.55, x, 13.45, 138 + i * 3, phase=(i % 2) * 0.5, direction=1 if i % 2 == 0 else -1)
    levels.append(b.build())

    # Level 2: the route doubles back on itself.
    b = LevelBuilder("THE LONG WAY", "Every yellow coin must reach the goal with you.")
    b.rect(1, 2, 4, 4, safe=True).rect(5, 2, 20, 4).rect(22, 6, 3, 8)
    b.rect(4, 11, 18, 3).rect(1, 10, 3, 5, goal=True).spawn(2.5, 4)
    for pos in ((7.5, 3.5), (18.5, 4.5), (23.5, 8.5), (17.5, 12.5), (7.5, 12.5)):
        b.coin(*pos)
    for i, x in enumerate((8.5, 12.5, 16.5, 20.5)):
        b.enemy(x, 2.45, x, 5.55, 125 + i * 8, phase=i * 0.22)
    b.enemy(22.45, 7.5, 24.55, 7.5, 125, phase=0.1)
    b.enemy(22.45, 10.5, 24.55, 10.5, 150, phase=0.6)
    for i, x in enumerate((8.5, 12.5, 16.5, 20.5)):
        b.enemy(x, 11.45, x, 13.55, 120 + i * 9, phase=0.55 if i % 2 else 0.05)
    levels.append(b.build())

    # Level 3: checkpoint in a crossfire room.
    b = LevelBuilder("CROSSFIRE", "Touch the middle checkpoint to bank collected coins.")
    b.rect(1, 7, 4, 4, safe=True).rect(5, 2, 20, 14).rect(13, 7, 4, 4, checkpoint=True)
    b.rect(25, 7, 4, 4, goal=True).spawn(2.5, 9)
    for pos in ((7.5, 3.5), (10.5, 14.5), (19.5, 3.5), (22.5, 14.5)):
        b.coin(*pos)
    for i, x in enumerate((7.5, 10.5, 19.5, 22.5)):
        b.enemy(x, 2.45, x, 15.55, 160 + (i % 2) * 20, phase=i * 0.21)
    for i, y in enumerate((5.5, 12.5)):
        b.enemy(5.45, y, 12.55, y, 145, phase=i * 0.42)
        b.enemy(17.45, y, 24.55, y, 155, phase=0.7 - i * 0.3)
    levels.append(b.build())

    # Level 4: an inward spiral with a checkpoint at the last big corner.
    b = LevelBuilder("THE SPIRAL", "The shortest-looking route is usually a wall.")
    b.rect(1, 1, 4, 4, safe=True).rect(5, 1, 23, 3).rect(25, 4, 3, 12)
    b.rect(3, 13, 22, 3).rect(3, 6, 3, 7).rect(6, 6, 15, 3)
    b.rect(3, 12, 3, 4, checkpoint=True).rect(20, 5, 4, 5, goal=True).spawn(2.5, 3)
    for pos in ((10.5, 2.5), (22.5, 2.5), (26.5, 9.5), (19.5, 14.5), (4.5, 9.5), (12.5, 7.5)):
        b.coin(*pos)
    for i, x in enumerate((8.5, 13.5, 18.5, 23.5)):
        b.enemy(x, 1.45, x, 3.55, 130 + i * 7, phase=i * 0.18)
    for i, y in enumerate((6.5, 10.5)):
        b.enemy(25.45, y, 27.55, y, 140 + i * 15, phase=i * 0.5)
    for i, x in enumerate((9.5, 14.5, 19.5, 23.5)):
        b.enemy(x, 13.45, x, 15.55, 145 + i * 6, phase=0.15 + i * 0.2)
    b.enemy(3.45, 8.5, 5.55, 8.5, 145, phase=0.3)
    b.enemy(3.45, 11.5, 5.55, 11.5, 160, phase=0.7)
    for i, x in enumerate((8.5, 12.5, 16.5)):
        b.enemy(x, 6.45, x, 8.55, 145 + i * 10, phase=i * 0.28)
    levels.append(b.build())

    # Level 5: alternating wall openings force a long zig-zag.
    b = LevelBuilder("THE GAUNTLET", "Use the walls as cover, but never stop watching.")
    b.rect(4, 1, 22, 16).rect(1, 13, 4, 4, safe=True).rect(25, 1, 4, 4, goal=True)
    b.remove_rect(8, 1, 1, 11).remove_rect(12, 6, 1, 11)
    b.remove_rect(16, 1, 1, 11).remove_rect(20, 6, 1, 11)
    b.rect(13, 13, 3, 3, checkpoint=True).spawn(2.5, 15)
    for pos in ((6.5, 14.5), (10.5, 3.5), (14.5, 14.5), (18.5, 3.5), (23.5, 3.5)):
        b.coin(*pos)
    for i, x in enumerate((6.2, 10.2, 14.2, 18.2, 22.2, 24.2)):
        b.enemy(x, 1.55, x, 16.45, 150 + (i % 3) * 13, phase=i * 0.14, direction=-1 if i % 2 else 1)
    b.enemy(4.55, 12.5, 7.55, 12.5, 155, phase=0.2)
    b.enemy(9.45, 5.0, 11.55, 5.0, 145, phase=0.65)
    b.enemy(17.45, 12.5, 19.55, 12.5, 165, phase=0.35)
    b.enemy(21.45, 5.0, 25.55, 5.0, 160, phase=0.8)
    levels.append(b.build())

    # Level 6: overlapping rhythms, with one final safe island in the middle.
    b = LevelBuilder("BLUE HELL", "Stay calm. Tiny corrections beat desperate sprints.")
    b.rect(1, 7, 4, 4, safe=True).rect(5, 1, 20, 16).rect(14, 7, 2, 4, checkpoint=True)
    b.rect(25, 7, 4, 4, goal=True).spawn(2.5, 9)
    for pos in ((7.5, 2.5), (7.5, 15.5), (12.5, 5.5), (17.5, 12.5), (22.5, 2.5), (22.5, 15.5)):
        b.coin(*pos)
    for i, x in enumerate((6.5, 8.8, 11.1, 13.2, 16.8, 18.9, 21.2, 23.5)):
        b.enemy(x, 1.45, x, 16.55, 175 + (i % 3) * 14, phase=i * 0.115, direction=-1 if i % 2 else 1)
    for i, y in enumerate((4.5, 6.5, 11.5, 13.5)):
        b.enemy(5.45, y, 24.55, y, 185 + (i % 2) * 15, phase=0.12 + i * 0.21, radius=9)
    levels.append(b.build())

    return levels


class Enemy:
    def __init__(self, spec: EnemySpec) -> None:
        self.spec = spec
        self.start = grid_point(*spec.start)
        self.end = grid_point(*spec.end)
        self.segment = self.end - self.start
        self.distance = max(1.0, self.segment.length())
        self.progress = clamp(spec.phase, 0.0, 1.0)
        self.direction = 1 if spec.direction >= 0 else -1
        self.position = self.start.lerp(self.end, self.progress)

    def reset(self) -> None:
        self.progress = clamp(self.spec.phase, 0.0, 1.0)
        self.direction = 1 if self.spec.direction >= 0 else -1
        self.position = self.start.lerp(self.end, self.progress)

    def update(self, dt: float) -> None:
        self.progress += self.direction * (self.spec.speed / self.distance) * dt
        while self.progress > 1.0 or self.progress < 0.0:
            if self.progress > 1.0:
                self.progress = 2.0 - self.progress
                self.direction = -1
            elif self.progress < 0.0:
                self.progress = -self.progress
                self.direction = 1
        self.position = self.start.lerp(self.end, self.progress)

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        p = self.position + offset
        r = self.spec.radius
        pygame.draw.circle(surface, RED_DARK, p, r + 3)
        pygame.draw.circle(surface, RED, p, r)
        pygame.draw.circle(surface, (255, 129, 139), p - pygame.Vector2(3, 3), max(2, r // 3))


@dataclass
class Particle:
    position: pygame.Vector2
    velocity: pygame.Vector2
    color: tuple[int, int, int]
    life: float
    max_life: float
    size: float

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.position += self.velocity * dt
        self.velocity *= max(0.0, 1.0 - 2.6 * dt)
        return self.life > 0.0

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        ratio = max(0.0, self.life / self.max_life)
        radius = max(1, int(self.size * ratio))
        pygame.draw.circle(surface, self.color, self.position + offset, radius)


class Game:
    PLAYER_SIZE = 22
    PLAYER_SPEED = 226.0

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Impossible Square")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("arial", 18, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 28, bold=True)
        self.font_large = pygame.font.SysFont("arial", 54, bold=True)
        self.font_huge = pygame.font.SysFont("arial", 76, bold=True)
        self.levels = build_levels()
        self.level_index = 0
        self.level = self.levels[0]
        self.enemies: list[Enemy] = []
        self.player = pygame.Vector2()
        self.respawn = pygame.Vector2()
        self.coins_collected: set[int] = set()
        self.banked_coins: set[int] = set()
        self.active_checkpoint: tuple[int, int] | None = None
        self.deaths = 0
        self.elapsed = 0.0
        self.level_elapsed = 0.0
        self.state = "menu"
        self.death_timer = 0.0
        self.transition_timer = 0.0
        self.end_input_delay = 0.0
        self.message = ""
        self.message_timer = 0.0
        self.shake = 0.0
        self.particles: list[Particle] = []
        self.running = True
        self.load_level(0)

    @property
    def player_rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.player.x - self.PLAYER_SIZE / 2),
            round(self.player.y - self.PLAYER_SIZE / 2),
            self.PLAYER_SIZE,
            self.PLAYER_SIZE,
        )

    def load_level(self, index: int) -> None:
        self.level_index = index
        scores.record("impossible", index + 1)   # persist furthest level reached
        self.level = self.levels[index]
        self.enemies = [Enemy(spec) for spec in self.level.enemies]
        self.respawn = grid_point(*self.level.start)
        self.player = self.respawn.copy()
        self.coins_collected.clear()
        self.banked_coins.clear()
        self.active_checkpoint = None
        self.death_timer = 0.0
        self.transition_timer = 0.0
        self.level_elapsed = 0.0
        self.particles.clear()
        self.message = self.level.hint
        self.message_timer = 3.4

    def restart_run(self) -> None:
        self.deaths = 0
        self.elapsed = 0.0
        self.load_level(0)
        self.state = "playing"

    def rect_on_floor(self, rect: pygame.Rect) -> bool:
        inset = 2
        samples = (
            (rect.left + inset, rect.top + inset),
            (rect.right - inset - 1, rect.top + inset),
            (rect.left + inset, rect.bottom - inset - 1),
            (rect.right - inset - 1, rect.bottom - inset - 1),
        )
        for px, py in samples:
            gx = int(px // TILE)
            gy = int((py - HUD_H) // TILE)
            if (gx, gy) not in self.level.floor:
                return False
        return True

    def player_cell(self) -> tuple[int, int]:
        return int(self.player.x // TILE), int((self.player.y - HUD_H) // TILE)

    def on_safe_zone(self) -> bool:
        return self.player_cell() in self.level.safe

    def move_player(self, direction: pygame.Vector2, dt: float) -> None:
        if direction.length_squared() > 1.0:
            direction = direction.normalize()
        movement = direction * self.PLAYER_SPEED * dt
        if movement.x:
            self.player.x += movement.x
            if not self.rect_on_floor(self.player_rect):
                self.player.x -= movement.x
        if movement.y:
            self.player.y += movement.y
            if not self.rect_on_floor(self.player_rect):
                self.player.y -= movement.y

    def collect_coins(self) -> None:
        rect = self.player_rect
        for index, coin in enumerate(self.level.coins):
            if index in self.coins_collected:
                continue
            if circle_hits_rect(grid_point(*coin), 9, rect):
                self.coins_collected.add(index)
                self.message = "COIN COLLECTED"
                self.message_timer = 0.85
                self.emit_burst(grid_point(*coin), GOLD, 9, speed=105)

    def activate_checkpoint(self) -> None:
        cell = self.player_cell()
        if cell not in self.level.checkpoints or cell == self.active_checkpoint:
            return
        self.active_checkpoint = cell
        self.respawn = grid_point(cell[0] + 0.5, cell[1] + 0.5)
        self.banked_coins = set(self.coins_collected)
        self.message = "CHECKPOINT — COINS BANKED"
        self.message_timer = 1.8
        self.emit_burst(self.player, SAFE_B, 18, speed=135)

    def try_finish(self) -> None:
        if self.player_cell() not in self.level.goal:
            return
        missing = len(self.level.coins) - len(self.coins_collected)
        if missing:
            self.message = f"{missing} COIN{'S' if missing != 1 else ''} LEFT"
            self.message_timer = 0.8
            return
        # The final level gets a permanent end state. It never goes through the
        # automatic between-level transition, so it cannot accidentally loop.
        if self.level_index == len(self.levels) - 1:
            self.state = "finished"
            self.end_input_delay = 0.8
        else:
            self.state = "level_complete"
            self.transition_timer = 1.25
        self.emit_burst(self.player, SAFE_B, 34, speed=220)

    def die(self) -> None:
        if self.death_timer > 0.0:
            return
        self.deaths += 1
        self.death_timer = 0.55
        self.shake = 0.34
        self.emit_burst(self.player, BLUE, 28, speed=245)

    def finish_respawn(self) -> None:
        self.player = self.respawn.copy()
        self.coins_collected = set(self.banked_coins)
        for enemy in self.enemies:
            enemy.reset()
        self.death_timer = 0.0
        self.message = "TRY AGAIN"
        self.message_timer = 0.65

    def emit_burst(
        self,
        position: pygame.Vector2,
        color: tuple[int, int, int],
        count: int,
        *,
        speed: float,
    ) -> None:
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            magnitude = random.uniform(speed * 0.35, speed)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * magnitude
            life = random.uniform(0.3, 0.68)
            self.particles.append(Particle(position.copy(), velocity, color, life, life, random.uniform(3, 7)))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
        if self.state == "menu" and event.key in (
            pygame.K_RETURN,
            pygame.K_SPACE,
            pygame.K_w,
            pygame.K_a,
            pygame.K_s,
            pygame.K_d,
            pygame.K_UP,
            pygame.K_DOWN,
            pygame.K_LEFT,
            pygame.K_RIGHT,
        ):
            self.restart_run()
        elif self.state == "playing":
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.state = "paused"
            elif event.key == pygame.K_r:
                self.deaths += 1
                self.finish_respawn()
        elif self.state == "paused" and event.key in (pygame.K_ESCAPE, pygame.K_p, pygame.K_RETURN):
            self.state = "playing"
        elif self.state == "finished" and self.end_input_delay <= 0.0:
            if event.key == pygame.K_r:
                self.restart_run()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "menu"
            elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False

    def update(self, dt: float) -> None:
        self.particles = [p for p in self.particles if p.update(dt)]
        self.message_timer = max(0.0, self.message_timer - dt)
        self.shake = max(0.0, self.shake - dt)

        if self.state == "finished":
            self.end_input_delay = max(0.0, self.end_input_delay - dt)
            return

        if self.state == "level_complete":
            self.transition_timer -= dt
            if self.transition_timer <= 0.0:
                self.load_level(self.level_index + 1)
                self.state = "playing"
            return
        if self.state != "playing":
            return

        self.elapsed += dt
        self.level_elapsed += dt
        if self.death_timer > 0.0:
            self.death_timer -= dt
            if self.death_timer <= 0.0:
                self.finish_respawn()
            return

        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT]),
            int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        self.move_player(direction, dt)
        for enemy in self.enemies:
            enemy.update(dt)
        self.collect_coins()
        self.activate_checkpoint()
        self.try_finish()

        if not self.on_safe_zone():
            rect = self.player_rect
            for enemy in self.enemies:
                if circle_hits_rect(enemy.position, enemy.spec.radius, rect):
                    self.die()
                    break

    def draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        center: tuple[float, float],
        *,
        shadow: bool = False,
    ) -> None:
        rendered = font.render(text, True, color)
        rect = rendered.get_rect(center=center)
        if shadow:
            shade = font.render(text, True, (16, 18, 27))
            self.screen.blit(shade, rect.move(3, 4))
        self.screen.blit(rendered, rect)

    def draw_board(self, offset: pygame.Vector2) -> None:
        self.screen.fill(WALL_DARK)
        for y in range(GRID_H):
            for x in range(GRID_W):
                rect = pygame.Rect(x * TILE + offset.x, HUD_H + y * TILE + offset.y, TILE, TILE)
                cell = (x, y)
                if cell in self.level.floor:
                    if cell in self.level.safe:
                        color = SAFE_A if (x + y) % 2 == 0 else SAFE_B
                    else:
                        color = FLOOR_A if (x + y) % 2 == 0 else FLOOR_B
                    pygame.draw.rect(self.screen, color, rect)
                    pygame.draw.rect(self.screen, (221, 225, 239), rect, 1)
                else:
                    color = WALL if (x + y) % 2 == 0 else WALL_DARK
                    pygame.draw.rect(self.screen, color, rect)
        # Strong edge lines make the playable shape readable at a glance.
        for x, y in self.level.floor:
            base_x = x * TILE + offset.x
            base_y = HUD_H + y * TILE + offset.y
            for neighbor, start, end in (
                ((x - 1, y), (base_x, base_y), (base_x, base_y + TILE)),
                ((x + 1, y), (base_x + TILE, base_y), (base_x + TILE, base_y + TILE)),
                ((x, y - 1), (base_x, base_y), (base_x + TILE, base_y)),
                ((x, y + 1), (base_x, base_y + TILE), (base_x + TILE, base_y + TILE)),
            ):
                if neighbor not in self.level.floor:
                    pygame.draw.line(self.screen, INK_SOFT, start, end, 3)

    def draw_coin(self, position: tuple[float, float], offset: pygame.Vector2, tick: float) -> None:
        p = grid_point(*position) + offset
        pulse = 1.0 + 0.1 * math.sin(tick * 5.5 + position[0])
        radius = int(9 * pulse)
        pygame.draw.circle(self.screen, GOLD_DARK, p, radius + 3)
        pygame.draw.circle(self.screen, GOLD, p, radius)
        pygame.draw.circle(self.screen, (255, 244, 155), p - pygame.Vector2(2, 3), max(2, radius // 3))

    def draw_player(self, offset: pygame.Vector2) -> None:
        if self.death_timer > 0.0:
            return
        rect = self.player_rect.move(round(offset.x), round(offset.y))
        pygame.draw.rect(self.screen, BLUE_DARK, rect.inflate(6, 6), border_radius=4)
        pygame.draw.rect(self.screen, BLUE, rect, border_radius=3)
        shine = pygame.Rect(rect.x + 4, rect.y + 4, rect.w - 8, 5)
        pygame.draw.rect(self.screen, (113, 162, 255), shine, border_radius=2)

    def format_time(self, seconds: float) -> str:
        minutes = int(seconds) // 60
        remainder = seconds - minutes * 60
        return f"{minutes:02d}:{remainder:05.2f}"

    def draw_hud(self) -> None:
        pygame.draw.rect(self.screen, INK, (0, 0, SCREEN_W, HUD_H))
        pygame.draw.line(self.screen, (52, 58, 77), (0, HUD_H - 1), (SCREEN_W, HUD_H - 1), 2)
        level_text = f"LEVEL {self.level_index + 1}/{len(self.levels)}  ·  {self.level.name}"
        self.screen.blit(self.font_small.render(level_text, True, WHITE), (22, 12))
        coin_text = f"COINS  {len(self.coins_collected)}/{len(self.level.coins)}"
        self.screen.blit(self.font_small.render(coin_text, True, GOLD), (22, 36))
        deaths = self.font_small.render(f"DEATHS  {self.deaths}", True, (255, 151, 160))
        self.screen.blit(deaths, (SCREEN_W - deaths.get_width() - 22, 12))
        timer = self.font_small.render(self.format_time(self.elapsed), True, WHITE)
        self.screen.blit(timer, (SCREEN_W - timer.get_width() - 22, 36))

    def draw_overlay(self, title: str, subtitle: str = "") -> None:
        layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        layer.fill((15, 18, 29, 174))
        self.screen.blit(layer, (0, 0))
        panel = pygame.Rect(170, 188, 620, 254)
        pygame.draw.rect(self.screen, (247, 248, 255), panel, border_radius=16)
        pygame.draw.rect(self.screen, INK, panel, 4, border_radius=16)
        self.draw_text(title, self.font_large, INK, (SCREEN_W / 2, 270))
        if subtitle:
            self.draw_text(subtitle, self.font_small, INK_SOFT, (SCREEN_W / 2, 330))

    def draw_menu(self) -> None:
        self.screen.fill(INK)
        # Decorative board preview.
        for y in range(6, SCREEN_H, 32):
            for x in range(0, SCREEN_W, 32):
                color = WALL if (x // 32 + y // 32) % 2 else WALL_DARK
                pygame.draw.rect(self.screen, color, (x, y, 32, 32))
        panel = pygame.Rect(105, 92, 750, 456)
        pygame.draw.rect(self.screen, (247, 248, 255), panel, border_radius=22)
        pygame.draw.rect(self.screen, INK, panel, 5, border_radius=22)
        self.draw_text("IMPOSSIBLE", self.font_huge, INK, (SCREEN_W / 2, 174))
        self.draw_text("SQUARE", self.font_huge, BLUE, (SCREEN_W / 2, 246))
        self.draw_text("A tiny square. Six brutal rooms.", self.font_medium, INK_SOFT, (SCREEN_W / 2, 310))
        self.draw_text("WASD / ARROWS  ·  MOVE", self.font_small, INK, (SCREEN_W / 2, 372))
        self.draw_text("R  ·  RESTART     P / ESC  ·  PAUSE     F11  ·  FULLSCREEN", self.font_small, INK, (SCREEN_W / 2, 405))
        pulse = 185 + int(70 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 320)))
        self.draw_text("PRESS ENTER OR A MOVE KEY", self.font_medium, (35, 78, pulse), (SCREEN_W / 2, 478))

    def draw_end_screen(self) -> None:
        """Draw a standalone final screen that remains until the player chooses."""
        self.screen.fill(INK)
        for y in range(0, SCREEN_H, TILE):
            for x in range(0, SCREEN_W, TILE):
                color = WALL if (x // TILE + y // TILE) % 2 else WALL_DARK
                pygame.draw.rect(self.screen, color, (x, y, TILE, TILE))

        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((18, 22, 38, 118))
        self.screen.blit(shade, (0, 0))

        panel = pygame.Rect(120, 72, 720, 496)
        pygame.draw.rect(self.screen, (247, 248, 255), panel, border_radius=22)
        pygame.draw.rect(self.screen, INK, panel, 5, border_radius=22)

        # A tiny crowned blue square serves as a code-drawn victory badge.
        badge = pygame.Rect(SCREEN_W // 2 - 36, 112, 72, 72)
        pygame.draw.rect(self.screen, BLUE_DARK, badge.inflate(10, 10), border_radius=10)
        pygame.draw.rect(self.screen, BLUE, badge, border_radius=8)
        crown = [
            (badge.left + 6, badge.top - 4),
            (badge.left + 16, badge.top - 24),
            (badge.left + 31, badge.top - 7),
            (badge.left + 45, badge.top - 25),
            (badge.right - 6, badge.top - 4),
        ]
        pygame.draw.polygon(self.screen, GOLD, crown)
        pygame.draw.lines(self.screen, GOLD_DARK, False, crown, 3)

        self.draw_text("YOU BEAT IT!", self.font_large, INK, (SCREEN_W / 2, 235))
        self.draw_text("All six impossible rooms cleared", self.font_small, INK_SOFT, (SCREEN_W / 2, 278))

        pygame.draw.rect(self.screen, FLOOR_B, (226, 310, 230, 82), border_radius=12)
        pygame.draw.rect(self.screen, FLOOR_B, (504, 310, 230, 82), border_radius=12)
        self.draw_text("FINAL TIME", self.font_small, INK_SOFT, (341, 330))
        self.draw_text(self.format_time(self.elapsed), self.font_medium, BLUE, (341, 364))
        self.draw_text("TOTAL DEATHS", self.font_small, INK_SOFT, (619, 330))
        self.draw_text(str(self.deaths), self.font_medium, RED, (619, 364))

        if self.deaths == 0:
            rank = "FLAWLESS"
        elif self.deaths < 15:
            rank = "LEGENDARY"
        elif self.deaths < 40:
            rank = "HARDENED SURVIVOR"
        else:
            rank = "TOO STUBBORN TO LOSE"
        self.draw_text(rank, self.font_medium, GOLD_DARK, (SCREEN_W / 2, 430))

        prompt_color = BLUE if self.end_input_delay <= 0.0 else INK_SOFT
        self.draw_text("ENTER · TITLE     R · PLAY AGAIN     Q / ESC · QUIT", self.font_small, prompt_color, (SCREEN_W / 2, 510))

    def draw(self) -> None:
        if self.state == "menu":
            self.draw_menu()
            pygame.display.flip()
            return
        if self.state == "finished":
            self.draw_end_screen()
            pygame.display.flip()
            return

        offset = pygame.Vector2()
        if self.shake > 0.0:
            strength = 7.0 * (self.shake / 0.34)
            offset.update(random.uniform(-strength, strength), random.uniform(-strength, strength))
        self.draw_board(offset)
        tick = pygame.time.get_ticks() / 1000.0
        for index, coin in enumerate(self.level.coins):
            if index not in self.coins_collected:
                self.draw_coin(coin, offset, tick)
        for enemy in self.enemies:
            enemy.draw(self.screen, offset)
        for particle in self.particles:
            particle.draw(self.screen, offset)
        self.draw_player(offset)
        self.draw_hud()

        if self.message_timer > 0.0 and self.state == "playing":
            message = self.font_small.render(self.message, True, WHITE)
            box = message.get_rect(center=(SCREEN_W // 2, HUD_H + 24)).inflate(28, 14)
            layer = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (31, 35, 48, 218), layer.get_rect(), border_radius=8)
            self.screen.blit(layer, box)
            self.screen.blit(message, message.get_rect(center=box.center))

        if self.state == "paused":
            self.draw_overlay("PAUSED", "Press P, Esc, or Enter to continue")
        elif self.state == "level_complete":
            self.draw_overlay("LEVEL CLEAR!", f"Deaths: {self.deaths}   ·   Time: {self.format_time(self.elapsed)}")
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 30)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
