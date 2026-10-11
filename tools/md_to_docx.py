#!/usr/bin/env python3
"""
توليد ملف Word أكاديمي (RTL) من «دراسة مشروع التخرج.md».

- غلاف أكاديمي + صفحات فاصلة للأبواب
- فهرس محتويات آلي + قائمة الأشكال + قائمة الجداول (حقول Word تُحدَّث عند الفتح أو عبر COM)
- عناوين مرقّمة بأنماط Word الحقيقية (Heading 1–3) لتعمل مع الفهرس
- جداول بترويسة ملوّنة وتظليل متناوب وعناوين مرقّمة
- مخططات Mermaid تُصيَّر إلى PNG عبر mmdc (إن توفّر) وتُدرج كأشكال مرقّمة
- مقتطفات برمجية بخط أحادي المسافة LTR

الاستخدام:
    python tools/md_to_docx.py [input.md] [output.docx] [--mmdc PATH] [--chrome PATH] [--finalize [--pdf out.pdf]]

المتطلبات:
    pip install python-docx pillow
    npm install @mermaid-js/mermaid-cli   (اختياري — لتصيير المخططات؛ يُكتشف mmdc تلقائياً)
    Microsoft Word                        (اختياري — مع --finalize لتحديث الفهارس وتصدير PDF)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Pt, RGBColor

# ---------------------------------------------------------------------------
# الهوية البصرية والخطوط
# ---------------------------------------------------------------------------
ARABIC_FONT = "Sakkal Majalla"
LATIN_FONT = "Calibri"
CODE_FONT = "Consolas"

PRIMARY = RGBColor(0x1B, 0x4F, 0x72)      # نيلي
SECONDARY = RGBColor(0x14, 0x8F, 0x77)    # فيروزي
ACCENT = RGBColor(0xD4, 0xA0, 0x17)       # ذهبي
MUTED = RGBColor(0x5A, 0x6A, 0x7A)
TEXT = RGBColor(0x1F, 0x2A, 0x36)
PRIMARY_HEX = "1B4F72"
ZEBRA_HEX = "F4F7FB"
CODE_BG_HEX = "F2F4F7"
QUOTE_BG_HEX = "EEF5FA"

BODY_PT = 14
TABLE_PT = 11.5
CODE_PT = 9.5
CAPTION_PT = 11

PAGE_W_CM = 21.0
MARGIN_CM = 2.5
CONTENT_W_CM = PAGE_W_CM - 2 * MARGIN_CM

DOC_TITLE = "دراسة مشروع التخرج — نظام بصيرة (Basera)"


# ---------------------------------------------------------------------------
# أدوات XML منخفضة المستوى
# ---------------------------------------------------------------------------
def _child(parent, tag: str):
    el = parent.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        parent.append(el)
    return el


def set_par_rtl(p, align: str = "both") -> None:
    p_pr = p._p.get_or_add_pPr()
    _child(p_pr, "w:bidi").set(qn("w:val"), "1")
    p.alignment = {
        "both": WD_ALIGN_PARAGRAPH.JUSTIFY,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "left": WD_ALIGN_PARAGRAPH.LEFT,
    }[align]


def set_par_ltr(p, align: str = "left") -> None:
    p_pr = p._p.get_or_add_pPr()
    bidi = p_pr.find(qn("w:bidi"))
    if bidi is not None:
        p_pr.remove(bidi)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT if align == "left" else WD_ALIGN_PARAGRAPH.CENTER


def set_indent(p, start_cm: float = 0, hanging_cm: float = 0, end_cm: float = 0) -> None:
    p_pr = p._p.get_or_add_pPr()
    ind = _child(p_pr, "w:ind")
    if start_cm:
        ind.set(qn("w:start"), str(int(Cm(start_cm).twips)))
    if end_cm:
        ind.set(qn("w:end"), str(int(Cm(end_cm).twips)))
    if hanging_cm:
        ind.set(qn("w:hanging"), str(int(Cm(hanging_cm).twips)))


def set_par_shading(p, fill_hex: str) -> None:
    p_pr = p._p.get_or_add_pPr()
    shd = _child(p_pr, "w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)


def set_par_border(p, side: str, color_hex: str, size: int = 18, space: int = 6) -> None:
    p_pr = p._p.get_or_add_pPr()
    pbdr = _child(p_pr, "w:pBdr")
    b = _child(pbdr, f"w:{side}")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), str(size))
    b.set(qn("w:space"), str(space))
    b.set(qn("w:color"), color_hex)


def keep_with_next(p, on: bool = True) -> None:
    p.paragraph_format.keep_with_next = on


def style_run(
    run,
    size_pt: float = BODY_PT,
    *,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor | None = None,
    arabic_font: str = ARABIC_FONT,
    latin_font: str = LATIN_FONT,
    rtl: bool = True,
) -> None:
    r_pr = run._r.get_or_add_rPr()
    fonts = _child(r_pr, "w:rFonts")
    fonts.set(qn("w:ascii"), latin_font)
    fonts.set(qn("w:hAnsi"), latin_font)
    fonts.set(qn("w:eastAsia"), latin_font)
    fonts.set(qn("w:cs"), arabic_font)
    half = str(int(round(size_pt * 2)))
    _child(r_pr, "w:sz").set(qn("w:val"), half)
    _child(r_pr, "w:szCs").set(qn("w:val"), half)
    for tag, flag in (("w:b", bold), ("w:bCs", bold), ("w:i", italic), ("w:iCs", italic)):
        el = r_pr.find(qn(tag))
        if flag:
            if el is None:
                r_pr.append(OxmlElement(tag))
        elif el is not None:
            r_pr.remove(el)
    rtl_el = r_pr.find(qn("w:rtl"))
    if rtl and rtl_el is None:
        r_pr.append(OxmlElement("w:rtl"))
    elif not rtl and rtl_el is not None:
        r_pr.remove(rtl_el)
    if color is not None:
        run.font.color.rgb = color
    lang = _child(r_pr, "w:lang")
    lang.set(qn("w:val"), "en-US")
    lang.set(qn("w:bidi"), "ar-SA")


def add_field(paragraph, instr: str, placeholder: str = "", size_pt: float = BODY_PT, bold=False) -> None:
    run = paragraph.add_run()
    style_run(run, size_pt, bold=bold)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    txt = OxmlElement("w:t")
    txt.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, it, sep, txt, end):
        run._r.append(el)


def shade_cell(cell, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = _child(tc_pr, "w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)


def set_cell_margins(table, top=60, bottom=60, start=100, end=100) -> None:
    tbl_pr = table._tbl.tblPr
    mar = _child(tbl_pr, "w:tblCellMar")
    for tag, val in (("w:top", top), ("w:bottom", bottom), ("w:start", start), ("w:end", end)):
        el = _child(mar, tag)
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")


def set_table_rtl(table) -> None:
    tbl_pr = table._tbl.tblPr
    _child(tbl_pr, "w:bidiVisual").set(qn("w:val"), "1")


def set_table_full_width(table) -> None:
    tbl_pr = table._tbl.tblPr
    w = _child(tbl_pr, "w:tblW")
    w.set(qn("w:type"), "pct")
    w.set(qn("w:w"), "5000")
    layout = _child(tbl_pr, "w:tblLayout")
    layout.set(qn("w:type"), "autofit")


def set_repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    _child(tr_pr, "w:tblHeader").set(qn("w:val"), "true")
    _child(tr_pr, "w:cantSplit").set(qn("w:val"), "true")


def set_cell_valign_center(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    _child(tc_pr, "w:vAlign").set(qn("w:val"), "center")


# ---------------------------------------------------------------------------
# تنسيق النص المضمّن (**غامق**، *مائل*، `كود`، [رابط](url))
# ---------------------------------------------------------------------------
INLINE_RE = re.compile(
    r"(\*\*[^*]+?\*\*|`[^`]+?`|\[[^\]]+?\]\([^)]+?\)|(?<![\w*])\*[^*\s][^*]*?\*(?![\w*]))"
)


def add_inline(paragraph, text: str, size_pt: float = BODY_PT, *, bold=False, italic=False, color=None) -> None:
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            r = paragraph.add_run(text[pos:m.start()])
            style_run(r, size_pt, bold=bold, italic=italic, color=color)
        chunk = m.group(0)
        if chunk.startswith("**"):
            r = paragraph.add_run(chunk[2:-2])
            style_run(r, size_pt, bold=True, italic=italic, color=color)
        elif chunk.startswith("`"):
            r = paragraph.add_run(chunk[1:-1])
            style_run(r, max(size_pt - 3, 9), latin_font=CODE_FONT, arabic_font=CODE_FONT, color=RGBColor(0x8A, 0x2B, 0x2B), rtl=False)
        elif chunk.startswith("["):
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", chunk).groups()
            r = paragraph.add_run(label)
            style_run(r, size_pt, bold=bold, italic=italic, color=PRIMARY)
            r2 = paragraph.add_run(f" ({url})")
            style_run(r2, size_pt - 2, latin_font=CODE_FONT, arabic_font=CODE_FONT, color=MUTED, rtl=False)
        else:
            r = paragraph.add_run(chunk[1:-1])
            style_run(r, size_pt, bold=bold, italic=True, color=color)
        pos = m.end()
    if pos < len(text):
        r = paragraph.add_run(text[pos:])
        style_run(r, size_pt, bold=bold, italic=italic, color=color)


def strip_md(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


# ---------------------------------------------------------------------------
# محلل Markdown بسيط
# ---------------------------------------------------------------------------
def is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 2


def is_sep_row(line: str) -> bool:
    s = line.strip().strip("|")
    cells = [c.strip() for c in s.split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def split_row(line: str) -> list[str]:
    s = line.strip()
    s = s[1:-1]
    out, cur, i = [], "", 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "`":
            j = s.find("`", i + 1)
            if j == -1:
                cur += s[i:]
                break
            cur += s[i:j + 1]
            i = j + 1
            continue
        if ch == "|":
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    out.append(cur.strip())
    return out


class Block:
    def __init__(self, kind: str, **kw):
        self.kind = kind
        self.__dict__.update(kw)


def parse_markdown(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            lang = s[3:].strip().lower()
            code: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append(Block("code", lang=lang, lines=code))
            continue

        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            blocks.append(Block("heading", level=len(m.group(1)), text=m.group(2).strip()))
            i += 1
            continue

        if s in ("---", "***", "___"):
            blocks.append(Block("hr"))
            i += 1
            continue

        if s.startswith(">"):
            quote: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(Block("quote", text=" ".join(q for q in quote if q)))
            continue

        if is_table_row(line):
            rows: list[list[str]] = []
            aligns: list[str] | None = None
            while i < n and is_table_row(lines[i]):
                if is_sep_row(lines[i]):
                    aligns = []
                    for c in lines[i].strip().strip("|").split("|"):
                        c = c.strip()
                        if c.startswith(":") and c.endswith(":"):
                            aligns.append("center")
                        elif c.endswith(":"):
                            aligns.append("left")
                        else:
                            aligns.append("right")
                else:
                    rows.append(split_row(lines[i]))
                i += 1
            blocks.append(Block("table", rows=rows, aligns=aligns or []))
            continue

        m = re.match(r"^(\s*)(\d+)[.)]\s+(.+)$", line)
        if m:
            items: list[tuple[str, str]] = []
            while i < n:
                mm = re.match(r"^(\s*)(\d+)[.)]\s+(.+)$", lines[i])
                if not mm:
                    # سطر متابعة داخل العنصر (مسافة بادئة)
                    if items and lines[i].startswith("   ") and lines[i].strip():
                        items[-1] = (items[-1][0], items[-1][1] + " " + lines[i].strip())
                        i += 1
                        continue
                    break
                items.append((mm.group(2), mm.group(3).strip()))
                i += 1
            blocks.append(Block("olist", items=items))
            continue

        m = re.match(r"^(\s*)[-*•]\s+(.+)$", line)
        if m:
            items = []
            while i < n:
                mm = re.match(r"^(\s*)[-*•]\s+(.+)$", lines[i])
                if not mm:
                    if items and lines[i].startswith("   ") and lines[i].strip():
                        items[-1] = (items[-1][0], items[-1][1] + " " + lines[i].strip())
                        i += 1
                        continue
                    break
                depth = 1 if len(mm.group(1)) >= 2 else 0
                txt = mm.group(2).strip()
                txt = re.sub(r"^\[[ xX]\]\s*", "", txt)
                items.append((depth, txt))
                i += 1
            blocks.append(Block("ulist", items=items))
            continue

        if not s:
            i += 1
            continue

        # فقرة: اجمع الأسطر المتتالية غير الفارغة (مع مراعاة السطرين الفاصلين "  ")
        para: list[str] = []
        while i < n:
            cur = lines[i]
            cs = cur.strip()
            if (
                not cs
                or cs.startswith("```")
                or re.match(r"^#{1,6}\s", cur)
                or cs in ("---", "***", "___")
                or cs.startswith(">")
                or is_table_row(cur)
                or re.match(r"^\s*\d+[.)]\s+", cur)
                or re.match(r"^\s*[-*•]\s+", cur)
            ):
                break
            para.append(cs)
            hard_break = cur.endswith("  ")
            i += 1
            if hard_break:
                para.append("\n")
        text = " ".join(para).replace(" \n ", "\n").replace(" \n", "\n").replace("\n ", "\n")
        blocks.append(Block("para", text=text.strip()))
    return blocks


# ---------------------------------------------------------------------------
# تصيير Mermaid
# ---------------------------------------------------------------------------
class MermaidRenderer:
    def __init__(self, mmdc: str | None, chrome: str | None, cache_dir: Path):
        self.mmdc = mmdc
        self.chrome = chrome
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.available = bool(mmdc and Path(mmdc).exists())
        self._config_path = self.cache_dir / "mermaid.config.json"
        self._puppeteer_path = self.cache_dir / "puppeteer.json"
        if self.available:
            self._config_path.write_text(
                json.dumps(
                    {
                        "theme": "base",
                        "fontFamily": "Segoe UI, Tahoma, Arial, sans-serif",
                        "themeVariables": {
                            "fontFamily": "Segoe UI, Tahoma, Arial, sans-serif",
                            "fontSize": "16px",
                            "primaryColor": "#EAF2F8",
                            "primaryTextColor": "#1F2A36",
                            "primaryBorderColor": "#1B4F72",
                            "lineColor": "#1B4F72",
                            "secondaryColor": "#E8F6F3",
                            "tertiaryColor": "#FDF6E3",
                            "clusterBkg": "#F4F7FB",
                            "clusterBorder": "#B0C4D8",
                            "edgeLabelBackground": "#FFFFFF",
                            "actorBkg": "#EAF2F8",
                            "actorBorder": "#1B4F72",
                            "signalColor": "#1B4F72",
                            "noteBkgColor": "#FDF6E3",
                            "noteBorderColor": "#D4A017",
                        },
                        "flowchart": {"htmlLabels": True, "curve": "basis", "padding": 12},
                        "sequence": {"useMaxWidth": False},
                        "er": {"useMaxWidth": False},
                        "gantt": {
                            "useMaxWidth": False,
                            "useWidth": 900,
                            "barHeight": 34,
                            "barGap": 8,
                            "topPadding": 60,
                            "fontSize": 15,
                            "sectionFontSize": 15,
                            "leftPadding": 120,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            pupp = {"args": ["--no-sandbox", "--disable-gpu", "--lang=ar"]}
            if chrome and Path(chrome).exists():
                pupp["executablePath"] = chrome
            self._puppeteer_path.write_text(json.dumps(pupp), encoding="utf-8")

    @staticmethod
    def _prepare(source: str) -> str:
        head = source.strip().splitlines()[0].strip() if source.strip() else ""
        if head.startswith(("flowchart", "graph", "sequenceDiagram")):
            source = source.replace("\\n", "<br/>")
        return source

    def render(self, source: str) -> Path | None:
        if not self.available:
            return None
        prepared = self._prepare(source)
        key = hashlib.sha1(prepared.encode("utf-8")).hexdigest()[:16]
        out_png = self.cache_dir / f"{key}.png"
        if out_png.exists() and out_png.stat().st_size > 0:
            return out_png
        in_mmd = self.cache_dir / f"{key}.mmd"
        in_mmd.write_text(prepared, encoding="utf-8")
        cmd = [
            self.mmdc,
            "-i", str(in_mmd),
            "-o", str(out_png),
            "-b", "white",
            "-w", "1400",
            "-s", "2",
            "-c", str(self._config_path),
            "-p", str(self._puppeteer_path),
            "-q",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, shell=str(self.mmdc).lower().endswith(".cmd"))
        except Exception as exc:  # pragma: no cover
            print(f"  [mermaid] فشل التشغيل: {exc}", file=sys.stderr)
            return None
        if res.returncode != 0 or not out_png.exists():
            print(f"  [mermaid] فشل التصيير ({res.returncode}): {res.stderr.strip()[:300]}", file=sys.stderr)
            return None
        _trim_png(out_png)
        return out_png


def _trim_png(path: Path, pad: int = 24) -> None:
    """قصّ الهوامش البيضاء الزائدة حول المخطط (بعض المخططات مثل journey تترك فراغاً كبيراً)."""
    try:
        from PIL import Image, ImageChops
    except Exception:
        return
    try:
        img = Image.open(path).convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if not bbox:
            return
        l, t, r, b = bbox
        l, t = max(l - pad, 0), max(t - pad, 0)
        r, b = min(r + pad, img.width), min(b + pad, img.height)
        if (r - l) < img.width or (b - t) < img.height:
            img.crop((l, t, r, b)).save(path, "PNG", optimize=True)
    except Exception as exc:  # pragma: no cover
        print(f"  [trim] {exc}", file=sys.stderr)


def png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    w = int.from_bytes(head[16:20], "big")
    h = int.from_bytes(head[20:24], "big")
    return (w, h)


# ---------------------------------------------------------------------------
# منشئ الوثيقة
# ---------------------------------------------------------------------------
class DocBuilder:
    def __init__(self, renderer: MermaidRenderer):
        self.doc = Document()
        self.renderer = renderer
        self.fig_no = 0
        self.tbl_no = 0
        self.current_heading = ""
        self.heading_table_count: dict[str, int] = {}
        self.heading_fig_count: dict[str, int] = {}
        self.parts: dict[int, tuple[str, str]] = {}  # chapter_no -> (part label, part title)
        self._setup_styles()
        self._setup_sections()

    # ---- إعداد الأنماط -------------------------------------------------
    def _setup_styles(self) -> None:
        styles = self.doc.styles
        normal = styles["Normal"]
        normal.font.name = LATIN_FONT
        normal.font.size = Pt(BODY_PT)
        r_pr = normal.element.get_or_add_rPr()
        fonts = _child(r_pr, "w:rFonts")
        fonts.set(qn("w:ascii"), LATIN_FONT)
        fonts.set(qn("w:hAnsi"), LATIN_FONT)
        fonts.set(qn("w:cs"), ARABIC_FONT)
        _child(r_pr, "w:szCs").set(qn("w:val"), str(BODY_PT * 2))
        lang = _child(r_pr, "w:lang")
        lang.set(qn("w:val"), "en-US")
        lang.set(qn("w:bidi"), "ar-SA")
        p_pr = normal.element.get_or_add_pPr()
        _child(p_pr, "w:bidi").set(qn("w:val"), "1")
        pf = normal.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        pf.space_after = Pt(6)
        pf.space_before = Pt(0)

        sizes = {1: 22, 2: 17, 3: 14.5, 4: 13}
        colors = {1: PRIMARY, 2: PRIMARY, 3: SECONDARY, 4: TEXT}
        for lvl in range(1, 5):
            st = styles[f"Heading {lvl}"]
            st.font.name = LATIN_FONT
            st.font.size = Pt(sizes[lvl])
            st.font.bold = True
            st.font.italic = False
            st.font.color.rgb = colors[lvl]
            r_pr = st.element.get_or_add_rPr()
            fonts = _child(r_pr, "w:rFonts")
            for k in ("w:ascii", "w:hAnsi", "w:eastAsia"):
                fonts.set(qn(k), LATIN_FONT)
            fonts.set(qn("w:cs"), ARABIC_FONT)
            for k in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                if fonts.get(qn(k)) is not None:
                    del fonts.attrib[qn(k)]
            _child(r_pr, "w:szCs").set(qn("w:val"), str(int(sizes[lvl] * 2)))
            _child(r_pr, "w:bCs")
            p_pr = st.element.get_or_add_pPr()
            _child(p_pr, "w:bidi").set(qn("w:val"), "1")
            pf = st.paragraph_format
            pf.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pf.keep_with_next = True
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            pf.space_before = Pt({1: 18, 2: 16, 3: 12, 4: 8}[lvl])
            pf.space_after = Pt({1: 12, 2: 8, 3: 6, 4: 4}[lvl])

        # أنماط الفهرس (TOC 1..3) — خط عربي وRTL
        for lvl in range(1, 4):
            try:
                st = styles[f"TOC {lvl}"]
            except KeyError:
                continue
            st.font.name = LATIN_FONT
            st.font.size = Pt(13 if lvl == 1 else 12)
            r_pr = st.element.get_or_add_rPr()
            fonts = _child(r_pr, "w:rFonts")
            fonts.set(qn("w:cs"), ARABIC_FONT)
            _child(r_pr, "w:szCs").set(qn("w:val"), str((13 if lvl == 1 else 12) * 2))
            p_pr = st.element.get_or_add_pPr()
            _child(p_pr, "w:bidi").set(qn("w:val"), "1")
            st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            st.paragraph_format.space_after = Pt(3)
            if lvl == 1:
                st.font.bold = True

    def _setup_sections(self) -> None:
        sec = self.doc.sections[0]
        sec.page_height = Cm(29.7)
        sec.page_width = Cm(PAGE_W_CM)
        sec.top_margin = Cm(2.5)
        sec.bottom_margin = Cm(2.5)
        sec.left_margin = Cm(MARGIN_CM)
        sec.right_margin = Cm(MARGIN_CM)
        sec.header_distance = Cm(1.2)
        sec.footer_distance = Cm(1.2)
        # قسم الغلاف والمقدمات: بلا ترويسة أو ترقيم
        sec.header.is_linked_to_previous = False
        sec.footer.is_linked_to_previous = False
        # ترقيم رومي للمقدمات
        sect_pr = sec._sectPr
        pg = _child(sect_pr, "w:pgNumType")
        pg.set(qn("w:fmt"), "lowerRoman")
        pg.set(qn("w:start"), "1")
        # bidi للقسم
        _child(sect_pr, "w:bidi")

    def start_body_section(self) -> None:
        """قسم جديد للمتن: ترويسة + ترقيم صفحات يبدأ من 1."""
        sec = self.doc.add_section(WD_SECTION.NEW_PAGE)
        sec.header.is_linked_to_previous = False
        sec.footer.is_linked_to_previous = False
        sect_pr = sec._sectPr
        pg = _child(sect_pr, "w:pgNumType")
        pg.set(qn("w:fmt"), "decimal")
        pg.set(qn("w:start"), "1")
        _child(sect_pr, "w:bidi")

        hp = sec.header.paragraphs[0]
        hp.text = ""
        set_par_rtl(hp, "right")
        r = hp.add_run(DOC_TITLE)
        style_run(r, 10, color=MUTED)
        set_par_border(hp, "bottom", PRIMARY_HEX, size=8, space=4)

        fp = sec.footer.paragraphs[0]
        fp.text = ""
        set_par_rtl(fp, "center")
        r = fp.add_run("صفحة ")
        style_run(r, 10, color=MUTED)
        add_field(fp, "PAGE", "1", 10)
        r = fp.add_run(" من ")
        style_run(r, 10, color=MUTED)
        add_field(fp, "SECTIONPAGES", "1", 10)

    def front_footer(self) -> None:
        """ترقيم رومي في قسم المقدمات (بعد الغلاف)."""
        sec = self.doc.sections[0]
        sec.different_first_page_header_footer = True
        fp = sec.footer.paragraphs[0]
        fp.text = ""
        set_par_rtl(fp, "center")
        add_field(fp, "PAGE", "i", 10)

    # ---- عناصر أساسية -------------------------------------------------
    def para(self, text: str, *, size=BODY_PT, align="both", bold=False, italic=False, color=None, space_after=6):
        p = self.doc.add_paragraph()
        parts = text.split("\n")
        # الفقرات ذات الأسطر القسرية لا تُضبط (تجنّب تمدد الفراغات قبل فاصل السطر)
        set_par_rtl(p, "right" if (len(parts) > 1 and align == "both") else align)
        p.paragraph_format.space_after = Pt(space_after)
        for idx, part in enumerate(parts):
            if idx:
                p.add_run().add_break(WD_BREAK.LINE)
            add_inline(p, part, size, bold=bold, italic=italic, color=color)
        return p

    def page_break(self) -> None:
        self.doc.add_page_break()

    def heading(self, text: str, level: int, *, new_page: bool = False) -> None:
        clean = strip_md(text)
        p = self.doc.add_paragraph(style=f"Heading {min(level, 4)}")
        set_par_rtl(p, "right")
        if new_page:
            p.paragraph_format.page_break_before = True
        add_inline(p, clean, {1: 22, 2: 17, 3: 14.5, 4: 13}[min(level, 4)], bold=True,
                   color={1: PRIMARY, 2: PRIMARY, 3: SECONDARY, 4: TEXT}[min(level, 4)])
        if level == 1:
            set_par_border(p, "bottom", PRIMARY_HEX, size=12, space=6)
        self.current_heading = re.sub(r"^[\d٠-٩]+(\.[\d٠-٩]+)*[ب]?\.?\s*", "", clean).strip()
        self.current_heading = re.sub(r"^\d+[ب]?\.\d+[ب]?\s*", "", self.current_heading).strip()

    def part_page(self, label: str, title: str) -> None:
        self._part_body(label, title, page_break=True)

    def part_page_inline(self, label: str, title: str) -> None:
        """صفحة باب في بداية قسم جديد (القسم نفسه يبدأ صفحة جديدة)."""
        self._part_body(label, title, page_break=False)

    def _part_body(self, label: str, title: str, *, page_break: bool) -> None:
        first = True
        for _ in range(11):
            sp = self.doc.add_paragraph()
            sp.paragraph_format.space_after = Pt(0)
            if first and page_break:
                sp.paragraph_format.page_break_before = True
            first = False
        p = self.doc.add_paragraph()
        set_par_rtl(p, "center")
        r = p.add_run(label)
        style_run(r, 20, bold=True, color=SECONDARY)
        p.paragraph_format.space_after = Pt(6)
        p2 = self.doc.add_paragraph()
        set_par_rtl(p2, "center")
        r = p2.add_run(title)
        style_run(r, 30, bold=True, color=PRIMARY)
        line = self.doc.add_paragraph()
        set_par_rtl(line, "center")
        r = line.add_run("━" * 18)
        style_run(r, 14, color=ACCENT, rtl=False)
        # وصف مختصر لمحتوى الباب (أرقام الفصول)
        chapters = [c for c, (lab, _) in self.parts.items() if lab == label]
        if chapters:
            nxt = sorted(c for c in self.parts if c > chapters[0])
            last = (nxt[0] - 1) if nxt else None
            desc = f"الفصول {chapters[0]}–{last}" if last is not None else f"الفصول {chapters[0]} فما بعد"
            pd = self.doc.add_paragraph()
            set_par_rtl(pd, "center")
            r = pd.add_run(desc)
            style_run(r, 13, color=MUTED)

    def quote(self, text: str) -> None:
        p = self.doc.add_paragraph()
        set_par_rtl(p, "both")
        set_indent(p, start_cm=0.6, end_cm=0.3)
        set_par_shading(p, QUOTE_BG_HEX)
        set_par_border(p, "right", PRIMARY_HEX, size=24, space=8)
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(10)
        add_inline(p, text, BODY_PT - 1, italic=True, color=PRIMARY)
        return p

    def ulist(self, items: list[tuple[int, str]]) -> None:
        for depth, txt in items:
            p = self.doc.add_paragraph()
            set_par_rtl(p, "both")
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            set_indent(p, start_cm=0.9 + depth * 0.7, hanging_cm=0.45)
            bullet = "•" if depth == 0 else "◦"
            r = p.add_run(f"{bullet}\t")
            style_run(r, BODY_PT, color=PRIMARY)
            add_inline(p, txt, BODY_PT)

    def olist(self, items: list[tuple[str, str]]) -> None:
        for num, txt in items:
            p = self.doc.add_paragraph()
            set_par_rtl(p, "both")
            p.paragraph_format.space_after = Pt(3)
            set_indent(p, start_cm=1.0, hanging_cm=0.6)
            r = p.add_run(f"{num}.\t")
            style_run(r, BODY_PT, bold=True, color=PRIMARY)
            add_inline(p, txt, BODY_PT)

    def code(self, lines: list[str], lang: str) -> None:
        if lang == "mermaid":
            self.mermaid("\n".join(lines))
            return
        # تجاهل الأسطر الفارغة في البداية/النهاية
        while lines and not lines[0].strip():
            lines = lines[1:]
        while lines and not lines[-1].strip():
            lines = lines[:-1]
        if not lines:
            return
        first = True
        for ln in lines:
            p = self.doc.add_paragraph()
            set_par_ltr(p)
            set_par_shading(p, CODE_BG_HEX)
            pf = p.paragraph_format
            pf.space_after = Pt(0)
            pf.space_before = Pt(6 if first else 0)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            set_indent(p, start_cm=0.3, end_cm=0.3)
            keep_with_next(p, True)
            r = p.add_run(ln.replace("\t", "    ") if ln.strip() else " ")
            style_run(r, CODE_PT, latin_font=CODE_FONT, arabic_font=CODE_FONT, color=TEXT, rtl=False)
            first = False
        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(4)

    # ---- الأشكال والجداول --------------------------------------------
    def _caption(self, label: str, seq_name: str, title: str, *, above: bool) -> None:
        p = self.doc.add_paragraph()
        set_par_rtl(p, "center")
        p.paragraph_format.space_before = Pt(2 if not above else 8)
        p.paragraph_format.space_after = Pt(10 if not above else 4)
        if above:
            keep_with_next(p, True)
        r = p.add_run(f"{label} ")
        style_run(r, CAPTION_PT, bold=True, color=PRIMARY)
        add_field(p, f"SEQ {seq_name} \\* ARABIC", "0", CAPTION_PT, bold=True)
        r = p.add_run(f": {title}")
        style_run(r, CAPTION_PT, bold=False, color=TEXT)

    def _numbered_title(self, base: str, counter: dict[str, int]) -> str:
        counter[base] = counter.get(base, 0) + 1
        return base if counter[base] == 1 else f"{base} ({counter[base]})"

    def mermaid(self, source: str) -> None:
        png = self.renderer.render(source)
        title = self._numbered_title(self.current_heading or "مخطط", self.heading_fig_count)
        if png is None:
            # بديل: عرض الكود
            note = self.doc.add_paragraph()
            set_par_rtl(note, "right")
            r = note.add_run("مخطط Mermaid (لم يُصيَّر — المصدر أدناه):")
            style_run(r, 11, italic=True, color=MUTED)
            self.code(source.splitlines(), "text")
            self._caption("الشكل", "شكل", title, above=False)
            return
        w_px, h_px = png_size(png)
        max_w = Cm(CONTENT_W_CM)
        max_h = Cm(19.5)
        # DPI 192 (scale 2) → الحجم الطبيعي بالسم
        nat_w = Emu(int(w_px / 192 * 914400))
        nat_h = Emu(int(h_px / 192 * 914400))
        width = min(nat_w, max_w)
        height = int(nat_h * (width / nat_w)) if nat_w else max_h
        if height > max_h:
            height = max_h
            width = int(nat_w * (height / nat_h))
        # المخططات الصغيرة لا تُكبَّر فوق 80% من العرض
        if width < Cm(7):
            width = Cm(7)
            height = int(nat_h * (width / nat_w))
        p = self.doc.add_paragraph()
        set_par_ltr(p, "center")
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        keep_with_next(p, True)
        p.add_run().add_picture(str(png), width=width, height=height)
        self._caption("الشكل", "شكل", title, above=False)

    def table(self, rows: list[list[str]], aligns: list[str]) -> None:
        if not rows:
            return
        cols = max(len(r) for r in rows)
        title = self._numbered_title(self.current_heading or "جدول", self.heading_table_count)
        self._caption("الجدول", "جدول", title, above=True)

        table = self.doc.add_table(rows=len(rows), cols=cols)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_rtl(table)
        set_table_full_width(table)
        set_cell_margins(table)

        # حدود ناعمة
        tbl_pr = table._tbl.tblPr
        borders = _child(tbl_pr, "w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = _child(borders, f"w:{side}")
            b.set(qn("w:val"), "single")
            b.set(qn("w:sz"), "4")
            b.set(qn("w:space"), "0")
            b.set(qn("w:color"), "B7C4D1")

        for ri, row in enumerate(rows):
            tr = table.rows[ri]
            if ri == 0:
                set_repeat_header(tr)
            for ci in range(cols):
                txt = row[ci] if ci < len(row) else ""
                cell = tr.cells[ci]
                set_cell_valign_center(cell)
                p = cell.paragraphs[0]
                align = "right"
                if ci < len(aligns) and aligns[ci] == "center":
                    align = "center"
                if ri == 0:
                    align = "center"
                # الخلايا القصيرة (أرقام/رموز) توسّط
                if ri > 0 and len(strip_md(txt)) <= 3:
                    align = "center"
                set_par_rtl(p, align)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                if ri == 0:
                    add_inline(p, txt, TABLE_PT, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
                    shade_cell(cell, PRIMARY_HEX)
                else:
                    add_inline(p, txt, TABLE_PT)
                    if ri % 2 == 0:
                        shade_cell(cell, ZEBRA_HEX)
        after = self.doc.add_paragraph()
        after.paragraph_format.space_after = Pt(6)

    # ---- الفهارس ------------------------------------------------------
    def toc(self, title: str, instr: str, placeholder: str) -> None:
        h = self.doc.add_paragraph()
        set_par_rtl(h, "right")
        h.paragraph_format.page_break_before = True
        r = h.add_run(title)
        style_run(r, 20, bold=True, color=PRIMARY)
        set_par_border(h, "bottom", PRIMARY_HEX, size=12, space=6)
        h.paragraph_format.space_after = Pt(12)
        p = self.doc.add_paragraph()
        set_par_rtl(p, "right")
        add_field(p, instr, placeholder, 12)

    # ---- الغلاف -------------------------------------------------------
    def cover(self, title_lines: list[str], quote: str, fields: list[list[str]]) -> None:
        d = self.doc
        # شريط علوي
        band = d.add_paragraph()
        set_par_rtl(band, "center")
        set_par_shading(band, PRIMARY_HEX)
        band.paragraph_format.space_after = Pt(0)
        r = band.add_run("مشروع تخرج")
        style_run(r, 14, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        sp = d.add_paragraph()
        sp.paragraph_format.space_after = Pt(0)
        sp.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE

        p = d.add_paragraph()
        set_par_rtl(p, "center")
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        r = p.add_run("بصيرة")
        style_run(r, 48, bold=True, color=PRIMARY)
        p.paragraph_format.space_after = Pt(0)
        p = d.add_paragraph()
        set_par_ltr(p, "center")
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        r = p.add_run("B A S E R A")
        style_run(r, 15, color=ACCENT, rtl=False)
        p.paragraph_format.space_after = Pt(14)

        for idx, t in enumerate(title_lines):
            p = d.add_paragraph()
            set_par_rtl(p, "center")
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            r = p.add_run(strip_md(t))
            style_run(r, 19 if idx == 0 else 14, bold=(idx == 0), color=(TEXT if idx == 0 else SECONDARY))
            p.paragraph_format.space_after = Pt(4)

        if quote:
            p = d.add_paragraph()
            set_par_rtl(p, "center")
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(14)
            r = p.add_run(strip_md(quote))
            style_run(r, 12, italic=True, color=MUTED)

        if fields:
            table = d.add_table(rows=len(fields), cols=2)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            set_table_rtl(table)
            set_cell_margins(table, 70, 70, 140, 140)
            tbl_pr = table._tbl.tblPr
            w = _child(tbl_pr, "w:tblW")
            w.set(qn("w:type"), "pct")
            w.set(qn("w:w"), "4200")
            borders = _child(tbl_pr, "w:tblBorders")
            for side in ("top", "left", "bottom", "right", "insideV"):
                b = _child(borders, f"w:{side}")
                b.set(qn("w:val"), "nil")
            b = _child(borders, "w:insideH")
            b.set(qn("w:val"), "single")
            b.set(qn("w:sz"), "4")
            b.set(qn("w:color"), "D5DEE7")
            for ri, row in enumerate(fields):
                k = row[0] if row else ""
                v = row[1] if len(row) > 1 else ""
                c0, c1 = table.rows[ri].cells
                p0 = c0.paragraphs[0]
                set_par_rtl(p0, "right")
                p0.paragraph_format.space_after = Pt(0)
                p0.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                add_inline(p0, k, 12.5, bold=True, color=PRIMARY)
                p1 = c1.paragraphs[0]
                set_par_rtl(p1, "right")
                p1.paragraph_format.space_after = Pt(0)
                p1.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                add_inline(p1, v, 12.5)
                shade_cell(c0, "F4F7FB")
        # أسفل الغلاف
        p = d.add_paragraph()
        set_par_rtl(p, "center")
        p.paragraph_format.space_before = Pt(16)
        r = p.add_run("منصة تعليمية صوتية للمكفوفين — Flutter + Django REST")
        style_run(r, 12, color=MUTED)


# ---------------------------------------------------------------------------
# تجميع الوثيقة من الكتل
# ---------------------------------------------------------------------------
def parse_parts(blocks: list[Block]) -> tuple[dict[int, tuple[str, str]], int, int]:
    """يستخرج الأبواب من قسم «فهرس المحتويات» اليدوي ويعيد (map, start_idx, end_idx)."""
    parts: dict[int, tuple[str, str]] = {}
    start = end = -1
    for i, b in enumerate(blocks):
        if b.kind == "heading" and b.level == 2 and "فهرس المحتويات" in b.text:
            start = i
            j = i + 1
            current = None
            while j < len(blocks) and not (blocks[j].kind == "heading" and blocks[j].level <= 2):
                bj = blocks[j]
                if bj.kind == "heading" and bj.level == 3:
                    m = re.match(r"^(الباب\s+\S+)\s*[—-]\s*(.+)$", bj.text)
                    current = (m.group(1), m.group(2)) if m else (bj.text, "")
                elif bj.kind == "olist" and current:
                    first = int(bj.items[0][0])
                    parts.setdefault(first, current)
                    current = None
                j += 1
            end = j
            break
    return parts, start, end


def chapter_number(text: str) -> int | None:
    m = re.match(r"^(\d+)(ب)?\.\s", text)
    return int(m.group(1)) if m else None


def build(md_path: Path, out_path: Path, renderer: MermaidRenderer) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    blocks = parse_markdown(lines)
    b = DocBuilder(renderer)

    parts, toc_start, toc_end = parse_parts(blocks)
    b.parts = parts

    # --- الغلاف: العناوين الأولى + الاقتباس + جدول «صفحة الغلاف الأكاديمية»
    idx = 0
    title_lines: list[str] = []
    while idx < len(blocks) and blocks[idx].kind == "heading":
        title_lines.append(blocks[idx].text)
        idx += 1
    quote = ""
    if idx < len(blocks) and blocks[idx].kind == "quote":
        quote = blocks[idx].text
        idx += 1
    while idx < len(blocks) and blocks[idx].kind == "hr":
        idx += 1
    cover_fields: list[list[str]] = []
    cover_note: str | None = None
    if idx < len(blocks) and blocks[idx].kind == "heading" and "الغلاف" in blocks[idx].text:
        idx += 1
        if idx < len(blocks) and blocks[idx].kind == "table":
            cover_fields = blocks[idx].rows[1:]
            idx += 1
        if idx < len(blocks) and blocks[idx].kind == "para":
            cover_note = blocks[idx].text
            idx += 1
    # العنوان الأول (H1) عنوان الوثيقة، والثاني اسم النظام… نعرض الثالث والرابع كعناوين فرعية
    sub_titles = [t for t in title_lines[2:]] or title_lines[1:]
    b.cover([title_lines[0]] + sub_titles if title_lines else ["دراسة مشروع التخرج"], quote, cover_fields)
    b.front_footer()

    pending_break = True  # أول عنصر بعد الغلاف يبدأ صفحة جديدة
    if cover_note:
        q = b.quote(cover_note)
        q.paragraph_format.page_break_before = True
        pending_break = False

    body_started = False
    i = idx
    seen_parts: set[int] = set()
    while i < len(blocks):
        blk = blocks[i]

        # تخطّي الفهرس اليدوي واستبداله بفهارس آلية
        if toc_start != -1 and i == toc_start:
            b.toc("فهرس المحتويات", 'TOC \\o "1-2" \\h \\z \\u', "(اضغط F9 لتحديث الفهرس)")
            b.toc("قائمة الأشكال", 'TOC \\h \\z \\c "شكل"', "(اضغط F9 لتحديث القائمة)")
            b.toc("قائمة الجداول", 'TOC \\h \\z \\c "جدول"', "(اضغط F9 لتحديث القائمة)")
            i = toc_end
            continue

        if blk.kind == "heading":
            lvl = blk.level
            if lvl == 2:
                ch = chapter_number(blk.text)
                if ch is not None and not body_started:
                    b.start_body_section()
                    body_started = True
                    # القسم الجديد يبدأ صفحة جديدة تلقائياً
                    if ch in b.parts and ch not in seen_parts:
                        label, title = b.parts[ch]
                        b.part_page_inline(label, title)
                        seen_parts.add(ch)
                        b.heading(blk.text, 1, new_page=True)
                    else:
                        b.heading(blk.text, 1)
                elif ch is not None and ch in b.parts and ch not in seen_parts:
                    label, title = b.parts[ch]
                    b.part_page(label, title)
                    seen_parts.add(ch)
                    b.heading(blk.text, 1, new_page=True)
                else:
                    b.heading(blk.text, 1, new_page=True)
            elif lvl == 3:
                # في المقدمات: العناوين (إهداء/شكر/ملخص…) تُعامل كـ Heading 1 لتظهر في الفهرس
                if not body_started:
                    brk = pending_break or any(k in blk.text for k in ("إهداء", "الملخص", "كيف تُقرأ"))
                    b.heading(blk.text, 1, new_page=brk)
                    pending_break = False
                else:
                    b.heading(blk.text, 2)
            elif lvl == 4:
                b.heading(blk.text, 3 if body_started else 2)
            else:
                b.heading(blk.text, 4)
        elif blk.kind == "para":
            b.para(blk.text)
        elif blk.kind == "quote":
            b.quote(blk.text)
        elif blk.kind == "ulist":
            b.ulist(blk.items)
        elif blk.kind == "olist":
            b.olist(blk.items)
        elif blk.kind == "table":
            b.table(blk.rows, blk.aligns)
        elif blk.kind == "code":
            b.code(blk.lines, blk.lang)
        elif blk.kind == "hr":
            pass
        i += 1

    # خصائص الملف
    cp = b.doc.core_properties
    cp.title = DOC_TITLE
    cp.subject = "دراسة تحليل وتصميم وتنفيذ — مشروع تخرج"
    cp.author = "فريق مشروع بصيرة"
    cp.language = "ar-SA"
    cp.keywords = "بصيرة; إمكانية الوصول; Flutter; Django; مشروع تخرج"

    # ملاحظة: الفهارس حقول TOC/SEQ تُحدَّث بـ F9 داخل Word، أو آلياً عبر خطوة COM في finalize
    if os.environ.get("BASERA_DOC_UPDATE_ON_OPEN") == "1":
        settings = b.doc.settings.element
        _child(settings, "w:updateFields").set(qn("w:val"), "true")

    b.doc.save(str(out_path))
    print(f"تم الحفظ: {out_path} ({out_path.stat().st_size // 1024} KB) — أشكال Mermaid: {sum(b.heading_fig_count.values())}, جداول: {sum(b.heading_table_count.values())}")


def find_mmdc(explicit: str | None) -> str | None:
    if explicit and Path(explicit).exists():
        return explicit
    cands = [
        shutil.which("mmdc"),
        shutil.which("mmdc.cmd"),
        str(Path(tempfile.gettempdir()) / "basera_doc" / "node_modules" / ".bin" / "mmdc.cmd"),
        str(Path.home() / "AppData" / "Roaming" / "npm" / "mmdc.cmd"),
    ]
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


def find_chrome(explicit: str | None) -> str | None:
    if explicit and Path(explicit).exists():
        return explicit
    for c in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ):
        if Path(c).exists():
            return c
    return None


FINALIZE_PS1 = r"""
param([string]$InDocx, [string]$OutDocx, [string]$OutPdf)
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($InDocx, $false, $false)
    $null = $doc.Fields.Update()
    foreach ($t in $doc.TablesOfContents) { $t.Update() }
    foreach ($t in $doc.TablesOfFigures) { $t.Update() }
    $null = $doc.Fields.Update()
    foreach ($t in $doc.TablesOfContents) { $t.UpdatePageNumbers() }
    foreach ($t in $doc.TablesOfFigures) { $t.UpdatePageNumbers() }
    $doc.Repaginate()
    $pages = $doc.ComputeStatistics(2)
    if (Test-Path $OutDocx) { Remove-Item $OutDocx -Force }
    $doc.SaveAs2($OutDocx, 16)
    if ($OutPdf) {
        if (Test-Path $OutPdf) { Remove-Item $OutPdf -Force }
        $doc.ExportAsFixedFormat($OutPdf, 17, $false, 0, 0, 0, 0, 0, $true, $true, 1, $true, $true, $false)
    }
    $doc.Close($false)
    Write-Output ("PAGES={0}" -f $pages)
} finally {
    $word.Quit()
}
"""


def finalize_with_word(docx_in: Path, docx_out: Path, pdf_out: Path | None) -> bool:
    """تحديث الفهارس وتصدير PDF عبر Microsoft Word (COM). يُفضَّل PowerShell 32-بت مع Office 32-بت."""
    ps_candidates = [
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
    ]
    script = Path(tempfile.gettempdir()) / "basera_doc" / "finalize_word.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(FINALIZE_PS1, encoding="utf-8-sig")
    for ps in ps_candidates:
        if not ps.exists():
            continue
        cmd = [str(ps), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
               "-InDocx", str(docx_in.resolve()), "-OutDocx", str(docx_out.resolve()),
               "-OutPdf", str(pdf_out.resolve()) if pdf_out else ""]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if res.returncode == 0 and "PAGES=" in res.stdout:
            print(f"Word: {res.stdout.strip()} → {docx_out.name}" + (f", {pdf_out.name}" if pdf_out else ""))
            return True
        print(f"  [word:{ps.parent.parent.parent.name}] {res.stderr.strip()[:200]}", file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent.parent
    ap.add_argument("md", nargs="?", default=str(base / "دراسة مشروع التخرج.md"))
    ap.add_argument("out", nargs="?", default=str(base / "دراسة مشروع التخرج.docx"))
    ap.add_argument("--mmdc", default=None)
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "basera_doc" / "diagrams"))
    ap.add_argument("--finalize", action="store_true", help="تحديث الفهارس وتصدير PDF عبر Word (يتطلب Microsoft Word)")
    ap.add_argument("--pdf", default=None, help="مسار PDF الناتج مع --finalize (افتراضي: بجانب DOCX)")
    args = ap.parse_args()

    md_path = Path(args.md)
    if not md_path.exists():
        print("ملف Markdown غير موجود", file=sys.stderr)
        return 1
    mmdc = find_mmdc(args.mmdc)
    chrome = find_chrome(args.chrome)
    renderer = MermaidRenderer(mmdc, chrome, Path(args.cache))
    print(f"mmdc: {mmdc or 'غير متوفر — ستُعرض المخططات كنص'} | chrome: {chrome or 'افتراضي'}")
    out_path = Path(args.out)
    if not args.finalize:
        build(md_path, out_path, renderer)
        return 0

    raw = Path(tempfile.gettempdir()) / "basera_doc" / (out_path.stem + ".raw.docx")
    raw.parent.mkdir(parents=True, exist_ok=True)
    build(md_path, raw, renderer)
    pdf = Path(args.pdf) if args.pdf else out_path.with_suffix(".pdf")
    if not finalize_with_word(raw, out_path, pdf):
        print("تعذّر تشغيل Word؛ حُفظ الملف دون تحديث الفهارس (اضغط F9 داخل Word).", file=sys.stderr)
        shutil.copyfile(raw, out_path)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
