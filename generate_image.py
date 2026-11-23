#!/usr/bin/env python3
"""Generate the 1024x1024 front-page news image for Monday, 23 November 2026."""

from __future__ import annotations

import math
import os
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

CANVAS_SIZE = 1024
MAX_FILE_BYTES = 1048576

BG_COLOR = "#F7F3E8"
INK_COLOR = "#111111"
ACCENT_COLOR = "#A31621"
WHITE_COLOR = "#FFFFFF"
PAPER_TINT = "#EFE9DA"

FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"

MASTHEAD_TITLE = "THE WORLD IN ONE PICTURE"
MASTHEAD_DATE = "MONDAY · 23 NOVEMBER 2026"

FOOTER_TEXT = (
    "ALSO TODAY — TRUMP SEEKS PERMANENT DEAL TO STOP IRAN NUCLEAR WEAPON · "
    "MEXICO MOURNS 11 DEAD AFTER CARTEL BOSS CAPTURE · "
    "KRYVYI RIH COUNTS 60 WOUNDED"
)

PANELS = [
    {
        "tag": "CLIMATE",
        "headline": "COP31 COLLAPSES WITH NO DEAL",
        "subline": "EU and UK reject final text with no fossil fuels; longest COP ever",
        "motif": "climate",
    },
    {
        "tag": "POLITICS",
        "headline": "DEMOCRATS CLINCH 258-SEAT HOUSE MAJORITY",
        "subline": "Largest since 1992; North Carolina recount seals the sweep",
        "motif": "politics",
    },
    {
        "tag": "GULF",
        "headline": "TWO WOUNDED AS IRAN STRIKES BAHRAIN BASES",
        "subline": "IRGC claims Patriot radar hits; tankers attacked near Hormuz",
        "motif": "gulf",
    },
    {
        "tag": "SPORT",
        "headline": "LIVERPOOL ROUT UNITED 4-0",
        "subline": "Pochettino's debut ends in rout; Yoro sent off in 8th minute",
        "motif": "sport",
    },
]


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, tuple[int, int, int, int]]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    *,
    balanced: bool = False,
) -> list[str]:
    """Wrap text into lines guaranteed to fit within max_width using draw.textbbox."""
    words = text.split()
    if not words:
        return []

    def width_of(s: str) -> int:
        bb = draw.textbbox((0, 0), s, font=font)
        return bb[2] - bb[0]

    # Greedy pass first to establish minimum line count and verify every word fits.
    greedy: list[str] = []
    cur = ""
    for word in words:
        assert width_of(word) <= max_width, f"Word {word!r} exceeds max_width={max_width}"
        candidate = f"{cur} {word}".strip()
        if not cur or width_of(candidate) <= max_width:
            cur = candidate
        else:
            greedy.append(cur)
            cur = word
    if cur:
        greedy.append(cur)

    if not balanced or len(greedy) <= 1:
        return greedy

    # Dynamic programming to balance line widths while keeping the exact same line count.
    n = len(words)
    target_lines = len(greedy)
    line_widths: dict[tuple[int, int], int] = {}
    for i in range(n):
        for j in range(i + 1, n + 1):
            w = width_of(" ".join(words[i:j]))
            if w <= max_width:
                line_widths[(i, j)] = w
            else:
                break

    total_w = width_of(text)
    ideal_w = total_w / target_lines
    inf = float("inf")
    dp: list[list[tuple[float, int]]] = [[(inf, -1)] * (n + 1) for _ in range(target_lines + 1)]
    dp[0][0] = (0.0, -1)

    avoid_trailing = {"in", "of", "to", "a", "an", "the", "north", "south", "east", "west"}

    for k in range(1, target_lines + 1):
        for j in range(k, n + 1):
            best_cost = inf
            best_i = -1
            for i in range(k - 1, j):
                if (i, j) not in line_widths:
                    continue
                prev_cost = dp[k - 1][i][0]
                if prev_cost == inf:
                    continue
                w = line_widths[(i, j)]
                cost = prev_cost + (w - ideal_w) ** 2
                # Gently reward clean clause breaks and avoid splitting short connectors/proper prefixes
                if k < target_lines:
                    last_word = words[j - 1]
                    if last_word.endswith((";", "—")):
                        cost -= 4500.0
                    elif last_word.lower() in avoid_trailing:
                        cost += 4500.0
                if cost < best_cost:
                    best_cost = cost
                    best_i = i
            dp[k][j] = (best_cost, best_i)

    if dp[target_lines][n][0] == inf:
        return greedy

    lines: list[str] = []
    idx = n
    for k in range(target_lines, 0, -1):
        prev = dp[k][idx][1]
        lines.append(" ".join(words[prev:idx]))
        idx = prev
    lines.reverse()
    for line in lines:
        assert width_of(line) <= max_width, f"Line {line!r} exceeds max_width={max_width}"
    return lines


def draw_text_exact(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    align: str = "left",
    box_width: int = 0,
) -> tuple[int, int, int, int]:
    """Draw text so its visual top edge sits at y and return its drawn bbox."""
    w, h, bb = text_size(draw, text, font)
    if align == "center":
        draw_x = x + (box_width - w) // 2 - bb[0]
    else:
        draw_x = x - bb[0]
    draw_y = y - bb[1]
    draw.text((draw_x, draw_y), text, font=font, fill=fill)
    return (draw_x + bb[0], draw_y + bb[1], draw_x + bb[2], draw_y + bb[3])


def render_supersampled(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    painter: Callable[[ImageDraw.ImageDraw, int, int, int], None],
    scale: int = 4,
) -> None:
    """Render a motif into box (x0, y0, x1, y1) using supersampling for smooth vector edges."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    assert w > 0 and h > 0, f"Invalid motif box {box}"
    layer = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(layer)
    painter(ldraw, w * scale, h * scale, scale)
    down = layer.resize((w, h), Image.Resampling.LANCZOS)
    canvas.paste(down, (x0, y0), down)


def draw_motif_climate(d: ImageDraw.ImageDraw, w: int, h: int, s: int) -> None:
    """Globe (circle + 2 curved meridians + horizontal equator) with jagged crack + clock beside it."""
    globe_r = min(int(h * 0.44), 54 * s)
    clock_r = int(globe_r * 0.56)
    # Bottom-weighted vertical alignment to harmonize baseline with right-hand panel
    cy = min(h - globe_r - 12 * s, int(h * 0.56))
    gap = 32 * s
    total_w = globe_r * 2 + gap + clock_r * 2
    gx = (w - total_w) // 2 + globe_r
    cx = gx + globe_r + gap + clock_r
    stroke = max(4 * s, int(globe_r * 0.085))
    thin = max(3 * s, int(globe_r * 0.055))

    # Globe interior + circle outline
    d.ellipse((gx - globe_r, cy - globe_r, gx + globe_r, cy + globe_r), fill=PAPER_TINT, outline=INK_COLOR, width=stroke)

    # One horizontal equator line
    d.line((gx - globe_r + stroke // 2, cy, gx + globe_r - stroke // 2, cy), fill=INK_COLOR, width=thin)

    # Two curved meridian lines (left and right vertical elliptical arcs)
    mer_rx = int(globe_r * 0.48)
    d.arc(
        (gx - mer_rx, cy - globe_r + stroke // 2, gx + mer_rx, cy + globe_r - stroke // 2),
        start=90,
        end=270,
        fill=INK_COLOR,
        width=thin,
    )
    d.arc(
        (gx - mer_rx, cy - globe_r + stroke // 2, gx + mer_rx, cy + globe_r - stroke // 2),
        start=270,
        end=90,
        fill=INK_COLOR,
        width=thin,
    )

    # Jagged crack line across the globe (with crisp off-white knockout for clear separation)
    crack_pts = [
        (gx - int(globe_r * 0.42), cy - int(globe_r * 0.88)),
        (gx - int(globe_r * 0.08), cy - int(globe_r * 0.34)),
        (gx - int(globe_r * 0.28), cy - int(globe_r * 0.04)),
        (gx + int(globe_r * 0.16), cy + int(globe_r * 0.28)),
        (gx - int(globe_r * 0.04), cy + int(globe_r * 0.56)),
        (gx + int(globe_r * 0.36), cy + int(globe_r * 0.90)),
    ]
    d.line(crack_pts, fill=BG_COLOR, width=stroke + 5 * s, joint="curve")
    d.line(crack_pts, fill=ACCENT_COLOR, width=stroke + 2 * s, joint="curve")

    # Small clock face beside the globe
    d.ellipse((cx - clock_r, cy - clock_r, cx + clock_r, cy + clock_r), fill=WHITE_COLOR, outline=INK_COLOR, width=stroke)
    # Four cardinal tick marks
    for deg in (0, 90, 180, 270):
        rad = math.radians(deg)
        r_in = clock_r - 7 * s
        r_out = clock_r - 2 * s
        d.line(
            (cx + r_in * math.cos(rad), cy + r_in * math.sin(rad), cx + r_out * math.cos(rad), cy + r_out * math.sin(rad)),
            fill=INK_COLOR,
            width=max(2 * s, thin - s),
        )
    # Two bold clock hands at a clear wide V-angle (~10:08) for unmistakable readability at thumbnail scale
    hour_ang = math.radians(-145)
    min_ang = math.radians(-42)
    d.line(
        (cx, cy, cx + int(clock_r * 0.50 * math.cos(hour_ang)), cy + int(clock_r * 0.50 * math.sin(hour_ang))),
        fill=INK_COLOR,
        width=stroke + s,
    )
    d.line(
        (cx, cy, cx + int(clock_r * 0.72 * math.cos(min_ang)), cy + int(clock_r * 0.72 * math.sin(min_ang))),
        fill=ACCENT_COLOR,
        width=stroke,
    )
    dot_r = 4 * s
    d.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=INK_COLOR)


def draw_motif_politics(d: ImageDraw.ImageDraw, w: int, h: int, s: int) -> None:
    """Ballot box (dark rect + thin slot on top) with tilted white ballot going in + large check mark beside it."""
    box_w = 114 * s
    box_h = 56 * s
    check_w = 72 * s
    gap = 38 * s
    total_w = box_w + gap + check_w
    left_x = (w - total_w) // 2

    # Anchor ballot box cleanly near bottom of motif box so tilted ballot paper rises above it.
    box_bottom = min(h - 6 * s, h // 2 + 46 * s)
    box_top = box_bottom - box_h
    box_right = left_x + box_w

    # Dark ballot box body
    d.rectangle((left_x, box_top, box_right, box_bottom), fill=INK_COLOR)

    # Single crisp thin slot centered near the top of the ballot box
    slot_w = 68 * s
    slot_h = 7 * s
    slot_x0 = left_x + (box_w - slot_w) // 2
    slot_x1 = slot_x0 + slot_w
    slot_y0 = box_top + 7 * s
    slot_y1 = slot_y0 + slot_h
    d.rectangle((slot_x0, slot_y0, slot_x1, slot_y1), fill=BG_COLOR)

    # Tilted white ballot paper entering the slot (clipped cleanly at slot_y1)
    paper_w = 40 * s
    paper_h = 44 * s
    angle = math.radians(-16)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    pivot_x = left_x + box_w // 2 - 2 * s
    pivot_y = slot_y0 + 3 * s

    corners = [
        (-paper_w / 2, -paper_h),
        (paper_w / 2, -paper_h),
        (paper_w / 2, 0),
        (-paper_w / 2, 0),
    ]
    rot_pts = [
        (pivot_x + px * cos_a - py * sin_a, pivot_y + px * sin_a + py * cos_a)
        for px, py in corners
    ]

    paper_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(paper_layer)
    pdraw.polygon(rot_pts, fill=WHITE_COLOR)
    pdraw.line(rot_pts + [rot_pts[0]], fill=INK_COLOR, width=3 * s, joint="curve")
    for frac in (0.34, 0.56):
        lx0, ly0 = -paper_w * 0.28, -paper_h * (1 - frac)
        lx1, ly1 = paper_w * 0.28, -paper_h * (1 - frac)
        pdraw.line(
            (
                pivot_x + lx0 * cos_a - ly0 * sin_a,
                pivot_y + lx0 * sin_a + ly0 * cos_a,
                pivot_x + lx1 * cos_a - ly1 * sin_a,
                pivot_y + lx1 * sin_a + ly1 * cos_a,
            ),
            fill=INK_COLOR,
            width=2 * s,
        )
    pdraw.rectangle((0, slot_y1 - s, w, h), fill=(0, 0, 0, 0))
    d._image.alpha_composite(paper_layer)
    d.line((slot_x0, slot_y1, slot_x1, slot_y1), fill=INK_COLOR, width=2 * s)

    # Large crisp polygonal deep-red check mark beside the ballot box
    ck_x = box_right + gap
    ck_cy = (box_top - 12 * s + box_bottom) // 2
    ck_poly = [
        (ck_x, ck_cy + 2 * s),
        (ck_x + 8 * s, ck_cy - 6 * s),
        (ck_x + 24 * s, ck_cy + 11 * s),
        (ck_x + check_w - 8 * s, ck_cy - 34 * s),
        (ck_x + check_w, ck_cy - 26 * s),
        (ck_x + 24 * s, ck_cy + 27 * s),
    ]
    d.polygon(ck_poly, fill=ACCENT_COLOR)


def draw_motif_gulf(d: ImageDraw.ImageDraw, w: int, h: int, s: int) -> None:
    """Missile arc (curved polyline with arrowhead) above low base silhouette (wide dark rect + window dots) + starburst."""
    base_w = 186 * s
    base_h = 34 * s
    arc_lead = 76 * s
    total_w = arc_lead + base_w
    arc_start_x = (w - total_w) // 2
    base_x0 = arc_start_x + arc_lead
    base_x1 = base_x0 + base_w
    base_bottom = h - 6 * s
    base_top = base_bottom - base_h

    # Low base silhouette (wide dark rectangle)
    d.rectangle((base_x0, base_top, base_x1, base_bottom), fill=INK_COLOR)

    # Small window dots evenly spaced across the base silhouette
    num_windows = 8
    win_w = 10 * s
    win_h = 8 * s
    pad_x = 16 * s
    step = (base_w - 2 * pad_x - win_w) / (num_windows - 1)
    win_y = base_top + (base_h - win_h) // 2
    for i in range(num_windows):
        wx = int(base_x0 + pad_x + i * step)
        d.rectangle((wx, win_y, wx + win_w, win_y + win_h), fill=BG_COLOR)

    # Starburst near top of the base silhouette (elevated cleanly above windows)
    star_x = base_x0 + int(base_w * 0.56)
    star_y = base_top - 15 * s

    # Curved missile arc sweeping from left over to just short of the starburst
    p0 = (arc_start_x, base_bottom - 10 * s)
    p1 = (base_x0 - 8 * s, max(6 * s, base_top - 80 * s))
    p2 = (star_x - 24 * s, star_y - 10 * s)
    steps = 36
    arc_pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        arc_pts.append((x, y))
    d.line(arc_pts, fill=INK_COLOR, width=5 * s, joint="curve")

    # Crisp arrowhead at the tip of the missile arc
    end_x, end_y = arc_pts[-1]
    prev_x, prev_y = arc_pts[-4]
    ang = math.atan2(end_y - prev_y, end_x - prev_x)
    head_len = 17 * s
    head_spread = math.radians(28)
    arrow_pts = [
        (end_x + 4 * s * math.cos(ang), end_y + 4 * s * math.sin(ang)),
        (end_x - head_len * math.cos(ang - head_spread), end_y - head_len * math.sin(ang - head_spread)),
        (end_x - head_len * math.cos(ang + head_spread), end_y - head_len * math.sin(ang + head_spread)),
    ]
    d.polygon(arrow_pts, fill=INK_COLOR)

    # Starburst (lines radiating from one point) in deep-red near top of base
    ray_angles = [i * 36 - 18 for i in range(10)]
    for idx, deg in enumerate(ray_angles):
        rad = math.radians(deg)
        r_out = (22 if idx % 2 == 0 else 14) * s
        # Keep downward rays from entering the window band
        ey = star_y + r_out * math.sin(rad)
        if ey > base_top + 2 * s:
            r_out = max(8 * s, (base_top + 2 * s - star_y) / math.sin(rad))
        r_in = 3 * s
        d.line(
            (
                star_x + r_in * math.cos(rad),
                star_y + r_in * math.sin(rad),
                star_x + r_out * math.cos(rad),
                star_y + r_out * math.sin(rad),
            ),
            fill=ACCENT_COLOR,
            width=4 * s if idx % 2 == 0 else 3 * s,
        )
    core_r = 5 * s
    d.ellipse((star_x - core_r, star_y - core_r, star_x + core_r, star_y + core_r), fill=ACCENT_COLOR)


def draw_motif_sport(d: ImageDraw.ImageDraw, w: int, h: int, s: int) -> None:
    """Soccer ball (filled circle + small centre pentagon + short seam lines) beside a goal frame (rect + net lines)."""
    ball_r = min(int(h * 0.36), 42 * s)
    goal_w = 136 * s
    goal_h = min(int(h * 0.72), 84 * s)
    # Bottom-weighted vertical alignment to harmonize baseline with left-hand GULF panel
    gy1 = min(h - 14 * s, int(h * 0.58) + goal_h // 2)
    gy0 = gy1 - goal_h
    cy = (gy0 + gy1) // 2
    gap = 38 * s

    total_w = ball_r * 2 + gap + goal_w
    bx = (w - total_w) // 2 + ball_r
    gx0 = bx + ball_r + gap
    gx1 = gx0 + goal_w

    stroke = 4 * s

    # Soccer ball: filled white circle with bold ink outline
    d.ellipse((bx - ball_r, cy - ball_r, bx + ball_r, cy + ball_r), fill=WHITE_COLOR, outline=INK_COLOR, width=stroke)

    # Centre regular pentagon (pointing straight up)
    pent_r = int(ball_r * 0.42)
    pent_pts = []
    for k in range(5):
        ang = math.radians(-90 + k * 72)
        pent_pts.append((bx + pent_r * math.cos(ang), cy + pent_r * math.sin(ang)))
    d.polygon(pent_pts, fill=INK_COLOR)

    # Short seam lines from pentagon vertices toward the edge of the ball
    seam_end_r = ball_r - stroke // 2
    for px, py in pent_pts:
        ang = math.atan2(py - cy, px - bx)
        ex = bx + seam_end_r * math.cos(ang)
        ey = cy + seam_end_r * math.sin(ang)
        d.line((px, py, ex, ey), fill=INK_COLOR, width=3 * s)

    # Goal frame: clean open net grid (5 cols x 3 rows) readable even at 300px thumbnail size
    net_cols = 5
    net_rows = 3
    net_stroke = 2 * s
    for i in range(1, net_cols):
        nx = gx0 + int(goal_w * i / net_cols)
        d.line((nx, gy0 + stroke // 2, nx, gy1 - stroke // 2), fill=INK_COLOR, width=net_stroke)
    for j in range(1, net_rows):
        ny = gy0 + int(goal_h * j / net_rows)
        d.line((gx0 + stroke // 2, ny, gx1 - stroke // 2, ny), fill=INK_COLOR, width=net_stroke)

    # Outer goal frame rectangle outline (deep-red frame + ink baseline)
    d.rectangle((gx0, gy0, gx1, gy1), outline=ACCENT_COLOR, width=stroke + s)
    d.line((gx0 - 6 * s, gy1, gx1 + 6 * s, gy1), fill=INK_COLOR, width=stroke)


MOTIF_PAINTERS = {
    "climate": draw_motif_climate,
    "politics": draw_motif_politics,
    "gulf": draw_motif_gulf,
    "sport": draw_motif_sport,
}


def build_image(output_path: str) -> None:
    img = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Load required fonts
    font_masthead = ImageFont.truetype(FONT_BOLD_PATH, 64)
    font_date = ImageFont.truetype(FONT_BOLD_PATH, 30)
    font_tag = ImageFont.truetype(FONT_BOLD_PATH, 19)
    font_headline = ImageFont.truetype(FONT_BOLD_PATH, 44)
    font_subline = ImageFont.truetype(FONT_REG_PATH, 25)
    font_footer = ImageFont.truetype(FONT_REG_PATH, 24)

    outer_x = 20
    content_w = CANVAS_SIZE - 2 * outer_x  # 984px

    # --- Masthead ---
    title_bb = draw_text_exact(
        draw, outer_x, 16, MASTHEAD_TITLE, font_masthead, INK_COLOR, align="center", box_width=content_w
    )
    assert title_bb[0] >= outer_x and title_bb[2] <= CANVAS_SIZE - outer_x, f"Masthead overflow: {title_bb}"

    rule_y = title_bb[3] + 10
    draw.rectangle((outer_x, rule_y, CANVAS_SIZE - outer_x, rule_y + 4), fill=ACCENT_COLOR)

    date_bb = draw_text_exact(
        draw, outer_x, rule_y + 13, MASTHEAD_DATE, font_date, INK_COLOR, align="center", box_width=content_w
    )
    assert date_bb[0] >= outer_x and date_bb[2] <= CANVAS_SIZE - outer_x, f"Date overflow: {date_bb}"

    # --- Footer Strip (layout computed before grid so grid fills exact middle space) ---
    footer_lines = wrap_text(draw, FOOTER_TEXT, font_footer, content_w - 8, balanced=True)
    footer_line_step = 29
    _, footer_sample_h, _ = text_size(draw, "AG", font_footer)
    footer_text_h = (len(footer_lines) - 1) * footer_line_step + footer_sample_h
    footer_bottom_pad = 15
    footer_top_pad = 11
    footer_rule_y = CANVAS_SIZE - footer_bottom_pad - footer_text_h - footer_top_pad - 3

    draw.rectangle((outer_x, footer_rule_y, CANVAS_SIZE - outer_x, footer_rule_y + 3), fill=INK_COLOR)

    fy = footer_rule_y + 3 + footer_top_pad
    for line in footer_lines:
        bb = draw_text_exact(
            draw, outer_x + 4, fy, line, font_footer, INK_COLOR, align="center", box_width=content_w - 8
        )
        assert bb[0] >= outer_x and bb[2] <= CANVAS_SIZE - outer_x, f"Footer line overflow: {line!r} {bb}"
        assert bb[3] <= CANVAS_SIZE - 8, f"Footer bottom overflow: {bb}"
        fy += footer_line_step

    # --- 2x2 Panel Grid ---
    grid_top = date_bb[3] + 13
    grid_bottom = footer_rule_y - 13
    col_gap = 16
    row_gap = 16
    panel_w = (content_w - col_gap) // 2  # 484
    panel_h = (grid_bottom - grid_top - row_gap) // 2  # ~372

    pad_x = 16
    pad_top = 14
    pad_bottom = 12
    inner_w = panel_w - 2 * pad_x  # 452

    headline_size = 44
    assert headline_size >= 44
    _, hl_cap_h, _ = text_size(draw, "AG", font_headline)
    hl_step = hl_cap_h + 10

    _, sub_cap_h, _ = text_size(draw, "Ag", font_subline)
    sub_step = sub_cap_h + 7

    for idx, panel in enumerate(PANELS):
        col = idx % 2
        row = idx // 2
        px0 = outer_x + col * (panel_w + col_gap)
        py0 = grid_top + row * (panel_h + row_gap)
        px1 = px0 + panel_w
        py1 = py0 + panel_h

        # Thin crisp black border
        draw.rectangle((px0, py0, px1, py1), fill=BG_COLOR, outline=INK_COLOR, width=2)

        tx = px0 + pad_x
        cursor_y = py0 + pad_top

        # Small deep-red category tag at top-left
        tag_w, tag_h, _ = text_size(draw, panel["tag"], font_tag)
        tag_pad_x = 9
        tag_pad_y = 5
        tag_box = (tx, cursor_y, tx + tag_w + 2 * tag_pad_x, cursor_y + tag_h + 2 * tag_pad_y)
        draw.rectangle(tag_box, fill=ACCENT_COLOR)
        draw_text_exact(draw, tx + tag_pad_x, cursor_y + tag_pad_y, panel["tag"], font_tag, BG_COLOR)
        cursor_y = tag_box[3] + 10

        # Bold headline (>= 44px, word-wrapped via draw.textbbox)
        hl_lines = wrap_text(draw, panel["headline"], font_headline, inner_w)
        hl_bottom = cursor_y
        for line in hl_lines:
            bb = draw_text_exact(draw, tx, cursor_y, line, font_headline, INK_COLOR)
            assert bb[0] >= px0 + pad_x - 1 and bb[2] <= px1 - pad_x + 1, f"Headline overflow in {panel['tag']}: {bb}"
            hl_bottom = bb[3]
            cursor_y += hl_step

        # Smaller sub-line (25px Arial Regular, balanced word-wrap via draw.textbbox)
        cursor_y = hl_bottom + 14
        sub_lines = wrap_text(draw, panel["subline"], font_subline, inner_w, balanced=True)
        sub_bottom = cursor_y
        for line in sub_lines:
            bb = draw_text_exact(draw, tx, cursor_y, line, font_subline, INK_COLOR)
            assert bb[0] >= px0 + pad_x - 1 and bb[2] <= px1 - pad_x + 1, f"Subline overflow in {panel['tag']}: {bb}"
            sub_bottom = bb[3]
            cursor_y += sub_step

        # Motif in remaining space inside panel
        motif_top = sub_bottom + 10
        motif_bottom = py1 - pad_bottom
        motif_h = motif_bottom - motif_top
        assert motif_h >= 75, f"Insufficient motif height ({motif_h}px) in panel {panel['tag']}"

        motif_box = (tx, motif_top, px1 - pad_x, motif_bottom)
        render_supersampled(img, motif_box, MOTIF_PAINTERS[panel["motif"]], scale=4)

    # Save deterministically (optimize=True keeps file well under 1 MiB)
    img.save(output_path, format="PNG", optimize=True)

    # Self-verification inside the script
    with Image.open(output_path) as check:
        assert check.size == (CANVAS_SIZE, CANVAS_SIZE), f"Expected 1024x1024, got {check.size}"
    file_bytes = os.path.getsize(output_path)
    assert file_bytes <= MAX_FILE_BYTES, f"File size {file_bytes} exceeds {MAX_FILE_BYTES} bytes"


def main() -> None:
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(repo_dir, "entry.png")
    build_image(out_path)


if __name__ == "__main__":
    main()
