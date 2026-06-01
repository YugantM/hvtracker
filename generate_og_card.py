#!/usr/bin/env python3
"""Generate a custom OG card (1200×630) for an agent profile page."""

import json
import sys
from PIL import Image, ImageDraw, ImageFont

# ── Colour palette (matches site dark theme) ────────────────────────
BG = (18, 22, 30)
CARD_BG = (26, 32, 44)
BORDER = (55, 65, 81)
ACCENT = (45, 212, 191)       # teal / --accent
YELLOW = (216, 166, 87)
TEXT = (226, 232, 240)
MUTED = (148, 163, 184)
GRADE_COLORS = {
    "A": (45, 212, 191),
    "B": (96, 165, 250),
    "C": (216, 166, 87),
    "D": (251, 146, 60),
    "F": (248, 113, 113),
}
TRUST_COLORS = {
    "safety":      (248, 113, 113),
    "identity":    (96, 165, 250),
    "transparency":(216, 166, 87),
    "maintenance":  (45, 212, 191),
    "adoption":    (167, 139, 250),
}
TRUST_MAX = {"safety": 25, "identity": 20, "transparency": 17, "maintenance": 20, "adoption": 20}

# ── Fonts ────────────────────────────────────────────────────────────
def load_font(size, mono=False):
    if mono:
        paths = [
            "/System/Library/Fonts/SFNSMono.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",  # Linux
        ]
    else:
        paths = [
            "/System/Library/Fonts/HelveticaNeue.ttc",  # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_bar(draw, x, y, w, h, ratio, color):
    """Draw a progress bar with rounded ends."""
    # Background track
    rounded_rect(draw, (x, y, x + w, y + h), radius=h // 2, fill=(40, 50, 65))
    # Filled portion
    fw = max(int(w * ratio), h)  # at least one circle width
    rounded_rect(draw, (x, y, x + fw, y + h), radius=h // 2, fill=color)


def generate(agent_data: dict, output_path: str):
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Outer card with rounded border
    margin = 24
    rounded_rect(draw, (margin, margin, W - margin, H - margin),
                 radius=24, fill=CARD_BG, outline=BORDER, width=2)

    # ── Fonts ──
    f_label = load_font(16)
    f_small = load_font(18)
    f_body = load_font(22)
    f_med = load_font(28)
    f_large = load_font(48)
    f_hero = load_font(64)
    f_mono = load_font(20, mono=True)
    f_mono_lg = load_font(36, mono=True)

    # ── Top label ──
    draw.text((60, 50), "OPEN-SOURCE AI AGENT TRUST PROFILE", font=f_small, fill=MUTED)

    # ── Agent name ──
    name = agent_data["name"]
    draw.text((60, 85), name, font=f_hero, fill=TEXT)

    # ── Description ──
    desc = agent_data.get("description", "")
    if desc:
        # Truncate if too long
        if len(desc) > 80:
            desc = desc[:77] + "..."
        draw.text((60, 165), desc, font=f_body, fill=MUTED)

    # ── Repo ──
    repo = agent_data.get("repo", "")
    draw.text((60, 198), repo, font=f_mono, fill=(100, 116, 139))

    # ── Evidence grade badge (top right) ──
    grade = agent_data.get("evidence_grade", "D")
    grade_color = GRADE_COLORS.get(grade, MUTED)
    gx, gy = W - 160, 50
    rounded_rect(draw, (gx, gy, gx + 120, gy + 70), radius=16, fill=grade_color)
    # Center the grade letter
    grade_text = f"Grade {grade}"
    bbox = draw.textbbox((0, 0), grade_text, font=f_med)
    tw = bbox[2] - bbox[0]
    draw.text((gx + (120 - tw) // 2, gy + 18), grade_text, font=f_med, fill=BG)

    # ── Trust score (large, center-left) ──
    trust = agent_data.get("trust_score", 0)
    ty = 255
    f_trust = load_font(80)
    draw.text((60, ty), f"{trust:.1f}", font=f_trust, fill=ACCENT)
    draw.text((60 + draw.textbbox((0, 0), f"{trust:.1f}", font=f_trust)[2] + 8, ty + 35), "/ 100", font=f_med, fill=MUTED)
    draw.text((60, ty + 90), "HVTrust Score", font=f_small, fill=MUTED)

    # ── Stat chips ──
    stats = [
        (agent_data.get("stars_fmt", "—"), "stars"),
        (str(agent_data.get("weekly_commits", "—")), "commits/4wk"),
        (agent_data.get("category", ""), "category"),
    ]
    cx = 60
    cy = 400
    for val, label in stats:
        if not val or val == "—" and label != "stars":
            continue
        # Chip background
        text_w = draw.textbbox((0, 0), str(val), font=f_med)[2] + 28
        chip_w = max(text_w, 100)
        rounded_rect(draw, (cx, cy, cx + chip_w, cy + 70), radius=14, fill=(34, 42, 56), outline=BORDER, width=1)
        draw.text((cx + 14, cy + 10), str(val), font=f_med, fill=TEXT)
        draw.text((cx + 14, cy + 44), label, font=f_label, fill=MUTED)
        cx += chip_w + 16

    # ── Trust breakdown bars (right side) ──
    breakdown = agent_data.get("trust_breakdown", {})
    if breakdown:
        bx = 640
        by = 255
        bar_w = 300
        bar_h = 16

        # Card for breakdown
        rounded_rect(draw, (bx - 20, by - 20, W - 50, by + 230),
                     radius=18, fill=(22, 28, 38), outline=BORDER, width=1)

        draw.text((bx, by - 5), "Trust Breakdown", font=f_small, fill=MUTED)
        by += 30

        for dim in ["safety", "identity", "transparency", "maintenance", "adoption"]:
            score = breakdown.get(dim, 0)
            max_score = TRUST_MAX.get(dim, 20)
            ratio = min(score / max_score, 1.0) if max_score else 0
            color = TRUST_COLORS.get(dim, MUTED)
            label = dim.capitalize()

            draw.text((bx, by), label, font=f_label, fill=MUTED)
            draw.text((bx + bar_w + 10, by), f"{score:.0f}/{max_score}", font=f_label, fill=MUTED)
            by += 20
            draw_bar(draw, bx, by, bar_w, bar_h, ratio, color)
            by += bar_h + 14

    # ── Bottom bar ──
    bottom_y = H - 65
    draw.line([(margin + 20, bottom_y - 8), (W - margin - 20, bottom_y - 8)], fill=BORDER, width=1)
    draw.text((60, bottom_y), "hvtracker.net", font=f_med, fill=ACCENT)

    rank = agent_data.get("rank", "")
    rank_text = f"Rank #{rank} of 192"
    bbox = draw.textbbox((0, 0), rank_text, font=f_small)
    draw.text((W - 60 - (bbox[2] - bbox[0]), bottom_y + 5), rank_text, font=f_small, fill=MUTED)

    img.save(output_path, "PNG", optimize=True)
    print(f"Generated OG card: {output_path} ({W}×{H})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_og_card.py <slug> [output_path]")
        sys.exit(1)

    slug = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else f"agents/{slug}/og.png"

    # Load agent data
    agent_path = f"data/agents/{slug}.json"
    try:
        with open(agent_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Agent data not found: {agent_path}")
        sys.exit(1)

    generate(data, out)
