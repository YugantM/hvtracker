"""Favicon delivery.

Bing rendered a blank globe for hvtracker.net results because two things were
true at once: no generated page declared an icon (only the homepage template
did), and the root /favicon.ico fallback was a 301 to an SVG rather than a real
raster file. These lock both halves, plus the Dockerfile copy that decides
whether the raster files exist in the image at all.
"""
import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent

ICO = ROOT / "favicon.ico"
APPLE = ROOT / "apple-touch-icon.png"

LITERAL_LINKS = (
    '<link rel="icon" href="/favicon.ico" sizes="32x32">',
    '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
)


def test_raster_icons_exist_with_the_sizes_crawlers_want():
    assert ICO.is_file() and APPLE.is_file(), "run scripts/generate_favicons.py"

    ico = Image.open(ICO)
    assert ico.format == "ICO"
    # Bing prefers 32x32 or larger; 16 stays for browser tabs, 48 for Google's
    # "larger than 48x48" guidance.
    assert {(16, 16), (32, 32), (48, 48)} <= set(ico.ico.sizes())

    apple = Image.open(APPLE)
    assert apple.format == "PNG"
    assert apple.size == (180, 180)
    # iOS composites transparency onto black, so this one must be opaque.
    assert apple.mode == "RGB"


def test_dockerfile_ships_the_raster_icons():
    """The image COPYs assets by filename — a file missing here 404s in prod
    while every local check still passes."""
    copy_lines = [
        ln for ln in (ROOT / "Dockerfile").read_text().splitlines()
        if ln.startswith("COPY") and "favicon.svg" in ln
    ]
    assert copy_lines, "expected a COPY line carrying the root static assets"
    assert "favicon.ico" in copy_lines[0]
    assert "apple-touch-icon.png" in copy_lines[0]


def _head_templates():
    return [p for p in sorted((ROOT / "templates").glob("*.j2"))
            if "<head>" in p.read_text(encoding="utf-8")]


def test_every_jinja_page_includes_the_shared_icon_partial():
    assert (ROOT / "templates" / "_head_icons.html.j2").is_file()
    missing = [p.name for p in _head_templates() + [ROOT / "template.html"]
               if "_head_icons.html.j2" not in p.read_text(encoding="utf-8")]
    assert not missing, f"templates with a <head> but no icon include: {missing}"


def test_hand_written_blog_posts_declare_the_icons():
    """blog_static/ is copied verbatim by the renderer, so these can't use the
    Jinja include and need the literal links instead."""
    posts = sorted((ROOT / "blog_static").glob("*/index.html"))
    assert posts, "expected hand-written posts under blog_static/"
    for post in posts:
        text = post.read_text(encoding="utf-8")
        for link in LITERAL_LINKS:
            assert link in text, f"{post.parent.name} is missing {link}"


def test_inline_generator_heads_declare_the_icons():
    """Two pages build their <head> as a Python string, out of reach of both
    the Jinja include and the blog lint: /data/ and app.py's marketing pages."""
    for path in (ROOT / "fetch_and_build.py", ROOT / "app.py"):
        text = path.read_text(encoding="utf-8")
        for link in LITERAL_LINKS:
            assert link in text, f"{path.name} inline head is missing {link}"


# The serving-side counterparts (routes return files not redirects; rendered
# pages carry the declaration) live in test_api.py, where the fixture that
# renders a site and drives the app already exists.
