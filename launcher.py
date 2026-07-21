"""Game launcher — pick and run a game, type your name, view leaderboards.

Each game is a self-contained pygame program, so the launcher runs the chosen
one as a separate process. The player's name is passed to the game via the
ARCADE_PLAYER environment variable; scores.py records each score under that name,
building a per-game leaderboard shared across all games.
"""
import os
import sys
import subprocess

import pygame

import scores

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

# (title, subtitle, filename, accent color, score_key, score_unit)
# key "karate" is a special Red-vs-Blue tally rather than a name leaderboard.
GAMES = [
    ("Slime Run",         "Endless platformer with a dragon boss",    "slimemain.py",          (90, 210, 110),  "slime",      "m"),
    ("Astroid Bird",      "Flappy-style UFO through an asteroid belt", "flappySpaceship.Py",    (110, 170, 255), "flappy",     "pts"),
    ("Two-Player Karate", "Local versus fighting",                    "Two-Player Karate.py",  (235, 120, 90),  "karate",     ""),
    ("Hangar 9",          "1993-style FPS",                           "Hangar 9 Fixed.py",     (220, 200, 100), "hangar",     "pts"),
    ("Impossible Square", "Precision dodging challenge",              "impossiblesquare.py",   (200, 120, 235), "impossible", "lvl"),
]
GAMES = [g for g in GAMES if os.path.exists(os.path.join(HERE, g[2]))]

# Slime keeps a separate leaderboard per difficulty
SLIME_DIFFS = [("EASY", "slime_easy"), ("NORMAL", "slime_normal"), ("HARD", "slime_hard")]

W, H = 820, 680
BG = (18, 20, 32)
ROW_TOP = 196
ROW_H = 82


def launch(game_file, player_name):
    """Close the menu, run the game (passing the player name), then reopen."""
    scores.set_player(player_name)
    pygame.display.quit()
    env = dict(os.environ, ARCADE_PLAYER=player_name)
    try:
        subprocess.run([PYTHON, os.path.join(HERE, game_file)], cwd=HERE, env=env)
    except Exception as exc:
        print(f"Could not run {game_file}: {exc}")
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Game Launcher")
    return screen


def item_rects():
    return [pygame.Rect(50, ROW_TOP + i * ROW_H, W - 100, ROW_H - 14) for i in range(len(GAMES))]


def lb_button_rect(row):
    """Small leaderboard button on the right side of a game row."""
    return pygame.Rect(row.right - 50, row.centery - 20, 38, 40)


def draw_trophy(surface, cx, cy, col):
    pygame.draw.ellipse(surface, col, (cx - 8, cy - 10, 16, 9))
    pygame.draw.polygon(surface, col, [(cx - 8, cy - 7), (cx + 8, cy - 7), (cx + 4, cy + 2), (cx - 4, cy + 2)])
    pygame.draw.rect(surface, col, (cx - 1, cy + 2, 2, 5))
    pygame.draw.rect(surface, col, (cx - 6, cy + 7, 12, 3))


def draw_menu(screen, fonts, selected, player_name, mouse):
    title_font, name_font, sub_font, hint_font = fonts
    rects = item_rects()

    screen.fill(BG)
    title = title_font.render("ARCADE", True, (240, 240, 250))
    screen.blit(title, title.get_rect(center=(W // 2, 54)))

    # Name input field
    cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
    name_txt = name_font.render(f"PLAYER: {player_name}{cursor}", True, (255, 230, 140))
    box = name_txt.get_rect(center=(W // 2, 118)).inflate(28, 14)
    pygame.draw.rect(screen, (30, 34, 50), box, border_radius=8)
    pygame.draw.rect(screen, (90, 100, 130), box, 2, border_radius=8)
    screen.blit(name_txt, name_txt.get_rect(center=(W // 2, 118)))
    tip = hint_font.render("(type to change your name)", True, (120, 126, 148))
    screen.blit(tip, tip.get_rect(center=(W // 2, 150)))

    scoredata = scores.load()
    for i, (name, sub, _file, accent, key, unit) in enumerate(GAMES):
        r = rects[i]
        is_sel = i == selected
        pygame.draw.rect(screen, (36, 40, 58) if is_sel else (28, 31, 46), r, border_radius=10)
        pygame.draw.rect(screen, accent, (r.x, r.y, 8, r.height), border_radius=4)
        if is_sel:
            pygame.draw.rect(screen, accent, r, 3, border_radius=10)

        nm = name_font.render(name, True, (245, 245, 250) if is_sel else (215, 218, 230))
        screen.blit(nm, (r.x + 24, r.y + 8))
        sb = sub_font.render(sub, True, (150, 156, 176))
        screen.blit(sb, (r.x + 24, r.y + 42))

        # Best score / record, to the left of the leaderboard button
        if key == "karate":
            info = f"Red {scoredata.get('karate_red', 0)} - {scoredata.get('karate_blue', 0)} Blue"
            col = (255, 200, 150)
        else:
            if key == "slime":
                boards = [scoredata.get(k) for _, k in SLIME_DIFFS]
            else:
                boards = [scoredata.get(key)]
            best = max([max(b.values()) for b in boards if isinstance(b, dict) and b] + [0])
            info = f"Best {best} {unit}".strip()
            col = (255, 220, 120)
        bs = sub_font.render(info, True, col)
        screen.blit(bs, bs.get_rect(midright=(r.right - 66, r.centery)))

        # Leaderboard button
        lb = lb_button_rect(r)
        hover = lb.collidepoint(mouse)
        pygame.draw.rect(screen, (60, 64, 86) if hover else (44, 48, 66), lb, border_radius=6)
        pygame.draw.rect(screen, accent, lb, 2, border_radius=6)
        draw_trophy(screen, lb.centerx, lb.centery, (255, 216, 120))

    hint = hint_font.render("Up/Down select   Enter play   trophy = leaderboard   Esc quit",
                            True, (130, 136, 156))
    screen.blit(hint, hint.get_rect(center=(W // 2, H - 26)))


def draw_leaderboard(screen, fonts, idx):
    title_font, name_font, sub_font, hint_font = fonts
    name, sub, _file, accent, key, unit = GAMES[idx]

    screen.fill(BG)
    title = title_font.render(name.upper(), True, accent)
    screen.blit(title, title.get_rect(center=(W // 2, 64)))
    hdr = sub_font.render("LEADERBOARD", True, (150, 156, 176))
    screen.blit(hdr, hdr.get_rect(center=(W // 2, 108)))

    if key == "karate":
        red, blue = scores.get("karate_red"), scores.get("karate_blue")
        r = title_font.render(f"RED {red}", True, (220, 80, 80))
        dash = title_font.render("—", True, (200, 200, 210))
        b = title_font.render(f"{blue} BLUE", True, (90, 130, 235))
        total_w = r.get_width() + dash.get_width() + b.get_width() + 40
        x = W // 2 - total_w // 2
        y = H // 2 - 40
        screen.blit(r, (x, y)); x += r.get_width() + 20
        screen.blit(dash, (x, y)); x += dash.get_width() + 20
        screen.blit(b, (x, y))
    elif key == "slime":
        # Three difficulty columns side by side
        col_w = (W - 80) // 3
        for ci, (label, k) in enumerate(SLIME_DIFFS):
            left = 40 + ci * col_w
            hdr = name_font.render(label, True, accent)
            screen.blit(hdr, hdr.get_rect(center=(left + col_w // 2, 150)))
            pygame.draw.line(screen, (60, 66, 88), (left + 20, 172), (left + col_w - 20, 172), 2)
            entries = scores.top(k, 9)
            if not entries:
                m = sub_font.render("no scores yet", True, (140, 146, 168))
                screen.blit(m, m.get_rect(center=(left + col_w // 2, 200)))
                continue
            y = 186
            for rank, (pname, sc) in enumerate(entries, start=1):
                rcol = (255, 220, 120) if rank == 1 else (222, 225, 238)
                screen.blit(sub_font.render(f"{rank}. {pname}", True, rcol), (left + 18, y))
                sctxt = sub_font.render(f"{sc}m", True, rcol)
                screen.blit(sctxt, sctxt.get_rect(topright=(left + col_w - 18, y)))
                y += 28
    else:
        entries = scores.top(key)
        if not entries:
            msg = name_font.render("No scores yet — be the first!", True, (170, 176, 196))
            screen.blit(msg, msg.get_rect(center=(W // 2, H // 2)))
        else:
            y = 170
            for rank, (pname, sc) in enumerate(entries, start=1):
                col = (255, 220, 120) if rank == 1 else (225, 228, 240)
                rank_txt = name_font.render(f"{rank}.", True, accent)
                screen.blit(rank_txt, (140, y))
                nm = name_font.render(pname, True, col)
                screen.blit(nm, (200, y))
                sc_txt = name_font.render(f"{sc} {unit}".strip(), True, col)
                screen.blit(sc_txt, sc_txt.get_rect(topright=(W - 140, y)))
                y += 42

    hint = hint_font.render("click or Esc to go back", True, (130, 136, 156))
    screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Game Launcher")
    clock = pygame.time.Clock()
    fonts = (
        pygame.font.SysFont("PIXY", 54, bold=True),
        pygame.font.SysFont("PIXY", 32, bold=True),
        pygame.font.SysFont("PIXY", 20),
        pygame.font.SysFont("PIXY", 20),
    )

    player_name = scores.get_player()
    selected = 0
    board_view = None   # None on the menu, else the game index being shown

    while True:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if board_view is not None:
                # Any key or click leaves the leaderboard
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    board_view = None
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_RETURN:
                    screen = launch(GAMES[selected][2], player_name)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(GAMES)
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(GAMES)
                elif event.key == pygame.K_BACKSPACE:
                    player_name = player_name[:-1]
                elif event.unicode and event.unicode.isprintable() and len(player_name) < 12:
                    player_name += event.unicode

            if event.type == pygame.MOUSEMOTION:
                for i, r in enumerate(item_rects()):
                    if r.collidepoint(mouse):
                        selected = i
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                rects = item_rects()
                opened = False
                for i, r in enumerate(rects):
                    if lb_button_rect(r).collidepoint(mouse):
                        board_view = i
                        opened = True
                        break
                if not opened:
                    for i, r in enumerate(rects):
                        if r.collidepoint(mouse):
                            screen = launch(GAMES[i][2], player_name)
                            break

        if not player_name:
            player_name = ""   # allow empty while typing; saved name falls back to YOU

        if board_view is not None:
            draw_leaderboard(screen, fonts, board_view)
        else:
            draw_menu(screen, fonts, selected, player_name, mouse)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
