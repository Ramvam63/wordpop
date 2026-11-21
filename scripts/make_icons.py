"""Generate the app icons in frontend/icons (requires Pillow: pip install pillow).

Design: two flashcards (a darker card behind, a deep-brown card in front with
"text" lines) on an amber background.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "frontend" / "icons"

AMBER = (255, 201, 41)  # #FFC929 background
BROWN = (110, 62, 0)  # #6E3E00 front card
DEEP = (196, 128, 0)  # #C48000 back card and text lines
S = 1024  # draw large, then shrink for smooth edges


def _rotated(draw_fn, angle: float, scale: float) -> Image.Image:
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), scale)
    return layer.rotate(angle, resample=Image.BICUBIC, center=(S / 2, S / 2))


def _card(fill):
    def draw(d: ImageDraw.ImageDraw, k: float) -> None:
        w, h, r = 430 * k, 560 * k, 60 * k
        d.rounded_rectangle([S / 2 - w / 2, S / 2 - h / 2, S / 2 + w / 2, S / 2 + h / 2], radius=r, fill=fill)
    return draw


def _lines(title, body):
    def draw(d: ImageDraw.ImageDraw, k: float) -> None:
        cx, cy = S / 2, S / 2
        d.rounded_rectangle([cx - 140 * k, cy - 150 * k, cx + 140 * k, cy - 90 * k], radius=30 * k, fill=title)
        d.rounded_rectangle([cx - 140 * k, cy - 20 * k, cx + 90 * k, cy + 25 * k], radius=22 * k, fill=body)
        d.rounded_rectangle([cx - 140 * k, cy + 75 * k, cx + 40 * k, cy + 120 * k], radius=22 * k, fill=body)
    return draw


def flashcards(*, scale: float = 1.0, background: str = "rounded") -> Image.Image:
    """background: 'rounded' (app icon), 'square' (iOS / maskable) or 'none' (badge)."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if background == "rounded":
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=AMBER)
    elif background == "square":
        d.rectangle([0, 0, S, S], fill=AMBER)

    if background == "none":
        # Notification badge: a single-colour silhouette (the system tints it).
        img.alpha_composite(_rotated(_card(BROWN), 14, scale))
        img.alpha_composite(_rotated(_card(BROWN), -6, scale))
        return img

    img.alpha_composite(_rotated(_card(DEEP), 14, scale))
    img.alpha_composite(_rotated(_card(BROWN), -6, scale))
    img.alpha_composite(_rotated(_lines(AMBER, DEEP), -6, scale))
    return img


def save(img: Image.Image, size: int, name: str, rgb: bool = False) -> None:
    out = img.resize((size, size), Image.LANCZOS)
    if rgb:
        out = out.convert("RGB")
    out.save(OUT / name, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app_icon = flashcards()
    save(app_icon, 192, "icon-192.png")
    save(app_icon, 512, "icon-512.png")
    # Maskable: Android may crop to a circle, so keep the cards inside the middle 80%.
    save(flashcards(scale=0.8, background="square"), 512, "icon-maskable-512.png")
    # iOS adds its own rounded corners, so give it a full square.
    save(flashcards(background="square"), 180, "apple-touch-icon.png", rgb=True)
    save(flashcards(scale=1.25, background="none"), 96, "badge-96.png")
    print("Icons written to", OUT)


if __name__ == "__main__":
    main()
