"""Regenerate the app logo: assets/logo.png (512px) + multi-size assets/icon.ico.

The original icon.ico held a single 32x32 frame, which looked blurry anywhere
it was shown larger (header, Explorer, alt-tab). This redraws the same design
- blue round badge, cloud, rain bars, RFF wordmark - as crisp vector-style art.

Run from the repo root:  venv\\Scripts\\python assets\\make_logo.py
Needs a real display session (the wordmark uses system fonts, which the
offscreen platform can't load).
"""
import os
import struct
import sys

from PyQt5.QtCore import QBuffer, QByteArray, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QGuiApplication, QImage,
                         QLinearGradient, QPainter, QPainterPath, QPen)

SIZE = 512
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw_logo(size=SIZE):
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.scale(size / 512.0, size / 512.0)

    # Round badge with a subtle vertical gradient and darker rim
    grad = QLinearGradient(0, 0, 0, 512)
    grad.setColorAt(0.0, QColor("#4D96DE"))
    grad.setColorAt(1.0, QColor("#2A66AC"))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(QColor("#1F5494"), 14))
    p.drawEllipse(QRectF(14, 14, 484, 484))

    # Cloud: union of puffs over a rounded base
    cloud = QPainterPath()
    cloud.setFillRule(Qt.WindingFill)
    cloud.addEllipse(QRectF(148, 122, 124, 124))
    cloud.addEllipse(QRectF(216, 86, 152, 152))
    cloud.addEllipse(QRectF(304, 134, 106, 106))
    cloud.addRoundedRect(QRectF(148, 178, 262, 72), 36, 36)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#F4F9FE"))
    p.drawPath(cloud.simplified())

    # Rain bars hanging from the cloud (rainfall hyetograph)
    p.setBrush(QColor(255, 255, 255, 215))
    for x, length in ((168, 44), (220, 78), (272, 56), (324, 88), (376, 46)):
        p.drawRoundedRect(QRectF(x, 262, 26, length), 13, 13)

    # Wordmark
    font = QFont("Segoe UI")
    font.setPixelSize(126)
    font.setWeight(QFont.Black)
    font.setLetterSpacing(QFont.PercentageSpacing, 104)
    p.setFont(font)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(0, 338, 512, 130), Qt.AlignCenter, "RFF")
    p.end()
    return img


def write_ico(path, image, sizes=ICO_SIZES):
    """Write a .ico with PNG-compressed frames (valid on Vista+)."""
    frames = []
    for sz in sizes:
        scaled = image.scaled(sz, sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.WriteOnly)
        scaled.save(buf, "PNG")
        buf.close()
        frames.append((sz, bytes(ba)))

    entries, blobs = b"", b""
    offset = 6 + 16 * len(frames)
    for sz, blob in frames:
        entries += struct.pack("<BBBBHHII", sz % 256, sz % 256, 0, 0, 1, 32,
                               len(blob), offset)
        offset += len(blob)
        blobs += blob
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(frames)) + entries + blobs)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    here = os.path.dirname(os.path.abspath(__file__))
    img = draw_logo()
    img.save(os.path.join(here, "logo.png"))
    write_ico(os.path.join(here, "icon.ico"), img)
    print("wrote logo.png (512px) and icon.ico", ICO_SIZES)
