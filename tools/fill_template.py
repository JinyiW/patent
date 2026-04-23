#!/usr/bin/env python3
"""
fill_template.py
将专利 disclosure.md 内容填充到 发明专利技术交底书模板.docx 模板中。
自动发现 patents/ 下的专利，支持按名称过滤。
图片与文本交叉排列，插入到对应章节位置。

用法:
  python tools/fill_template.py patent_06    # 填充指定专利
  python tools/fill_template.py              # 填充所有专利
"""

import os
import re
import copy
import glob
import shutil
import argparse
import zipfile
import traceback
from io import BytesIO
from lxml import etree

import latex2mathml.converter
from mathml2omml import convert as mathml2omml_convert

# ── Paths ──────────────────────────────────────────────────────────────────
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', '发明专利技术交底书模板.docx')
PATENTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'patents')

# ── Namespaces ──────────────────────────────────────────────────────────────
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

NSMAP_DOC = {
    'w': W, 'r': R, 'm': M,
    'wp': WP, 'a': A, 'pic': PIC,
    'w14': W14,
    'mc': "http://schemas.openxmlformats.org/markup-compatibility/2006",
}

IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

# ── Helpers ─────────────────────────────────────────────────────────────────

def qn(ns, local):
    """Qualified name."""
    return f"{{{ns}}}{local}"


def make_run(text, bold=False, font="微软雅黑", sz="18"):
    """Create a w:r element with text."""
    r_el = etree.SubElement(etree.Element("dummy"), qn(W, "r"))
    rpr = etree.SubElement(r_el, qn(W, "rPr"))
    fonts = etree.SubElement(rpr, qn(W, "rFonts"))
    fonts.set(qn(W, "ascii"), font)
    fonts.set(qn(W, "eastAsia"), font)
    fonts.set(qn(W, "hAnsi"), font)
    sz_el = etree.SubElement(rpr, qn(W, "sz"))
    sz_el.set(qn(W, "val"), sz)
    szcs = etree.SubElement(rpr, qn(W, "szCs"))
    szcs.set(qn(W, "val"), sz)
    if bold:
        etree.SubElement(rpr, qn(W, "b"))
        etree.SubElement(rpr, qn(W, "bCs"))
    t_el = etree.SubElement(r_el, qn(W, "t"))
    t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t_el.text = text
    return r_el


def make_ppr(indent=False, center=False, spacing=True):
    """Create w:pPr element."""
    ppr = etree.Element(qn(W, "pPr"))
    if spacing:
        sp = etree.SubElement(ppr, qn(W, "spacing"))
        sp.set(qn(W, "line"), "276")
        sp.set(qn(W, "lineRule"), "auto")
    rpr = etree.SubElement(ppr, qn(W, "rPr"))
    fonts = etree.SubElement(rpr, qn(W, "rFonts"))
    fonts.set(qn(W, "ascii"), "微软雅黑")
    fonts.set(qn(W, "eastAsia"), "微软雅黑")
    fonts.set(qn(W, "hAnsi"), "微软雅黑")
    sz_el = etree.SubElement(rpr, qn(W, "sz"))
    sz_el.set(qn(W, "val"), "18")
    szcs = etree.SubElement(rpr, qn(W, "szCs"))
    szcs.set(qn(W, "val"), "18")
    if indent:
        ind = etree.SubElement(ppr, qn(W, "ind"))
        ind.set(qn(W, "firstLineChars"), "200")
        ind.set(qn(W, "firstLine"), "420")
    if center:
        jc = etree.SubElement(ppr, qn(W, "jc"))
        jc.set(qn(W, "val"), "center")
    return ppr


def make_paragraph(runs=None, indent=False, center=False, spacing=True):
    """Create a w:p element."""
    p = etree.Element(qn(W, "p"))
    ppr = make_ppr(indent=indent, center=center, spacing=spacing)
    p.append(ppr)
    if runs:
        for r in runs:
            p.append(r)
    return p


def make_image_paragraph(rid, img_name, doc_pr_id, cx_emu=None, cy_emu=None):
    """Create a centered image paragraph with drawing.
    cx_emu/cy_emu: image dimensions in EMU (English Metric Units, 914400 EMU = 1 inch).
    If not provided, defaults to 5in x 2.73in (matching 1408x768 source aspect ratio).
    """
    if cx_emu is None or cy_emu is None:
        # Default: 5 inches wide, maintain 1408:768 aspect ratio
        cx_emu = 4572000  # 5 inches
        cy_emu = 2494171  # 5 * 768/1408 inches = 2.727 inches

    cx_str = str(int(cx_emu))
    cy_str = str(int(cy_emu))

    p = etree.Element(qn(W, "p"))
    ppr = etree.SubElement(p, qn(W, "pPr"))
    jc = etree.SubElement(ppr, qn(W, "jc"))
    jc.set(qn(W, "val"), "center")

    r_el = etree.SubElement(p, qn(W, "r"))
    drawing = etree.SubElement(r_el, qn(W, "drawing"))
    inline = etree.SubElement(drawing, qn(WP, "inline"))
    inline.set("distT", "0")
    inline.set("distB", "0")
    inline.set("distL", "0")
    inline.set("distR", "0")

    extent = etree.SubElement(inline, qn(WP, "extent"))
    extent.set("cx", cx_str)
    extent.set("cy", cy_str)

    effect = etree.SubElement(inline, qn(WP, "effectExtent"))
    effect.set("l", "0"); effect.set("t", "0")
    effect.set("r", "0"); effect.set("b", "0")

    docPr = etree.SubElement(inline, qn(WP, "docPr"))
    docPr.set("id", str(doc_pr_id))
    docPr.set("name", f"Picture {doc_pr_id}")

    cNvGF = etree.SubElement(inline, qn(WP, "cNvGraphicFramePr"))
    gfLocks = etree.SubElement(cNvGF, qn(A, "graphicFrameLocks"))
    gfLocks.set("noChangeAspect", "1")

    graphic = etree.SubElement(inline, qn(A, "graphic"))
    graphicData = etree.SubElement(graphic, qn(A, "graphicData"))
    graphicData.set("uri", PIC)

    pic_el = etree.SubElement(graphicData, qn(PIC, "pic"))

    nvPicPr = etree.SubElement(pic_el, qn(PIC, "nvPicPr"))
    cNvPr = etree.SubElement(nvPicPr, qn(PIC, "cNvPr"))
    cNvPr.set("id", str(doc_pr_id))
    cNvPr.set("name", img_name)
    etree.SubElement(nvPicPr, qn(PIC, "cNvPicPr"))

    blipFill = etree.SubElement(pic_el, qn(PIC, "blipFill"))
    blip = etree.SubElement(blipFill, qn(A, "blip"))
    blip.set(qn(R, "embed"), rid)
    stretch = etree.SubElement(blipFill, qn(A, "stretch"))
    etree.SubElement(stretch, qn(A, "fillRect"))

    spPr = etree.SubElement(pic_el, qn(PIC, "spPr"))
    xfrm = etree.SubElement(spPr, qn(A, "xfrm"))
    off = etree.SubElement(xfrm, qn(A, "off"))
    off.set("x", "0"); off.set("y", "0")
    ext = etree.SubElement(xfrm, qn(A, "ext"))
    ext.set("cx", cx_str); ext.set("cy", cy_str)
    prstGeom = etree.SubElement(spPr, qn(A, "prstGeom"))
    prstGeom.set("prst", "rect")
    etree.SubElement(prstGeom, qn(A, "avLst"))

    return p


def make_image_caption(caption_text):
    """Create centered caption paragraph."""
    p = etree.Element(qn(W, "p"))
    ppr = etree.SubElement(p, qn(W, "pPr"))
    jc = etree.SubElement(ppr, qn(W, "jc"))
    jc.set(qn(W, "val"), "center")
    r_el = etree.SubElement(p, qn(W, "r"))
    rpr = etree.SubElement(r_el, qn(W, "rPr"))
    sz_el = etree.SubElement(rpr, qn(W, "sz"))
    sz_el.set(qn(W, "val"), "18")
    szcs = etree.SubElement(rpr, qn(W, "szCs"))
    szcs.set(qn(W, "val"), "18")
    t_el = etree.SubElement(r_el, qn(W, "t"))
    t_el.text = caption_text
    return p


# ── LaTeX -> OMML conversion ───────────────────────────────────────────────

def latex_to_omml(latex_str, display=False):
    """Convert LaTeX to OMML XML element(s).
    Returns an oMath element (inline) or oMathPara element (display).
    """
    # Clean up LaTeX
    latex_str = latex_str.strip()
    if not latex_str:
        return None

    # Convert via MathML
    mode = "block" if display else "inline"
    try:
        mathml_str = latex2mathml.converter.convert(latex_str)
    except Exception as e:
        print(f"  [WARN] latex2mathml failed for: {latex_str[:60]}... -> {e}")
        return None

    try:
        omml_str = mathml2omml_convert(mathml_str)
    except Exception as e:
        print(f"  [WARN] mathml2omml failed for: {latex_str[:60]}... -> {e}")
        return None

    # Fix known mathml2omml bug: groupChrPr closed with </m:groupChr> instead of </m:groupChrPr>
    # Pattern: <m:groupChrPr>...</m:groupChr><m:e> should be </m:groupChrPr><m:e>
    omml_str = omml_str.replace('</m:groupChr><m:e>', '</m:groupChrPr><m:e>')

    try:
        # mathml2omml outputs with m: prefix but no namespace declaration
        # Wrap with namespace declaration before parsing
        wrapped = f'<m:oMathWrap xmlns:m="{M}">{omml_str}</m:oMathWrap>'
        wrapper_el = etree.fromstring(wrapped.encode('utf-8'))
        # Get the actual oMath element inside
        omml_el = wrapper_el[0]  # first child
    except Exception as e:
        print(f"  [WARN] OMML parse failed: {e}")
        return None

    # Fix nary elements
    fix_nary_elements(omml_el)

    # Fix groupChr -> acc: mathml2omml uses groupChr for \bar{}, \hat{} etc.
    # which causes content to render at subscript-like small size in Word.
    # Word natively uses m:acc (accent) for these -- convert.
    _fix_groupchr_to_acc(omml_el)

    if display:
        # Wrap in oMathPara if not already
        tag = etree.QName(omml_el.tag).localname
        if tag == 'oMathPara':
            return omml_el
        elif tag == 'oMath':
            para = etree.Element(qn(M, "oMathPara"))
            para.append(omml_el)
            return para
        else:
            # Might be wrapped differently
            omath = omml_el.find(f".//{qn(M, 'oMath')}")
            if omath is not None:
                para = etree.Element(qn(M, "oMathPara"))
                para.append(omath)
                return para
            return omml_el
    else:
        # Return oMath element for inline
        tag = etree.QName(omml_el.tag).localname
        if tag == 'oMath':
            return omml_el
        elif tag == 'oMathPara':
            omath = omml_el.find(f"{qn(M, 'oMath')}")
            return omath
        else:
            omath = omml_el.find(f".//{qn(M, 'oMath')}")
            return omath if omath is not None else omml_el


def fix_nary_elements(root):
    """Fix nary elements in OMML:
    - If subscript contains \u2208: add supHide
    - If no subscript: add supHide
    - Simple subscript like just 'k': change to k=1 sub, K sup
    """
    for nary in root.iter(qn(M, "nary")):
        nary_pr = nary.find(qn(M, "naryPr"))
        sub_el = nary.find(qn(M, "sub"))
        sup_el = nary.find(qn(M, "sup"))

        if nary_pr is None:
            nary_pr = etree.SubElement(nary, qn(M, "naryPr"))
            nary.insert(0, nary_pr)

        # Get sub text
        sub_text = ""
        if sub_el is not None:
            sub_text = "".join(sub_el.itertext()).strip()

        # Get sup text
        sup_text = ""
        if sup_el is not None:
            sup_text = "".join(sup_el.itertext()).strip()

        has_set_symbol = "\u2208" in sub_text or "\\in" in sub_text

        if has_set_symbol:
            # Set-based sum: hide superscript
            sup_hide = nary_pr.find(qn(M, "supHide"))
            if sup_hide is None:
                sup_hide = etree.SubElement(nary_pr, qn(M, "supHide"))
            sup_hide.set(qn(M, "val"), "1")

        elif not sub_text and not sup_text:
            # No sub/sup at all: hide sup
            sup_hide = nary_pr.find(qn(M, "supHide"))
            if sup_hide is None:
                sup_hide = etree.SubElement(nary_pr, qn(M, "supHide"))
            sup_hide.set(qn(M, "val"), "1")


def _fix_groupchr_to_acc(root):
    """Convert m:groupChr (top-positioned bar/overline) to m:acc (accent).

    mathml2omml uses <m:groupChr> for \\bar{}, \\hat{} etc., which wraps content
    in a box and renders at reduced (subscript-like) size in Word.
    Word natively uses <m:acc> for these accents, keeping content at normal size.
    """
    # Collect all groupChr elements first (avoid modifying tree during iteration)
    BAR_CHARS = frozenset(('\u00AF', '\u0304', '\u0305'))  # macron / combining macron / combining overline
    HAT_CHARS = frozenset(('\u0302', '\u005E', '\u0311'))   # combining circumflex / caret
    TILDE_CHARS = frozenset(('\u0303', '\u007E'))           # combining tilde / tilde
    ALL_TOP_ACCENTS = BAR_CHARS | HAT_CHARS | TILDE_CHARS

    replacements = []
    for gc in root.iter(qn(M, "groupChr")):
        pr = gc.find(qn(M, "groupChrPr"))
        e = gc.find(qn(M, "e"))
        if pr is None or e is None:
            continue
        chr_el = pr.find(qn(M, "chr"))
        pos_el = pr.find(qn(M, "pos"))
        if chr_el is None:
            continue
        char_val = chr_el.get(qn(M, "val"), "")
        pos_val = pos_el.get(qn(M, "val"), "") if pos_el is not None else ""
        if pos_val == "top" and char_val in ALL_TOP_ACCENTS:
            # Map to the combining character Word expects
            if char_val in BAR_CHARS:
                target_char = '\u0305'
            elif char_val in HAT_CHARS:
                target_char = '\u0302'
            else:
                target_char = '\u0303'
            replacements.append((gc, e, target_char))

    for gc, e, target_char in replacements:
        acc = etree.Element(qn(M, "acc"))
        accPr = etree.SubElement(acc, qn(M, "accPr"))
        new_chr = etree.SubElement(accPr, qn(M, "chr"))
        new_chr.set(qn(M, "val"), target_char)

        new_e = etree.SubElement(acc, qn(M, "e"))
        # Unwrap <m:box><m:e>...</m:e></m:box> if present
        box = e.find(qn(M, "box"))
        if box is not None:
            box_e = box.find(qn(M, "e"))
            src = box_e if box_e is not None else box
        else:
            src = e
        for child in list(src):
            new_e.append(child)

        parent = gc.getparent()
        if parent is not None:
            idx = list(parent).index(gc)
            parent.remove(gc)
            parent.insert(idx, acc)


# ── MD Parsing ─────────────────────────────────────────────────────────────

def parse_md_sections(md_path):
    """Parse a patent disclosure MD into sections."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = {}

    # Extract title
    m = re.search(r'## 交底书名称\s*\n+(.*?)(?=\n---|\n##)', content, re.DOTALL)
    if m:
        sections['title'] = m.group(1).strip()

    # 关键术语
    m = re.search(r'## 缩略语和关键术语定义\s*\n+(.*?)(?=\n---|\n## )', content, re.DOTALL)
    if m:
        sections['keywords'] = m.group(1).strip()

    # 发明构思 (技术关键点)
    m = re.search(r'## 1、\*本发明的技术关键点.*?\n+(.*?)(?=\n---|\n## )', content, re.DOTALL)
    if m:
        sections['invention_concept'] = m.group(1).strip()

    # 2.1 现有技术的技术方案
    m = re.search(r'### 2\.1\s+现有技术的技术方案\s*\n+(.*?)(?=\n### 2\.2)', content, re.DOTALL)
    if m:
        sections['prior_art_21'] = m.group(1).strip()

    # 2.2 现有技术缺点
    m = re.search(r'### 2\.2\s+现有技术缺点.*?\n+(.*?)(?=\n---|\n## )', content, re.DOTALL)
    if m:
        sections['prior_art_22'] = m.group(1).strip()

    # 3.1 产品侧
    m = re.search(r'### 3\.1\s+产品侧\s*\n+(.*?)(?=\n### 3\.2)', content, re.DOTALL)
    if m:
        sections['product_side'] = m.group(1).strip()

    # 3.2 技术侧 (everything under 3.2 including subheadings)
    m = re.search(r'### 3\.2\s+技术侧\s*\n+(.*?)(?=\n---|\n## 4)', content, re.DOTALL)
    if m:
        sections['tech_side'] = m.group(1).strip()

    # 4 有益效果
    m = re.search(r'## 4、\*技术方案所产生的有益效果\s*\n+(.*?)(?=\n---|\n## 5)', content, re.DOTALL)
    if m:
        sections['benefits'] = m.group(1).strip()

    # 5 发散思维
    m = re.search(r'## 5、发散思维.*?\n+(.*?)(?=\n---|\n## 附件)', content, re.DOTALL)
    if m:
        sections['alternatives'] = m.group(1).strip()

    # 参考文献
    m = re.search(r'## 附件参考文献.*?\n+(.*?)$', content, re.DOTALL)
    if m:
        sections['references'] = m.group(1).strip()

    return sections


# ── Text -> paragraphs conversion ──────────────────────────────────────────

# Patterns for bold labels
BOLD_LABEL_PATTERNS = [
    r'^(\*\*(?:模块|步骤|方案|缺陷|效果|关键点|指标|替代方案|抑制规则)\S*?[：:]\s*)',
    r'^(\*\*(?:模块|步骤|方案|缺陷|效果|关键点|指标|替代方案|抑制规则)\S*?\*\*\s*)',
]

# Patterns that should NOT get first-line indent
NO_INDENT_PATTERNS = [
    r'^#{2,}',           # headings
    r'^\*\*',            # bold sub-headings
    r'^- ',              # bullet items
    r'^\u00b7 ',              # bullet items
    r'^>\s',             # blockquote
    r'^\d+\.\s',         # numbered list items (standalone)
    r'^\$\$',            # block formula
]


def should_indent(line):
    """Check if a line should get first-line indent."""
    stripped = line.strip()
    if not stripped:
        return False
    for pat in NO_INDENT_PATTERNS:
        if re.match(pat, stripped):
            return False
    return True


def split_inline_latex(text):
    """Split text into segments of (text, is_latex) tuples.
    Handles \\(...\\) for inline LaTeX.
    """
    segments = []
    # Pattern for \(...\)
    pattern = r'\\\((.*?)\\\)'
    last_end = 0
    for m in re.finditer(pattern, text):
        if m.start() > last_end:
            segments.append((text[last_end:m.start()], False))
        segments.append((m.group(1), True))
        last_end = m.end()
    if last_end < len(text):
        segments.append((text[last_end:], False))
    return segments


def is_block_formula(line):
    """Check if line is a block formula delimiter."""
    return line.strip().startswith('$$')


def extract_block_formula(lines, start_idx):
    """Extract a block formula starting from start_idx.
    Returns (formula_text, end_idx).
    """
    formula_lines = []
    i = start_idx
    # Skip opening $$
    first_line = lines[i].strip()
    if first_line == '$$':
        i += 1
    else:
        # $$ with content on same line
        rest = first_line[2:]
        if rest.endswith('$$'):
            return rest[:-2].strip(), i
        formula_lines.append(rest)
        i += 1

    while i < len(lines):
        line = lines[i].strip()
        if line.endswith('$$'):
            remaining = line[:-2].strip()
            if remaining:
                formula_lines.append(remaining)
            break
        formula_lines.append(line)
        i += 1

    return '\n'.join(formula_lines).strip(), i


def text_to_paragraphs(text, section_type="body"):
    """Convert markdown text to list of w:p elements.
    section_type: "keywords", "body", "references"
    """
    paragraphs = []
    lines = text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Skip horizontal rules
        if re.match(r'^---+$', stripped):
            i += 1
            continue

        # Skip markdown image syntax ![...](...)
        # Images are inserted separately by _insert_images_into_document
        if re.match(r'^!\[.*?\]\(.*?\)$', stripped):
            i += 1
            continue

        # Block formula
        if stripped.startswith('$$'):
            formula_text, end_i = extract_block_formula(lines, i)
            if formula_text:
                omml = latex_to_omml(formula_text, display=True)
                if omml is not None:
                    p = etree.Element(qn(W, "p"))
                    ppr = make_ppr(indent=False, spacing=True)
                    p.append(ppr)
                    p.append(omml)
                    paragraphs.append(p)
                else:
                    # Fallback: plain text
                    paragraphs.append(make_paragraph(
                        [make_run(formula_text)], indent=False))
            i = end_i + 1
            continue

        # Blockquote (> ...)
        if stripped.startswith('> '):
            content = stripped[2:].strip()
            if content.startswith('**') and '**' in content[2:]:
                # Bold note
                paragraphs.append(make_paragraph(
                    [make_run(content.replace('**', ''), bold=True)],
                    indent=False))
            else:
                paragraphs.append(make_paragraph(
                    [make_run(content)], indent=True))
            i += 1
            continue

        # Sub-section headings: #### 3.2.x -> 4.2.x
        heading_match = re.match(r'^(#{3,4})\s+(\d+\.\d+\.\d+)\s+(.*)', stripped)
        if heading_match:
            level = heading_match.group(1)
            num = heading_match.group(2)
            title = heading_match.group(3)
            # Renumber 3.2.x -> 4.2.x
            new_num = renumber_section(num)
            heading_text = f"{new_num} {title}"
            paragraphs.append(make_paragraph(
                [make_run(heading_text, bold=False)], indent=False))
            i += 1
            continue

        # Keyword entry: - **term**: definition
        kw_match = re.match(r'^[-\u00b7]\s+\*\*(.+?)\*\*[\uff1a:]\s*(.*)', stripped)
        if kw_match:
            term = kw_match.group(1)
            definition = kw_match.group(2)
            runs = [make_run(f"{term}\uff1a", bold=True)]
            runs.extend(build_runs_with_inline_math(definition, bold=False))
            paragraphs.append(make_paragraph(runs, indent=True))
            i += 1
            continue

        # Bullet item: - text or . text (non-keyword)
        bullet_match = re.match(r'^[-\u00b7]\s+(.*)', stripped)
        if bullet_match and not kw_match:
            content = bullet_match.group(1)
            runs = build_runs_with_inline_math(content, bold=False)
            paragraphs.append(make_paragraph(runs, indent=False))
            i += 1
            continue

        # Numbered items: 1. text, 2. text, etc.
        numbered_match = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if numbered_match:
            num_text = numbered_match.group(1)
            content = numbered_match.group(2)
            runs = build_runs_with_inline_math(f"{num_text}. {content}", bold=False)
            paragraphs.append(make_paragraph(runs, indent=False))
            i += 1
            continue

        # Bold-labeled paragraph: **XXX** rest
        bold_label_match = re.match(r'^\*\*(.+?)\*\*\s*(.*)', stripped)
        if bold_label_match:
            label = bold_label_match.group(1)
            rest = bold_label_match.group(2)
            # If label contains \(...\), split into bold text + inline math
            if r'\(' in label and r'\)' in label:
                runs = build_runs_with_inline_math(label, bold=True)
            else:
                runs = [make_run(label, bold=True)]
            if rest:
                rest_runs = build_runs_with_inline_math(f" {rest}", bold=False)
                runs.extend(rest_runs)
            # These labels don't get indent
            paragraphs.append(make_paragraph(runs, indent=False))
            i += 1
            continue

        # Regular paragraph with possible inline LaTeX
        use_indent = should_indent(stripped)
        runs = build_runs_with_inline_math(stripped, bold=False)
        paragraphs.append(make_paragraph(runs, indent=use_indent))
        i += 1

    return paragraphs


def build_runs_with_inline_math(text, bold=False):
    """Build list of runs from text that may contain inline \\(...\\) and **bold**.
    
    Strategy: split by **bold** first (which may contain \\(...\\)),
    then handle inline LaTeX within each segment.
    """
    runs = []

    # First split by **bold** markers -- these may contain \(...\) inside
    # Use re.DOTALL so . matches across potential inline content
    bold_segments = re.split(r'(\*\*(?:(?!\*\*).)*?\*\*)', text, flags=re.DOTALL)

    for seg in bold_segments:
        if not seg:
            continue
        if seg.startswith('**') and seg.endswith('**') and len(seg) > 4:
            inner = seg[2:-2]
            # Process inline LaTeX within bold text
            latex_parts = split_inline_latex(inner)
            for part_text, is_latex in latex_parts:
                if is_latex:
                    omml = latex_to_omml(part_text, display=False)
                    if omml is not None:
                        runs.append(omml)
                    else:
                        runs.append(make_run(part_text, bold=True))
                elif part_text:
                    runs.append(make_run(part_text, bold=True))
        else:
            # Normal text -- process inline LaTeX
            latex_parts = split_inline_latex(seg)
            for part_text, is_latex in latex_parts:
                if is_latex:
                    omml = latex_to_omml(part_text, display=False)
                    if omml is not None:
                        runs.append(omml)
                    else:
                        runs.append(make_run(part_text, bold=bold))
                elif part_text:
                    runs.append(make_run(part_text, bold=bold))

    return runs


def renumber_section(num_str):
    """Renumber 3.2.x -> 4.2.x, leave others unchanged."""
    parts = num_str.split('.')
    if len(parts) >= 2 and parts[0] == '3' and parts[1] == '2':
        parts[0] = '4'
        return '.'.join(parts)
    return num_str


# ── Template manipulation ─────────────────────────────────────────────────

def find_section_heading(body, text_prefix):
    """Find paragraph index whose text starts with text_prefix."""
    children = list(body)
    for i, child in enumerate(children):
        tag = etree.QName(child.tag).localname
        if tag == 'p':
            texts = []
            for r in child.findall(f".//{qn(W, 'r')}"):
                for t in r.findall(qn(W, 't')):
                    if t.text:
                        texts.append(t.text)
            full_text = ''.join(texts).strip()
            if full_text.startswith(text_prefix):
                return i
    return -1


def remove_empty_paragraphs_after(body, start_idx, max_count=4):
    """Remove up to max_count empty paragraphs after start_idx.
    Returns count of removed paragraphs.
    """
    children = list(body)
    removed = 0
    for j in range(max_count):
        check_idx = start_idx + 1
        if check_idx >= len(list(body)):
            break
        child = list(body)[check_idx]
        tag = etree.QName(child.tag).localname
        if tag == 'p':
            texts = []
            for r in child.findall(f".//{qn(W, 'r')}"):
                for t in r.findall(qn(W, 't')):
                    if t.text:
                        texts.append(t.text)
            if not ''.join(texts).strip():
                body.remove(child)
                removed += 1
            else:
                break
        else:
            break
    return removed


def insert_paragraphs_after(body, idx, new_paragraphs):
    """Insert new paragraphs after the element at idx."""
    children = list(body)
    ref = children[idx]
    parent = body
    for i, p in enumerate(new_paragraphs):
        ref.addnext(p)
        ref = p


def fill_table_cell(body, row_idx, cell_idx, value):
    """Fill a table cell with text value."""
    tbl = None
    for child in body:
        if etree.QName(child.tag).localname == 'tbl':
            tbl = child
            break

    if tbl is None:
        print("  [WARN] No table found in template!")
        return

    rows = tbl.findall(f".//{qn(W, 'tr')}")
    if row_idx >= len(rows):
        print(f"  [WARN] Row {row_idx} not found")
        return

    cells = rows[row_idx].findall(f".//{qn(W, 'tc')}")
    if cell_idx >= len(cells):
        print(f"  [WARN] Cell {cell_idx} in row {row_idx} not found")
        return

    cell = cells[cell_idx]
    # Find existing paragraph in cell
    p = cell.find(qn(W, 'p'))
    if p is not None:
        # Clear existing runs
        for r in p.findall(qn(W, 'r')):
            p.remove(r)
        # Add new run
        r_el = make_run(value)
        p.append(r_el)
    else:
        new_p = make_paragraph([make_run(value)])
        cell.append(new_p)


# ── Image caption generation ──────────────────────────────────────────────


def _load_captions_file(patent_dir):
    """Load captions from figures/captions.txt if it exists.

    Format (one per line):
        fig_1_system_architecture_0.png  图1 系统架构示意图

    Returns dict: {filename_stem: caption_text} or empty dict.
    """
    captions_path = os.path.join(patent_dir, 'figures', 'captions.txt')
    if not os.path.isfile(captions_path):
        return {}
    result = {}
    with open(captions_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                stem = os.path.splitext(parts[0])[0]  # strip .png
                result[stem] = parts[1]
    return result


def _generate_caption(fig_basename, fig_index, captions_dict=None):
    """Generate a Chinese caption for a figure.

    Priority:
      1. captions_dict (from figures/captions.txt)
      2. Generic fallback: 图N 技术示意图
    """
    stem = os.path.splitext(fig_basename)[0]

    # 1. From captions file
    if captions_dict and stem in captions_dict:
        return captions_dict[stem]

    # 2. Fallback — always Chinese
    return f"图{fig_index} 技术示意图"


# ── Image placement ───────────────────────────────────────────────────────

def _insert_images_into_document(body, image_rids, figure_files, captions_dict=None):
    """Insert image paragraphs interleaved with text at relevant section positions.

    Strategy: distribute ALL figures evenly across the entire content of
    sections 4.1 and 4.2 combined, so images are spread out rather than
    clustered together.

    Args:
        body: lxml body element
        image_rids: list of (rid, img_name, doc_pr_id, fig_file_basename)
        figure_files: list of full paths to figure files (for dimension reading)
        captions_dict: dict from _load_captions_file (optional)
    """
    if not image_rids:
        return

    # Build caption for each figure
    captions = []
    for fig_idx, (rid, img_name, doc_pr_id, fig_basename) in enumerate(image_rids):
        caption = _generate_caption(fig_basename, fig_idx + 1, captions_dict)
        captions.append(caption)

    def _get_para_text(p_el):
        """Get the full text of a paragraph."""
        return ''.join(t.text for t in p_el.findall(f".//{qn(W, 't')}") if t.text).strip()

    def _find_section_start(keyword):
        """Find the index of the paragraph matching keyword."""
        children = list(body)
        for i, child in enumerate(children):
            if etree.QName(child.tag).localname != 'p':
                continue
            if _get_para_text(child).startswith(keyword):
                return i
        return -1

    def _find_major_section_end(start_keyword):
        """Find the end of a major section (4.1 or 4.2).
        Ends at the next major section heading (4.2, 4.3, 5、 etc)."""
        start_idx = _find_section_start(start_keyword)
        if start_idx < 0:
            return -1
        children = list(body)
        for j in range(start_idx + 1, len(children)):
            child = children[j]
            if etree.QName(child.tag).localname != 'p':
                continue
            text = _get_para_text(child)
            if not text:
                continue
            # Stop at next major heading: 4.2, 4.3, 5、 etc.
            if (re.match(r'^4\.[23][^\d]', text) or
                re.match(r'^[5-9]、', text)):
                return j - 1
        return len(children) - 1

    # Determine the full range of paragraphs for image distribution:
    # from 4.1产品侧 start to the end of 4.2技术侧
    product_idx = _find_section_start('4.1产品侧')
    tech_end = _find_major_section_end('4.2技术侧')

    if product_idx < 0:
        product_idx = _find_section_start('4.2技术侧')
    if tech_end < 0:
        tech_end = len(list(body)) - 1

    range_start = product_idx if product_idx >= 0 else 0
    range_end = tech_end
    range_len = range_end - range_start

    # Collect insert operations
    insert_ops = []
    n_figs = len(image_rids)

    for fig_i, (rid, img_name, doc_pr_id, fig_basename) in enumerate(image_rids):
        caption = captions[fig_i]
        fig_path = figure_files[fig_i] if fig_i < len(figure_files) else None

        if range_len > 0 and n_figs > 0:
            # Distribute figures evenly: figure k goes at position (k+1)/(n+1) of the range
            fraction = (fig_i + 1) / (n_figs + 1)
            target_idx = range_start + max(1, int(range_len * fraction))
            target_idx = min(target_idx, range_end)
        else:
            target_idx = len(list(body)) - 1

        anchor = list(body)[target_idx]
        insert_ops.append((anchor, rid, img_name, doc_pr_id, caption, fig_path))

    # Insert in reverse order so earlier insertions don't shift later anchors.
    # For same-anchor figures, reverse order ensures correct final ordering.
    children_snapshot = list(body)

    def _child_index(el):
        try:
            return children_snapshot.index(el)
        except ValueError:
            return -1

    def _fig_num(op):
        m_cap = re.search(r'图(\d+)', op[4])
        return int(m_cap.group(1)) if m_cap else 0

    insert_ops.sort(key=lambda x: (_child_index(x[0]), _fig_num(x)), reverse=True)

    for anchor, rid, img_name, doc_pr_id, caption, fig_path in insert_ops:
        # Read original image dimensions to preserve aspect ratio
        cx_emu, cy_emu = None, None
        if fig_path and os.path.exists(fig_path):
            try:
                from PIL import Image as PILImage
                with PILImage.open(fig_path) as img:
                    iw, ih = img.size
                target_w = 4572000
                cx_emu = target_w
                cy_emu = int(target_w * ih / iw)
            except Exception:
                pass
        img_p = make_image_paragraph(rid, img_name, doc_pr_id, cx_emu, cy_emu)
        cap_p = make_image_caption(caption)
        anchor.addnext(cap_p)
        anchor.addnext(img_p)
        print(f"    Inserted {os.path.basename(fig_path) if fig_path else img_name} -> {caption}")


# ── Post-processing ──────────────────────────────────────────────────────

def postprocess_docx(output_path):
    """Post-process a generated docx: renumber figure captions by document order."""
    print(f"  Post-processing: {os.path.basename(output_path)}")

    files = {}
    with zipfile.ZipFile(output_path) as z:
        for name in z.namelist():
            files[name] = z.read(name)

    tree = etree.fromstring(files['word/document.xml'])
    paras = tree.findall(f".//{qn(W, 'p')}")
    modified = False

    # Renumber figure captions by document order
    fig_num = 0
    for i, p in enumerate(paras):
        if i > 0 and paras[i - 1].findall(f".//{qn(W, 'drawing')}"):
            for t in p.iter(qn(W, 't')):
                if t.text and re.match(r'^图\d+', t.text.strip()):
                    fig_num += 1
                    new_text = re.sub(r'^图\d+', f'图{fig_num}', t.text)
                    if new_text != t.text:
                        t.text = new_text
                        modified = True
                    break

    if modified:
        files['word/document.xml'] = etree.tostring(
            tree, xml_declaration=True, encoding='UTF-8', standalone=True)
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name, data in files.items():
                zout.writestr(name, data)
        with open(output_path, 'wb') as f:
            f.write(buf.getvalue())
        print(f"    Renumbered {fig_num} figures")
    else:
        print(f"    No renumbering needed ({fig_num} figures)")


# ── Template loading ──────────────────────────────────────────────────────

def load_template():
    """Read template docx and return dict of {zip_entry_name: bytes}."""
    template_path = os.path.abspath(TEMPLATE_PATH)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    template_buf = BytesIO()
    with open(template_path, 'rb') as f:
        template_buf.write(f.read())
    template_buf.seek(0)
    with zipfile.ZipFile(template_buf, 'r') as zin:
        template_files = {}
        for name in zin.namelist():
            template_files[name] = zin.read(name)
    return template_files


# ── Main fill logic ───────────────────────────────────────────────────────

def fill_patent(patent_dir):
    """Fill template with a single patent's content.

    Returns the output docx path, or None on failure.
    """
    patent_name = os.path.basename(patent_dir)

    # Find the disclosure md
    md_files = glob.glob(os.path.join(patent_dir, 'patent_*_disclosure.md'))
    if not md_files:
        print(f"  No disclosure.md found in {patent_dir}")
        return None
    md_path = md_files[0]
    md_basename = os.path.basename(md_path)

    # Find figures
    figures_dir = os.path.join(patent_dir, 'figures')
    figure_files = sorted(glob.glob(os.path.join(figures_dir, '*.png'))) if os.path.isdir(figures_dir) else []

    # Parse sections
    print(f"  Parsing {md_basename}...")
    sections = parse_md_sections(md_path)
    title = sections.get('title', patent_name)
    print(f"  Title: {title[:60]}...")

    # Extract tech_area from title or fallback
    tech_area = "技术方案"
    if title:
        # Try to infer tech area from common title patterns
        # e.g. "基于XX的YY方法" -> use full title as tech area hint
        tech_area = title if len(title) <= 30 else title[:30]

    # Load template
    print("  Loading template...")
    template_files = load_template()

    # Parse document.xml
    doc_xml = template_files['word/document.xml']
    for prefix, uri in [
        ('w', W), ('r', R), ('m', M), ('wp', WP), ('a', A),
        ('pic', PIC), ('w14', W14),
        ('mc', "http://schemas.openxmlformats.org/markup-compatibility/2006"),
        ('wps', "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"),
        ('wpc', "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"),
        ('wpg', "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"),
    ]:
        etree.register_namespace(prefix, uri)

    tree = etree.fromstring(doc_xml)
    body = tree.find(f".//{qn(W, 'body')}")

    # 0. Strip all blue (0000FF) colors from template -> black (000000)
    for color_el in tree.iter(qn(W, "color")):
        val = color_el.get(qn(W, "val"), "")
        if val.lower() == "0000ff":
            color_el.set(qn(W, "val"), "000000")

    # 1. Fill table metadata
    print("  Filling table metadata...")
    fill_table_cell(body, 0, 1, title)                          # 交底书名称
    fill_table_cell(body, 1, 3, tech_area)                      # 产品技术名称

    # 2. Fill sections
    section_map = [
        ("1、【关键术语】", 'keywords', "keywords"),
        ("2、【发明构思】", 'invention_concept', "body"),
        ("3.1相关背景描述", 'prior_art_21', "body"),
        ("3.2现有技术的缺点", 'prior_art_22', "body"),
        ("4.1产品侧", 'product_side', "body"),
        ("4.2技术侧", 'tech_side', "body"),
        ("4.3专利方案所产生的有益效果", 'benefits', "body"),
        ("5、参考文献", 'references', "references"),
    ]

    for heading_prefix, section_key, sec_type in section_map:
        print(f"  Filling section: {heading_prefix[:30]}...")
        content = sections.get(section_key, "")
        if not content:
            print(f"    [SKIP] No content for {section_key}")
            continue

        # For benefits, append alternatives if present
        if section_key == 'benefits' and sections.get('alternatives'):
            content += "\n\n" + sections['alternatives']

        idx = find_section_heading(body, heading_prefix)
        if idx < 0:
            print(f"    [WARN] Heading not found: {heading_prefix}")
            continue

        # Remove empty placeholder paragraphs after heading
        removed = remove_empty_paragraphs_after(body, idx)
        print(f"    Removed {removed} empty placeholders")

        # Generate content paragraphs
        new_paras = text_to_paragraphs(content, sec_type)
        print(f"    Generated {len(new_paras)} paragraphs")

        # Insert after heading
        insert_paragraphs_after(body, idx, new_paras)

    # 3. Insert images
    print("  Inserting images...")
    image_rids = []
    img_counter = 2  # image1.png is the template logo
    rid_counter = 17  # Start from rId17
    doc_pr_id = 12

    # Parse existing rels
    rels_xml = template_files['word/_rels/document.xml.rels']
    rels_tree = etree.fromstring(rels_xml)

    # Parse Content_Types
    ct_xml = template_files['[Content_Types].xml']
    ct_tree = etree.fromstring(ct_xml)

    # Check if png extension is already registered
    has_png_ext = False
    for el in ct_tree:
        if el.get("Extension", "").lower() == "png":
            has_png_ext = True
            break
    if not has_png_ext:
        ext_el = etree.SubElement(ct_tree, "Default")
        ext_el.set("Extension", "png")
        ext_el.set("ContentType", "image/png")

    figure_full_paths = []
    for fig_path in figure_files:
        img_name = f"image{img_counter}.png"
        rid = f"rId{rid_counter}"
        fig_basename = os.path.basename(fig_path)

        # Add relationship
        rel_el = etree.SubElement(rels_tree, "Relationship")
        rel_el.set("Id", rid)
        rel_el.set("Type", IMAGE_REL_TYPE)
        rel_el.set("Target", f"media/{img_name}")

        # Copy image data
        if os.path.exists(fig_path):
            with open(fig_path, 'rb') as f:
                template_files[f"word/media/{img_name}"] = f.read()
        else:
            print(f"    [WARN] Figure not found: {fig_path}")

        image_rids.append((rid, img_name, doc_pr_id, fig_basename))
        figure_full_paths.append(fig_path)
        img_counter += 1
        rid_counter += 1
        doc_pr_id += 1

    # Insert image paragraphs into document
    captions_dict = _load_captions_file(patent_dir)
    if image_rids:
        _insert_images_into_document(body, image_rids, figure_full_paths, captions_dict)

    # 4. Serialize
    print("  Serializing document...")
    doc_bytes = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    template_files['word/document.xml'] = doc_bytes

    # Serialize rels
    rels_bytes = etree.tostring(rels_tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    template_files['word/_rels/document.xml.rels'] = rels_bytes

    # Serialize Content_Types
    ct_bytes = etree.tostring(ct_tree, xml_declaration=True, encoding='UTF-8', standalone=True)
    template_files['[Content_Types].xml'] = ct_bytes

    # 5. Write output
    # Derive patent_XX pattern from md filename
    pat_match = re.search(r'(patent_\d+)', md_basename)
    if pat_match:
        patent_prefix = pat_match.group(1)
    else:
        patent_prefix = patent_name
    output_path = os.path.join(patent_dir, f'{patent_prefix}_disclosure.docx')
    print(f"  Writing: {output_path}")

    out_buf = BytesIO()
    with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in template_files.items():
            zout.writestr(name, data)

    with open(output_path, 'wb') as f:
        f.write(out_buf.getvalue())

    file_size = os.path.getsize(output_path)
    print(f"  Done! File size: {file_size / 1024:.1f} KB")

    # Post-process: renumber figure captions
    try:
        postprocess_docx(output_path)
    except Exception as e:
        print(f"    [WARN] Post-processing failed: {e}")

    return output_path


# ── Discovery and CLI ─────────────────────────────────────────────────────

def discover_patents(filter_name=None):
    """Discover patent directories under PATENTS_DIR.
    
    Returns list of absolute paths to patent directories.
    """
    pattern = os.path.join(os.path.abspath(PATENTS_DIR), 'patent_*')
    dirs = sorted(d for d in glob.glob(pattern) if os.path.isdir(d))

    if filter_name:
        dirs = [d for d in dirs if filter_name in os.path.basename(d)]

    return dirs


def main():
    parser = argparse.ArgumentParser(
        description='将专利 disclosure.md 填充到发明专利技术交底书模板')
    parser.add_argument('filter', nargs='?', default=None,
                        help='按名称过滤专利目录 (e.g. patent_06)')
    args = parser.parse_args()

    patent_dirs = discover_patents(args.filter)
    if not patent_dirs:
        print(f"No patent directories found in {os.path.abspath(PATENTS_DIR)}")
        if args.filter:
            print(f"  (filter: {args.filter})")
        return

    print("=" * 70)
    print(f"  Fill Template Tool - {len(patent_dirs)} patent(s)")
    print("=" * 70)
    for d in patent_dirs:
        print(f"  - {os.path.basename(d)}")

    results = []
    for patent_dir in patent_dirs:
        print(f"\n{'=' * 60}")
        print(f"  Processing: {os.path.basename(patent_dir)}")
        print(f"{'=' * 60}")
        try:
            path = fill_patent(patent_dir)
            results.append((os.path.basename(patent_dir), path))
        except Exception as e:
            print(f"\n  [ERROR] {os.path.basename(patent_dir)} failed: {e}")
            traceback.print_exc()
            results.append((os.path.basename(patent_dir), None))

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for name, path in results:
        if path:
            size = os.path.getsize(path) / 1024
            print(f"  OK  {name} -> {os.path.basename(path)} ({size:.1f} KB)")
        else:
            print(f"  FAIL  {name}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
