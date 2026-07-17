"""World terrain: floating islands, the scrolling ground tile, clouds, and
the geometry/collision helpers that go with them."""
import math

import pygame

from config import *

_ground_tile_surf = None  # ground strip, built lazily on first draw


def get_active_islands(camera_x, view_width):
    """Build island instances for map chunks near the camera."""
    margin = CHUNK_WIDTH
    left = camera_x - margin
    right = camera_x + view_width + margin
    first_chunk = math.floor(left / CHUNK_WIDTH) - 1
    last_chunk = math.floor(right / CHUNK_WIDTH) + 1
    active = []
    for chunk_i in range(first_chunk, last_chunk + 1):
        # Slight vertical variety per chunk so repeats feel less identical
        y_shift = int(math.sin(chunk_i * 2.17) * 20)
        for template in ISLAND_TEMPLATES:
            active.append(
                {
                    "x": template["x"] + chunk_i * CHUNK_WIDTH,
                    "y": template["y"] + y_shift,
                    "width": template["width"],
                    "height": template["height"],
                }
            )
    return active


def island_at_world_x(wx):
    """Island instance whose horizontal span covers world x, or None.

    Mirrors the chunk math in get_active_islands (including per-chunk y_shift)
    so a placed obstacle lines up exactly with the drawn platform.
    """
    base_chunk = math.floor(wx / CHUNK_WIDTH)
    for chunk_i in (base_chunk - 1, base_chunk, base_chunk + 1):
        y_shift = int(math.sin(chunk_i * 2.17) * 20)
        for template in ISLAND_TEMPLATES:
            ix = template["x"] + chunk_i * CHUNK_WIDTH
            if ix <= wx <= ix + template["width"]:
                return {
                    "x": ix,
                    "y": template["y"] + y_shift,
                    "width": template["width"],
                    "height": template["height"],
                }
    return None


def world_to_screen(wx, wy, camera_x, camera_y):
    """Convert world coordinates to screen coordinates."""
    return wx - camera_x, wy - camera_y


def _island_tip_x(island):
    """World x of the inverted-triangle's bottom point (matches draw_island)."""
    seed = int(island["x"] * 7 + island["y"] * 13)
    return island["x"] + island["width"] * (0.42 + _pseudo_rand(seed, 0) * 0.16)


def island_solid_span(island, world_y):
    """Left/right x of the solid triangle at a given world y (point at the tip)."""
    height = island["height"]
    t = (world_y - island["y"]) / height if height else 0.0
    t = max(0.0, min(1.0, t))
    tip_x = _island_tip_x(island)
    left = island["x"] + (tip_x - island["x"]) * t
    right = (island["x"] + island["width"]) + (tip_x - island["x"] - island["width"]) * t
    return left, right


def get_support_surface_y(player_x, player_bottom, square_size, islands, ground_top):
    """Y of the nearest platform top at or below the slime's feet (world space)."""
    surface_y = ground_top
    left = player_x
    right = player_x + square_size
    for island in islands:
        if right > island["x"] and left < island["x"] + island["width"]:
            top = island["y"]
            if top >= player_bottom - 4:
                surface_y = min(surface_y, top)
    return surface_y


def resolve_island_x(x, y, prev_x, square_size, islands):
    """Block horizontal movement into the solid inverted-triangle body."""
    for island in islands:
        top = island["y"]
        bottom = island["y"] + island["height"]
        # Vertical overlap first (Y has not changed this step)
        if y + square_size <= top or y >= bottom:
            continue
        # Solid width at the highest overlapping row — the triangle is widest
        # there, so this matches the sprite instead of a full rectangle.
        left, right = island_solid_span(island, max(y, top))
        if x + square_size <= left or x >= right:
            continue
        # Came from the left side of the island
        if prev_x + square_size <= left:
            x = left - square_size
        # Came from the right side of the island
        elif prev_x >= right:
            x = right
        # Already overlapping: push out along the smaller horizontal penetration
        else:
            push_left = (x + square_size) - left
            push_right = right - x
            if push_left < push_right:
                x = left - square_size
            else:
                x = right
    return x


def resolve_island_y(x, y, prev_y, square_size, vertical_velocity, islands):
    """
    Block vertical movement into solid islands.
    Lands on tops, bounces off undersides, and stops tunneling through the body.
    Returns (y, vertical_velocity, landed_on_island).
    """
    landed = False
    for island in islands:
        top = island["y"]
        bottom = island["y"] + island["height"]

        # Solid width where the player's column meets the triangle (widest at
        # the top overlap row); the flat top stays full width for landing.
        left, right = island_solid_span(island, max(y, top))
        if x + square_size <= left or x >= right:
            continue

        prev_bottom = prev_y + square_size
        prev_top = prev_y
        cur_bottom = y + square_size
        cur_top = y

        # Landing: feet crossed or rest on the island top while falling
        crossed_top = prev_bottom <= top and cur_bottom >= top
        resting_on_top = (
            cur_bottom >= top
            and cur_bottom <= top + max(vertical_velocity, 0) + 2
            and prev_bottom <= top + 1
        )
        if vertical_velocity >= 0 and (crossed_top or resting_on_top):
            y = top - square_size
            vertical_velocity = 0
            landed = True
            continue

        # Ceiling: head crossed or entered the underside while rising
        crossed_bottom = prev_top >= bottom and cur_top <= bottom
        hit_underside = cur_top < bottom and cur_bottom > top and prev_top >= bottom - 1
        if vertical_velocity < 0 and (crossed_bottom or hit_underside):
            y = bottom
            vertical_velocity = 0
            continue

        # Still overlapping the body (high speed / corner entry): eject along the
        # axis of least penetration. When the horizontal overlap is smaller it's
        # a side hit — leave y alone and let resolve_island_x stop the slime, so
        # brushing a wall never snaps it up or down.
        if cur_bottom > top and cur_top < bottom:
            dist_up = cur_bottom - top
            dist_down = bottom - cur_top
            pen_vertical = min(dist_up, dist_down)
            pen_horizontal = min((x + square_size) - left, right - x)
            if pen_vertical <= pen_horizontal:
                if dist_up <= dist_down:
                    y = top - square_size
                    if vertical_velocity > 0:
                        vertical_velocity = 0
                    landed = True
                else:
                    y = bottom
                    if vertical_velocity < 0:
                        vertical_velocity = 0

    return y, vertical_velocity, landed


def draw_cloud(surface, cx, cy, scale=1.0):
    """Draw a soft puffy cloud from layered ellipses (center at cx, cy)."""
    # Shadow/base puffs slightly below, then bright tops for volume
    puffs = (
        # (dx, dy, w, h, color)
        (-28, 6, 52, 28, (210, 230, 245)),
        (22, 8, 48, 26, (210, 230, 245)),
        (-6, 10, 60, 30, (200, 220, 240)),
        (-34, -2, 44, 30, (245, 252, 255)),
        (30, 0, 40, 28, (245, 252, 255)),
        (-4, -12, 50, 36, (255, 255, 255)),
        (12, -6, 36, 28, (255, 255, 255)),
        (-18, -4, 34, 26, (250, 254, 255)),
    )
    for dx, dy, w, h, color in puffs:
        rw = max(8, int(w * scale))
        rh = max(6, int(h * scale))
        rect = pygame.Rect(
            int(cx + dx * scale - rw / 2),
            int(cy + dy * scale - rh / 2),
            rw,
            rh,
        )
        pygame.draw.ellipse(surface, color, rect)


def draw_clouds(surface, camera_x, time_ms=0):
    """Draw a cloud band across the top of the sky.

    Clouds are anchored in world space, so they scroll past with the ground as
    the player moves through the world (rather than staying stuck to the screen).
    A gentle idle drift keeps them alive when the player is still.
    """
    scroll = (-camera_x + time_ms * 0.012) % CLOUD_STRIP_WIDTH

    # Cover the screen with enough strips for the view width
    screen_w = surface.get_width()
    start = -CLOUD_STRIP_WIDTH - int(scroll)
    x_base = start
    while x_base < screen_w + CLOUD_STRIP_WIDTH:
        for i, cloud in enumerate(CLOUD_TEMPLATES):
            # Soft vertical bob so clouds feel alive
            bob = math.sin(time_ms * 0.0011 + i * 1.7) * 3.5
            cx = x_base + cloud["x"] + scroll
            cy = cloud["y"] + bob
            # Skip far off-screen clouds
            if cx < -120 or cx > screen_w + 120:
                continue
            draw_cloud(surface, cx, cy, cloud["scale"])
        x_base += CLOUD_STRIP_WIDTH


def _pseudo_rand(seed, index):
    """Deterministic 0..1 value so island details stay stable every frame."""
    value = math.sin(seed * 12.9898 + index * 78.233) * 43758.5453
    return value - math.floor(value)


def _draw_grass_tuft(surface, base_x, base_y, scale=1.0, seed=0):
    """Small cluster of grass blades along a surface."""
    blade_color = (46, 160, 55)
    highlight = (90, 200, 80)
    for i in range(4):
        offset = (i - 1.5) * 3 * scale
        height = (6 + _pseudo_rand(seed, i) * 5) * scale
        lean = (_pseudo_rand(seed, i + 4) - 0.5) * 4 * scale
        tip = (base_x + offset + lean, base_y - height)
        left = (base_x + offset - 1.5 * scale, base_y + 1)
        right = (base_x + offset + 1.5 * scale, base_y + 1)
        color = highlight if i % 2 == 0 else blade_color
        pygame.draw.polygon(surface, color, [left, tip, right])


def _draw_rock(surface, center_x, center_y, size, seed=0):
    """Irregular pebble / boulder on top of an island."""
    points = []
    for i in range(6):
        angle = (math.pi * 2 * i / 6) + _pseudo_rand(seed, i) * 0.4
        radius = size * (0.65 + _pseudo_rand(seed, i + 10) * 0.45)
        points.append(
            (
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius * 0.7,
            )
        )
    pygame.draw.polygon(surface, (105, 100, 92), points)
    # Soft highlight and shadow for volume
    pygame.draw.polygon(
        surface,
        (145, 138, 125),
        [
            points[0],
            points[1],
            (
                center_x - size * 0.15,
                center_y - size * 0.1,
            ),
        ],
    )
    pygame.draw.polygon(
        surface,
        (70, 66, 60),
        [
            points[3],
            points[4],
            (
                center_x + size * 0.1,
                center_y + size * 0.15,
            ),
        ],
    )


def _draw_flower(surface, x, y, seed=0):
    """Tiny flower for top-of-island decoration."""
    petal = (
        (220, 80, 100)
        if _pseudo_rand(seed, 1) < 0.5
        else (240, 210, 70)
    )
    for angle in (0, 90, 180, 270):
        rad = math.radians(angle)
        px = x + math.cos(rad) * 3
        py = y + math.sin(rad) * 2
        pygame.draw.circle(surface, petal, (int(px), int(py)), 2)
    pygame.draw.circle(surface, (255, 230, 90), (int(x), int(y)), 2)


def _draw_bush(surface, x, y, width=16):
    """Rounded leafy bush on the island surface."""
    pygame.draw.ellipse(surface, (28, 110, 40), (x - width // 2, y - 10, width, 14))
    pygame.draw.ellipse(surface, (40, 145, 55), (x - width // 2 + 2, y - 12, width - 4, 12))
    pygame.draw.ellipse(surface, (55, 170, 65), (x - 4, y - 11, 8, 8))


def draw_island(surface, island, camera_x=0, camera_y=0):
    """Draw a floating island as an inverted triangle with layers, shading, and props."""
    width = island["width"]
    height = island["height"]
    seed = int(island["x"] * 7 + island["y"] * 13)
    x = island["x"] - camera_x
    y = island["y"] - camera_y

    # Tip sits near the center, slightly offset for a more natural rock mass
    tip_x = x + width * (0.42 + _pseudo_rand(seed, 0) * 0.16)
    tip_y = y + height
    top_left = (x, y)
    top_right = (x + width, y)
    tip = (tip_x, tip_y)

    # Main stone body — classic upside-down triangle
    body = [top_left, top_right, tip]
    pygame.draw.polygon(surface, (112, 105, 95), body)

    # Right-side shade (away from light)
    shade_mid = (
        x + width * 0.55,
        y + height * 0.35,
    )
    pygame.draw.polygon(
        surface,
        (78, 72, 65),
        [top_right, tip, shade_mid],
    )

    # Left-side highlight
    highlight_mid = (
        x + width * 0.28,
        y + height * 0.32,
    )
    pygame.draw.polygon(
        surface,
        (138, 130, 118),
        [top_left, highlight_mid, tip],
    )

    # Dirt band under the grass cap (trapezoid tapering down)
    dirt_depth = height * 0.28
    dirt_inset = width * 0.08
    dirt_shape = [
        (x + 2, y + 4),
        (x + width - 2, y + 4),
        (x + width - dirt_inset, y + dirt_depth),
        (x + dirt_inset, y + dirt_depth),
    ]
    pygame.draw.polygon(surface, (120, 78, 42), dirt_shape)
    # Dirt shade on the right half
    pygame.draw.polygon(
        surface,
        (95, 58, 30),
        [
            (x + width * 0.55, y + 4),
            (x + width - 2, y + 4),
            (x + width - dirt_inset, y + dirt_depth),
            (x + width * 0.5, y + dirt_depth),
        ],
    )

    # Deeper stone core for the lower half of the triangle
    core_top = y + dirt_depth * 0.85
    core = [
        (x + width * 0.18, core_top),
        (x + width * 0.82, core_top),
        tip,
    ]
    pygame.draw.polygon(surface, (95, 90, 82), core)
    pygame.draw.polygon(
        surface,
        (68, 64, 58),
        [
            (x + width * 0.55, core_top),
            (x + width * 0.82, core_top),
            tip,
        ],
    )

    # Rock cracks / strata lines for texture
    for i in range(4):
        t = 0.2 + i * 0.18
        line_y = y + height * t
        left_x = x + (tip_x - x) * t
        right_x = x + width - (x + width - tip_x) * t
        # Slightly wavy strata
        mid_x = (left_x + right_x) / 2
        mid_y = line_y + (_pseudo_rand(seed, 20 + i) - 0.5) * 4
        color = (60, 55, 50) if i % 2 == 0 else (125, 118, 108)
        pygame.draw.lines(
            surface,
            color,
            False,
            [
                (left_x + 4, line_y),
                (mid_x, mid_y),
                (right_x - 4, line_y),
            ],
            1,
        )

    # Speckles / pebbles embedded in the rock face
    for i in range(8):
        t = 0.25 + _pseudo_rand(seed, 30 + i) * 0.55
        across = 0.15 + _pseudo_rand(seed, 40 + i) * 0.7
        left_edge = x + (tip_x - x) * t
        right_edge = x + width - (x + width - tip_x) * t
        px = left_edge + (right_edge - left_edge) * across
        py = y + height * t
        radius = 1 + int(_pseudo_rand(seed, 50 + i) * 2)
        speck = (55, 50, 45) if _pseudo_rand(seed, 60 + i) < 0.5 else (140, 132, 120)
        pygame.draw.circle(surface, speck, (int(px), int(py)), radius)

    # Moss patches clinging to the lower rock
    for i in range(3):
        t = 0.55 + _pseudo_rand(seed, 70 + i) * 0.3
        across = 0.25 + _pseudo_rand(seed, 80 + i) * 0.5
        left_edge = x + (tip_x - x) * t
        right_edge = x + width - (x + width - tip_x) * t
        mx = left_edge + (right_edge - left_edge) * across
        my = y + height * t
        pygame.draw.ellipse(
            surface,
            (55, 120, 50),
            (int(mx - 5), int(my - 3), 10, 6),
        )

    # Hanging roots / vines from the underside of the dirt band
    for i in range(3):
        root_x = x + width * (0.25 + i * 0.22 + _pseudo_rand(seed, 90 + i) * 0.05)
        root_top = y + dirt_depth
        root_len = 10 + _pseudo_rand(seed, 100 + i) * 14
        pygame.draw.line(
            surface,
            (90, 60, 35),
            (root_x, root_top),
            (root_x + (_pseudo_rand(seed, 110 + i) - 0.5) * 6, root_top + root_len),
            2,
        )

    # Grass cap — slightly raised, softly uneven top edge
    grass_points = []
    steps = max(6, int(width // 10))
    for i in range(steps + 1):
        t = i / steps
        gx = x + width * t
        wave = math.sin(t * math.pi * 2 + seed) * 1.5
        grass_points.append((gx, y - 3 + wave))
    # Drop grass sides slightly down the triangle for thickness
    grass_points.append((x + width - 3, y + 10))
    grass_points.append((x + 3, y + 10))
    pygame.draw.polygon(surface, (42, 145, 48), grass_points)

    # Grass highlight strip near the front-left
    highlight_grass = []
    for i in range(steps // 2 + 1):
        t = i / max(1, steps // 2) * 0.55
        gx = x + width * t
        wave = math.sin(t * math.pi * 2 + seed) * 1.5
        highlight_grass.append((gx, y - 3 + wave))
    highlight_grass.append((x + width * 0.55, y + 7))
    highlight_grass.append((x + 4, y + 7))
    pygame.draw.polygon(surface, (70, 175, 70), highlight_grass)

    # Dark grass edge along the right / back for depth
    pygame.draw.line(
        surface,
        (28, 100, 35),
        (x + width * 0.5, y - 2),
        (x + width - 2, y + 1),
        2,
    )

    # Surface props: tufts, rocks, flowers, bushes (deterministic)
    _draw_grass_tuft(surface, x + width * 0.18, y - 1, 0.9, seed + 1)
    _draw_grass_tuft(surface, x + width * 0.4, y - 2, 1.1, seed + 2)
    _draw_grass_tuft(surface, x + width * 0.72, y - 1, 0.85, seed + 3)

    if _pseudo_rand(seed, 120) > 0.35:
        _draw_rock(
            surface,
            x + width * (0.3 + _pseudo_rand(seed, 121) * 0.2),
            y + 2,
            5 + _pseudo_rand(seed, 122) * 3,
            seed + 5,
        )
    if _pseudo_rand(seed, 123) > 0.4:
        _draw_rock(
            surface,
            x + width * (0.65 + _pseudo_rand(seed, 124) * 0.15),
            y + 3,
            4 + _pseudo_rand(seed, 125) * 2,
            seed + 6,
        )

    if _pseudo_rand(seed, 130) > 0.45:
        _draw_flower(
            surface,
            x + width * (0.25 + _pseudo_rand(seed, 131) * 0.2),
            y - 5,
            seed + 7,
        )
    if _pseudo_rand(seed, 132) > 0.5:
        _draw_flower(
            surface,
            x + width * (0.55 + _pseudo_rand(seed, 133) * 0.2),
            y - 4,
            seed + 8,
        )

    if width >= 110 and _pseudo_rand(seed, 140) > 0.3:
        _draw_bush(surface, x + width * 0.78, y - 1, int(14 + _pseudo_rand(seed, 141) * 6))
    elif width >= 100:
        _draw_bush(surface, x + width * 0.22, y, 12)

    # Sharp tip accent so the inverted triangle reads clearly
    pygame.draw.polygon(
        surface,
        (55, 52, 48),
        [
            (tip_x - 6, tip_y - 8),
            (tip_x + 6, tip_y - 8),
            tip,
        ],
    )
    pygame.draw.circle(surface, (70, 66, 60), (int(tip_x), int(tip_y - 2)), 3)


def _ground_crest_y(top, gx):
    """Uneven grass height; matches the tiled ground strip (periodic)."""
    lx = gx % GROUND_TILE_WIDTH
    wave = (
        math.sin(lx * (2 * math.pi * 2 / GROUND_TILE_WIDTH)) * 5
        + math.sin(lx * (2 * math.pi * 5 / GROUND_TILE_WIDTH) + 1.2) * 3
        + math.sin(lx * (2 * math.pi * 8 / GROUND_TILE_WIDTH)) * 1.5
    )
    return top - 1 - abs(wave) * 0.45


def draw_island_ground_shadows(surface, islands, ground_top, camera_x, camera_y):
    """Cast each island's shadow onto the ground platform (world → screen)."""
    for island in islands:
        ix = island["x"]
        iy = island["y"]
        width = island["width"]
        seed = int(ix * 7 + iy * 13)

        # Same tip x as draw_island so the shadow sits under the rock mass
        tip_x = ix + width * (0.42 + _pseudo_rand(seed, 0) * 0.16)
        center_x = ix + width * 0.5

        # Higher islands cast slightly larger, softer shadows
        height_above = max(40, ground_top - iy)
        size_scale = 0.9 + min(0.55, height_above / 500)
        shadow_w = max(36, int(width * 1.15 * size_scale))
        shadow_h = max(12, int(18 * size_scale))

        # Light from upper-left → nudge shadow a bit right/down on the ground
        world_cx = center_x * 0.45 + tip_x * 0.55 + width * 0.08
        world_cy = _ground_crest_y(ground_top, world_cx) + shadow_h * 0.35
        shadow_cx, shadow_cy = world_to_screen(world_cx, world_cy, camera_x, camera_y)
        shadow_cx, shadow_cy = int(shadow_cx), int(shadow_cy)

        # Skip if far off-screen
        if shadow_cx < -shadow_w or shadow_cx > surface.get_width() + shadow_w:
            continue
        if shadow_cy < -shadow_h or shadow_cy > surface.get_height() + shadow_h:
            continue

        outer = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(outer, (25, 45, 30, 70), outer.get_rect())
        surface.blit(outer, (shadow_cx - shadow_w // 2, shadow_cy - shadow_h // 2))

        inner_w = max(20, int(shadow_w * 0.62))
        inner_h = max(8, int(shadow_h * 0.55))
        inner = pygame.Surface((inner_w, inner_h), pygame.SRCALPHA)
        pygame.draw.ellipse(inner, (20, 35, 25, 95), inner.get_rect())
        surface.blit(inner, (shadow_cx - inner_w // 2, shadow_cy - inner_h // 2 + 1))


def build_ground_tile(ground_top):
    """
    Bake one seamless ground strip: grass, dirt, gray rock, plants, pebbles.
    The whole strip is blitted with a camera offset so every layer scrolls together.
    """
    width = GROUND_TILE_WIDTH
    # Tile is only as tall as the ground stack; y=0 is the top of the walkable crest area
    height = GROUND_DEPTH + 24
    tile = pygame.Surface((width, height), pygame.SRCALPHA)
    # Local coords: crest near y=12 so plants above crest still fit on the tile
    local_top = 12
    step = 12

    def period_wave(lx, cycles, phase=0.0):
        """Wave that matches at lx=0 and lx=width so tiles join seamlessly."""
        return math.sin(lx * (2 * math.pi * cycles / width) + phase)

    def crest_local(lx):
        wave = (
            period_wave(lx, 2) * 5
            + period_wave(lx, 5, 1.2) * 3
            + period_wave(lx, 8) * 1.5
        )
        return local_top - 1 - abs(wave) * 0.45

    # --- Grass ---
    grass_top_points = [(gx, crest_local(gx)) for gx in range(0, width, step)]
    grass_top_points.append((width, crest_local(0)))  # matches left edge for seamless tiling
    grass_depth = 38
    grass_poly = list(grass_top_points)
    grass_poly.append((width, local_top + grass_depth))
    grass_poly.append((0, local_top + grass_depth))
    pygame.draw.polygon(tile, (40, 140, 48), grass_poly)

    light_grass = list(grass_top_points)
    for gx in range(width, -1, -step):
        wave = period_wave(gx if gx < width else 0, 2) * 5 + period_wave(gx if gx < width else 0, 5, 1.2) * 3
        light_grass.append((gx, local_top + 14 + wave * 0.3))
    pygame.draw.polygon(tile, (62, 168, 62), light_grass)

    soil_edge = []
    for gx in range(0, width + step, step):
        lx = 0 if gx >= width else gx
        wave = period_wave(lx, 3, 0.5) * 3
        soil_edge.append((gx, local_top + grass_depth - 4 + wave))
    soil_edge.append((width, local_top + grass_depth + 8))
    soil_edge.append((0, local_top + grass_depth + 8))
    pygame.draw.polygon(tile, (28, 95, 32), soil_edge)

    # --- Dirt ---
    dirt_top = local_top + grass_depth - 2
    dirt_bottom = local_top + 105
    dirt_poly = []
    for gx in range(0, width + step, step):
        lx = 0 if gx >= width else gx
        wave = period_wave(lx, 2, 2) * 4
        dirt_poly.append((gx, dirt_top + wave))
    for gx in range(width, -1, -step):
        lx = 0 if gx >= width else gx
        wave = period_wave(lx, 1, 0) * 5
        dirt_poly.append((gx, dirt_bottom + wave))
    pygame.draw.polygon(tile, (118, 76, 40), dirt_poly)

    for band in range(3):
        band_y = dirt_top + 18 + band * 18
        shade = (100 - band * 8, 62 - band * 5, 32 - band * 3)
        points = []
        for gx in range(0, width + step, step):
            lx = 0 if gx >= width else gx
            wave = period_wave(lx, 2, band) * 3
            points.append((gx, band_y + wave))
        for gx in range(width, -1, -step):
            lx = 0 if gx >= width else gx
            wave = period_wave(lx, 2, band) * 3
            points.append((gx, band_y + 12 + wave))
        pygame.draw.polygon(tile, shade, points)

    for gx in range(0, width, 28):
        cell = gx // 28
        sy = dirt_top + 10 + _pseudo_rand(cell, 240) * (dirt_bottom - dirt_top - 20)
        color = (90, 55, 28) if _pseudo_rand(cell, 280) < 0.5 else (145, 100, 55)
        pygame.draw.circle(
            tile,
            color,
            (int(gx + _pseudo_rand(cell, 200) * 20), int(sy)),
            1 + int(_pseudo_rand(cell, 300) * 2),
        )

    # --- Gray rock (same tile → must scroll with grass) ---
    stone_top = dirt_bottom - 8
    stone_poly = []
    for gx in range(0, width + 20, 20):
        jagged = (_pseudo_rand(gx // 20, 400) - 0.5) * 12
        stone_poly.append((gx, stone_top + jagged))
    stone_poly.append((width, height))
    stone_poly.append((0, height))
    pygame.draw.polygon(tile, (115, 108, 98), stone_poly)

    for i in range(5):
        band_y = stone_top + 20 + i * 16
        shade = (95 - i * 6, 90 - i * 5, 82 - i * 4)
        pygame.draw.rect(tile, shade, (0, int(band_y), width, 10))

    # Distinct vertical cracks so rock motion is obvious while scrolling
    for gx in range(30, width, 70):
        cell = gx // 70
        cx = gx + (_pseudo_rand(cell, 500) - 0.5) * 16
        top_y = stone_top + 4 + _pseudo_rand(cell, 510) * 12
        pygame.draw.line(
            tile,
            (70, 65, 58),
            (cx, top_y),
            (cx + (_pseudo_rand(cell, 520) - 0.5) * 8, height - 8),
            2,
        )
        # Extra darker groove for visibility
        pygame.draw.line(
            tile,
            (55, 50, 45),
            (cx + 3, top_y + 10),
            (cx + 2, height - 20),
            1,
        )

    for gx in range(40, width, 90):
        cell = gx // 90
        bx = gx + _pseudo_rand(cell, 530) * 20
        by = stone_top + 20 + _pseudo_rand(cell, 540) * 50
        _draw_rock(tile, bx, by, 6 + _pseudo_rand(cell, 541) * 5, cell + 50)

    # --- Plants & surface pebbles (baked into the same scrolling tile) ---
    for gx in range(8, width, 48):
        cell = gx // 48
        tx = gx + _pseudo_rand(cell, 600) * 12
        ty = crest_local(tx)
        _draw_grass_tuft(tile, tx, ty, 0.9 + _pseudo_rand(cell, 610) * 0.5, cell)

    for gx in range(50, width, 140):
        cell = gx // 140
        fx = gx + _pseudo_rand(cell, 700) * 30
        _draw_flower(tile, fx, crest_local(fx) - 4, cell + 20)

    for gx in range(90, width, 200):
        cell = gx // 200
        bx = gx + _pseudo_rand(cell, 720) * 25
        _draw_bush(tile, bx, crest_local(bx) - 2, int(16 + _pseudo_rand(cell, 730) * 8))

    for gx in range(70, width, 160):
        cell = gx // 160
        rx = gx + _pseudo_rand(cell, 740) * 25
        _draw_rock(tile, rx, crest_local(rx) + 4, 5 + _pseudo_rand(cell, 750) * 3, cell + 30)

    for i in range(len(grass_top_points) - 1):
        pygame.draw.line(
            tile,
            (95, 195, 85),
            grass_top_points[i],
            grass_top_points[i + 1],
            2,
        )

    return tile


def draw_ground_platform(surface, ground_top, camera_x, camera_y):
    """Tile the ground strip across the view; offset by camera so the whole stack scrolls."""
    global _ground_tile_surf
    if _ground_tile_surf is None:
        _ground_tile_surf = build_ground_tile(ground_top)

    tile = _ground_tile_surf
    tile_w = tile.get_width()
    # Local crest sits at y=12 inside the tile; align that to world ground_top on screen
    tile_draw_y = int(ground_top - camera_y - 12)

    # Screen x of world x=0 is -camera_x; tile repeats every tile_w world units
    scroll = -int(round(camera_x)) % tile_w
    # Start one tile early so the left edge is always covered
    start_x = scroll - tile_w
    if scroll == 0:
        start_x = -tile_w

    x_pos = start_x
    screen_w = surface.get_width()
    while x_pos < screen_w:
        surface.blit(tile, (x_pos, tile_draw_y))
        x_pos += tile_w
