"""Generate the app icons in frontend/icons (requires Pillow: pip install pillow)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "frontend" / "icons"
BRAND = (79, 70, 229)
WHITE = (255, 255, 255)


def font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def icon(size: int, *, padding: float = 0.0, rounded: bool = True, transparent: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not transparent:
        if rounded:
            d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=BRAND)
        else:
            d.rectangle([0, 0, size, size], fill=BRAND)
    inner = size * (1 - 2 * padding)
    # speech bubble
    cx, cy, r = size / 2, size / 2 - inner * 0.04, inner * 0.30
    color = BRAND if transparent else WHITE
    d.rounded_rectangle([cx - r * 1.25, cy - r, cx + r * 1.25, cy + r * 0.85], radius=int(r * 0.45), fill=color)
    d.polygon([(cx - r * 0.55, cy + r * 0.8), (cx - r * 0.85, cy + r * 1.35), (cx - r * 0.05, cy + r * 0.8)], fill=color)
    # letter
    f = font(int(r * 1.3))
    text_color = WHITE if transparent else BRAND
    d.text((cx, cy - r * 0.07), "Aa", font=f, fill=text_color, anchor="mm")
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon(192).save(OUT / "icon-192.png")
    icon(512).save(OUT / "icon-512.png")
    icon(512, padding=0.1, rounded=False).save(OUT / "icon-maskable-512.png")
    icon(180, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png")  # iOS rounds it itself
    icon(96, transparent=True).save(OUT / "badge-96.png")
    print("Icons written to", OUT)


if __name__ == "__main__":
    main()
