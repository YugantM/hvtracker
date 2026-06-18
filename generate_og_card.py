#!/usr/bin/env python3
"""Generate a custom OG card (1200x630) for a project profile page."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630

BG = "#f4f1eb"
SURFACE = "#eae6de"
BORDER = "#d4cfc5"
TEXT = "#1a1a1a"
MUTED = "#6b6560"
ACCENT = "#2c5282"
ACCENT_WARM = "#b05a3a"
GREEN = "#2f6846"
RED = "#9b3c3c"
AMBER = "#8b6914"

GRADE_COLORS = {
    "A": ("#e8f5e9", GREEN, GREEN),
    "B": ("#e3ecf6", ACCENT, ACCENT),
    "C": ("#fdf3e0", AMBER, AMBER),
    "D": ("#f0ebe5", MUTED, MUTED),
    "F": ("#fde8e8", RED, RED),
}

TRUST_COLORS = {
    "safety": "#c0392b",
    "identity": ACCENT,
    "transparency": AMBER,
    "maintenance": GREEN,
    "adoption": ACCENT_WARM,
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


def stat_box(draw, x, y, w, value, label, accent):
    rounded(draw, (x, y, x + w, y + 78), 14, fill=hex_rgb(SURFACE), outline=hex_rgb(BORDER))
    # Shrink the value font to fit the box width (long categories like
    # "Agent Frameworks" were overflowing the box at the fixed size 26).
    value_font = fit_text(draw, str(value), w - 32, 26, 14, bold=True)
    draw.text((x + 16, y + 12), str(value), font=value_font, fill=hex_rgb(TEXT))
    draw.text((x + 16, y + 46), label, font=load_font(14), fill=hex_rgb(accent))


def trust_bar(draw, x, y, w, label, score, maximum, color):
    draw.text((x, y), label, font=load_font(15, bold=True), fill=hex_rgb(TEXT))
    value = f"{score:.0f}/{maximum}"
    vfont = load_font(14, mono=True)
    vb = draw.textbbox((0, 0), value, font=vfont)
    draw.text((x + w - (vb[2] - vb[0]), y), value, font=vfont, fill=hex_rgb(MUTED))
    y += 22
    rounded(draw, (x, y, x + w, y + 12), 6, fill=hex_rgb(BORDER), outline=None)
    fill_w = max(14, int(w * min(max(score / maximum, 0), 1)))
    rounded(draw, (x, y, x + fill_w, y + 12), 6, fill=hex_rgb(color), outline=None)
    return y + 24


def category_label(text: str) -> str:
    if len(text) <= 22:
        return text
    return text[:21] + "..."


def safe_description(text: str) -> str:
    return (text or "").replace("\n", " ").strip()


def generate(agent_data: dict, output_path: str):
    img = Image.new("RGB", (W, H), hex_rgb(BG))
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle((0, 0, W, 6), fill=hex_rgb(ACCENT_WARM))

    left_x = 60
    top_y = 36
    content_w = 600

    # Header
    draw.text((left_x, top_y), "HV", font=load_font(20, bold=True, mono=True), fill=hex_rgb(TEXT))
    hv_w = draw.textbbox((0, 0), "HV", font=load_font(20, bold=True, mono=True))[2]
    tracker_font = load_font(20, mono=True)
    draw.text((left_x + hv_w, top_y), "Tracker", font=tracker_font, fill=hex_rgb(ACCENT_WARM))
    tracker_w = draw.textbbox((0, 0), "Tracker", font=tracker_font)[2]
    draw.text((left_x + hv_w + tracker_w + 18, top_y + 2), "AI Trust Registry", font=load_font(16), fill=hex_rgb(MUTED))

    # Grade pill
    grade = agent_data.get("evidence_grade", "D")
    grade_bg, grade_fg, _ = GRADE_COLORS.get(grade, GRADE_COLORS["D"])
    pill_text = f"Grade {grade}"
    pill_font = load_font(22, bold=True)
    pill_bbox = draw.textbbox((0, 0), pill_text, font=pill_font)
    pill_w = (pill_bbox[2] - pill_bbox[0]) + 36
    pill_h = 46
    pill_x = W - 60 - pill_w
    pill_y = 30
    rounded(draw, (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h), 12, fill=hex_rgb(grade_bg), outline=hex_rgb(grade_fg))
    draw.text((pill_x + 18, pill_y + 11), pill_text, font=pill_font, fill=hex_rgb(grade_fg))

    # Separator line
    draw.line((left_x, 76, W - 60, 76), fill=hex_rgb(BORDER), width=1)

    # Agent name
    name = agent_data["name"]
    name_font = fit_text(draw, name, content_w, 56, 36, bold=True)
    draw.text((left_x, 96), name, font=name_font, fill=hex_rgb(TEXT))

    # Description
    desc_font = load_font(20)
    desc = safe_description(agent_data.get("description", ""))
    desc_lines = wrap_text(draw, desc, desc_font, content_w, 2)
    name_bbox = draw.textbbox((0, 0), name, font=name_font)
    desc_y = 96 + name_bbox[3] + 12
    for line in desc_lines:
        draw.text((left_x, desc_y), line, font=desc_font, fill=hex_rgb(MUTED))
        desc_y += 28

    # Repo
    repo = agent_data.get("repo", "")
    draw.text((left_x, desc_y + 6), repo, font=load_font(18, mono=True), fill=hex_rgb(ACCENT))

    # Trust score
    trust = float(agent_data.get("trust_score") or 0)
    score_y = 290
    score_font = load_font(72, bold=True)
    score_text = f"{trust:.1f}"
    score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
    draw.text((left_x, score_y), score_text, font=score_font, fill=hex_rgb(GREEN))
    draw.text((left_x + (score_bbox[2] - score_bbox[0]) + 10, score_y + 28), "/ 100", font=load_font(28, mono=True), fill=hex_rgb(MUTED))
    draw.text((left_x, score_y + 78), "HVTrust score", font=load_font(18), fill=hex_rgb(MUTED))

    # Stat boxes
    stars = agent_data.get("stars_fmt", "—")
    commits = str(agent_data.get("weekly_commits") or 0)
    category = category_label(agent_data.get("category", "Uncategorized"))
    stat_y = 440
    stat_box(draw, left_x, stat_y, 140, stars, "stars", GREEN)
    stat_box(draw, left_x + 154, stat_y, 140, commits, "commits / 4wk", ACCENT)
    stat_box(draw, left_x + 308, stat_y, 248, category, "category", ACCENT_WARM)

    # Trust breakdown panel
    panel_x = 690
    panel_y = 96
    panel_w = 450
    panel_h = 330
    rounded(draw, (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h), 18, fill=hex_rgb(SURFACE), outline=hex_rgb(BORDER), width=1)
    draw.text((panel_x + 24, panel_y + 20), "Trust breakdown", font=load_font(24, bold=True), fill=hex_rgb(TEXT))
    draw.text((panel_x + 24, panel_y + 50), "Public, checkable signals by dimension", font=load_font(14), fill=hex_rgb(MUTED))

    by = panel_y + 84
    breakdown = agent_data.get("trust_breakdown", {})
    for dim in ["safety", "identity", "transparency", "maintenance", "adoption"]:
        by = trust_bar(
            draw,
            panel_x + 24,
            by,
            panel_w - 48,
            dim.capitalize(),
            float(breakdown.get(dim, 0) or 0),
            TRUST_MAX[dim],
            TRUST_COLORS[dim],
        )

    # Footer
    footer_y = 560
    draw.line((left_x, footer_y, W - 60, footer_y), fill=hex_rgb(BORDER), width=1)
    draw.text((left_x, footer_y + 16), "hvtracker.net", font=load_font(22, bold=True, mono=True), fill=hex_rgb(TEXT))

    rank = agent_data.get("rank")
    total = agent_data.get("total") or 196
    rank_text = f"Rank #{rank} of {total}" if rank else ""
    if rank_text:
        rb = draw.textbbox((0, 0), rank_text, font=load_font(20, mono=True))
        draw.text((W - 60 - (rb[2] - rb[0]), footer_y + 18), rank_text, font=load_font(20, mono=True), fill=hex_rgb(MUTED))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"Generated OG card: {output_path} ({W}x{H})")


def generate_site_card(output_path: str, total: int = 196, categories: int = 15):
    """Generate the site-level OG card for the homepage."""
    img = Image.new("RGB", (W, H), hex_rgb(BG))
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle((0, 0, W, 6), fill=hex_rgb(ACCENT_WARM))

    left_x = 60
    top_y = 40

    # Logo
    draw.text((left_x, top_y), "HV", font=load_font(28, bold=True, mono=True), fill=hex_rgb(TEXT))
    hv_w = draw.textbbox((0, 0), "HV", font=load_font(28, bold=True, mono=True))[2]
    draw.text((left_x + hv_w, top_y), "Tracker", font=load_font(28, mono=True), fill=hex_rgb(ACCENT_WARM))

    # Separator
    draw.line((left_x, 86, W - 60, 86), fill=hex_rgb(BORDER), width=1)

    # Title
    draw.text((left_x, 110), "AI Trust Registry", font=load_font(52, bold=True), fill=hex_rgb(TEXT))

    # Subtitle
    sub_font = load_font(22)
    sub_lines = [
        "Independent trust scores for open-source AI agent projects.",
        "Based on public, checkable signals across safety, provenance,",
        "transparency, maintenance, and adoption.",
    ]
    sub_y = 180
    for line in sub_lines:
        draw.text((left_x, sub_y), line, font=sub_font, fill=hex_rgb(MUTED))
        sub_y += 32

    # Stats row
    stat_y = 320
    stat_w = 200
    gap = 24

    stats = [
        (str(total), "active projects", GREEN),
        (str(categories), "categories", ACCENT),
        ("2h", "refresh cycle", ACCENT_WARM),
        ("v3", "methodology", AMBER),
    ]
    for i, (val, label, color) in enumerate(stats):
        x = left_x + i * (stat_w + gap)
        rounded(draw, (x, stat_y, x + stat_w, stat_y + 90), 14, fill=hex_rgb(SURFACE), outline=hex_rgb(BORDER))
        draw.text((x + 18, stat_y + 12), val, font=load_font(34, bold=True), fill=hex_rgb(TEXT))
        draw.text((x + 18, stat_y + 54), label, font=load_font(14), fill=hex_rgb(color))

    # Signals list
    signals_y = 450
    draw.text((left_x, signals_y), "Signals tracked:", font=load_font(16, bold=True), fill=hex_rgb(MUTED))
    signals = "OSSF Scorecard · Build provenance · Signed commits · License · Maintenance · Adoption"
    draw.text((left_x + 140, signals_y), signals, font=load_font(16), fill=hex_rgb(MUTED))

    # Footer
    footer_y = 540
    draw.line((left_x, footer_y, W - 60, footer_y), fill=hex_rgb(BORDER), width=1)
    draw.text((left_x, footer_y + 22), "hvtracker.net", font=load_font(24, bold=True, mono=True), fill=hex_rgb(TEXT))

    tag = "Evidence-weighted trust scores · Badge ready · Public JSON API"
    tb = draw.textbbox((0, 0), tag, font=load_font(18))
    draw.text((W - 60 - (tb[2] - tb[0]), footer_y + 24), tag, font=load_font(18), fill=hex_rgb(MUTED))

    img.save(output_path, "PNG", optimize=True)
    print(f"Generated site OG card: {output_path} ({W}x{H})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_og_card.py <slug> [output_path]")
        print("       python generate_og_card.py --site [output_path]")
        sys.exit(1)

    if sys.argv[1] == "--site":
        out = sys.argv[2] if len(sys.argv) > 2 else "og-v2.png"
        generate_site_card(out)
    else:
        slug = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else f"agents/{slug}/og.png"
        data_path = Path(f"data/agents/{slug}.json")

        if not data_path.exists():
            print(f"Agent data not found: {data_path}")
            sys.exit(1)

        with data_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        generate(data, out)
