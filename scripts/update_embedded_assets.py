from __future__ import annotations

from pathlib import Path
import base64
import textwrap

ASSETS = {
    "AIO_PNG_B64": "aio.png",
    "AIO_2_PNG_B64": "aio-2.png",
    "APP_ICON_ICO_B64": "app_icon.ico",
}

OUT = Path("serial_verifier/embedded_assets.py")


def wrap(s: str, width: int = 76) -> str:
    return "\n".join(textwrap.wrap(s, width))


def main() -> None:
    lines: list[str] = []
    lines.append('"""Embedded assets for the serial verification GUI."""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import base64")
    lines.append("from PyQt5.QtGui import QIcon, QPixmap")
    lines.append("")
    lines.append("def _decode(data: str) -> bytes:")
    lines.append('    return base64.b64decode(data.encode("ascii"))')
    lines.append("")

    for name, filename in ASSETS.items():
        payload = Path(filename).read_bytes()
        b64 = base64.b64encode(payload).decode("ascii")
        lines.append(f'{name} = """\\')
        lines.append(wrap(b64))
        lines.append('"""')
        lines.append("")

    lines.append("def load_pixmap(b64: str) -> QPixmap:")
    lines.append("    pixmap = QPixmap()")
    lines.append("    pixmap.loadFromData(_decode(b64))")
    lines.append("    return pixmap")
    lines.append("")
    lines.append("def load_app_icon() -> QIcon:")
    lines.append("    icon = QIcon()")
    lines.append("    ico_pixmap = load_pixmap(APP_ICON_ICO_B64)")
    lines.append("    if not ico_pixmap.isNull():")
    lines.append("        icon.addPixmap(ico_pixmap)")
    lines.append("    else:")
    lines.append("        fallback = load_pixmap(AIO_PNG_B64)")
    lines.append("        if not fallback.isNull():")
    lines.append("            icon.addPixmap(fallback)")
    lines.append("    return icon")

    OUT.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
