"""Create docs/qr-wordpop.png: a QR code that opens the live app (pip install "qrcode[pil]")."""

import sys
from pathlib import Path

import qrcode
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://wordpopapp.onrender.com"

qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=3)
qr.add_data(URL)
img = qr.make_image(fill_color=(59, 35, 0), back_color="white").convert("RGBA")

# App icon in the middle (high error correction keeps the code readable)
icon = Image.open(ROOT / "frontend" / "icons" / "icon-512.png").convert("RGBA")
size = img.width // 4
icon = icon.resize((size, size), Image.LANCZOS)
pad = Image.new("RGBA", (size + 16, size + 16), "white")
pad.paste(icon, (8, 8), icon)
img.paste(pad, ((img.width - pad.width) // 2, (img.height - pad.height) // 2), pad)

out = ROOT / "docs" / "qr-wordpop.png"
img.convert("RGB").save(out, optimize=True)
print("QR code for", URL, "->", out)
