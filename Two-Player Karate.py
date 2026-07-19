"""
2-Player Karate Fight
---------------------
Player 1 (Red gi):  WASD move | F punch | G kick | R special | T block
Player 2 (Blue gi): Arrows move | K punch | L kick | O special | P block

Punch cycle (F/K): Jab → Cross → Uppercut → …
Kick cycle  (G/L): Front Kick → Roundhouse → Sweep → …
(Chains reset after a short idle gap.)

Press SPACE on the menu to start. First to KO wins.
"""
import math
import sys

import pygame

pygame.init()

# ---------------------------------------------------------------------------
# Display / constants
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 1000, 600
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Karate Duel — 2 Player")
clock = pygame.time.Clock()
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (220, 50, 50)
DARK_RED = (140, 20, 20)
BLUE = (50, 100, 230)
DARK_BLUE = (20, 50, 140)
GOLD = (255, 200, 50)
FLOOR = (90, 70, 50)
FLOOR_LINE = (60, 45, 30)
SKY_TOP = (25, 20, 45)
SKY_BOT = (70, 50, 90)
LANTERN = (255, 120, 40)
WOOD = (100, 65, 40)
HP_BG = (40, 40, 40)
HP_GREEN = (40, 200, 80)
HP_YELLOW = (230, 200, 40)
HP_RED = (220, 60, 40)
GRAY = (160, 160, 160)
DARK_GRAY = (80, 80, 80)
SKIN = (240, 195, 150)
BELT_BLACK = (20, 20, 20)

# Physics
GRAVITY = 0.75
JUMP_STRENGTH = -14
MOVE_SPEED = 5
GROUND_Y = SCREEN_H - 100

# Combat
MAX_HP = 100
SPECIAL_DAMAGE = 22
SPECIAL_RANGE = 90
PUNCH_COOLDOWN = 300
KICK_COOLDOWN = 360
SPECIAL_COOLDOWN = 1800
BLOCK_DAMAGE_MULT = 0.25
HIT_STUN_MS = 320
# Combo chain resets if you wait too long between same-button presses
COMBO_RESET_MS = 900
# Default ranges (overridden per style)
PUNCH_RANGE = 55
KICK_RANGE = 70
# Attack timing defaults (overridden per style)
PUNCH_WINDUP_MS = 90
PUNCH_ACTIVE_MS = 110
PUNCH_RECOVER_MS = 170
KICK_WINDUP_MS = 110
KICK_ACTIVE_MS = 120
KICK_RECOVER_MS = 200
SPECIAL_WINDUP_MS = 100
SPECIAL_ACTIVE_MS = 280
SPECIAL_RECOVER_MS = 160
# Smooth knockback (velocity-based; special aims for ~30px travel)
KNOCKBACK_FRICTION = 0.88
SPECIAL_KNOCKBACK_PX = 30
ATTACK_ACTIVE_MS = PUNCH_ACTIVE_MS  # legacy alias

# ---------------------------------------------------------------------------
# 3-hit punch / kick style cycles
# style index advances 0 → 1 → 2 → 0 each button press
# ---------------------------------------------------------------------------
PUNCH_STYLES = (
    {  # 0 Jab — quick lead-hand poke
        "name": "Jab",
        "damage": 6,
        "range": 48,
        "y_off": 0.32,
        "hit_h": 24,
        "knock_px": 6,
        "lift": -1.5,
        "windup": 55,
        "active": 85,
        "recover": 120,
        "step": 0.6,
    },
    {  # 1 Cross — heavier rear-hand straight
        "name": "Cross",
        "damage": 9,
        "range": 58,
        "y_off": 0.36,
        "hit_h": 28,
        "knock_px": 10,
        "lift": -2.2,
        "windup": 90,
        "active": 110,
        "recover": 160,
        "step": 1.0,
    },
    {  # 2 Uppercut — rising finisher
        "name": "Uppercut",
        "damage": 12,
        "range": 46,
        "y_off": 0.18,
        "hit_h": 40,
        "knock_px": 8,
        "lift": -5.5,
        "windup": 110,
        "active": 120,
        "recover": 200,
        "step": 0.7,
    },
)

KICK_STYLES = (
    {  # 0 Front kick — mid snap
        "name": "Front Kick",
        "damage": 10,
        "range": 64,
        "y_off": 0.48,
        "hit_h": 30,
        "knock_px": 12,
        "lift": -2.8,
        "windup": 90,
        "active": 105,
        "recover": 160,
        "step": 1.0,
    },
    {  # 1 Roundhouse — longer arc, body shot
        "name": "Roundhouse",
        "damage": 13,
        "range": 74,
        "y_off": 0.40,
        "hit_h": 34,
        "knock_px": 15,
        "lift": -3.5,
        "windup": 120,
        "active": 125,
        "recover": 190,
        "step": 1.3,
    },
    {  # 2 Sweep — low trip / launch finisher feel
        "name": "Sweep",
        "damage": 11,
        "range": 68,
        "y_off": 0.72,
        "hit_h": 26,
        "knock_px": 18,
        "lift": -1.2,
        "windup": 100,
        "active": 115,
        "recover": 210,
        "step": 0.9,
    },
)

# Base damage constants used for rough comparisons elsewhere
PUNCH_DAMAGE = PUNCH_STYLES[1]["damage"]
KICK_DAMAGE = KICK_STYLES[0]["damage"]

# Crit combo: 3 consecutive hits unlocks 1.05x, then +0.05x per hit after
CRIT_HIT_THRESHOLD = 3
CRIT_BASE_MULT = 1.05
CRIT_STEP = 0.05

# Fonts
font_title = pygame.font.SysFont("arial", 72, bold=True)
font_large = pygame.font.SysFont("arial", 42, bold=True)
font_med = pygame.font.SysFont("arial", 28)
font_small = pygame.font.SysFont("arial", 20)
font_tiny = pygame.font.SysFont("arial", 16)
font_crit = pygame.font.SysFont("arial", 26, bold=True)
font_asterisk = pygame.font.SysFont("arial", 28, bold=True)


def crit_multiplier_from_hits(consecutive_hits):
    """Return damage multiplier for a hit that is the Nth in a consecutive streak."""
    if consecutive_hits < CRIT_HIT_THRESHOLD:
        return 1.0
    # 3rd hit -> 1.05, 4th -> 1.10, 5th -> 1.15, ...
    return CRIT_BASE_MULT + CRIT_STEP * (consecutive_hits - CRIT_HIT_THRESHOLD)


def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_quad(t):
    t = max(0.0, min(1.0, t))
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def attack_timings(kind, style=0):
    """Return (windup, active, recover) ms for an attack type / style."""
    if kind == "punch":
        s = PUNCH_STYLES[style % 3]
        return s["windup"], s["active"], s["recover"]
    if kind == "kick":
        s = KICK_STYLES[style % 3]
        return s["windup"], s["active"], s["recover"]
    return SPECIAL_WINDUP_MS, SPECIAL_ACTIVE_MS, SPECIAL_RECOVER_MS


def get_attack_style_data(kind, style=0):
    if kind == "punch":
        return PUNCH_STYLES[style % 3]
    if kind == "kick":
        return KICK_STYLES[style % 3]
    return {
        "name": "Dragon Fist",
        "damage": SPECIAL_DAMAGE,
        "range": SPECIAL_RANGE,
        "y_off": 0.25,
        "hit_h": 50,
        "knock_px": SPECIAL_KNOCKBACK_PX,
        "lift": -6.5,
        "step": 2.0,
    }


def knockback_velocity_for_distance(pixels):
    """Initial horizontal speed so friction decay travels about `pixels`."""
    # Sum of geometric series: v + v*f + v*f^2 + ... = v / (1 - f)
    return pixels * (1.0 - KNOCKBACK_FRICTION)


# ---------------------------------------------------------------------------
# Fighter
# ---------------------------------------------------------------------------
class Fighter:
    def __init__(self, x, facing, color, dark_color, name, controls):
        self.spawn_x = x
        self.x = float(x)
        self.y = float(GROUND_Y)
        self.vx = 0.0
        self.vy = 0.0
        self.width = 56
        self.height = 110
        self.facing = facing  # 1 = right, -1 = left
        self.color = color
        self.dark_color = dark_color
        self.name = name
        self.controls = controls

        self.hp = MAX_HP
        self.on_ground = True
        self.crouching = False
        self.blocking = False
        self.alive = True

        self.attack = None  # "punch", "kick", "special"
        self.attack_style = 0  # 0/1/2 within punch or kick cycle
        self.attack_start = 0
        self.hit_this_attack = False
        self.last_punch = -9999
        self.last_kick = -9999
        self.last_special = -9999
        self.stun_until = 0
        self.flash_until = 0

        # Button combo cycles (separate punch / kick 3-chains)
        self.punch_combo = 0  # next punch style to fire (0 jab, 1 cross, 2 uppercut)
        self.kick_combo = 0   # next kick style (0 front, 1 roundhouse, 2 sweep)

        # Combo / crit tracking
        # consecutive_hits: hits this fighter has landed in a row
        # crit_dealt_mult: active crit multiplier (shown on the attacker's side)
        self.consecutive_hits = 0
        self.crit_dealt_mult = 1.0
        self.crit_flash_until = 0

        # Smooth knockback / hit reaction
        self.knockback_vx = 0.0
        self.hit_recoil = 0.0  # visual lean 0..1

        # Animation helpers
        self.anim_t = 0.0
        self.walk_phase = 0.0

    def reset(self):
        self.x = float(self.spawn_x)
        self.y = float(GROUND_Y)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1 if self.spawn_x < SCREEN_W // 2 else -1
        self.hp = MAX_HP
        self.on_ground = True
        self.crouching = False
        self.blocking = False
        self.alive = True
        self.attack = None
        self.attack_style = 0
        self.hit_this_attack = False
        self.last_punch = -9999
        self.last_kick = -9999
        self.last_special = -9999
        self.punch_combo = 0
        self.kick_combo = 0
        self.stun_until = 0
        self.flash_until = 0
        self.consecutive_hits = 0
        self.crit_dealt_mult = 1.0
        self.crit_flash_until = 0
        self.knockback_vx = 0.0
        self.hit_recoil = 0.0

    def rect(self):
        h = self.height * 0.65 if self.crouching else self.height
        return pygame.Rect(int(self.x - self.width / 2), int(self.y - h), self.width, int(h))

    def hitbox(self):
        """Hurtbox used for receiving hits."""
        r = self.rect()
        return r.inflate(-8, -4)

    def attack_elapsed(self, now=None):
        if not self.attack:
            return 0
        if now is None:
            now = pygame.time.get_ticks()
        return now - self.attack_start

    def current_style_data(self):
        if not self.attack:
            return None
        return get_attack_style_data(self.attack, self.attack_style)

    def attack_total_ms(self):
        if not self.attack:
            return 0
        w, a, r = attack_timings(self.attack, self.attack_style)
        return w + a + r

    def attack_phase(self, now=None):
        """Return ('windup'|'active'|'recover'|None, phase_t 0..1, overall_t 0..1)."""
        if not self.attack:
            return None, 0.0, 0.0
        elapsed = self.attack_elapsed(now)
        windup, active, recover = attack_timings(self.attack, self.attack_style)
        total = windup + active + recover
        overall = max(0.0, min(1.0, elapsed / max(1, total)))
        if elapsed < windup:
            return "windup", elapsed / max(1, windup), overall
        if elapsed < windup + active:
            return "active", (elapsed - windup) / max(1, active), overall
        if elapsed < total:
            return "recover", (elapsed - windup - active) / max(1, recover), overall
        return None, 0.0, 1.0

    def attack_extension(self, now=None):
        """0..1 how far a punch/kick is extended (smooth windup → strike → recover)."""
        phase, t, _ = self.attack_phase(now)
        if phase is None:
            return 0.0
        if phase == "windup":
            # Chamber / pull-back: slightly negative feel via low extension
            return 0.15 * (1.0 - ease_out_cubic(t))
        if phase == "active":
            return ease_out_cubic(t)
        # recover: retract
        return 1.0 - ease_in_out_quad(t)

    def attack_hitbox(self):
        if not self.attack:
            return None
        now = pygame.time.get_ticks()
        phase, phase_t, _ = self.attack_phase(now)
        # Only hurt during the active strike (after windup)
        if phase != "active":
            return None
        # Hitbox grows with extension so early active frames are shorter range
        ext = ease_out_cubic(phase_t)
        style = self.current_style_data()
        reach = style["range"]
        hit_h = style["hit_h"]
        y_frac = style["y_off"]

        r = self.rect()
        if self.attack == "punch":
            w, h = int(reach * (0.45 + 0.55 * ext)), hit_h
            y_off = r.height * y_frac
        elif self.attack == "kick":
            w, h = int(reach * (0.4 + 0.6 * ext)), hit_h
            y_off = r.height * y_frac
        else:  # special
            w, h = int(SPECIAL_RANGE * (0.5 + 0.5 * ext)), 50
            y_off = r.height * 0.25

        if self.facing > 0:
            return pygame.Rect(r.right - 10, r.top + int(y_off), w, h)
        return pygame.Rect(r.left - w + 10, r.top + int(y_off), w, h)

    def is_stunned(self):
        return pygame.time.get_ticks() < self.stun_until

    def can_act(self):
        return self.alive and not self.is_stunned() and self.attack is None

    def handle_input(self, keys, now):
        if not self.alive:
            return

        c = self.controls
        self.blocking = False
        self.crouching = False

        # Preserve knockback while stunned — do not zero velocity
        if self.is_stunned():
            return

        move_vx = 0.0

        # Block
        if keys[c["block"]] and self.on_ground and self.attack is None:
            self.blocking = True
            # Light friction when blocking
            self.vx *= 0.7
            return

        # Crouch
        if keys[c["down"]] and self.on_ground and self.attack is None:
            self.crouching = True

        # Horizontal move (reduced while attacking for weight)
        can_move = not self.crouching and (
            self.attack is None or self.attack_phase(now)[0] == "recover"
        )
        if can_move:
            if keys[c["left"]]:
                move_vx = -MOVE_SPEED
                if self.attack is None:
                    self.facing = -1
            if keys[c["right"]]:
                move_vx = MOVE_SPEED
                if self.attack is None:
                    self.facing = 1
        elif self.attack is not None:
            # Tiny step into the punch/kick during active frames
            phase, _, _ = self.attack_phase(now)
            if phase == "active":
                style = self.current_style_data()
                step = style["step"] if style else 0.8
                move_vx = self.facing * step

        # Blend input with residual knockback (knockback decays in update)
        if abs(self.knockback_vx) > 0.3:
            self.vx = self.knockback_vx * 0.65 + move_vx * 0.35
        else:
            self.vx = move_vx

        # Jump
        if keys[c["up"]] and self.on_ground and self.attack is None and not self.crouching:
            self.vy = JUMP_STRENGTH
            self.on_ground = False

    def try_attack(self, kind, now):
        if not self.can_act() or self.blocking or self.crouching:
            return False
        if kind == "punch" and now - self.last_punch >= PUNCH_COOLDOWN:
            # Reset chain if the gap was too long, else continue cycle
            if now - self.last_punch > COMBO_RESET_MS:
                self.punch_combo = 0
            self.attack = "punch"
            self.attack_style = self.punch_combo
            self.attack_start = now
            self.hit_this_attack = False
            self.last_punch = now
            # Advance cycle for next press: Jab → Cross → Uppercut → Jab ...
            self.punch_combo = (self.punch_combo + 1) % 3
            # Switching to kicks resets is independent; punching doesn't reset kick chain
            style = get_attack_style_data("punch", self.attack_style)
            self.vx += self.facing * (1.0 + style["step"] * 0.5)
            return True
        if kind == "kick" and now - self.last_kick >= KICK_COOLDOWN:
            if now - self.last_kick > COMBO_RESET_MS:
                self.kick_combo = 0
            self.attack = "kick"
            self.attack_style = self.kick_combo
            self.attack_start = now
            self.hit_this_attack = False
            self.last_kick = now
            # Front Kick → Roundhouse → Sweep → Front Kick ...
            self.kick_combo = (self.kick_combo + 1) % 3
            style = get_attack_style_data("kick", self.attack_style)
            self.vx += self.facing * (0.9 + style["step"] * 0.4)
            return True
        if kind == "special" and now - self.last_special >= SPECIAL_COOLDOWN:
            self.attack = "special"
            self.attack_style = 0
            self.attack_start = now
            self.hit_this_attack = False
            self.last_special = now
            # Small hop for special
            if self.on_ground:
                self.vy = -6
                self.on_ground = False
            self.vx += self.facing * 2.0
            return True
        return False

    def update(self, now, opponent):
        self.anim_t += 1 / FPS
        self.hit_recoil = max(0.0, self.hit_recoil - 0.045)

        if not self.alive:
            # Collapse
            self.y = min(self.y + 2, GROUND_Y + 20)
            return

        # End attack after full windup+active+recover
        if self.attack:
            if now - self.attack_start > self.attack_total_ms():
                # Whiffed swings break the consecutive-hit crit streak
                if not self.hit_this_attack:
                    self.consecutive_hits = 0
                    self.crit_dealt_mult = 1.0
                self.attack = None
                self.hit_this_attack = False

        # Smooth knockback decay (launched slide, not a teleport)
        if abs(self.knockback_vx) > 0.05:
            self.knockback_vx *= KNOCKBACK_FRICTION
            if abs(self.knockback_vx) < 0.15:
                self.knockback_vx = 0.0
            # While stunned, knockback fully drives horizontal motion
            if self.is_stunned():
                self.vx = self.knockback_vx
        elif self.is_stunned():
            self.vx *= 0.85

        # Physics
        self.vy += GRAVITY
        self.x += self.vx
        self.y += self.vy

        # Ground
        if self.y >= GROUND_Y:
            self.y = GROUND_Y
            self.vy = 0
            self.on_ground = True
            # Slide friction on landing while still carrying knockback
            if abs(self.knockback_vx) > 0.05:
                self.knockback_vx *= 0.92
        else:
            self.on_ground = False

        # Walls
        margin = 30
        self.x = max(margin, min(SCREEN_W - margin, self.x))

        # Face opponent when idle
        if (
            abs(self.vx) < 0.1
            and abs(self.knockback_vx) < 0.1
            and self.attack is None
            and not self.blocking
            and not self.is_stunned()
        ):
            if opponent.x > self.x:
                self.facing = 1
            else:
                self.facing = -1

        # Walk animation — cadence scales a bit with move speed
        if abs(self.vx) > 0.1 and self.on_ground and not self.is_stunned():
            speed_t = min(1.0, abs(self.vx) / MOVE_SPEED)
            self.walk_phase += 0.20 + 0.12 * speed_t
        else:
            self.walk_phase *= 0.82

        # Separate fighters slightly so they don't stack
        if opponent.alive:
            dx = self.x - opponent.x
            min_dist = (self.width + opponent.width) * 0.45
            if abs(dx) < min_dist and abs(self.y - opponent.y) < self.height:
                push = (min_dist - abs(dx)) * 0.5
                if dx >= 0:
                    self.x += push
                    opponent.x -= push
                else:
                    self.x -= push
                    opponent.x += push

    def take_damage(
        self,
        amount,
        attacker_facing,
        now,
        is_special=False,
        is_crit=False,
        knock_px=10,
        lift=-2.5,
    ):
        if not self.alive:
            return 0

        dmg = amount
        if self.blocking and self.on_ground:
            dmg = max(1, int(round(amount * BLOCK_DAMAGE_MULT)))
            # Chip damage only; short block stun + soft shove
            self.stun_until = now + 80
            self.knockback_vx = attacker_facing * 1.8
            self.hit_recoil = min(1.0, self.hit_recoil + 0.25)
        else:
            # Velocity-based launch (no instant teleport)
            if is_special:
                knock_px = SPECIAL_KNOCKBACK_PX
                lift = -6.5
                stun = HIT_STUN_MS + 60
            elif is_crit:
                knock_px = max(knock_px, 16)
                lift = min(lift, -5.0)
                stun = HIT_STUN_MS + 80
            else:
                stun = HIT_STUN_MS

            speed = knockback_velocity_for_distance(knock_px)
            if is_special:
                speed = max(speed, 3.8)

            self.stun_until = now + stun
            self.knockback_vx = attacker_facing * speed
            self.vx = self.knockback_vx
            self.vy = lift
            self.on_ground = False
            self.hit_recoil = 1.0 if is_special or is_crit else 0.7
            self.attack = None

        self.hp = max(0, self.hp - dmg)
        self.flash_until = now + (200 if is_crit else 120)
        if is_crit:
            self.crit_flash_until = now + 350
        if self.hp <= 0:
            self.alive = False
            self.hp = 0
            self.attack = None
        return dmg

    def draw(self, surface, now):
        r = self.rect()
        flash = now < self.flash_until
        body = WHITE if flash else self.color
        outline = self.dark_color
        f = self.facing

        # Hit recoil lean + attack body lean (visual only)
        lean = int(-self.hit_recoil * 10 * (1 if self.knockback_vx >= 0 else -1))
        if abs(self.knockback_vx) > 0.2:
            lean = int(-8 * (1 if self.knockback_vx > 0 else -1) * min(1.0, abs(self.knockback_vx) / 4))
        atk_lean = 0
        if self.attack:
            ext = self.attack_extension(now)
            style_i = self.attack_style
            if self.attack == "kick":
                lean_amt = (3, 5, 2)[style_i % 3]  # roundhouse leans more
            elif self.attack == "punch":
                lean_amt = (2, 4, 5)[style_i % 3]  # uppercut leans in
            else:
                lean_amt = 4
            atk_lean = int(f * lean_amt * ext)
            # Uppercut rises slightly
            if self.attack == "punch" and style_i == 2:
                atk_lean = int(f * 3 * ext)
        draw_ox = lean + atk_lean
        draw_oy = 0
        if self.attack == "punch" and self.attack_style == 2:
            draw_oy = -int(8 * self.attack_extension(now))

        # Shadow - larger for bigger build
        sh_w = int(self.width * (0.9 if self.on_ground else 0.55))
        pygame.draw.ellipse(
            surface,
            (0, 0, 0, 60),
            (int(self.x - sh_w // 2), GROUND_Y - 10, sh_w, 16),
        )

        # Body geometry first (legs need hip at torso bottom)
        body_top_width = r.width - 6
        body_waist_width = r.width - 30  # Narrow athletic waist
        body_height = r.height - 38
        body_y = r.y + 24 + draw_oy
        body_x = r.x + draw_ox

        if self.crouching:
            body_height = max(24, body_height - 12)
            body_y += 10
            body_top_width = r.width - 8
            body_waist_width = r.width - 24

        shoulder_y = body_y
        waist_y = body_y + body_height * 0.55
        bottom_y = body_y + body_height
        hip_flare = 3  # slight widen at hips below the belt

        hip = (r.centerx + draw_ox, int(bottom_y) - 6)
        leg_y = r.bottom - 4
        leg_bob = int(math.sin(self.walk_phase) * 6) if abs(self.vx) > 0.1 and not self.is_stunned() else 0
        leg_spread = 12 if not self.crouching else 7

        # Legs (animated kick chamber / extension — style-dependent)
        kick_ext = self.attack_extension(now) if self.attack == "kick" else 0.0
        if self.attack == "kick" and kick_ext > 0.02:
            phase, phase_t, _ = self.attack_phase(now)
            style = self.attack_style % 3
            reach = get_attack_style_data("kick", style)["range"]
            plant = (hip[0] - int(leg_spread * 0.6) * f, leg_y)

            if style == 0:
                # Front kick: chamber mid, thrust straight
                if phase == "windup":
                    chamber = ease_out_cubic(phase_t)
                    foot = (hip[0] + int(10 * f), hip[1] + int(4 - 22 * chamber))
                else:
                    foot = (
                        hip[0] + int((16 + reach * 0.72 * kick_ext) * f),
                        hip[1] + int(4 + 8 * kick_ext),
                    )
            elif style == 1:
                # Roundhouse: leg swings in an arc (high chamber → whip around)
                if phase == "windup":
                    chamber = ease_out_cubic(phase_t)
                    foot = (
                        hip[0] + int((-8 + 20 * chamber) * f),
                        hip[1] + int(-6 - 30 * chamber),
                    )
                else:
                    ang = -0.9 + 1.5 * kick_ext  # arc from up to forward-down
                    foot = (
                        hip[0] + int((math.cos(ang) * reach * 0.85) * f),
                        hip[1] + int(math.sin(ang) * reach * 0.55 + 10),
                    )
            else:
                # Sweep: low horizontal scythe
                if phase == "windup":
                    chamber = ease_out_cubic(phase_t)
                    foot = (
                        hip[0] + int((-6 + 8 * chamber) * f),
                        leg_y - int(6 + 10 * chamber),
                    )
                else:
                    foot = (
                        hip[0] + int((14 + reach * 0.78 * kick_ext) * f),
                        leg_y - int(4 * (1.0 - kick_ext)),
                    )

            knee = (
                (hip[0] + foot[0]) // 2 - int(6 * f * (1.0 - kick_ext)),
                (hip[1] + foot[1]) // 2 - (12 if style == 1 else 8),
            )
            pygame.draw.line(surface, outline, hip, plant, 8)
            pygame.draw.circle(surface, BELT_BLACK, plant, 6)
            pygame.draw.line(surface, outline, hip, knee, 9)
            pygame.draw.line(surface, outline, knee, foot, 9)
            pygame.draw.circle(surface, BELT_BLACK, foot, 9)
        else:
            left_leg = (r.centerx + draw_ox - leg_spread - leg_bob // 2, leg_y)
            right_leg = (r.centerx + draw_ox + leg_spread + leg_bob // 2, leg_y)
            # Hit reaction: feet drag slightly opposite launch
            if self.hit_recoil > 0.2:
                drag = int(self.hit_recoil * 4)
                left_leg = (left_leg[0] - drag * (1 if self.knockback_vx > 0 else -1), left_leg[1])
                right_leg = (right_leg[0] - drag * (1 if self.knockback_vx > 0 else -1), right_leg[1])
            pygame.draw.line(surface, outline, hip, left_leg, 8)
            pygame.draw.line(surface, outline, hip, right_leg, 8)
            pygame.draw.circle(surface, BELT_BLACK, left_leg, 6)
            pygame.draw.circle(surface, BELT_BLACK, right_leg, 6)

        # Gi torso — broad shoulders, narrow waist
        body_points = [
            (body_x + (r.width - body_top_width) // 2, shoulder_y),
            (body_x + r.width - (r.width - body_top_width) // 2, shoulder_y),
            (body_x + r.width - (r.width - body_waist_width) // 2, waist_y),
            (body_x + r.width - (r.width - body_waist_width) // 2 + hip_flare, bottom_y),
            (body_x + (r.width - body_waist_width) // 2 - hip_flare, bottom_y),
            (body_x + (r.width - body_waist_width) // 2, waist_y),
        ]

        pygame.draw.polygon(surface, body, body_points)
        pygame.draw.polygon(surface, outline, body_points, 2)

        body_rect = pygame.Rect(
            body_x + (r.width - body_top_width) // 2,
            shoulder_y,
            body_top_width,
            body_height,
        )

        # Belt sits on the narrow waist (body_x already includes lean)
        belt_width = body_waist_width + 2
        belt_x = body_x + (r.width - belt_width) // 2
        pygame.draw.rect(surface, BELT_BLACK, (belt_x, waist_y, belt_width, 7))
        pygame.draw.line(
            surface, BELT_BLACK,
            (belt_x + belt_width // 2, waist_y + 7),
            (belt_x + belt_width // 2 - 5 * f, waist_y + 20), 3,
        )

        # Head
        head_r = 18 if not self.crouching else 16
        head_cx = r.centerx + draw_ox
        head_cy = body_y - head_r + 2  # body_y already includes draw_oy
        # Recoil tip head back slightly
        head_cx += int(-self.hit_recoil * 5 * (1 if self.knockback_vx >= 0 else -1))
        pygame.draw.circle(surface, SKIN, (head_cx, head_cy), head_r)
        pygame.draw.circle(surface, outline, (head_cx, head_cy), head_r, 2)

        eye_dx = 6 * f
        pygame.draw.circle(surface, BLACK, (head_cx + eye_dx - 5, head_cy - 1), 2)
        pygame.draw.circle(surface, BLACK, (head_cx + eye_dx + 5, head_cy - 1), 2)

        pygame.draw.arc(
            surface, self.dark_color,
            (head_cx - head_r, head_cy - head_r, head_r * 2, head_r * 2),
            0.2, math.pi - 0.2, 3,
        )

        # Arms / attack poses
        self._draw_arms(surface, r, body_rect, outline, now)

        # Move name tag during attacks (helps read the 3-hit cycle)
        if self.attack in ("punch", "kick") and self.attack_phase(now)[0] in (
            "windup",
            "active",
        ):
            style = self.current_style_data()
            if style:
                tag = font_tiny.render(style["name"], True, GOLD)
                surface.blit(tag, (r.centerx - tag.get_width() // 2, r.y - 22 + draw_oy))

        # Block pose shield
        if self.blocking:
            bx = body_rect.right - 4 if f > 0 else body_rect.left - 14
            shield = pygame.Rect(bx, body_rect.y, 18, body_rect.height - 8)
            s = pygame.Surface((shield.width, shield.height), pygame.SRCALPHA)
            s.fill((*self.color, 90))
            surface.blit(s, shield.topleft)
            pygame.draw.rect(surface, GOLD, shield, 2, border_radius=4)

        # Special VFX
        if self.attack == "special":
            self._draw_special_fx(surface, now)

        # Crit hit flash ring on victim
        if now < self.crit_flash_until:
            t = 1.0 - (self.crit_flash_until - now) / 350.0
            rad = int(30 + 50 * t)
            alpha = int(200 * (1.0 - t))
            ring = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (0, 0, 0, alpha), (rad + 2, rad + 2), rad, 4)
            pygame.draw.circle(ring, (255, 255, 255, alpha // 2), (rad + 2, rad + 2), max(1, rad - 8), 2)
            surface.blit(ring, (r.centerx - rad - 2, r.centery - rad - 2))

        # KO mark
        if not self.alive:
            ko = font_med.render("KO", True, GOLD)
            surface.blit(ko, (r.centerx - ko.get_width() // 2, r.y - 36))

    def _draw_arms(self, surface, r, body_rect, outline, now):
        # Separate shoulder points on each side of the torso - positioned at broader shoulders
        shoulder_l = (body_rect.left + 2, body_rect.y + 18)
        shoulder_r = (body_rect.right - 2, body_rect.y + 18)
        f = self.facing
        ext = self.attack_extension(now)
        phase, phase_t, _ = self.attack_phase(now)
        style_i = self.attack_style % 3

        if self.attack == "punch":
            reach_base = get_attack_style_data("punch", style_i)["range"]
            # Jab/uppercut use lead hand; cross uses rear hand
            lead_shoulder = shoulder_r if f > 0 else shoulder_l
            rear_shoulder = shoulder_l if f > 0 else shoulder_r
            punch_shoulder = rear_shoulder if style_i == 1 else lead_shoulder
            back_shoulder = lead_shoulder if style_i == 1 else rear_shoulder
            if style_i == 0:
                # Jab — lead hand snaps from cheek guard
                if phase == "windup":
                    pull = ease_out_cubic(phase_t)
                    fist = (
                        punch_shoulder[0] + int((10 - 6 * pull) * f),
                        punch_shoulder[1] + int(-2 + 4 * pull),
                    )
                    elbow = (punch_shoulder[0] + int(5 * f), punch_shoulder[1] + 6)
                else:
                    reach = reach_base * (0.4 + 0.6 * ext)
                    fist = (punch_shoulder[0] + int(reach * f), punch_shoulder[1] + int(-2 + 2 * (1 - ext)))
                    elbow = (punch_shoulder[0] + int(reach * 0.4 * f), punch_shoulder[1] + 4)
                back = (back_shoulder[0] - int(8 * f), back_shoulder[1] + 16)
            elif style_i == 1:
                # Cross — rear hand from hip/shoulder, longer line
                if phase == "windup":
                    pull = ease_out_cubic(phase_t)
                    fist = (
                        punch_shoulder[0] + int((-18 - 8 * pull) * f),
                        punch_shoulder[1] + int(10 + 6 * pull),
                    )
                    elbow = (
                        punch_shoulder[0] + int((-10 - 4 * pull) * f),
                        punch_shoulder[1] + int(12 + 2 * pull),
                    )
                else:
                    reach = reach_base * (0.35 + 0.65 * ext)
                    fist = (punch_shoulder[0] + int(reach * f), punch_shoulder[1] + int(2 + 3 * (1 - ext)))
                    elbow = (
                        punch_shoulder[0] + int(reach * 0.5 * f),
                        punch_shoulder[1] + int(8 * (1.0 - ext * 0.6)),
                    )
                back = (back_shoulder[0] + int((-8 + 6 * ext) * f), back_shoulder[1] + int(18 - 4 * ext))
            else:
                # Uppercut — fist drops then rockets upward along body line
                if phase == "windup":
                    pull = ease_out_cubic(phase_t)
                    fist = (
                        punch_shoulder[0] + int((6 - 2 * pull) * f),
                        punch_shoulder[1] + int(24 + 10 * pull),
                    )
                    elbow = (punch_shoulder[0] + int(3 * f), punch_shoulder[1] + int(16 + 6 * pull))
                else:
                    up = ext
                    fist = (
                        punch_shoulder[0] + int((12 + reach_base * 0.35 * up) * f),
                        punch_shoulder[1] + int(26 - 42 * up),
                    )
                    elbow = (
                        punch_shoulder[0] + int((8 + 8 * up) * f),
                        punch_shoulder[1] + int(18 - 18 * up),
                    )
                back = (back_shoulder[0] - int(6 * f), back_shoulder[1] + 12)

            pygame.draw.line(surface, outline, punch_shoulder, elbow, 8)
            pygame.draw.line(surface, outline, elbow, fist, 9)
            pygame.draw.circle(surface, SKIN, fist, 10)
            pygame.draw.circle(surface, outline, fist, 10, 2)
            pygame.draw.line(surface, outline, back_shoulder, back, 7)
            pygame.draw.circle(surface, SKIN, back, 7)

        elif self.attack == "kick":
            # Hands for balance — lead/back by facing (not always left/right)
            lead_s = shoulder_r if f > 0 else shoulder_l
            back_s = shoulder_l if f > 0 else shoulder_r
            if style_i == 0:
                # Front kick: hands up lightly
                guard_y = (-6 - 8 * phase_t) if phase == "windup" else (-12 + 6 * ext)
                hand_f = (lead_s[0] + int(14 * f), lead_s[1] + int(guard_y))
                hand_b = (back_s[0] - int(10 * f), back_s[1] + int(10 + guard_y * 0.2))
            elif style_i == 1:
                # Roundhouse: opposite arm swings for counterbalance
                if phase == "windup":
                    hand_f = (back_s[0] - int(16 * f), back_s[1] - int(8 + 10 * phase_t))
                    hand_b = (lead_s[0] + int(8 * f), lead_s[1] + 12)
                else:
                    hand_f = (back_s[0] - int((18 - 6 * ext) * f), back_s[1] - int(14 - 4 * ext))
                    hand_b = (lead_s[0] + int(12 * f), lead_s[1] + int(6 + 4 * ext))
            else:
                # Sweep: low guard, arms dip with the body
                hand_f = (lead_s[0] + int(12 * f), lead_s[1] + int(14 - 4 * ext))
                hand_b = (back_s[0] - int(8 * f), back_s[1] + int(18 - 2 * ext))
            pygame.draw.line(surface, outline, lead_s, hand_f, 7)
            pygame.draw.line(surface, outline, back_s, hand_b, 7)
            pygame.draw.circle(surface, SKIN, hand_f, 7)
            pygame.draw.circle(surface, SKIN, hand_b, 7)

        elif self.attack == "special":
            reach = SPECIAL_RANGE * (0.4 + 0.55 * ext)
            for i, (shoulder_pt, yoff) in enumerate(zip((shoulder_r, shoulder_l), (-10, 14))):
                tip = (shoulder_pt[0] + int(reach * f), shoulder_pt[1] + yoff)
                mid = (shoulder_pt[0] + int(reach * 0.5 * f), shoulder_pt[1] + yoff // 2)
                pygame.draw.line(surface, outline, shoulder_pt, mid, 8)
                pygame.draw.line(surface, outline, mid, tip, 8)
                pygame.draw.circle(surface, GOLD if i == 0 else SKIN, tip, 9)

        elif self.blocking:
            guard1 = (shoulder_r[0] + 12 * f, shoulder_r[1] - 5)
            guard2 = (shoulder_l[0] + 10 * f, shoulder_l[1] + 18)
            pygame.draw.line(surface, outline, shoulder_r, guard1, 8)
            pygame.draw.line(surface, outline, shoulder_l, guard2, 8)
            pygame.draw.circle(surface, SKIN, guard1, 8)
            pygame.draw.circle(surface, SKIN, guard2, 8)

        elif self.is_stunned() or self.hit_recoil > 0.15:
            # Arms flail slightly on hit
            flail = int(self.hit_recoil * 12)
            hand_f = (shoulder_r[0] + int((10 + flail) * f), shoulder_r[1] + 8 - flail)
            hand_b = (shoulder_l[0] - int((8 + flail * 0.5) * f), shoulder_l[1] + 16)
            pygame.draw.line(surface, outline, shoulder_r, hand_f, 7)
            pygame.draw.line(surface, outline, shoulder_l, hand_b, 7)
            pygame.draw.circle(surface, SKIN, hand_f, 7)
            pygame.draw.circle(surface, SKIN, hand_b, 7)

        else:
            # Idle guard or walking arm swing (bent elbows, opposite-phase stride)
            walking = (
                abs(self.vx) > 0.15
                and self.on_ground
                and not self.crouching
                and abs(self.walk_phase) > 0.02
            )
            if walking:
                intensity = min(1.0, abs(self.vx) / MOVE_SPEED)
                s = math.sin(self.walk_phase)
                # Right arm opposite left (and opposite the leg bob on that side)
                for shoulder, side, phase in (
                    (shoulder_r, 1, -1.0),
                    (shoulder_l, -1, 1.0),
                ):
                    t = s * phase  # -1..1, positive = forward along facing
                    fwd = t * (11 + 9 * intensity)
                    # Pendulum: hang lower at mid-swing, lift slightly at extremes
                    hang = 11 + 3 * intensity + (1.0 - abs(t)) * 4
                    hand_drop = 20 + 5 * intensity - abs(t) * 6
                    elbow = (
                        shoulder[0] + int(fwd * 0.42 * f) + side * 3,
                        shoulder[1] + int(hang),
                    )
                    hand = (
                        shoulder[0] + int(fwd * f) + side * 5,
                        shoulder[1] + int(hand_drop),
                    )
                    pygame.draw.line(surface, outline, shoulder, elbow, 7)
                    pygame.draw.line(surface, outline, elbow, hand, 7)
                    pygame.draw.circle(surface, SKIN, hand, 7)
            else:
                # Soft idle guard with a light breath so arms aren't frozen
                breath = math.sin(self.anim_t * 2.4) * 1.8
                elbow_r = (shoulder_r[0] + int(5 * f) + 2, shoulder_r[1] + int(10 + breath * 0.4))
                elbow_l = (shoulder_l[0] + int(4 * f) - 2, shoulder_l[1] + int(12 - breath * 0.3))
                hand_r = (shoulder_r[0] + int(10 * f) + 3, shoulder_r[1] + int(16 + breath))
                hand_l = (shoulder_l[0] + int(8 * f) - 3, shoulder_l[1] + int(20 - breath * 0.6))
                pygame.draw.line(surface, outline, shoulder_r, elbow_r, 7)
                pygame.draw.line(surface, outline, elbow_r, hand_r, 7)
                pygame.draw.line(surface, outline, shoulder_l, elbow_l, 7)
                pygame.draw.line(surface, outline, elbow_l, hand_l, 7)
                pygame.draw.circle(surface, SKIN, hand_r, 7)
                pygame.draw.circle(surface, SKIN, hand_l, 7)

    def _draw_special_fx(self, surface, now):
        phase, phase_t, overall = self.attack_phase(now)
        if phase is None:
            return
        # VFX strongest during active extension
        ext = self.attack_extension(now)
        r = self.rect()
        cx = r.centerx + int(self.facing * (20 + SPECIAL_RANGE * 0.5 * ext))
        cy = r.centery - 10
        radius = int(12 + 36 * ext)
        alpha_scale = 0.35 if phase == "windup" else (0.9 if phase == "active" else 0.4)
        for i, alpha_mult in enumerate((0.35, 0.55, 0.8)):
            rad = radius - i * 10
            if rad <= 0:
                continue
            s = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            col = (*GOLD, int(180 * alpha_mult * alpha_scale * (0.5 + 0.5 * ext)))
            pygame.draw.circle(s, col, (rad, rad), rad, 3)
            surface.blit(s, (cx - rad, cy - rad))
        if phase == "active":
            for i in range(5):
                ang = (i / 5) * math.pi * 2 + overall * 4
                x2 = cx + int(math.cos(ang) * radius)
                y2 = cy + int(math.sin(ang) * radius * 0.6)
                pygame.draw.line(surface, GOLD, (cx, cy), (x2, y2), 2)


# ---------------------------------------------------------------------------
# Particles for hit feedback
# ---------------------------------------------------------------------------
class Particle:
    def __init__(self, x, y, color):
        self.x = float(x)
        self.y = float(y)
        angle = math.radians(pygame.time.get_ticks() % 360 + (hash((x, y)) % 90))
        speed = 2 + (hash((int(x), int(y))) % 5)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 2
        self.life = 25
        self.color = color
        self.size = 4 + hash((int(x * 3), int(y))) % 4

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.2
        self.life -= 1

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = max(0, min(255, self.life * 10))
        s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color[:3], alpha), (self.size, self.size), self.size)
        surface.blit(s, (int(self.x - self.size), int(self.y - self.size)))


class CritAsterisk:
    """Black asterisk that bursts outward from the hit and fades out."""

    def __init__(self, x, y, angle, speed):
        self.x = float(x)
        self.y = float(y)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.age = 0
        self.max_life = 36
        self.spin = (speed * 0.04) * (1 if hash((int(x), int(y * 5))) % 2 == 0 else -1)
        self.angle = 0.0
        self.alive = True
        self._base = font_asterisk.render("*", True, BLACK)

    def update(self):
        self.age += 1
        # Burst outward, then slow a bit
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.vy += 0.08  # slight gravity so the burst settles
        self.angle += self.spin
        if self.age > self.max_life:
            self.alive = False

    def draw(self, surface):
        if not self.alive:
            return
        life_t = self.age / self.max_life
        alpha = int(255 * max(0.0, 1.0 - life_t))
        if alpha <= 0:
            return
        scale = 1.0 + 0.25 * life_t
        w = max(1, int(self._base.get_width() * scale))
        h = max(1, int(self._base.get_height() * scale))
        scaled = pygame.transform.smoothscale(self._base, (w, h))
        if abs(self.angle) > 0.01:
            scaled = pygame.transform.rotate(scaled, math.degrees(self.angle))
        scaled.set_alpha(alpha)
        rect = scaled.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(scaled, rect.topleft)


def spawn_crit_asterisk_burst(asterisks, cx, cy):
    """Spawn 4–6 black asterisks bursting outward from the punch impact."""
    count = 4 + (hash((int(cx), int(cy), pygame.time.get_ticks())) % 3)  # 4, 5, or 6
    base_angle = (pygame.time.get_ticks() % 360) * math.pi / 180.0
    for i in range(count):
        # Evenly spaced around the impact, with a little jitter
        angle = base_angle + (i / count) * math.pi * 2
        angle += ((hash((i, int(cx))) % 20) - 10) * 0.03
        speed = 3.5 + (hash((i, int(cy))) % 100) / 100.0 * 2.5  # ~3.5–6.0
        asterisks.append(CritAsterisk(cx, cy, angle, speed))


def spawn_crit_burst(particles, cx, cy, mult):
    """Extra spark particles when a crit lands."""
    count = 12 + int((mult - 1.0) * 40)
    for i in range(count):
        particles.append(Particle(cx, cy, BLACK if i % 2 == 0 else GOLD))


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_dojo(surface, frame):
    """Paint a simple dojo background."""
    # Sky gradient
    for y in range(GROUND_Y):
        t = y / GROUND_Y
        r = int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * t)
        g = int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * t)
        b = int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (SCREEN_W, y))

    # Back wall panels
    pygame.draw.rect(surface, (55, 40, 35), (0, 80, SCREEN_W, GROUND_Y - 80))
    for i in range(0, SCREEN_W, 80):
        pygame.draw.line(surface, WOOD, (i, 80), (i, GROUND_Y), 3)

    # Horizontal wood beams
    pygame.draw.rect(surface, WOOD, (0, 80, SCREEN_W, 18))
    pygame.draw.rect(surface, WOOD, (0, GROUND_Y - 30, SCREEN_W, 12))

    # Paper lanterns
    for lx in (120, 350, 650, 880):
        sway = int(math.sin(frame * 0.03 + lx) * 3)
        pygame.draw.line(surface, (40, 30, 20), (lx, 98), (lx + sway, 130), 2)
        pygame.draw.ellipse(surface, LANTERN, (lx - 14 + sway, 125, 28, 36))
        pygame.draw.ellipse(surface, (255, 180, 80), (lx - 10 + sway, 130, 20, 24))
        pygame.draw.rect(surface, (60, 40, 20), (lx - 16 + sway, 122, 32, 6))

    # Center emblem
    cx, cy = SCREEN_W // 2, 200
    pygame.draw.circle(surface, (80, 50, 40), (cx, cy), 50, 3)
    pygame.draw.circle(surface, (120, 40, 40), (cx, cy), 28)
    kanji = font_large.render("武", True, GOLD)
    surface.blit(kanji, (cx - kanji.get_width() // 2, cy - kanji.get_height() // 2))

    # Floor
    pygame.draw.rect(surface, FLOOR, (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
    for i in range(0, SCREEN_W, 40):
        pygame.draw.line(surface, FLOOR_LINE, (i, GROUND_Y), (i + 20, SCREEN_H), 1)
    pygame.draw.line(surface, GOLD, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 3)
    # Mat center circle
    pygame.draw.ellipse(surface, (70, 55, 40), (SCREEN_W // 2 - 80, GROUND_Y + 20, 160, 40), 2)


def draw_hp_bar(surface, x, y, w, h, hp, max_hp, color, align_right=False):
    ratio = max(0, hp / max_hp)
    fill_w = int(w * ratio)
    if ratio > 0.5:
        fill_col = HP_GREEN
    elif ratio > 0.25:
        fill_col = HP_YELLOW
    else:
        fill_col = HP_RED

    pygame.draw.rect(surface, HP_BG, (x - 2, y - 2, w + 4, h + 4), border_radius=4)
    pygame.draw.rect(surface, DARK_GRAY, (x, y, w, h), border_radius=3)
    if fill_w > 0:
        if align_right:
            fx = x + w - fill_w
        else:
            fx = x
        pygame.draw.rect(surface, fill_col, (fx, y, fill_w, h), border_radius=3)
    # Accent border
    pygame.draw.rect(surface, color, (x - 2, y - 2, w + 4, h + 4), 2, border_radius=4)


def draw_crit_multiplier_badge(surface, fighter, side, now):
    """Show the crit multiplier on the side of the player dealing the crit."""
    mult = fighter.crit_dealt_mult
    if mult <= 1.0:
        return

    pulse = 1.0 + 0.06 * math.sin(now * 0.012)
    label = f"CRIT  x{mult:.2f}"
    text = font_crit.render(label, True, BLACK)
    # Gold outline via multi-blit
    outline = font_crit.render(label, True, GOLD)
    w, h = text.get_width(), text.get_height()
    pad_x, pad_y = 12, 8
    badge_w = int((w + pad_x * 2) * pulse)
    badge_h = int((h + pad_y * 2) * pulse)

    # Side of screen for the attacker
    if side == "left":
        bx = 30
    else:
        bx = SCREEN_W - 30 - badge_w
    by = 88

    badge = pygame.Surface((badge_w, badge_h), pygame.SRCALPHA)
    badge.fill((255, 255, 255, 210))
    pygame.draw.rect(badge, BLACK, (0, 0, badge_w, badge_h), 3, border_radius=8)
    # Inner accent
    pygame.draw.rect(badge, GOLD, (3, 3, badge_w - 6, badge_h - 6), 2, border_radius=6)
    surface.blit(badge, (bx, by))

    tx = bx + (badge_w - w) // 2
    ty = by + (badge_h - h) // 2
    # Soft outline
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        surface.blit(outline, (tx + ox, ty + oy))
    surface.blit(text, (tx, ty))

    # Combo stars under badge
    stars = min(8, max(1, int(round((mult - 1.0) / CRIT_STEP))))
    star_txt = font_small.render("*" * stars, True, BLACK)
    if side == "left":
        surface.blit(star_txt, (bx, by + badge_h + 4))
    else:
        surface.blit(star_txt, (bx + badge_w - star_txt.get_width(), by + badge_h + 4))


def draw_hud(surface, p1, p2, now):
    # Names
    n1 = font_small.render(p1.name, True, RED)
    n2 = font_small.render(p2.name, True, BLUE)
    surface.blit(n1, (30, 12))
    surface.blit(n2, (SCREEN_W - 30 - n2.get_width(), 12))

    draw_hp_bar(surface, 30, 36, 320, 22, p1.hp, MAX_HP, RED, align_right=False)
    draw_hp_bar(surface, SCREEN_W - 350, 36, 320, 22, p2.hp, MAX_HP, BLUE, align_right=True)

    # VS badge
    vs = font_med.render("VS", True, GOLD)
    surface.blit(vs, (SCREEN_W // 2 - vs.get_width() // 2, 28))

    # Special cooldowns
    def special_ready(fighter, sx):
        cd = max(0, SPECIAL_COOLDOWN - (now - fighter.last_special))
        ready = cd <= 0
        label = "SPECIAL READY" if ready else f"SPECIAL {cd // 100 / 10:.1f}s"
        col = GOLD if ready else GRAY
        txt = font_tiny.render(label, True, col)
        surface.blit(txt, (sx, 64))

    special_ready(p1, 30)
    # measure for right side
    cd2 = max(0, SPECIAL_COOLDOWN - (now - p2.last_special))
    ready2 = cd2 <= 0
    label2 = "SPECIAL READY" if ready2 else f"SPECIAL {cd2 // 100 / 10:.1f}s"
    t2 = font_tiny.render(label2, True, GOLD if ready2 else GRAY)
    surface.blit(t2, (SCREEN_W - 30 - t2.get_width(), 64))

    # Crit multiplier shown on the attacker who is dealing the crit
    draw_crit_multiplier_badge(surface, p1, "left", now)
    draw_crit_multiplier_badge(surface, p2, "right", now)


def draw_menu(surface, frame):
    draw_dojo(surface, frame)

    # Dark overlay
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surface.blit(overlay, (0, 0))

    # Title with pulse
    pulse = 1.0 + 0.04 * math.sin(frame * 0.08)
    title = font_title.render("KARATE DUEL", True, GOLD)
    tw = int(title.get_width() * pulse)
    th = int(title.get_height() * pulse)
    title_scaled = pygame.transform.smoothscale(title, (max(1, tw), max(1, th)))
    surface.blit(title_scaled, (SCREEN_W // 2 - tw // 2, 70))

    sub = font_med.render("2-Player Local Fight", True, WHITE)
    surface.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 160))

    # Control cards
    card_w, card_h = 380, 260
    y0 = 210
    # P1 card
    c1 = pygame.Rect(70, y0, card_w, card_h)
    c2 = pygame.Rect(SCREEN_W - 70 - card_w, y0, card_w, card_h)
    for rect, col in ((c1, RED), (c2, BLUE)):
        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        s.fill((20, 20, 30, 200))
        surface.blit(s, rect.topleft)
        pygame.draw.rect(surface, col, rect, 3, border_radius=10)

    p1t = font_med.render("PLAYER 1 — Red", True, RED)
    p2t = font_med.render("PLAYER 2 — Blue", True, BLUE)
    surface.blit(p1t, (c1.x + 20, c1.y + 16))
    surface.blit(p2t, (c2.x + 20, c2.y + 16))

    p1_lines = [
        "A / D  — Move left / right",
        "W      — Jump",
        "S      — Crouch",
        "F      — Punch (Jab→Cross→Upper)",
        "G      — Kick (Front→Round→Sweep)",
        "R      — Special (Dragon Fist)",
        "T      — Block",
    ]
    p2_lines = [
        "← / →  — Move left / right",
        "↑      — Jump",
        "↓      — Crouch",
        "K      — Punch (Jab→Cross→Upper)",
        "L      — Kick (Front→Round→Sweep)",
        "O      — Special (Dragon Fist)",
        "P      — Block",
    ]
    for i, line in enumerate(p1_lines):
        t = font_small.render(line, True, WHITE)
        surface.blit(t, (c1.x + 28, c1.y + 60 + i * 26))
    for i, line in enumerate(p2_lines):
        t = font_small.render(line, True, WHITE)
        surface.blit(t, (c2.x + 28, c2.y + 60 + i * 26))

    # Blink prompt
    if (frame // 30) % 2 == 0:
        prompt = font_large.render("Press SPACE to Fight!", True, WHITE)
        surface.blit(prompt, (SCREEN_W // 2 - prompt.get_width() // 2, 500))
    else:
        prompt = font_large.render("Press SPACE to Fight!", True, GOLD)
        surface.blit(prompt, (SCREEN_W // 2 - prompt.get_width() // 2, 500))

    tip = font_tiny.render("ESC returns to menu  ·  First to KO wins", True, GRAY)
    surface.blit(tip, (SCREEN_W // 2 - tip.get_width() // 2, 560))


def draw_game_over(surface, winner_name, winner_color, frame):
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))

    ko = font_title.render("K.O.!", True, GOLD)
    surface.blit(ko, (SCREEN_W // 2 - ko.get_width() // 2, 160))

    win = font_large.render(f"{winner_name} WINS!", True, winner_color)
    surface.blit(win, (SCREEN_W // 2 - win.get_width() // 2, 260))

    if (frame // 30) % 2 == 0:
        again = font_med.render("SPACE — Rematch    ESC — Menu", True, WHITE)
        surface.blit(again, (SCREEN_W // 2 - again.get_width() // 2, 360))


# ---------------------------------------------------------------------------
# Combat resolution
# ---------------------------------------------------------------------------
def resolve_hits(attacker, defender, particles, asterisks, now):
    if not attacker.attack or attacker.hit_this_attack:
        return
    if not defender.alive:
        return

    hb = attacker.attack_hitbox()
    if hb is None:
        return
    if not hb.colliderect(defender.hitbox()):
        return

    style = get_attack_style_data(attacker.attack, attacker.attack_style)
    base = style["damage"]
    knock_px = style.get("knock_px", 10)
    lift = style.get("lift", -2.5)

    blocked = defender.blocking and defender.on_ground

    if blocked:
        # Blocked hits do not build or keep a crit streak
        attacker.consecutive_hits = 0
        attacker.crit_dealt_mult = 1.0
        mult = 1.0
        is_crit = False
    else:
        # Successful consecutive hit on opponent
        attacker.consecutive_hits += 1
        # Getting hit resets the defender's own offensive combo
        defender.consecutive_hits = 0
        defender.crit_dealt_mult = 1.0
        mult = crit_multiplier_from_hits(attacker.consecutive_hits)
        is_crit = mult > 1.0
        # Multiplier is displayed on the attacker's side of the screen
        attacker.crit_dealt_mult = mult if is_crit else 1.0

    dmg = max(1, int(round(base * mult)))
    dealt = defender.take_damage(
        dmg,
        attacker.facing,
        now,
        is_special=(attacker.attack == "special"),
        is_crit=is_crit,
        knock_px=knock_px,
        lift=lift,
    )
    attacker.hit_this_attack = True

    # Particles at contact
    cx = (hb.centerx + defender.rect().centerx) // 2
    cy = (hb.centery + defender.rect().centery) // 2
    for _ in range(10 if attacker.attack == "special" else 6):
        particles.append(Particle(cx, cy, GOLD if attacker.attack == "special" else WHITE))

    if is_crit:
        spawn_crit_burst(particles, cx, cy, mult)
        # Asterisks burst outward from the punch contact point (4–6 only)
        spawn_crit_asterisk_burst(asterisks, cx, cy)

    _ = dealt


# ---------------------------------------------------------------------------
# Setup players
# ---------------------------------------------------------------------------
P1_CONTROLS = {
    "left": pygame.K_a,
    "right": pygame.K_d,
    "up": pygame.K_w,
    "down": pygame.K_s,
    "punch": pygame.K_f,
    "kick": pygame.K_g,
    "special": pygame.K_r,
    "block": pygame.K_t,
}
P2_CONTROLS = {
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "punch": pygame.K_k,
    "kick": pygame.K_l,
    "special": pygame.K_o,
    "block": pygame.K_p,
}

player1 = Fighter(220, 1, RED, DARK_RED, "Player 1", P1_CONTROLS)
player2 = Fighter(780, -1, BLUE, DARK_BLUE, "Player 2", P2_CONTROLS)

state = "menu"  # menu | playing | gameover
winner = None
winner_color = GOLD
particles = []
asterisks = []
frame = 0
round_start_time = 0
show_fight_banner = 0
crit_screen_flash = 0  # alpha residual for crit screen pulse


def start_match():
    global state, winner, particles, asterisks, round_start_time, show_fight_banner, crit_screen_flash
    player1.reset()
    player2.reset()
    particles = []
    asterisks = []
    winner = None
    crit_screen_flash = 0
    state = "playing"
    round_start_time = pygame.time.get_ticks()
    show_fight_banner = round_start_time + 1200


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
while True:
    now = pygame.time.get_ticks()
    frame += 1

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if state == "playing":
                    state = "menu"
                elif state == "gameover":
                    state = "menu"
                elif state == "menu":
                    pygame.quit()
                    sys.exit()

            if state == "menu" and event.key == pygame.K_SPACE:
                start_match()

            elif state == "gameover" and event.key == pygame.K_SPACE:
                start_match()

            elif state == "playing":
                # Ignore attacks during fight banner
                if now < show_fight_banner:
                    continue
                if event.key == player1.controls["punch"]:
                    player1.try_attack("punch", now)
                elif event.key == player1.controls["kick"]:
                    player1.try_attack("kick", now)
                elif event.key == player1.controls["special"]:
                    player1.try_attack("special", now)
                if event.key == player2.controls["punch"]:
                    player2.try_attack("punch", now)
                elif event.key == player2.controls["kick"]:
                    player2.try_attack("kick", now)
                elif event.key == player2.controls["special"]:
                    player2.try_attack("special", now)

    keys = pygame.key.get_pressed()

    # ---- UPDATE ----
    if state == "playing":
        if now >= show_fight_banner:
            player1.handle_input(keys, now)
            player2.handle_input(keys, now)

        player1.update(now, player2)
        player2.update(now, player1)

        prev_p1_crit = player1.crit_dealt_mult
        prev_p2_crit = player2.crit_dealt_mult

        resolve_hits(player1, player2, particles, asterisks, now)
        resolve_hits(player2, player1, particles, asterisks, now)

        # Trigger screen flash when a new crit lands or multiplier climbs
        if player2.crit_dealt_mult > prev_p2_crit or player1.crit_dealt_mult > prev_p1_crit:
            crit_screen_flash = 90

        # Win check
        if not player1.alive or not player2.alive:
            state = "gameover"
            if not player1.alive and not player2.alive:
                winner = "Draw — Double KO"
                winner_color = GOLD
            elif not player2.alive:
                winner = player1.name
                winner_color = RED
            else:
                winner = player2.name
                winner_color = BLUE

    # Keep VFX alive through playing + game over
    if state in ("playing", "gameover"):
        for p in particles:
            p.update()
        particles = [p for p in particles if p.life > 0]

        for a in asterisks:
            a.update()
        asterisks = [a for a in asterisks if a.alive]

        if crit_screen_flash > 0:
            crit_screen_flash = max(0, crit_screen_flash - 4)

    # ---- DRAW ----
    if state == "menu":
        draw_menu(screen, frame)
    else:
        draw_dojo(screen, frame)
        player1.draw(screen, now)
        player2.draw(screen, now)
        for p in particles:
            p.draw(screen)
        for a in asterisks:
            a.draw(screen)
        draw_hud(screen, player1, player2, now)

        # Brief dark screen pulse on crit
        if crit_screen_flash > 0:
            flash = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            flash.fill((0, 0, 0, min(120, crit_screen_flash)))
            screen.blit(flash, (0, 0))

        # FIGHT! banner
        if state == "playing" and now < show_fight_banner:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, 0))
            elapsed = now - round_start_time
            if elapsed < 600:
                msg = font_title.render("READY?", True, WHITE)
            else:
                msg = font_title.render("FIGHT!", True, GOLD)
            screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2 - 40))

        if state == "gameover":
            draw_game_over(screen, winner, winner_color, frame)

    pygame.display.flip()
    clock.tick(FPS)
