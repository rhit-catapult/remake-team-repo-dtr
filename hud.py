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


def get_stamina_bar_rect():
    """Return the stamina bar rect in the top-right corner."""
    bar_width = 240
    bar_height = 26
    return pygame.Rect(SCREEN_W - bar_width - 20, 46, bar_width, bar_height)


def draw_stamina_bar(surface, bar_rect, ratio, sprinting, time_ms):
    """Draw a clear, labeled sprint/stamina bar."""
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
    """Draw a five-slot hotbar with a clearly highlighted selected slot."""
    slot_size = 48
    gap = 7
    start_x = 16
    start_y = 16

    for slot in range(hotbar_slots):
        slot_rect = pygame.Rect(start_x + slot * (slot_size + gap), start_y, slot_size, slot_size)
        selected = slot == selected_slot
        cx, cy = slot_rect.center

        # Background, and a bold gold highlight (tinted fill, thick border, glow ring)
        pygame.draw.rect(surface, (74, 68, 34) if selected else (40, 40, 52), slot_rect, border_radius=7)
        if selected:
            pygame.draw.rect(surface, (255, 205, 40), slot_rect.inflate(8, 8), 3, border_radius=10)
            pygame.draw.rect(surface, (255, 225, 70), slot_rect, 4, border_radius=7)
        else:
            pygame.draw.rect(surface, (195, 200, 212), slot_rect, 2, border_radius=7)

        # Draw whatever item this slot holds (icons scaled up for the bigger slots)
        item = hotbar_items[slot]
        if item == "star":
            draw_star_shape(surface, cx, cy, 15, (255, 220, 60))
            draw_star_shape(surface, cx, cy, 8, (255, 250, 200))
        elif item == "potion":
            pygame.draw.rect(surface, (150, 96, 48), (cx - 4, cy - 17, 8, 5), border_radius=1)  # cork
            pygame.draw.rect(surface, (215, 228, 240), (cx - 3, cy - 13, 6, 5))                 # neck
            pygame.draw.circle(surface, (232, 240, 250), (cx, cy + 3), 12)                       # glass
            pygame.draw.circle(surface, (206, 44, 54), (cx, cy + 4), 9)                          # liquid
            pygame.draw.circle(surface, (255, 255, 255), (cx - 4, cy), 3)                        # shine
        elif item == "sprint":
            pygame.draw.rect(surface, (120, 120, 150), (cx - 4, cy - 17, 8, 5), border_radius=1)  # cork
            pygame.draw.rect(surface, (215, 228, 240), (cx - 3, cy - 13, 6, 5))                   # neck
            pygame.draw.circle(surface, (232, 240, 250), (cx, cy + 3), 12)                         # glass
            pygame.draw.circle(surface, (40, 140, 220), (cx, cy + 4), 9)                           # blue liquid
            bolt = [(cx + 1, cy - 4), (cx - 4, cy + 4), (cx, cy + 4),
                    (cx - 1, cy + 12), (cx + 5, cy + 1), (cx + 1, cy + 1)]
            pygame.draw.polygon(surface, (255, 240, 120), bolt)                                    # lightning

        # Slot number in the corner so 1-5 selection is obvious
        num = HEALTH_FONT.render(str(slot + 1), True, (255, 240, 160) if selected else (185, 190, 205))
        surface.blit(num, (slot_rect.x + 4, slot_rect.bottom - num.get_height() + 2))


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
