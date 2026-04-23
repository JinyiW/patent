#!/usr/bin/env python3
# [DEPRECATED] 仅用于 patent_01~05（已定版）。新专利请使用 tools/fill_template.py。
"""
batch_fill_patents.py
Fill patents 02-05 into the 专利技术交底书模板 template.

Reads each patent markdown, parses sections, converts LaTeX to OMML,
inserts images, and writes filled docx files.
"""

import os
import re
import copy
import shutil
import zipfile
import traceback
from io import BytesIO
from lxml import etree

import latex2mathml.converter
from mathml2omml import convert as mathml2omml_convert

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

TEMPLATE_PATH = "/data/zhuanli/发明专利技术交底书模板.docx"
FIGURE_DIR = "/data/zhuanli/output/imagegen/patent_figures/"
OUTPUT_DIR = "/data/zhuanli/专利技术交底书/"

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


# ── LaTeX → OMML conversion ───────────────────────────────────────────────

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

    # Fix groupChr → acc: mathml2omml uses groupChr for \bar{}, \hat{} etc.
    # which causes content to render at subscript-like small size in Word.
    # Word natively uses m:acc (accent) for these — convert.
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
    - If subscript contains ∈: add supHide
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

        has_set_symbol = "∈" in sub_text or "\\in" in sub_text

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


# ── Text → paragraphs conversion ──────────────────────────────────────────

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
    r'^· ',              # bullet items
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

        # Sub-section headings: #### 3.2.x → 4.2.x
        heading_match = re.match(r'^(#{3,4})\s+(\d+\.\d+\.\d+)\s+(.*)', stripped)
        if heading_match:
            level = heading_match.group(1)
            num = heading_match.group(2)
            title = heading_match.group(3)
            # Renumber 3.2.x → 4.2.x
            new_num = renumber_section(num)
            heading_text = f"{new_num} {title}"
            paragraphs.append(make_paragraph(
                [make_run(heading_text, bold=False)], indent=False))
            i += 1
            continue

        # Keyword entry: - **term**: definition
        kw_match = re.match(r'^[-·]\s+\*\*(.+?)\*\*[：:]\s*(.*)', stripped)
        if kw_match:
            term = kw_match.group(1)
            definition = kw_match.group(2)
            runs = [make_run(f"{term}：", bold=True)]
            runs.extend(build_runs_with_inline_math(definition, bold=False))
            paragraphs.append(make_paragraph(runs, indent=True))
            i += 1
            continue

        # Bullet item: - text or · text (non-keyword)
        bullet_match = re.match(r'^[-·]\s+(.*)', stripped)
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

        # Bold-labeled paragraph: **方案一：XXX** rest or **效果一：XXX**rest
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

    # First split by **bold** markers — these may contain \(...\) inside
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
            # Normal text — process inline LaTeX
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
    """Renumber 3.2.x → 4.2.x, leave others unchanged."""
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


# ── Main processing ───────────────────────────────────────────────────────

def process_patent(patent_num, md_path, figure_paths, tech_area, output_title):
    """Process a single patent: parse MD, fill template, write docx."""
    print(f"\n{'='*60}")
    print(f"Processing Patent {patent_num:02d}: {output_title[:50]}...")
    print(f"{'='*60}")

    # Parse MD
    print("  Parsing markdown...")
    sections = parse_md_sections(md_path)
    title = sections.get('title', output_title)
    print(f"  Title: {title[:60]}...")

    # Read template
    print("  Reading template...")
    template_buf = BytesIO()
    with open(TEMPLATE_PATH, 'rb') as f:
        template_buf.write(f.read())
    template_buf.seek(0)

    # Extract template contents
    with zipfile.ZipFile(template_buf, 'r') as zin:
        template_files = {}
        for name in zin.namelist():
            template_files[name] = zin.read(name)

    # Parse document.xml
    doc_xml = template_files['word/document.xml']
    # Register namespaces to preserve them during serialization
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

    # 0. Strip all blue (0000FF) colors from template → black (000000)
    for color_el in tree.iter(qn(W, "color")):
        val = color_el.get(qn(W, "val"), "")
        if val.lower() == "0000ff":
            color_el.set(qn(W, "val"), "000000")

    # 1. Fill table metadata
    print("  Filling table metadata...")
    fill_table_cell(body, 0, 1, title)       # 交底书名称
    fill_table_cell(body, 1, 1, "汪金奕")    # 撰写人
    fill_table_cell(body, 1, 3, tech_area)   # 产品技术名称
    fill_table_cell(body, 2, 3, "andyjywang@tencent.com")  # 联络方式

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

    for fig_idx, fig_path in enumerate(figure_paths):
        img_name = f"image{img_counter}.png"
        rid = f"rId{rid_counter}"

        # Add relationship
        rel_el = etree.SubElement(rels_tree, "Relationship")
        rel_el.set("Id", rid)
        rel_el.set("Type", IMAGE_REL_TYPE)
        rel_el.set("Target", f"media/{img_name}")

        # Copy image data
        full_fig_path = os.path.join(FIGURE_DIR, fig_path)
        if os.path.exists(full_fig_path):
            with open(full_fig_path, 'rb') as f:
                template_files[f"word/media/{img_name}"] = f.read()
        else:
            print(f"    [WARN] Figure not found: {full_fig_path}")

        image_rids.append((rid, img_name, doc_pr_id, fig_path))
        img_counter += 1
        rid_counter += 1
        doc_pr_id += 1

    # Insert image paragraphs into document
    # Strategy: distribute images near their relevant sections
    if image_rids:
        _insert_images_into_document(body, image_rids, patent_num)


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
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{title}.docx")
    print(f"  Writing: {output_path}")

    out_buf = BytesIO()
    with zipfile.ZipFile(out_buf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in template_files.items():
            zout.writestr(name, data)

    with open(output_path, 'wb') as f:
        f.write(out_buf.getvalue())

    file_size = os.path.getsize(output_path)
    print(f"  Done! File size: {file_size / 1024:.1f} KB")
    return output_path


def _insert_images_into_document(body, image_rids, patent_num):
    """Insert image paragraphs interleaved with text at relevant sections.

    Each image is placed after its most relevant section heading,
    rather than clustering all images together.
    """
    # Per-patent configuration: (figure_file, caption, target_section_keyword)
    # target_section_keyword is used to find the section after which to insert
    fig_placement = {
        2: [
            ('fig_2_1', '图1 无GT质量评估与闭环平台系统架构图', '4.1产品侧'),
            ('fig_2_2', '图2 可插拔指标计算架构示意图', '4.2.2'),
            ('fig_2_3', '图3 数据闭环迭代流程图', '4.2.6'),
            ('fig_2_4', '图4 质量闸门三级部署架构图', '4.1产品侧'),
        ],
        3: [
            ('fig_3_1', '图1 分离轴投影原理示意图', '4.1产品侧'),
            ('fig_3_2', '图2 边链与面簇检测对象构建示意图', '4.2.1'),
            ('fig_3_3', '图3 SAT共线与形变异常检测流程总览图', '4.2.3'),
            ('fig_3_4', '图4 跨帧持续性判定时序示意图', '4.2.6'),
            ('fig_3_5', '图5 SAT多轴投影共线检测原理示意图', '4.2.3'),
        ],
        4: [
            ('fig_4_1', '图1 双阶段穿插粘连检测框架流程图', '4.1产品侧'),
            ('fig_4_2', '图2 穿插检测几何特征示意图', '4.2.4'),
            ('fig_4_3', '图3 粘连检测几何与运动特征示意图', '4.2.5'),
            ('fig_4_4', '图4 有效接触与粘连区分的三重抑制规则', '4.2.6'),
            ('fig_4_5', '图5 穿插与粘连特征对比示意图', '4.2.6'),
        ],
        5: [
            ('fig_5_1', '图1 长尾布料确定性后处理闭环流程图', '4.1产品侧'),
            ('fig_5_2', '图2 异常区域拓扑扩展与锚定边界示意图', '4.2.1'),
            ('fig_5_3', '图3 布料表面平滑处理前后对比示意图', '4.2.2'),
            ('fig_5_4', '图4 降级重试与回滚决策树', '4.2.6'),
            ('fig_5_5', '图5 确定性后处理重试与回退决策流程图', '4.2.6'),
        ],
    }

    placements = fig_placement.get(patent_num, [])

    def _find_section_end(keyword):
        """Find the last paragraph of the section matching keyword.
        Returns the body child element just before the next section heading.
        """
        children = list(body)
        section_idx = -1
        for i, child in enumerate(children):
            if etree.QName(child.tag).localname != 'p':
                continue
            texts = ''.join(t.text for t in child.findall(f".//{qn(W, 't')}") if t.text).strip()
            if texts.startswith(keyword):
                section_idx = i
                break
        if section_idx < 0:
            return None

        # Find next section heading after current section
        # Headings are identified by: short text starting with number pattern (4.x.x or 4.x)
        # or starting with 5、 (references section)
        next_heading_idx = len(children)
        for j in range(section_idx + 1, len(children)):
            child = children[j]
            if etree.QName(child.tag).localname != 'p':
                continue
            texts = ''.join(t.text for t in child.findall(f".//{qn(W, 't')}") if t.text).strip()
            if not texts or len(texts) > 80:
                continue
            # Match section heading patterns: 4.2.X, 4.X, 5、
            if (re.match(r'^\d+\.\d+\.\d+\s', texts) or
                re.match(r'^\d+\.\d+[^\d]', texts) or
                re.match(r'^\d+、', texts)):
                next_heading_idx = j
                break

        # Return the element just before the next heading
        target_idx = next_heading_idx - 1
        if target_idx <= section_idx:
            target_idx = section_idx
        return children[target_idx]

    # Track which image_rids we've used (match by fig prefix)
    rid_map = {}
    for rid, img_name, doc_pr_id, fig_path in image_rids:
        # Extract prefix like 'fig_2_1' from 'fig_2_1_system_arch_0.png'
        parts = fig_path.split('_')
        if len(parts) >= 3:
            prefix = '_'.join(parts[:3])
        else:
            prefix = fig_path
        rid_map[prefix] = (rid, img_name, doc_pr_id, fig_path)

    # Insert images in reverse order to avoid index shifts
    insert_ops = []
    for fig_prefix, caption, section_kw in placements:
        if fig_prefix not in rid_map:
            continue
        rid, img_name, doc_pr_id, fig_path = rid_map[fig_prefix]
        anchor = _find_section_end(section_kw)
        if anchor is not None:
            insert_ops.append((anchor, rid, img_name, doc_pr_id, fig_path, caption, section_kw))

    # Insert in reverse document order so earlier insertions don't shift later anchors.
    # For figures sharing the same anchor, insert in REVERSE figure order
    # (since addnext places each one right after the anchor, the last inserted
    # ends up first — so reverse order gives correct final sequence).
    children = list(body)
    def _child_index(el):
        try:
            return children.index(el)
        except ValueError:
            return -1

    # Sort by: primary = anchor position (descending), secondary = figure number (descending)
    # Extract figure number from caption like "图3 ..."
    def _fig_num(op):
        import re
        m = re.search(r'图(\d+)', op[5])  # op[5] = caption
        return int(m.group(1)) if m else 0

    insert_ops.sort(key=lambda x: (_child_index(x[0]), _fig_num(x)), reverse=True)

    for anchor, rid, img_name, doc_pr_id, fig_path, caption, section_kw in insert_ops:
        # Read original image dimensions to preserve aspect ratio
        full_fig_path = os.path.join(FIGURE_DIR, fig_path)
        cx_emu, cy_emu = None, None
        if os.path.exists(full_fig_path):
            try:
                from PIL import Image as PILImage
                with PILImage.open(full_fig_path) as img:
                    iw, ih = img.size
                # Target width: 5 inches = 4572000 EMU
                target_w = 4572000
                cx_emu = target_w
                cy_emu = int(target_w * ih / iw)
            except Exception:
                pass
        img_p = make_image_paragraph(rid, img_name, doc_pr_id, cx_emu, cy_emu)
        cap_p = make_image_caption(caption)
        anchor.addnext(cap_p)
        anchor.addnext(img_p)
        print(f"    Inserted {fig_path} after {section_kw}")


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
        print(f"    ✓ Renumbered {fig_num} figures")
    else:
        print(f"    - No renumbering needed ({fig_num} figures)")


# ── Verification ──────────────────────────────────────────────────────────

def verify_output(output_path):
    """Verify a filled docx file."""
    print(f"\n  Verifying: {os.path.basename(output_path)}")
    stats = {
        'file_size': 0,
        'image_count': 0,
        'nary_count': 0,
        'blue_color_count': 0,
        'paragraph_count': 0,
    }

    if not os.path.exists(output_path):
        print(f"    [ERROR] File does not exist!")
        return stats

    stats['file_size'] = os.path.getsize(output_path)

    with zipfile.ZipFile(output_path, 'r') as z:
        # Count images
        media_files = [f for f in z.namelist() if f.startswith('word/media/')]
        stats['image_count'] = len(media_files)

        # Parse document.xml
        doc_xml = z.read('word/document.xml')
        tree = etree.fromstring(doc_xml)

        # Count nary elements
        nary_els = tree.findall(f".//{qn(M, 'nary')}")
        stats['nary_count'] = len(nary_els)

        # Count blue color occurrences
        doc_str = doc_xml.decode('utf-8', errors='replace')
        stats['blue_color_count'] = doc_str.lower().count('0000ff')

        # Count paragraphs
        paras = tree.findall(f".//{qn(W, 'p')}")
        stats['paragraph_count'] = len(paras)

    print(f"    File size: {stats['file_size'] / 1024:.1f} KB")
    print(f"    Images: {stats['image_count']} (including template logo)")
    print(f"    Paragraphs: {stats['paragraph_count']}")
    print(f"    oMath nary elements: {stats['nary_count']}")
    print(f"    Blue color (0000FF) occurrences: {stats['blue_color_count']}")

    return stats


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  Batch Patent Disclosure Filler (Patents 02-05)")
    print("=" * 70)

    patents = [
        {
            'num': 2,
            'md_path': '/data/zhuanli/output/patent_02_no_gt_quality_closedloop_20260228/patent_02_disclosure.md',
            'figures': ['fig_2_1_system_arch_0.png', 'fig_2_2_pluggable_arch_0.png', 'fig_2_3_data_loop_0.png', 'fig_2_4_quality_gate_arch_0.png'],
            'tech_area': '三维角色动画蒙皮质量评估',
        },
        {
            'num': 3,
            'md_path': '/data/zhuanli/output/patent_03_sat_collinearity_metric_20260228/patent_03_disclosure.md',
            'figures': ['fig_3_1_sat_projection_0.png', 'fig_3_2_detection_objects_0.png',
                        'fig_3_3_detection_pipeline_0.png', 'fig_3_4_temporal_persistence_0.png',
                        'fig_3_5_sat_collinear_principle_0.png'],
            'tech_area': '三维角色动画蒙皮异常检测',
        },
        {
            'num': 4,
            'md_path': '/data/zhuanli/output/patent_04_insertion_sticking_metric_20260228/patent_04_disclosure.md',
            'figures': ['fig_4_1_dual_phase_framework_0.png', 'fig_4_2_penetration_0.png',
                        'fig_4_3_sticking_0.png', 'fig_4_4_valid_contact_0.png',
                        'fig_4_5_pen_vs_stick_comparison_0.png'],
            'tech_area': '三维角色动画蒙皮穿插粘连检测',
        },
        {
            'num': 5,
            'md_path': '/data/zhuanli/output/patent_05_longtail_cloth_postprocess_20260228/patent_05_disclosure.md',
            'figures': ['fig_5_1_closed_loop_pipeline_0.png', 'fig_5_2_anomaly_region_0.png',
                        'fig_5_3_smoothing_comparison_0.png', 'fig_5_4_rollback_decision_tree_0.png',
                        'fig_5_5_retry_rollback_flow_0.png'],
            'tech_area': '三维角色动画布料蒙皮后处理',
        },
    ]

    output_paths = []

    for patent in patents:
        try:
            path = process_patent(
                patent_num=patent['num'],
                md_path=patent['md_path'],
                figure_paths=patent['figures'],
                tech_area=patent['tech_area'],
                output_title="",  # Will be extracted from MD
            )
            output_paths.append(path)
        except Exception as e:
            print(f"\n  [ERROR] Patent {patent['num']:02d} failed: {e}")
            traceback.print_exc()
            output_paths.append(None)

    # Post-processing: renumber figure captions
    print("\n" + "=" * 70)
    print("  POST-PROCESSING")
    print("=" * 70)

    # Include patent 01 (generated separately) for bracket cleanup
    for path in output_paths:
        if path and os.path.exists(path):
            try:
                postprocess_docx(path)
            except Exception as e:
                print(f"    [WARN] Post-processing failed for {os.path.basename(path)}: {e}")

    # Verification
    print("\n" + "=" * 70)
    print("  VERIFICATION SUMMARY")
    print("=" * 70)

    for path in output_paths:
        if path:
            verify_output(path)

    print("\n" + "=" * 70)
    print("  ALL DONE")
    print("=" * 70)


if __name__ == '__main__':
    main()
