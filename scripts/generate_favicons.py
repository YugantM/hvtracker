#!/usr/bin/env python3
"""Rasterize favicon.svg into the formats search engines actually fetch.

Bing (and any crawler falling back to the root /favicon.ico convention) wants a
real file at a real path, not a redirect to an SVG. This renders the same target
pulse geometry as favicon.svg into:

  favicon.ico          16/32/48 multi-size, transparent — the root fallback
  apple-touch-icon.png 180x180, opaque — iOS composites transparency onto black

Geometry is kept in the SVG's 64x64 user space and supersampled 16x before
downsampling, so the thin strokes survive at 16px.

Run from the repo root:  python scripts/generate_favicons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

VIEWBOX = 64  # favicon.svg viewBox is "0 0 64 64"
SS = 16  # supersample factor before LANCZOS downsample

STROKE = (111, 102, 93, 255)  # #6f665d
ACCENT = (198, 124, 109, 255)  # #c67c6d
PAGE_BG = (244, 241, 235, 255)  # #f4f1eb — site background, for the opaque icon

ICO_SIZES = [16, 32, 48]
APPLE_SIZE = 180

REPO_ROOT = Path(__file__).resolve().parent.parent


def _draw_master(bg):
    """Render the icon once at VIEWBOX * SS, in SVG user-space coordinates."""
    n = VIEWBOX * SS
    img = Image.new("RGBA", (n, n), bg)
    d = ImageDraw.Draw(img)

    def s(v):
        return v * SS

    # <circle cx=32 cy=32 r=18 fill=none stroke=#6f665d stroke-width=5>
    r, w = 18, 5
    d.ellipse(
        [s(32 - r), s(32 - r), s(32 + r), s(32 + r)],
        outline=STROKE,
        width=int(s(w)),
    )

    # <path d="M32 12v11M32 41v11M12 32h11M41 32h11" stroke-width=5 linecap=round>
    cap = w / 2
    for x0, y0, x1, y1 in [
        (32, 12, 32, 23),
        (32, 41, 32, 52),
        (12, 32, 23, 32),
        (41, 32, 52, 32),
    ]:
        d.line([s(x0), s(y0), s(x1), s(y1)], fill=STROKE, width=int(s(w)))
        # Pillow has no round line cap; disc the endpoints to match linecap="round".
        for cx, cy in ((x0, y0), (x1, y1)):
            d.ellipse(
                [s(cx - cap), s(cy - cap), s(cx + cap), s(cy + cap)], fill=STROKE
            )

    # <circle cx=32 cy=32 r=4.5 fill=#6f665d>
    d.ellipse([s(32 - 4.5), s(32 - 4.5), s(32 + 4.5), s(32 + 4.5)], fill=STROKE)

    # <circle cx=46 cy=18 r=5 fill=#c67c6d> — painted last, overlaps the ring.
    d.ellipse([s(46 - 5), s(18 - 5), s(46 + 5), s(18 + 5)], fill=ACCENT)

    return img


def main():
    transparent = _draw_master((0, 0, 0, 0))
    opaque = _draw_master(PAGE_BG)

    ico_path = REPO_ROOT / "favicon.ico"
    transparent.resize((ICO_SIZES[-1],) * 2, Image.LANCZOS).save(
        ico_path, format="ICO", sizes=[(n, n) for n in ICO_SIZES]
    )
    print(f"wrote {ico_path.name} ({', '.join(f'{n}x{n}' for n in ICO_SIZES)})")

    apple_path = REPO_ROOT / "apple-touch-icon.png"
    opaque.convert("RGB").resize((APPLE_SIZE,) * 2, Image.LANCZOS).save(
        apple_path, format="PNG", optimize=True
    )
    print(f"wrote {apple_path.name} ({APPLE_SIZE}x{APPLE_SIZE})")


if __name__ == "__main__":
    main()
