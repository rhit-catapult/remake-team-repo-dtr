import pygame
import sys
import random
import math


from astroid import Astroid
import scores
pygame.init()

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("astroid bird")
spaceship = pygame.image.load("spaceship.png").convert_alpha()
w, h = spaceship.get_size()
spaceship = pygame.transform.scale(spaceship, (w // 20, h // 20))   # half of its own size
# Hitbox: the ship's pixel shape shrunk toward its center so edge grazes are forgiven.
# Lower LENIENCY = smaller hitbox = more lenient.
LENIENCY = 0.65
_sw, _sh = spaceship.get_size()
ship_mask = pygame.mask.from_surface(spaceship).scale((int(_sw * LENIENCY), int(_sh * LENIENCY)))
mask_ox = (_sw - ship_mask.get_size()[0]) // 2   # keep the smaller mask centered on the ship
mask_oy = (_sh - ship_mask.get_size()[1]) // 2
font = pygame.font.SysFont("PIXY", 48)  # Pixel Code font, size 48

PLANET_COLORS = [
    (176, 92, 60), (90, 120, 190), (150, 140, 90), (110, 160, 110),
    (150, 100, 170), (190, 150, 90), (80, 175, 175), (205, 105, 70),
    (120, 130, 225), (175, 80, 115), (95, 185, 130), (210, 175, 95),
]

RING_COLORS = [
    (215, 205, 180), (185, 205, 230), (195, 195, 200), (205, 165, 140),
    (225, 200, 140), (185, 210, 195), (210, 180, 205),
]


def draw_thruster(surface, cx, base_y, direction, scale=1.0):
    """Draw a flickering pixel flame from (cx, base_y). direction +1 = down, -1 = up."""
    block = max(2, int(4 * scale))
    widths = [int(w * scale) for w in (10, 8, 6, 4, 3)]
    n = len(widths) + random.randint(0, 2)          # length flickers each frame
    for i in range(n):
        w = widths[i] if i < len(widths) else max(2, int(2 * scale))
        col = [(255, 245, 160), (255, 190, 70), (255, 140, 40)][i] if i < 3 else (225, 80, 25)
        ry = base_y + i * block if direction > 0 else base_y - (i + 1) * block
        pygame.draw.rect(surface, col, (int(cx - w / 2), int(ry), max(1, w), block))


def _shade(c, f):
    """Multiply a color's brightness by f, clamped to 0..255."""
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))), max(0, min(255, int(c[2] * f))))


def _mix(a, b, t):
    """Blend color a toward b by fraction t."""
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def make_planet_surface(radius, base, has_ring):
    """Pre-render a pixelated planet with real surface features, optionally ringed.

    Each planet is either a gas giant (horizontal bands + a storm spot) or a
    rocky world (continents), often with bright polar caps. Rendering once and
    blitting it avoids per-frame shimmer.
    """
    rng = random.Random()                       # local stream, doesn't disturb the game's RNG
    gas = rng.random() < 0.5
    phase = rng.uniform(0, math.tau)
    band_light = _shade(base, 1.20)
    band_dark = _shade(base, 0.70)
    caps = rng.random() < 0.55
    cap_col = (232, 238, 245)

    land = None
    blobs = []
    if not gas:                                 # rocky: scatter continent blobs
        land = _shade(base, 1.28) if rng.random() < 0.5 else _shade(base, 0.58)
        for _ in range(rng.randint(3, 6)):
            a = rng.uniform(0, math.tau)
            rr = rng.uniform(0, radius * 0.6)
            blobs.append((math.cos(a) * rr, math.sin(a) * rr, rng.uniform(radius * 0.18, radius * 0.42)))

    spot = None
    if gas and rng.random() < 0.7:              # gas giant storm spot (à la the Great Red Spot)
        a = rng.uniform(0, math.tau)
        sr = rng.uniform(radius * 0.2, radius * 0.5)
        spot = (math.cos(a) * sr, math.sin(a) * sr * 0.6,
                rng.uniform(radius * 0.14, radius * 0.24),
                _shade(base, 1.45) if rng.random() < 0.5 else (205, 120, 90))

    # Ring variety: random tilt, colour, and 1-3 concentric bands of varying width
    ring_bands = []
    if has_ring:
        tilt = rng.uniform(0.15, 0.36)
        outer = rng.uniform(1.6, 2.2)
        gap = rng.uniform(0.16, 0.32)
        base_ring = rng.choice(RING_COLORS)
        for i in range(rng.randint(1, 3)):
            brx = (outer - i * gap) * radius
            if brx <= radius * 0.95:
                break
            ring_bands.append((brx, brx * tilt, rng.randint(2, 5),
                               _shade(base_ring, rng.uniform(0.80, 1.14))))

    max_rx = max((b[0] for b in ring_bands), default=radius)
    pad = int(max_rx - radius) + 4
    W = int(radius * 2 + pad * 2)
    H = int(radius * 2 + 8)
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx, cy = W // 2, H // 2

    def _ring_rect(brx, bry):
        r = pygame.Rect(0, 0, int(brx * 2), int(bry * 2))
        r.center = (cx, cy)
        return r

    for brx, bry, thick, bcol in ring_bands:            # ring bands behind the planet
        pygame.draw.ellipse(surf, bcol, _ring_rect(brx, bry), thick)

    block = 5
    for by in range(cy - radius, cy + radius, block):
        for bx in range(cx - radius, cx + radius, block):
            dx = (bx + block / 2) - cx
            dy = (by + block / 2) - cy
            if dx * dx + dy * dy > radius * radius:
                continue

            c = base
            if gas:
                band = math.sin(dy * 0.35 + phase) + 0.4 * math.sin(dy * 0.13 + phase * 1.7)
                if band > 0.5:
                    c = band_light
                elif band < -0.5:
                    c = band_dark
                if spot is not None:
                    sx, sy, srr, scol = spot
                    if ((dx - sx) / 1.4) ** 2 + (dy - sy) ** 2 < srr * srr:
                        c = scol
            else:
                for bxc, byc, br in blobs:
                    if (dx - bxc) ** 2 + (dy - byc) ** 2 < br * br:
                        c = land
                        break

            if caps and abs(dy) > radius * 0.72:                 # polar caps
                c = _mix(c, cap_col, 0.6)

            shade = (dx + dy) / (radius * 2)                     # lit from upper-left
            f = max(0.4, 1.0 - 0.55 * shade)
            pygame.draw.rect(surf, _shade(c, f), (bx, by, block, block))

    if ring_bands:
        prev = surf.get_clip()
        surf.set_clip(pygame.Rect(0, cy, W, H - cy))            # redraw front (lower) half over planet
        for brx, bry, thick, bcol in ring_bands:
            pygame.draw.ellipse(surf, bcol, _ring_rect(brx, bry), thick)
        surf.set_clip(prev)

    return surf


# 3. Set up the game clock (controls frame rate)
highscore = scores.get("flappy")   # persistent best, shared across launcher sessions
clock = pygame.time.Clock()
counter = 0
score = 0
FPS = 60
yVelo = 0
start = False
gameEnd = False
speedScore = 10
speedIncrease = False

x = 270
y = 180
l = 20
spawn = False
velo = 2

# Main Game Loop
running = True
astroids = []
# Background starfield: [x, y, size, speedFactor] — smaller/dimmer stars drift slower
stars = []
for _ in range(70):
    stars.append([random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT),
                  random.randint(1, 3), random.uniform(0.35, 1.0)])
planets = []   # occasional far-background planets: [x, y, radius, color]
while running:
    pressed = pygame.key.get_pressed()
    
        
    if pressed[pygame.K_UP]:
        if spawn == False:
            spawn = True
        yVelo -= 0.5
    if pressed[pygame.K_DOWN]:
        if spawn == False:
            spawn = True
        yVelo += 0.5
    if pressed[pygame.K_r]:
        counter = 0
        gameEnd = False
        score = 0
        astroids.clear()
        y = 180
        x=270
        
    if not gameEnd:
        y += yVelo
    else:
        counter = 0
        if y < 400:
            x+=2
        y += 9.8 
    if (y) >= 440-l:
        y = 440-l
        yVelo *= -0.7
        
    if (y) < 0:
        y = 0
        yVelo *= -0.7
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((12, 12, 22))  # deep-space background

    beltSpeed = 3 if score >= 20 else 2.5 if score >= 10 else 2

    # Occasional planets far in the background — big, rare, pre-rendered so they don't shimmer
    if not gameEnd and len(planets) < 2 and random.random() < 0.005:
        r = random.randint(28, 60)
        surf = make_planet_surface(r, random.choice(PLANET_COLORS), random.random() < 0.65)
        planets.append([SCREEN_WIDTH + surf.get_width() // 2,
                        random.randint(50, SCREEN_HEIGHT - 50), surf])
    for p in planets:
        if not gameEnd:
            p[0] -= beltSpeed * 0.75          # faster parallax drift
        surf = p[2]
        screen.blit(surf, (int(p[0] - surf.get_width() / 2), int(p[1] - surf.get_height() / 2)))
    planets = [p for p in planets if p[0] + p[2].get_width() / 2 > 0]

    # Starfield drifting past at the same pace as the asteroid belt (parallax by depth)
    for s in stars:
        if not gameEnd:
            s[0] -= beltSpeed * s[3]
            if s[0] < 0:                       # recycle off-screen stars to the right
                s[0] = SCREEN_WIDTH
                s[1] = random.randint(0, SCREEN_HEIGHT)
        b = 110 + int(s[3] * 140)              # closer stars are brighter
        pygame.draw.rect(screen, (b, b, b), (int(s[0]), int(s[1]), s[2], s[2]))

    
        
    # Thrusters fire opposite the way you're accelerating
    if not gameEnd:
        ship_cx = x + _sw / 2
        if pressed[pygame.K_UP]:        # push up -> jets fire downward from the belly
            for off, sc in ((-9, 0.7), (0, 1.0), (9, 0.7)):
                draw_thruster(screen, ship_cx + off, y + _sh, 1, sc)
        if pressed[pygame.K_DOWN]:      # push down -> jets fire upward from the top
            for off, sc in ((-9, 0.7), (0, 1.0), (9, 0.7)):
                draw_thruster(screen, ship_cx + off, y, -1, sc)

    screen.blit(spaceship, (x, y))     # top-left corner goes at (x, y)
    if counter % 150 == 0 and spawn and not gameEnd:
        astroids.append(Astroid(700, random.randint((int)(100 + max((100 - 0.025*counter),0)),(int)(150 + max((100-0.01*counter),0)))))


    if score == speedScore:
        speedScore += 10
        velo += 0.5

    if not gameEnd:
        for ast in astroids:
            ast.velo = velo
            ast.update(screen)
            if ast.x < 260 and ast.point and not gameEnd:
                score += 1
                if score > highscore:
                    highscore = score
                    scores.record("flappy", score)   # persist the new best
                ast.point = False
            # Pixel-vs-pixel: ship hitbox against the actual asteroid pixels (not the gaps)
            mx, my = x + mask_ox, y + mask_oy
            up, lo = ast.upperRectangle, ast.lowerRectangle
            if (ship_mask.overlap(ast.upperMask, (up.x - mx, up.y - my)) or
                    ship_mask.overlap(ast.lowerMask, (lo.x - mx, lo.y - my))):
                gameEnd = True


    astroids = [ast for ast in astroids if ast.x > -100]
        
    if not spawn:
            text = font.render("Start: Press Up or Down", True, (255, 255, 255))
    elif score % 10 == 0 and not score == 0:
            text = font.render(f"{round(score)} pts! Speed Increased", True, (255, 255, 255))
    else:
            text = font.render(f"{round(score)}", True, (255, 255, 255))

    gameoverText = font.render("Game Over", True, (255, 255, 255))
    scoreText = font.render(f"Score: {round(score)}", True, (255, 255, 255))

    if not gameEnd:
        text_rect = text.get_rect(center = (320,420))
        screen.blit(text,text_rect)
    else:
        highscoreText = font.render(f"highscore: {round(highscore)}", True, (255, 255, 255))
        highscore_rect = highscoreText.get_rect(center = (320,50))
        screen.blit(highscoreText,highscore_rect)
        text = font.render("Restart: Press R", True, (255, 255, 255))
        text_rect = text.get_rect(center = (320,420))
        screen.blit(text,text_rect)
        gameover_rect = gameoverText.get_rect(center = (320,160))
        screen.blit(gameoverText,gameover_rect)
        scoreText_rect = scoreText.get_rect(center = (320,220))
        screen.blit(scoreText,scoreText_rect)
    
    pygame.display.flip()  # Update the full display Surface to the screen

    # 7. Maintain frame rate
    if not gameEnd:
        counter += 1
    clock.tick(FPS)


pygame.quit()
sys.exit()


