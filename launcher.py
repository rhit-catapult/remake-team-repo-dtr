"""Game launcher — a menu screen to pick and run any of the games.

Each game is a self-contained pygame program with its own window size and main
loop, so the launcher runs the chosen one as a separate process and returns to
this menu when it closes. Arrow keys / number keys / mouse all work.
"""
import os
import sys
import subprocess

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

# (title, subtitle, filename, accent color)
GAMES = [
    ("Slime Run",         "Endless platformer with a dragon boss", "slimemain.py",          (90, 210, 110)),
    ("Astroid Bird",      "Flappy-style UFO through an asteroid belt", "flappySpaceship.Py", (110, 170, 255)),
    ("Two-Player Karate", "Local versus fighting",                 "Two-Player Karate.py",  (235, 120, 90)),
    ("Hangar 9",          "The big one",                           "Hangar 9 Fixed.py",     (220, 200, 100)),
    ("Impossible Square", "Precision dodging challenge",           "impossiblesquare.py",   (200, 120, 235)),
]
GAMES = [g for g in GAMES if os.path.exists(os.path.join(HERE, g[2]))]

W, H = 760, 620
BG = (18, 20, 32)


def launch(game_file):
    """Close the menu window, run the game in its own process, then reopen the menu."""
    pygame.display.quit()
    try:
        subprocess.run([PYTHON, os.path.join(HERE, game_file)], cwd=HERE)
    except Exception as exc:  # keep the launcher alive if a game fails to start
        print(f"Could not run {game_file}: {exc}")
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Game Launcher")
    return screen


def item_rects():
    """Screen rects for each game row (for mouse hit-testing and drawing)."""
    rects = []
    top = 170
    row_h = 78
    for i in range(len(GAMES)):
        rects.append(pygame.Rect(60, top + i * row_h, W - 120, row_h - 14))
    return rects


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Game Launcher")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("PIXY", 60, bold=True)
    name_font = pygame.font.SysFont("PIXY", 34, bold=True)
    sub_font = pygame.font.SysFont("PIXY", 20)
    hint_font = pygame.font.SysFont("PIXY", 20)

    selected = 0
    rects = item_rects()

    while True:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(GAMES)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(GAMES)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    screen = launch(GAMES[selected][2])
                elif pygame.K_1 <= event.key < pygame.K_1 + len(GAMES):
                    selected = event.key - pygame.K_1
                    screen = launch(GAMES[selected][2])
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
            if event.type == pygame.MOUSEMOTION:
                for i, r in enumerate(rects):
                    if r.collidepoint(mouse):
                        selected = i
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(rects):
                    if r.collidepoint(mouse):
                        screen = launch(GAMES[i][2])

        # --- Draw the menu ---
        screen.fill(BG)
        title = title_font.render("ARCADE", True, (240, 240, 250))
        screen.blit(title, title.get_rect(center=(W // 2, 70)))
        tag = sub_font.render("Choose a game", True, (150, 156, 176))
        screen.blit(tag, tag.get_rect(center=(W // 2, 118)))

        for i, (name, sub, _file, accent) in enumerate(GAMES):
            r = rects[i]
            is_sel = i == selected
            # Card background + accent
            pygame.draw.rect(screen, (36, 40, 58) if is_sel else (28, 31, 46), r, border_radius=10)
            pygame.draw.rect(screen, accent, (r.x, r.y, 8, r.height), border_radius=4)
            if is_sel:
                pygame.draw.rect(screen, accent, r, 3, border_radius=10)

            num = name_font.render(str(i + 1), True, accent)
            screen.blit(num, (r.x + 24, r.centery - num.get_height() // 2))
            nm = name_font.render(name, True, (245, 245, 250) if is_sel else (215, 218, 230))
            screen.blit(nm, (r.x + 64, r.y + 10))
            sb = sub_font.render(sub, True, (150, 156, 176))
            screen.blit(sb, (r.x + 64, r.y + 44))

        #hint = hint_font.render("Up/Down or mouse to pick  -  Enter/click to play  -  1-{} quick  -  Esc quits".format(len(GAMES)),
                         #       True, (130, 136, 156))
        #screen.blit(hint, hint.get_rect(center=(W // 2, H - 34)))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
