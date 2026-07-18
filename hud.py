"""On-screen UI: hotbar, stamina bar, difficulty menu, and death screen."""
import math

import pygame

from config import *
from fonts import *
from terrain import *
from slime import *
from pickups import *


def draw_boss_banner(surface, alpha):
    """Flash a 'BOSS ZONE' warning across the middle of the screen (alpha 0-255)."""
    alpha = max(0, min(255, int(alpha)))
    if alpha <= 0:
        return
    big = DEATH_FONT_BIG.render("BOSS ZONE", True, (235, 60, 60))
    sub = DEATH_FONT_MED.render("harder hazards ahead!", True, (250, 210, 120))
    big.set_alpha(alpha)
    sub.set_alpha(alpha)
    surface.blit(big, big.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 30)))
    surface.blit(sub, sub.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 30)))


def draw_distance(surface, meters):
    """Draw the run's distance (meters) in a pill at the top-middle of the screen."""
    label = f"{int(meters)} m"

    text = DEATH_FONT_MED.render(label, True, (255, 255, 255))
    shadow = DEATH_FONT_MED.render(label, True, (0, 0, 0))
    pad_x, pad_y = 18, 6
    w = text.get_width() + pad_x * 2
    h = text.get_height() + pad_y * 2
    x = SCREEN_W // 2 - w // 2
    y = 10

    pill = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(pill, (20, 24, 40, 175), pill.get_rect(), border_radius=14)
    pygame.draw.rect(pill, (255, 255, 255, 70), pill.get_rect(), 2, border_radius=14)
    surface.blit(pill, (x, y))
    surface.blit(shadow, (x + pad_x + 1, y + pad_y + 1))
    surface.blit(text, (x + pad_x, y + pad_y))


def draw_runner_icon(surface, bar_rect, time_ms, sprinting):
    """A little running person beside the stamina bar; strides faster when sprinting."""
    cx = bar_rect.x - 24
    cy = bar_rect.centery
    stride_speed = 0.03 if sprinting else 0.009
    swing = math.sin(time_ms * stride_speed)
    color = (90, 225, 130) if sprinting else (210, 216, 228)

    pygame.draw.circle(surface, color, (cx, cy - 10), 4)                 # head
    pygame.draw.line(surface, color, (cx, cy - 6), (cx, cy + 4), 2)     # torso
    # Arms swinging
    pygame.draw.line(surface, color, (cx, cy - 3), (cx + int(swing * 6), cy + 1), 2)
    pygame.draw.line(surface, color, (cx, cy - 3), (cx - int(swing * 6), cy - 4), 2)
    # Legs striding
    pygame.draw.line(surface, color, (cx, cy + 4), (cx + int(swing * 7), cy + 12), 2)
    pygame.draw.line(surface, color, (cx, cy + 4), (cx - int(swing * 7), cy + 12), 2)


def get_stamina_bar_rect():
    """Return the stamina bar rect in the top-right corner."""
    bar_width = 240
    bar_height = 26
    return pygame.Rect(SCREEN_W - bar_width - 20, 46, bar_width, bar_height)


def draw_stamina_bar(surface, bar_rect, ratio, sprinting, time_ms):
    """Draw a clear, labeled sprint/stamina bar with the runner icon beside it."""
    ratio = max(0.0, min(1.0, ratio))

    # Label above the bar
    label = HEALTH_FONT.render("SPRINT", True, (235, 238, 245))
    shadow = HEALTH_FONT.render("SPRINT", True, (0, 0, 0))
    surface.blit(shadow, (bar_rect.x + 1, bar_rect.y - label.get_height() - 1))
    surface.blit(label, (bar_rect.x, bar_rect.y - label.get_height() - 2))

    # Dark track for contrast, bright fill, thick border
    pygame.draw.rect(surface, (28, 30, 40), bar_rect, border_radius=7)
    fill_w = int(bar_rect.width * ratio)
    if fill_w > 0:
        fill_col = (90, 230, 135) if sprinting else (70, 195, 110)
        pygame.draw.rect(surface, fill_col,
                         (bar_rect.x, bar_rect.y, fill_w, bar_rect.height), border_radius=7)
        gloss = pygame.Surface((fill_w, bar_rect.height // 2), pygame.SRCALPHA)
        gloss.fill((255, 255, 255, 55))
        surface.blit(gloss, (bar_rect.x, bar_rect.y))
    pygame.draw.rect(surface, (245, 247, 252), bar_rect, 2, border_radius=7)

    draw_runner_icon(surface, bar_rect, time_ms, sprinting)


def draw_death_screen(surface, meters):
    """'YOU DIED', distance travelled, and a restart hint over the frozen scene."""
    def centered(font, text, color, cy, shadow=(0, 0, 0)):
        sh = font.render(text, True, shadow)
        tx = font.render(text, True, color)
        rect = tx.get_rect(center=(SCREEN_W // 2, cy))
        surface.blit(sh, (rect.x + 2, rect.y + 2))
        surface.blit(tx, rect)

    centered(DEATH_FONT_BIG, "YOU DIED", (215, 55, 55), SCREEN_H // 2 - 70)
    centered(DEATH_FONT_MED, f"Distance travelled: {meters} m", (240, 240, 245), SCREEN_H // 2 + 10)
    centered(HEALTH_FONT, "R to try again    M for difficulty menu", (200, 205, 215), SCREEN_H // 2 + 70)


def draw_hotbar(surface, selected_slot):
    """Draw a five-slot hotbar below the stamina bar."""
    slot_size = 32
    gap = 4
    start_x = 15
    start_y = 15

    for slot in range(hotbar_slots):
        slot_rect = pygame.Rect(start_x + slot * (slot_size + gap), start_y, slot_size, slot_size)
        selected = slot == selected_slot
        border_color = (255, 220, 40) if selected else (255, 255, 255)
        pygame.draw.rect(surface, (45, 45, 55), slot_rect, border_radius=4)
        pygame.draw.rect(surface, border_color, slot_rect, 2, border_radius=4)

        # Draw whatever item this slot holds
        item = hotbar_items[slot]
        if item == "star":
            draw_star_shape(surface, slot_rect.centerx, slot_rect.centery, 10, (255, 220, 60))
            draw_star_shape(surface, slot_rect.centerx, slot_rect.centery, 5.5, (255, 250, 200))
        elif item == "potion":
            fx, fy = slot_rect.centerx, slot_rect.centery
            pygame.draw.rect(surface, (150, 96, 48), (fx - 3, fy - 12, 6, 4), border_radius=1)  # cork
            pygame.draw.rect(surface, (215, 228, 240), (fx - 2, fy - 9, 4, 4))                  # neck
            pygame.draw.circle(surface, (232, 240, 250), (fx, fy + 2), 8)                        # glass
            pygame.draw.circle(surface, (206, 44, 54), (fx, fy + 3), 6)                          # liquid
            pygame.draw.circle(surface, (255, 255, 255), (fx - 3, fy - 1), 2)                    # shine

        # Tiny slot number in the corner so 1-5 selection is obvious
        num = HEALTH_FONT.render(str(slot + 1), True, (210, 210, 220))
        surface.blit(num, (slot_rect.x + 2, slot_rect.bottom - num.get_height() + 2))


def draw_menu(surface, time_ms, difficulty):
    """Difficulty select screen: press 1, 2, or 3."""
    surface.fill((26, 30, 46))
    # Subtle scrolling ground strip at the bottom for flavor
    draw_ground_platform(surface, GROUND_TOP, (time_ms * 0.05) % 480, 0)

    def centered(font, text, color, cy, shadow=(0, 0, 0)):
        sh = font.render(text, True, shadow)
        tx = font.render(text, True, color)
        rect = tx.get_rect(center=(SCREEN_W // 2, cy))
        surface.blit(sh, (rect.x + 2, rect.y + 2))
        surface.blit(tx, rect)

    # Bobbing slime mascot
    bob = int(math.sin(time_ms * 0.004) * 8)
    draw_slime(surface, pygame.Rect(SCREEN_W // 2 - 34, 150 + bob, 68, 54))
    draw_eyes(surface, pygame.Rect(SCREEN_W // 2 - 34, 150 + bob, 68, 54), 0, 0)

    centered(DEATH_FONT_BIG, "SLIME RUN", (120, 230, 120), 90)
    centered(DEATH_FONT_MED, "Choose a difficulty", (235, 235, 245), 260)

    y0 = 330
    for level in (1, 2, 3):
        cfg = DIFFICULTY_SETTINGS[level]
        selected = level == difficulty
        color = (255, 220, 90) if selected else (215, 220, 230)
        label = f"[{level}]  {cfg['name']}"
        centered(DEATH_FONT_MED, label, color, y0 + (level - 1) * 60)

    centered(HEALTH_FONT, "Press 1, 2, or 3 to start", (190, 200, 215), y0 + 210)
    centered(HEALTH_FONT, "Move: A/D or Arrows   Jump: W/Up   Stomp enemies from above",
             (150, 160, 180), y0 + 245)
    centered(HEALTH_FONT, "Grab stars, pick a slot with 1-5, press F for invincibility",
             (150, 160, 180), y0 + 270)
