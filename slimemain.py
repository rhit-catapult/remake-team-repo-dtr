"""Slime side-scrolling platformer - entry point and main game loop.

The game is split across small, single-concern modules:
  config    - constants and difficulty presets
  fonts     - shared fonts
  terrain   - islands, ground, clouds, world geometry and collision
  slime     - the player slime's rendering and animations
  enemies   - patrolling monsters
  hazards   - spikes and moving obstacles
  pickups   - health potions, star power-ups, and the hotbar inventory
  hud       - hotbar, stamina bar, difficulty menu, and death screen
  healthbar - the health bar widget

This file owns the mutable game state (player, camera, score, the live
difficulty values) and wires the modules together in the loop at the bottom.
"""
import sys
import math

import pygame

from config import *
from fonts import *
from healthbar import HealthBar
from terrain import *
from slime import *
from enemies import *
from hazards import *
from pickups import *
from hud import *
from sky import *
from border import *
from dragon import *

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Slime Platformer")
clock = pygame.time.Clock()

health_bar = HealthBar(
    HEALTH_FONT,
    x=SCREEN_W // 2 - 200,
    y=SCREEN_H - 60,
    width=400,
    height=24,
    max_hp=100,
)

# --- Mutable game state -------------------------------------------------------
# Player lives in world space; the camera centers them on screen.
x = 0.0
y = float(GROUND_TOP - square_size)
vertical_velocity = 0
jumps_used = 0
second_jump_started_at = 0
on_ground = True
landing_squash_frames = 0

green_ticks = sprint_ticks
last_stamina_regen_time = pygame.time.get_ticks()
selected_hotbar_slot = 0

last_monster_attack_time = 0
knockback_velocity_x = 0.0
consuming = None          # active enclose animation, or None
invincible_until = 0      # tick until which the slime takes no damage

# Entity lists (spawn cursors that refill them live in the entity modules).
monsters = []
potions = []
sprint_pots = []
stars = []
spikes = []
obstacles = []

# Death / run stats
max_distance = 0.0
game_over = False
death_time = 0
run_start_time = 0        # tick when the current run began (for the stopwatch)

# Trailing void border (lethal wall that follows behind the slime)
border_x = float(-BORDER_TRAIL)

# Boss level (harder hazards + a flying dragon once past BOSS_METERS)
boss_triggered = False
boss_zone_active = False       # open from reaching 200 m until reaching 225 m
boss_banner_until = 0
boss_dragon = None
boss_dragon_cleared = False   # dragon slain during the current zone visit

# Difficulty: picked on the menu, then applied to the live tuning values below.
game_state = "menu"
difficulty = 2
spike_gap = DIFFICULTY_SETTINGS[difficulty]["spike_gap"]
obstacle_gap = DIFFICULTY_SETTINGS[difficulty]["obstacle_gap"]
obstacle_speed = DIFFICULTY_SETTINGS[difficulty]["obstacle_speed"]
monster_max = DIFFICULTY_SETTINGS[difficulty]["monster_max"]
obstacle_damage = DIFFICULTY_SETTINGS[difficulty]["obstacle_dmg"]
spike_damage = DIFFICULTY_SETTINGS[difficulty]["spike_dmg"]
last_hazard_hit_time = 0


def start_run(level):
    """Apply a difficulty level and (re)initialize a fresh run."""
    global difficulty, spike_gap, obstacle_gap, obstacle_speed, monster_max
    global obstacle_damage, spike_damage, game_state
    global x, y, vertical_velocity, on_ground, jumps_used, second_jump_started_at
    global landing_squash_frames, knockback_velocity_x, consuming, invincible_until
    global green_ticks, last_monster_attack_time, last_stamina_regen_time, last_hazard_hit_time
    global max_distance, game_over, death_time, run_start_time
    global border_x, boss_triggered, boss_zone_active, boss_banner_until
    global boss_dragon, boss_dragon_cleared

    difficulty = level
    cfg = DIFFICULTY_SETTINGS[level]
    spike_gap = cfg["spike_gap"]
    obstacle_gap = cfg["obstacle_gap"]
    obstacle_speed = cfg["obstacle_speed"]
    monster_max = cfg["monster_max"]
    obstacle_damage = cfg["obstacle_dmg"]
    spike_damage = cfg["spike_dmg"]

    health_bar.reset()
    x = 0.0
    y = float(GROUND_TOP - square_size)
    vertical_velocity = 0
    on_ground = True
    jumps_used = 0
    second_jump_started_at = 0
    landing_squash_frames = 0
    knockback_velocity_x = 0.0
    consuming = None
    invincible_until = 0
    monsters.clear()
    potions.clear()
    sprint_pots.clear()
    stars.clear()
    spikes.clear()
    obstacles.clear()
    reset_monsters()
    reset_hazards()
    reset_pickups()
    green_ticks = sprint_ticks
    last_monster_attack_time = 0
    last_hazard_hit_time = 0
    last_stamina_regen_time = pygame.time.get_ticks()
    max_distance = 0.0
    game_over = False
    death_time = 0
    run_start_time = pygame.time.get_ticks()
    border_x = float(-BORDER_TRAIL)
    boss_triggered = False
    boss_zone_active = False
    boss_banner_until = 0
    boss_dragon = None
    boss_dragon_cleared = False
    game_state = "playing"


DIFFICULTY_KEYS = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}

while True:
    jump_requested = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        if game_state == "menu":
            # Difficulty select: 1 / 2 / 3 starts the run
            if event.type == pygame.KEYDOWN and event.key in DIFFICULTY_KEYS:
                start_run(DIFFICULTY_KEYS[event.key])
            continue
        if game_over and event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            start_run(difficulty)  # restart at the same difficulty
            continue
        if game_over and event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            game_state = "menu"    # back to difficulty select
            continue
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_w) and not game_over:
            jump_requested = True
        if event.type == pygame.KEYDOWN and pygame.K_1 <= event.key <= pygame.K_5:
            selected_hotbar_slot = event.key - pygame.K_1
        if event.type == pygame.KEYDOWN and event.key == pygame.K_f and not game_over:
            used = use_selected_item(selected_hotbar_slot)
            if used:
                kind, amount = used
                if kind == "star":
                    invincible_until = max(invincible_until, pygame.time.get_ticks() + amount)
                elif kind == "potion":
                    health_bar.heal(amount)
                elif kind == "sprint":
                    green_ticks = min(sprint_ticks, green_ticks + amount)
        if event.type == pygame.MOUSEWHEEL:
            selected_hotbar_slot = (selected_hotbar_slot - event.y) % hotbar_slots

    if game_state == "menu":
        draw_menu(screen, pygame.time.get_ticks(), difficulty)
        pygame.display.update()
        clock.tick(60)
        continue

    pressed_keys = pygame.key.get_pressed()
    moving_left = pressed_keys[pygame.K_LEFT] or pressed_keys[pygame.K_a]
    moving_right = pressed_keys[pygame.K_RIGHT] or pressed_keys[pygame.K_d]
    crouching = pressed_keys[pygame.K_DOWN] or pressed_keys[pygame.K_s]
    if game_over:
        # Freeze all control once the slime dies
        moving_left = moving_right = crouching = False
        jump_requested = False
    current_speed = speed if not on_ground else half_ellipse_speed
    sprinting = False
    # Sprint: hold Space while moving left/right — boosts the base speed, so it
    # works both on the ground and midair, and drains stamina.
    if pressed_keys[pygame.K_SPACE] and (moving_left or moving_right) and green_ticks > 0:
        current_speed *= 1.25
        green_ticks -= 1
        sprinting = True

    # Debug fly: hold ';' to pin the slime to the top of the screen and rush it
    # forward, for quickly testing far-off parts of the world.
    if pressed_keys[pygame.K_SEMICOLON] and not game_over:
        y = 100
        x += 100
        vertical_velocity = 0
        on_ground = False

    # Snapshot before movement so we know which face of an island was entered
    prev_x, prev_y = x, y
    current_time = pygame.time.get_ticks()
    camera_x = x + square_size / 2 - SCREEN_W / 2
    camera_y = 0
    if not game_over:
        update_monsters(monsters, camera_x, monster_max)
        update_spikes(spikes, camera_x, spike_gap)
        update_obstacles(obstacles, camera_x, obstacle_gap, obstacle_speed, monsters)

    if moving_left:
        x -= current_speed
    if moving_right:
        x += current_speed
    # Enemy knockback shove decays over a few frames
    x += knockback_velocity_x
    knockback_velocity_x *= KNOCKBACK_DECAY
    if abs(knockback_velocity_x) < 0.3:
        knockback_velocity_x = 0.0
    # World is endless horizontally — no screen edge clamp

    # Islands near the player (world continues as you explore)
    islands = get_active_islands(x + square_size / 2 - SCREEN_W / 2, SCREEN_W)

    # Crouching uses a shorter, feet-anchored collision body so the slime can
    # squeeze under low islands. top_off shifts the box down from the full square.
    collide_h = square_size // 3 if crouching else square_size
    top_off = square_size - collide_h

    # Solid islands: stop walking/jumping sideways through their bodies
    x = resolve_island_x(x, y + top_off, prev_x, collide_h, islands)

    if jump_requested and jumps_used < 2:
        vertical_velocity = jump_strength
        on_ground = False
        jumps_used += 1
        if jumps_used == 2:
            second_jump_started_at = pygame.time.get_ticks()

    vertical_velocity += gravity
    y += vertical_velocity

    # Check collision with main platform (world ground top)
    if y + square_size >= GROUND_TOP:
        if not on_ground and vertical_velocity > 0:
            landing_squash_frames = 6
        y = GROUND_TOP - square_size
        vertical_velocity = 0
        on_ground = True
        jumps_used = 0
        second_jump_started_at = 0
    else:
        # Solid islands: land on top, hit underside when jumping, never pass through
        was_airborne = not on_ground
        body_top, vertical_velocity, landed_on_island = resolve_island_y(
            x, y + top_off, prev_y + top_off, collide_h, vertical_velocity, islands
        )
        y = body_top - top_off   # convert the feet-anchored box back to the full square
        if landed_on_island:
            if was_airborne:
                landing_squash_frames = 6
            on_ground = True
            jumps_used = 0
            second_jump_started_at = 0
        else:
            on_ground = False

    # Enemy hitboxes: stomp from above to consume; side/below contact hurts
    # Crouching shrinks the hitbox from the top (feet stay planted) so the slime
    # can duck under high hazards.
    crouch_h = square_size // 3 if crouching else square_size
    player_world_rect = pygame.Rect(int(x), int(y + square_size - crouch_h), square_size, crouch_h)
    hit_monster = None
    for monster in monsters:
        if player_world_rect.colliderect(get_monster_hitbox(monster)):
            hit_monster = monster
            break
    if hit_monster is not None and not game_over:
        # Stomp: falling onto the enemy from above (feet were above its top)
        feet_prev = prev_y + square_size
        is_stomp = vertical_velocity > 0 and feet_prev <= hit_monster["y"] + 10
        if is_stomp:
            # Consume the enemy: settle onto whatever surface the slime is over
            # (the platform it's on, or the ground) and start the enclose
            # animation — the slime's bottom curves around and closes in.
            consuming = {
                "start": current_time,
                "ew": hit_monster["width"],
                "eh": hit_monster["height"],
                "ecolor": (85, 150, 75),
            }
            monsters.remove(hit_monster)
            support_y = get_support_surface_y(x, y + square_size, square_size, islands, GROUND_TOP)
            y = float(support_y - square_size)
            vertical_velocity = 0
            on_ground = True
            jumps_used = 0
            landing_squash_frames = 0
            # A clean consume grants brief mercy i-frames and heals a little
            invincible_until = max(invincible_until, current_time + CONSUME_IFRAME_MS)
            health_bar.heal(5)
        elif current_time >= invincible_until:
            player_center = x + square_size / 2
            monster_center = hit_monster["x"] + hit_monster["width"] / 2
            push_dir = -1 if player_center < monster_center else 1
            # Shove the slime backwards (away from the enemy), not upward
            knockback_velocity_x = push_dir * MONSTER_KNOCKBACK
            if current_time - last_monster_attack_time >= monster_attack_cooldown_ms:
                health_bar.damage(MONSTER_DAMAGE)
                last_monster_attack_time = current_time

    # Horizontal camera only: map (grass, plants, rock, islands) scrolls together
    camera_x = x + square_size / 2 - SCREEN_W / 2
    camera_y = 0

    # Potions: collect any the slime is now overlapping (heals + green "+" popup)
    if not game_over:
        crouch_h = square_size // 3 if crouching else square_size
        player_world_rect = pygame.Rect(int(x), int(y + square_size - crouch_h), square_size, crouch_h)
        update_potions(potions, camera_x, player_world_rect, health_bar, spikes)
        # Sprint potions refill stamina (no auto-regen); stow in hotbar when full
        refilled = update_sprint_pots(sprint_pots, camera_x, player_world_rect,
                                      spikes, green_ticks >= sprint_ticks)
        if refilled:
            green_ticks = min(sprint_ticks, green_ticks + refilled * SPRINT_REFILL)
        update_stars(stars, camera_x, player_world_rect)
        # Track furthest distance from spawn for the run's meter count
        max_distance = max(max_distance, abs(x))

        # Hazards: spikes and moving obstacles hurt and shove the slime backwards
        hit_hazard = False
        hazard_center = None
        for spike in spikes:
            if player_world_rect.colliderect(spike_hitbox(spike)):
                hit_hazard, hazard_center = True, spike["x"] + SPIKE_WIDTH / 2
                hazard_dmg = spike_damage
                break
        if not hit_hazard:
            for ob in obstacles:
                if player_world_rect.colliderect(obstacle_hitbox(ob)):
                    hit_hazard, hazard_center = True, obstacle_x(ob) + OBSTACLE_SIZE / 2
                    hazard_dmg = obstacle_damage
                    break
        if hit_hazard and current_time >= invincible_until:
            push_dir = -1 if (x + square_size / 2) < hazard_center else 1
            knockback_velocity_x = push_dir * MONSTER_KNOCKBACK
            if current_time - last_hazard_hit_time >= HAZARD_COOLDOWN_MS:
                health_bar.damage(hazard_dmg)
                last_hazard_hit_time = current_time

        # Trailing void border: it only ever advances, so it stays offscreen
        # while you push forward — but backtracking runs the slime into it.
        border_x = advance_border(border_x, x)
        if x <= border_x:
            x = border_x + 1  # solid wall: keep the slime out of the void
            if (current_time >= invincible_until
                    and current_time - last_hazard_hit_time >= HAZARD_COOLDOWN_MS):
                knockback_velocity_x = BORDER_KNOCKBACK
                health_bar.damage(BORDER_DAMAGE)
                last_hazard_hit_time = current_time

        # Boss zone: opens the first time you reach BOSS_METERS and stays open
        # (dragon + red sky) even if you fall back — closing only once you reach
        # BOSS_END_METERS, at which point the dragon flies off.
        current_m = x / PIXELS_PER_METER

        if not boss_triggered and current_m >= BOSS_METERS:
            boss_triggered = True
            boss_zone_active = True
            obstacle_speed *= 1.6
            obstacle_gap = max(240, int(obstacle_gap * 0.55))
            spike_gap = max(180, int(spike_gap * 0.6))
            obstacle_damage += 10
            spike_damage += 8
            monster_max += 12
            boss_banner_until = current_time + 3500

        if boss_zone_active and current_m >= BOSS_END_METERS:
            boss_zone_active = False              # cleared the gate
            if boss_dragon is not None:
                boss_dragon["fleeing"] = True     # send it soaring off

        # While the zone is open, keep a dragon in play (unless already slain)
        if boss_zone_active and boss_dragon is None and not boss_dragon_cleared:
            boss_dragon = spawn_dragon(x + SCREEN_W)

        # Flying dragon boss: weaves and swoops; hurts on contact, dies to a stomp.
        # While fleeing it just soars off and can't be hit.
        if boss_dragon is not None:
            update_dragon(boss_dragon, x, y, current_time)
            if boss_dragon.get("fleeing"):
                if boss_dragon["y"] < camera_y - 220:
                    boss_dragon = None              # gone once it clears the top
            elif player_world_rect.colliderect(dragon_hitbox(boss_dragon)):
                feet_prev = prev_y + square_size
                is_stomp = vertical_velocity > 0 and feet_prev <= boss_dragon["y"] - 6
                if is_stomp:
                    boss_dragon = None              # slay the dragon
                    boss_dragon_cleared = True      # stays gone until you leave the zone
                    vertical_velocity = jump_strength * 0.9   # big bounce off it
                    invincible_until = max(invincible_until, current_time + CONSUME_IFRAME_MS)
                elif current_time >= invincible_until:
                    push_dir = -1 if (x + square_size / 2) < boss_dragon["x"] else 1
                    knockback_velocity_x = push_dir * MONSTER_KNOCKBACK
                    if current_time - last_hazard_hit_time >= HAZARD_COOLDOWN_MS:
                        health_bar.damage(obstacle_damage + 6)
                        last_hazard_hit_time = current_time

    # Screen-space rect (centered horizontally; vertical position is true world Y)
    player_screen_x, player_screen_y = world_to_screen(x, y, camera_x, camera_y)
    player_rect = pygame.Rect(
        int(player_screen_x), int(player_screen_y), square_size, square_size
    )

    current_time = pygame.time.get_ticks()
    # Stamina no longer regenerates on its own — refill it with sprint potions.

    # Trigger the death sequence the moment HP hits zero
    if health_bar.is_dead and not game_over:
        game_over = True
        death_time = current_time
        knockback_velocity_x = 0.0
        vertical_velocity = 0

    draw_sky(screen, current_time)
    draw_clouds(screen, camera_x, current_time)
    # Boss zone: wash the sky red for as long as the zone is open
    if boss_zone_active:
        boss_tint = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        boss_tint.fill((185, 20, 20, 130))
        screen.blit(boss_tint, (0, 0))
    draw_ground_platform(screen, GROUND_TOP, camera_x, camera_y)
    # Shadows land on the ground under each island, then islands draw above
    draw_island_ground_shadows(screen, islands, GROUND_TOP, camera_x, camera_y)

    for island in islands:
        # Only draw islands near the view for a bit of extra performance
        sx = island["x"] - camera_x
        if sx + island["width"] < -50 or sx > SCREEN_W + 50:
            continue
        draw_island(screen, island, camera_x, camera_y)

    for spike in spikes:
        sx = spike["x"] - camera_x
        if sx + SPIKE_WIDTH < -20 or sx > SCREEN_W + 20:
            continue
        draw_spike(screen, spike, camera_x, camera_y)

    for monster in monsters:
        draw_monster(screen, monster, camera_x, camera_y, current_time)

    for ob in obstacles:
        sx = obstacle_x(ob) - camera_x
        if sx + OBSTACLE_SIZE < -40 or sx > SCREEN_W + 40:
            continue
        draw_obstacle(screen, ob, camera_x, camera_y, current_time)

    for potion in potions:
        sx = potion["x"] - camera_x
        if sx + potion["width"] < -60 or sx > SCREEN_W + 60:
            continue
        draw_potion(screen, potion, camera_x, camera_y, current_time)

    for pot in sprint_pots:
        sx = pot["x"] - camera_x
        if sx + pot["width"] < -60 or sx > SCREEN_W + 60:
            continue
        draw_sprint_pot(screen, pot, camera_x, camera_y, current_time)

    for star in stars:
        sx = star["x"] - camera_x
        if sx + STAR_SIZE < -60 or sx > SCREEN_W + 60:
            continue
        draw_star(screen, star, camera_x, camera_y, current_time)

    # Dotted red gate line marking the end of the boss zone (BOSS_END_METERS)
    gate_screen = int(BOSS_END_METERS * PIXELS_PER_METER - camera_x)
    if -6 <= gate_screen <= SCREEN_W + 6:
        for gy in range(0, SCREEN_H, 26):
            pygame.draw.line(screen, (255, 70, 70),
                             (gate_screen, gy), (gate_screen, gy + 14), 4)

    # The flying dragon boss soars above the scene
    if boss_dragon is not None:
        draw_dragon(screen, boss_dragon, camera_x, camera_y, current_time)

    # The trailing void border, drawn over the world it has swallowed
    draw_border(screen, border_x, camera_x, current_time)

    draw_slime_shadow(
        screen,
        x,
        y,
        square_size,
        islands,
        GROUND_TOP,
        camera_x,
        camera_y,
        crouching=crouching,
        landing_squash=landing_squash_frames > 0,
    )

    if game_over:
        # Draw the melting death animation, then park the live-slime rect off
        # screen so the normal slime/eyes drawing below renders invisibly.
        death_progress = (current_time - death_time) / DEATH_ANIM_MS
        draw_dead_slime(screen, player_rect, death_progress)
        player_rect = pygame.Rect(-9999, -9999, square_size, square_size)
    elif consuming is not None:
        consume_t = (current_time - consuming["start"]) / CONSUME_ANIM_MS
        if consume_t >= 1:
            consuming = None  # animation done; slime stays put where it ate
        else:
            # Draw the enclosing slime and park the normal rect off screen
            draw_consuming(
                screen, player_rect, consume_t,
                consuming["ew"], consuming["eh"], consuming["ecolor"],
            )
            player_rect = pygame.Rect(-9999, -9999, square_size, square_size)

    display_player_rect = player_rect.copy()
    display_player_rect.x -= 4
    display_player_rect.y += 5
    display_player_rect.width += 8
    display_player_rect.height -= 5
    if not on_ground:
        second_jump_elapsed = pygame.time.get_ticks() - second_jump_started_at
        is_intermediate_frame = second_jump_started_at and (
            second_jump_elapsed < 16 or 31 <= second_jump_elapsed < 47
        )
        is_wide_second_jump = second_jump_started_at and 16 <= second_jump_elapsed < 31

        if is_wide_second_jump:
            # Second jump: flip the first-jump proportions into a wide, flat ellipse.
            display_player_rect.x -= 3
            display_player_rect.y += 4
            display_player_rect.width += 6
            display_player_rect.height -= 8
        elif is_intermediate_frame:
            # Midpoint between the tall and wide ellipse poses.
            display_player_rect.x += 2
            display_player_rect.width -= 4
        else:
            # First jump: use a taller ellipse with an 8-pixel smaller horizontal radius.
            display_player_rect.x += 8
            display_player_rect.y -= 4
            display_player_rect.width -= 16
            display_player_rect.height += 8
        display_player_rect.x -= 5
        display_player_rect.y -= 5
        display_player_rect.width += 10
        display_player_rect.height += 10
        pygame.draw.ellipse(screen, (0, 200, 0), display_player_rect)
    elif landing_squash_frames > 0:
        # Landing: keep the bottom fixed while briefly spreading out.
        display_player_rect.x -= 6
        display_player_rect.y += 10
        display_player_rect.width += 12
        display_player_rect.height -= 10
        draw_slime(screen, display_player_rect)
    elif crouching:
        # Keep the bottom fixed while making the player shorter and wider.
        display_player_rect.x -= 7
        display_player_rect.y += 15
        display_player_rect.width += 14
        display_player_rect.height -= 15
        draw_slime(screen, display_player_rect)
    else:
        # Apply bobbing animation when moving on the ground
        bob_offset = 0
        if on_ground and (moving_left or moving_right):
            bob_offset = round(math.sin(current_time * bob_frequency * 0.01) * bob_amplitude)
        
        # Bobbing: keep bottom fixed, top bounces up and down
        display_player_rect.y -= bob_offset
        display_player_rect.height += bob_offset

        # Smooth tail stretch: sine ease between 0 and max (no hard on/off toggle)
        if moving_left and not moving_right or moving_right and not moving_left:
            phase = (current_time % tail_cycle_ms) / tail_cycle_ms * math.pi * 2
            # (sin + 1) / 2 → 0..1 with soft ease at both ends
            stretch = (math.sin(phase) + 1) * 0.5 * tail_max_stretch
            stretch_px = round(stretch)
            if moving_left and not moving_right:
                display_player_rect.width += stretch_px
            else:
                display_player_rect.x -= stretch_px
                display_player_rect.width += stretch_px
        draw_slime(screen, display_player_rect)

    look_x = 0
    look_y = 0
    if moving_left and not moving_right:
        look_x = -2
    elif moving_right and not moving_left:
        look_x = 2
    if vertical_velocity < 0:
        look_y = -2
    elif vertical_velocity > 0:
        look_y = 2
    draw_eyes(
        screen,
        display_player_rect,
        look_x,
        look_y,
        6 if not on_ground else 0,
        blink=is_blinking(current_time),
    )

    # Invincibility shield: pulsing golden ring around the slime, flickering as
    # it wears off, so the player can see the post-consume buff is active.
    if not game_over and current_time < invincible_until:
        remaining = invincible_until - current_time
        if remaining > 600 or (current_time // 90) % 2 == 0:
            alpha = int(120 + math.sin(current_time * 0.02) * 60)
            ring = pygame.Surface((square_size * 3, square_size * 3), pygame.SRCALPHA)
            rc = ring.get_width() // 2
            rad = int(square_size * 0.9 + math.sin(current_time * 0.02) * 3)
            pygame.draw.circle(ring, (255, 225, 90, alpha), (rc, rc), rad, 3)
            pygame.draw.circle(ring, (255, 245, 170, alpha // 2), (rc, rc), max(1, rad - 4), 2)
            screen.blit(ring, (display_player_rect.centerx - rc, display_player_rect.centery - rc))

    if landing_squash_frames > 0:
        landing_squash_frames -= 1

    # Dim the world toward night (after the scene, before the HUD stays bright)
    draw_night_veil(screen, current_time)

    # Distance meter: the slime's current position, so it drops when backtracking
    draw_distance(screen, int(x / PIXELS_PER_METER))

    health_bar.update()
    health_bar.draw(screen)
    draw_stamina_bar(screen, get_stamina_bar_rect(), green_ticks / sprint_ticks,
                     sprinting, current_time)
    draw_hotbar(screen, selected_hotbar_slot)

    # Boss-zone warning banner, fading out over its final stretch
    if not game_over and current_time < boss_banner_until:
        remaining = boss_banner_until - current_time
        banner_alpha = 255 if remaining > 2500 else int(255 * remaining / 2500)
        draw_boss_banner(screen, banner_alpha)

    if game_over:
        meters = int(max_distance / PIXELS_PER_METER)
        draw_death_screen(screen, meters)

    pygame.display.update()
    clock.tick(60)
