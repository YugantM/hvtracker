#!/usr/bin/env python3
"""Generate a custom OG card (1200x630) for a project profile page."""

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630

BG = "#08111b"
PANEL = "#0f1b2b"
PANEL_2 = "#122338"
BORDER = "#26384f"
TEXT = "#edf4ff"
MUTED = "#95a9c5"
SOFT = "#6e86a6"
TEAL = "#2dd4bf"
BLUE = "#62a5ff"
GOLD = "#e1ae55"
ROSE = "#ff7373"
VIOLET = "#a78bfa"

GRADE_COLORS = {
    "A": ("#102f2a", "#3ce3c6", "#d9fff7"),
    "B": ("#102946", "#69a8ff", "#e7f1ff"),
    "C": ("#3a2a12", "#e1ae55", "#fff4da"),
    "D": ("#472513", "#fb923c", "#fff0e2"),
    "F": ("#47181d", "#ff7373", "#ffe9ec"),
}

TRUST_COLORS = {
    "safety": ROSE,
    "identity": BLUE,
    "transparency": GOLD,
    "maintenance": TEAL,
    "adoption": VIOLET,
}
TRUST_MAX = {
    "safety": 25,
    "identity": 20,
    "transparency": 17,
    "maintenance": 20,
    "adoption": 20,
}


def load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if mono:
        paths = [
            "/System/Library/Fonts/SFNSMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
    elif bold:
        paths = [
            "/System/Library/Fonts/HelveticaNeueDeskInterface.ttc",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        paths = [
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int, bold=False, mono=False):
    for size in range(start_size, min_size - 1, -2):
        font = load_font(size, bold=bold, mono=mono)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return load_font(min_size, bold=bold, mono=mono)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if words and len(lines) == max_lines:
        consumed = " ".join(lines).split()
        if len(consumed) < len(words):
            last = lines[-1]
            while draw.textbbox((0, 0), f"{last}...", font=font)[2] > max_width and len(last) > 4:
                last = last[:-1]
            lines[-1] = f"{last.rstrip()}..."
    return lines


def draw_gradient_background(img: Image.Image):
    base = Image.new("RGBA", (W, H), hex_rgb(BG) + (255,))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-120, -80, 520, 480), fill=(45, 212, 191, 54))
    gd.ellipse((700, -100, 1320, 420), fill=(98, 165, 255, 50))
    gd.ellipse((820, 320, 1320, 760), fill=(225, 174, 85, 36))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img.alpha_composite(base)
    img.alpha_composite(glow)


def stat_box(draw, x, y, w, value, label, accent):
    rounded(draw, (x, y, x + w, y + 82), 20, fill=hex_rgb(PANEL_2), outline=hex_rgb(BORDER))
    draw.text((x + 18, y + 14), value, font=load_font(28, bold=True), fill=hex_rgb(TEXT))
    draw.text((x + 18, y + 48), label, font=load_font(16), fill=hex_rgb(accent))


def trust_bar(draw, x, y, w, label, score, maximum, color):
    draw.text((x, y), label, font=load_font(16, bold=True), fill=hex_rgb(TEXT))
    value = f"{score:.0f}/{maximum}"
    vb = draw.textbbox((0, 0), value, font=load_font(16, mono=True))
    draw.text((x + w - (vb[2] - vb[0]), y), value, font=load_font(16, mono=True), fill=hex_rgb(MUTED))
    y += 26
    rounded(draw, (x, y, x + w, y + 14), 7, fill=(34, 49, 70), outline=None)
    fill_w = max(18, int(w * min(max(score / maximum, 0), 1)))
    rounded(draw, (x, y, x + fill_w, y + 14), 7, fill=hex_rgb(color), outline=None)
    return y + 28


def category_label(text: str) -> str:
    if len(text) <= 22:
        return text
    return text[:21] + "..."


def safe_description(text: str) -> str:
    return (text or "").replace("\n", " ").strip()


def generate(agent_data: dict, output_path: str):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_gradient_background(img)
    draw = ImageDraw.Draw(img)

    outer = (28, 24, W - 28, H - 24)
    rounded(draw, outer, 34, fill=(10, 20, 33, 220), outline=(42, 60, 84), width=2)
    rounded(draw, (42, 40, W - 42, H - 42), 28, outline=(255, 255, 255, 18), width=1)

    left_x = 72
    top_y = 62
    content_w = 610

    draw.text((left_x, top_y), "AI TRUST REGISTRY", font=load_font(22, bold=True), fill=hex_rgb(SOFT))
    draw.text((left_x, top_y + 28), "Open-source AI project profile", font=load_font(18), fill=hex_rgb(MUTED))

    grade = agent_data.get("evidence_grade", "D")
    grade_bg, grade_fg, grade_text = GRADE_COLORS.get(grade, GRADE_COLORS["D"])
    pill_text = f"Grade {grade}"
    pill_font = load_font(24, bold=True)
    pill_bbox = draw.textbbox((0, 0), pill_text, font=pill_font)
    pill_w = (pill_bbox[2] - pill_bbox[0]) + 42
    pill_h = 56
    pill_x = W - 72 - pill_w
    pill_y = 64
    rounded(draw, (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h), 18, fill=hex_rgb(grade_bg), outline=None)
    draw.text((pill_x + 21, pill_y + 14), pill_text, font=pill_font, fill=hex_rgb(grade_fg))

    name = agent_data["name"]
    name_font = fit_text(draw, name, content_w, 72, 44, bold=False)
    draw.text((left_x, 128), name, font=name_font, fill=hex_rgb(TEXT))

    desc_font = load_font(24)
    desc = safe_description(agent_data.get("description", ""))
    desc_lines = wrap_text(draw, desc, desc_font, content_w, 2)
    desc_y = 128 + (draw.textbbox((0, 0), name, font=name_font)[3] + 20)
    for line in desc_lines:
        draw.text((left_x, desc_y), line, font=desc_font, fill=hex_rgb(MUTED))
        desc_y += 32

    repo = agent_data.get("repo", "")
    draw.text((left_x, desc_y + 8), repo, font=load_font(24, mono=True), fill=hex_rgb(BLUE))

    trust = float(agent_data.get("trust_score") or 0)
    score_y = 308
    score_font = load_font(84, bold=True)
    score_text = f"{trust:.1f}"
    score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
    draw.text((left_x, score_y), score_text, font=score_font, fill=hex_rgb(TEAL))
    draw.text((left_x + (score_bbox[2] - score_bbox[0]) + 12, score_y + 32), "/ 100", font=load_font(34, mono=True), fill=hex_rgb(MUTED))
    draw.text((left_x, score_y + 88), "HVTrust score", font=load_font(22), fill=hex_rgb(SOFT))

    stars = agent_data.get("stars_fmt", "—")
    commits = str(agent_data.get("weekly_commits") or 0)
    category = category_label(agent_data.get("category", "Uncategorized"))
    stat_y = 454
    stat_box(draw, left_x, stat_y, 146, stars, "stars", TEAL)
    stat_box(draw, left_x + 162, stat_y, 146, commits, "commits / 4wk", BLUE)
    stat_box(draw, left_x + 324, stat_y, 260, category, "category", GOLD)

    panel_x = 700
    panel_y = 142
    panel_w = 430
    panel_h = 360
    rounded(draw, (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h), 28, fill=hex_rgb(PANEL), outline=hex_rgb(BORDER), width=2)
    draw.text((panel_x + 28, panel_y + 24), "Trust breakdown", font=load_font(28, bold=True), fill=hex_rgb(TEXT))
    draw.text((panel_x + 28, panel_y + 58), "Public, checkable signals by dimension", font=load_font(18), fill=hex_rgb(MUTED))

    by = panel_y + 104
    breakdown = agent_data.get("trust_breakdown", {})
    for dim in ["safety", "identity", "transparency", "maintenance", "adoption"]:
        by = trust_bar(
            draw,
            panel_x + 28,
            by,
            panel_w - 56,
            dim.capitalize(),
            float(breakdown.get(dim, 0) or 0),
            TRUST_MAX[dim],
            TRUST_COLORS[dim],
        )

    footer_y = 536
    draw.line((60, footer_y, W - 60, footer_y), fill=(46, 64, 89), width=1)
    draw.text((72, footer_y + 18), "hvtracker.net", font=load_font(26, bold=True), fill=hex_rgb(TEXT))
    draw.text((72 + 154, footer_y + 18), "AI Trust Registry", font=load_font(26), fill=hex_rgb(TEAL))

    rank = agent_data.get("rank")
    total = agent_data.get("total") or 197
    rank_text = f"Rank #{rank} of {total}" if rank else "Rank unavailable"
    rb = draw.textbbox((0, 0), rank_text, font=load_font(24, mono=True))
    draw.text((W - 72 - (rb[2] - rb[0]), footer_y + 20), rank_text, font=load_font(24, mono=True), fill=hex_rgb(MUTED))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output_path, "PNG", optimize=True)
    print(f"Generated OG card: {output_path} ({W}x{H})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_og_card.py <slug> [output_path]")
        sys.exit(1)

    slug = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else f"agents/{slug}/og.png"
    data_path = Path(f"data/agents/{slug}.json")

    if not data_path.exists():
        print(f"Agent data not found: {data_path}")
        sys.exit(1)

    with data_path.open() as fh:
        data = json.load(fh)
    generate(data, out)
