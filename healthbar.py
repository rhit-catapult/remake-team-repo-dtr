import sys
import pygame
import random


def _clamp(value, low, high):
    return max(low, min(high, value))


def _lerp_color(a, b, t):
    """Blend between two RGB colors."""
    t = _clamp(t, 0.0, 1.0)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class HealCross:
    """Floating green '+' that drifts up and fades — heal feedback."""

    def __init__(self, font, x=320, y=180):
        self.x = x + random.uniform(-14, 14)
        self.y = y
        self.img = font.render("+", True, (60, 220, 90)).convert_alpha()
        self.alpha = 255

    def update(self):
        self.y -= 0.9
        self.alpha = max(0, self.alpha - 4)
        self.img.set_alpha(self.alpha)

    def draw(self, screen):
        screen.blit(self.img, self.img.get_rect(center=(self.x, self.y)))

    def dead(self):
        return self.alpha <= 0


class HealthBar:
    def __init__(self, font, x=120, y=220, width=400, height=50, max_hp=400):
        self.font = font
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.max_hp = float(max_hp)
        self.hp = float(max_hp)
        # hp_display trails hp: it lags on damage (pale drain) and eases up on heal.
        self.hp_display = float(max_hp)
        self.hit_counter = 999  # frames since last hit; large so it starts settled
        self.crosses = []
        # Fraction of the remaining gap closed each frame (exponential ease).
        self._animation_speed = 0.18
        # Brief pause after a hit before the pale trail starts draining.
        self._drain_delay_frames = 12

    @property
    def is_dead(self):
        return self.hp <= 0

    def damage(self, amount):
        self.hp = max(0.0, self.hp - amount)
        self.hit_counter = 0

    def heal(self, amount):
        if self.hp <= 0:
            return
        previous_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        if self.hp > previous_hp:
            self.crosses.append(
                HealCross(self.font, self.x + self.width / 2, self.y - 20)
            )

    def reset(self):
        self.hp = float(self.max_hp)
        self.hp_display = float(self.max_hp)
        self.hit_counter = 999
        self.crosses = []

    def update(self):
        self.hp = _clamp(self.hp, 0.0, self.max_hp)

        healing = self.hp > self.hp_display
        # On heal, catch up immediately; on damage, hold briefly then drain.
        if healing or self.hit_counter >= self._drain_delay_frames:
            self.hp_display += (self.hp - self.hp_display) * self._animation_speed
            if abs(self.hp_display - self.hp) < 0.4:
                self.hp_display = self.hp

        self.hit_counter += 1

        for cross in self.crosses:
            cross.update()
        self.crosses = [cross for cross in self.crosses if not cross.dead()]

    def _hp_color(self, ratio):
        """Green when healthy, through yellow, to red when low."""
        if ratio > 0.5:
            return _lerp_color((230, 190, 40), (60, 200, 90), (ratio - 0.5) / 0.5)
        return _lerp_color((200, 45, 45), (230, 190, 40), ratio / 0.5)

    def draw(self, screen):
        max_hp = self.max_hp if self.max_hp else 1.0
        hp_ratio = _clamp(self.hp / max_hp, 0.0, 1.0)
        display_ratio = _clamp(self.hp_display / max_hp, 0.0, 1.0)
        front_ratio = min(hp_ratio, display_ratio)
        back_ratio = max(hp_ratio, display_ratio)
        is_healing = self.hp > self.hp_display + 0.01

        radius = int(min(self.height // 2, 12))
        pad = 3
        inner_x = self.x + pad
        inner_y = self.y + pad
        inner_w = self.width - 2 * pad
        inner_h = self.height - 2 * pad
        inner_r = max(2, radius - pad)

        track = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(screen, (28, 28, 36), track, border_radius=radius)

        def fill(ratio, color):
            fill_w = int(round(inner_w * ratio))
            if fill_w <= 0:
                return 0
            pygame.draw.rect(
                screen, color, (inner_x, inner_y, fill_w, inner_h),
                border_radius=inner_r,
            )
            return fill_w

        # Difference region behind the main bar: pale-green when gaining,
        # near-white when a hit is draining away.
        diff_color = (120, 235, 150) if is_healing else (238, 238, 244)
        fill(back_ratio, diff_color)

        # Main colored bar (true current HP).
        front_w = fill(front_ratio, self._hp_color(hp_ratio))

        # Glassy top-half gloss over the filled portion.
        if front_w > 0 and inner_h >= 4:
            gloss = pygame.Surface((front_w, inner_h // 2), pygame.SRCALPHA)
            gloss.fill((255, 255, 255, 50))
            screen.blit(gloss, (inner_x, inner_y))

        pygame.draw.rect(screen, (245, 245, 250), track, 3, border_radius=radius)

        # Label / status text, centered just above the bar.
        label = f"{int(round(self.hp))} / {int(self.max_hp)}"
        color = (255, 255, 255)
        text = self.font.render(label, True, color)
        shadow = self.font.render(label, True, (0, 0, 0))
        tx = self.x + self.width // 2 - text.get_width() // 2
        ty = self.y - text.get_height() - 6
        screen.blit(shadow, (tx + 1, ty + 1))
        screen.blit(text, (tx, ty))

        for cross in self.crosses:
            cross.draw(screen)


def main():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Pixel Code", 24)

    health_bar = HealthBar(font)
    damage_timer = 0
    heal_timer = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        dt = clock.tick(60)
        damage_timer += dt
        heal_timer += dt

        if damage_timer >= 2000:
            health_bar.damage(20)
            damage_timer -= 2000

        if heal_timer >= 4000 and not health_bar.is_dead:
            health_bar.heal(10)
            heal_timer -= 4000

        screen.fill((20, 20, 20))
        health_bar.update()
        health_bar.draw(screen)
        pygame.display.update()


if __name__ == "__main__":
    main()
