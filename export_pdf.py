# i18n-converted
"""The PDF side of the exports (export_routes.py): a clean printed list, not a
screenshot of the page.

Two shapes. A tune list (My Tunes, a session's tunes) is one heading, the filter
lines, then each tune with its title line and its notation. A session's logs
are nights as headings, sets as sub-headings, and the tunes under them the same
way. Notation comes in as PNG bytes (tune_setting.image, the abc-renderer's
output); a tune with no image gets one muted line saying so, and the rest of the
document is unaffected.

Fonts: fpdf2's built-in fonts are Latin-1 only, and tune names carry curly
apostrophes and the odd character beyond that, so DejaVu Sans is shipped in
static/fonts/ (its licence sits beside it).
"""

import os
import struct
from io import BytesIO
from typing import Iterable, List, Optional

from flask_babel import gettext as _, gettext as tr
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# The tune types (tune.tune_type's CHECK list), named here so the extractor puts
# them in the catalog: the detail lines and set labels translate them at run time.
_TUNE_TYPE_NAMES = (
    _("Jig"),
    _("Reel"),
    _("Slip Jig"),
    _("Hop Jig"),
    _("Hornpipe"),
    _("Polka"),
    _("Set Dance"),
    _("Slide"),
    _("Waltz"),
    _("Barndance"),
    _("Strathspey"),
    _("Three-Two"),
    _("Mazurka"),
    _("March"),
    _("Air"),
)

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts")

# A4 portrait with 18 mm margins: the notation images are rendered at a width
# that reads at a music stand without being a poster.
_MARGIN = 18
_IMAGE_WIDTH = 174  # mm; the page's text width


def _png_size(data: bytes):
    """(width, height) in pixels from a PNG's IHDR, or None if it is not a PNG."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return (w, h) if w and h else None


class _Document(FPDF):
    def __init__(self, title: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.set_auto_page_break(auto=True, margin=_MARGIN)
        self.add_font("DejaVu", "", os.path.join(_FONT_DIR, "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf"))
        self.set_title(title)
        self.set_creator("Ceol")
        self.doc_title = title
        self.add_page()

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120)
        self.cell(
            0,
            6,
            f"{self.doc_title}  ·  {self.page_no()}",
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.set_text_color(0)

    # -- building blocks -------------------------------------------------------

    def para(self, text: str, size: float):
        """A full-width paragraph that leaves the cursor at the left margin on
        the next line (multi_cell's default leaves it at the right edge, where
        the next paragraph would have no room)."""
        self.multi_cell(0, size * 0.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(self, text: str, size: int = 18, before: float = 0, after: float = 2):
        if before:
            self.ln(before)
        self.set_font("DejaVu", "B", size)
        self.para(text, size)
        self.ln(after)

    def muted(self, text: str, size: int = 9):
        self.set_font("DejaVu", "", size)
        self.set_text_color(110)
        self.para(text, size)
        self.set_text_color(0)

    def lines(self, items: Iterable[str], size: int = 9):
        for item in items:
            if item:
                self.muted(item, size)

    def rule(self):
        y = self.get_y()
        self.set_draw_color(190)
        self.line(_MARGIN, y, _MARGIN + _IMAGE_WIDTH, y)
        self.ln(2)

    def tune(self, title: str, detail: Optional[str], image: Optional[bytes]):
        """One tune: its title line, a muted detail line, then the notation. The
        whole block moves to a new page together when the image would not fit."""
        size = _png_size(image) if image else None
        img_h = (_IMAGE_WIDTH * size[1] / size[0]) if size else 0
        needed = 7 + (4 if detail else 0) + (img_h if size else 5) + 4
        if self.will_page_break(needed) and needed < (self.h - 2 * _MARGIN):
            self.add_page()
        self.set_font("DejaVu", "B", 11)
        self.para(title, 12)
        if detail:
            self.muted(detail, 8.5)
        if size:
            self.image(BytesIO(image), w=_IMAGE_WIDTH)
        else:
            self.muted(_("No notation for this tune."), 8.5)
        self.ln(4)


def _detail_line(tune: dict) -> str:
    """'Reel · D · thesession.org: The Silver Spear' with the empty parts left out."""
    parts = []
    if tune.get("tune_type"):
        parts.append(tr(tune["tune_type"]))
    if tune.get("key"):
        parts.append(tune["key"])
    catalogue = tune.get("catalogue_name")
    if catalogue and catalogue != tune.get("name"):
        parts.append(_("thesession.org: %(name)s", name=catalogue))
    return "  ·  ".join(parts)


def tunes_pdf(
    title: str, subtitle: str, filters: List[str], tunes: List[dict]
) -> bytes:
    """A tune list. Each tune dict: name, tune_type, key, catalogue_name, image (PNG
    bytes or None). Order is the caller's."""
    doc = _Document(title)
    doc.heading(title)
    doc.muted(subtitle)
    doc.lines(filters)
    doc.ln(3)
    doc.rule()
    for tune in tunes:
        doc.tune(
            tune.get("name") or _("Unnamed tune"), _detail_line(tune), tune.get("image")
        )
    return bytes(doc.output())


def logs_pdf(
    title: str, subtitle: str, filters: List[str], nights: List[dict]
) -> bytes:
    """A session's nights. Each night: heading, notes, attendees (optional), sets.
    Each set: number, label, started_by (optional), tunes as in tunes_pdf."""
    doc = _Document(title)
    doc.heading(title)
    doc.muted(subtitle)
    doc.lines(filters)
    doc.ln(3)
    for index, night in enumerate(nights):
        if index:
            doc.add_page()
        doc.heading(night["heading"], size=15)
        doc.lines([night.get("where"), night.get("notes"), night.get("attendees")])
        doc.rule()
        if not night["sets"]:
            doc.muted(_("Nothing logged this night."))
        for set_ in night["sets"]:
            label = _("Set %(n)s · %(label)s", n=set_["number"], label=set_["label"])
            if set_.get("started_by"):
                label += "  ·  " + _("started by %(name)s", name=set_["started_by"])
            doc.heading(label, size=11, before=2, after=1)
            for tune in set_["tunes"]:
                doc.tune(
                    tune.get("name") or _("Unnamed tune"),
                    _detail_line(tune),
                    tune.get("image"),
                )
    return bytes(doc.output())
