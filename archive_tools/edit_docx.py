#!/usr/bin/env python3
# [DEPRECATED] 仅用于 patent_01（已定版）。新专利请使用 tools/fill_template.py。
"""
Comprehensive script to edit the unpacked docx at /data/zhuanli/unpacked_filled/
Tasks:
  1. Fix font colors (blue -> black)
  2. Fill author info in header table
  3. Review OMML formulas (print nary elements)
  4. Fix indentation (first-line indent for body paragraphs)
  5. Insert 4 patent figures with relationships
  6. Repack into final .docx
"""

import os
import shutil
import zipfile
import xml.etree.ElementTree as ET

# ── Paths ──
UNPACKED = "/data/zhuanli/unpacked_filled"
DOC_XML = os.path.join(UNPACKED, "word/document.xml")
RELS_XML = os.path.join(UNPACKED, "word/_rels/document.xml.rels")
MEDIA_DIR = os.path.join(UNPACKED, "word/media")

OUTPUT_DIR = "/data/zhuanli/一种基于稀疏雅可比矩阵的反向蒙皮权重求解方法"
OUTPUT_DOCX = os.path.join(OUTPUT_DIR, "一种基于稀疏雅可比矩阵的反向蒙皮权重求解方法、系统及存储介质.docx")

# Source images
FIGURE_SRC = "/data/zhuanli/output/imagegen/patent_figures"
FIGURES = [
    ("fig_1_1_system_flow_0.png",          "image2.png", "rId17", "图1 系统整体流程图"),
    ("fig_1_2_sparse_vs_dense_0.png",      "image3.png", "rId18", "图2 稀疏与稠密雅可比矩阵对比示意图"),
    ("fig_1_3_vertex_bone_subspace_0.png",  "image4.png", "rId19", "图3 顶点-骨骼子空间构建示意图"),
    ("fig_1_4_objective_function_0.png",    "image5.png", "rId20", "图4 目标函数结构示意图"),
]

# ── Namespaces ──
NS = {
    "w":   "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r":   "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m":   "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp":  "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "wp14":"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Register all namespaces to avoid ns0/ns1 prefix pollution on output
_NSMAP = {
    "wpc":   "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "cx":    "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "cx1":   "http://schemas.microsoft.com/office/drawing/2015/9/8/chartex",
    "cx2":   "http://schemas.microsoft.com/office/drawing/2015/10/21/chartex",
    "cx3":   "http://schemas.microsoft.com/office/drawing/2016/5/9/chartex",
    "cx4":   "http://schemas.microsoft.com/office/drawing/2016/5/10/chartex",
    "cx5":   "http://schemas.microsoft.com/office/drawing/2016/5/11/chartex",
    "cx6":   "http://schemas.microsoft.com/office/drawing/2016/5/12/chartex",
    "cx7":   "http://schemas.microsoft.com/office/drawing/2016/5/13/chartex",
    "cx8":   "http://schemas.microsoft.com/office/drawing/2016/5/14/chartex",
    "mc":    "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "aink":  "http://schemas.microsoft.com/office/drawing/2016/ink",
    "am3d":  "http://schemas.microsoft.com/office/drawing/2017/model3d",
    "o":     "urn:schemas-microsoft-com:office:office",
    "oel":   "http://schemas.microsoft.com/office/2019/extlst",
    "r":     "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m":     "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v":     "urn:schemas-microsoft-com:vml",
    "wp14":  "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wp":    "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w10":   "urn:schemas-microsoft-com:office:word",
    "w":     "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14":   "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15":   "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16cex":"http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid":"http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16":   "http://schemas.microsoft.com/office/word/2018/wordml",
    "w16du": "http://schemas.microsoft.com/office/word/2023/wordml/word16du",
    "w16sdtdh":"http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash",
    "w16se": "http://schemas.microsoft.com/office/word/2015/wordml/symex",
    "a":     "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic":   "http://schemas.openxmlformats.org/drawingml/2006/picture",
}
for prefix, uri in _NSMAP.items():
    ET.register_namespace(prefix, uri)

# Also register the rels namespace
ET.register_namespace("", "http://schemas.openxmlformats.org/package/2006/relationships")
ET.register_namespace("", "http://schemas.openxmlformats.org/package/2006/content-types")


def tag(ns_prefix, local):
    """Build a Clark-notation tag."""
    return f"{{{NS[ns_prefix]}}}{local}"


def get_para_text(p):
    """Extract plain text from a paragraph element."""
    return "".join(t.text for t in p.findall(f".//{tag('w','t')}") if t.text)


# ════════════════════════════════════════════════════════════
# Parse document.xml
# ════════════════════════════════════════════════════════════
tree = ET.parse(DOC_XML)
root = tree.getroot()
body = root.find(tag("w", "body"))

# ════════════════════════════════════════════════════════════
# TASK 1: Fix font colors (0000FF → remove element)
# ════════════════════════════════════════════════════════════
print("=" * 60)
print("TASK 1: Fix blue font colors")
blue_count = 0
for rPr in root.findall(f".//{tag('w','rPr')}"):
    color = rPr.find(tag("w", "color"))
    if color is not None:
        val = color.get(tag("w", "val"))
        if val == "0000FF":
            rPr.remove(color)
            blue_count += 1
print(f"  Removed {blue_count} blue <w:color> elements (default is black)")

# ════════════════════════════════════════════════════════════
# TASK 2: Fill author info in header table
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 2: Fill author info in header table")

table = root.findall(f".//{tag('w','tbl')}")[0]
rows = table.findall(tag("w", "tr"))

# Row 1 (index 1): Cell 1 is the 撰写人 value cell (empty)
row1_cells = rows[1].findall(tag("w", "tc"))
author_cell = row1_cells[1]  # 2nd cell = 撰写人 value
# Find the paragraph in this cell, add a run with text
author_para = author_cell.find(tag("w", "p"))
# Copy rPr from label cell for consistent formatting
label_runs = row1_cells[0].findall(f".//{tag('w','r')}")
ref_rPr = None
if label_runs:
    ref_rPr = label_runs[0].find(tag("w", "rPr"))

new_run = ET.SubElement(author_para, tag("w", "r"))
if ref_rPr is not None:
    new_run.append(ref_rPr.__class__(ref_rPr.tag, ref_rPr.attrib))
    # Deep copy rPr
    new_rPr = ET.SubElement(new_run, tag("w", "rPr"))
    for child in ref_rPr:
        new_rPr.append(child.__class__(child.tag, child.attrib))
    # But remove the blue color if any
    for c in new_rPr.findall(tag("w", "color")):
        new_rPr.remove(c)
else:
    new_rPr = ET.SubElement(new_run, tag("w", "rPr"))

t_el = ET.SubElement(new_run, tag("w", "t"))
t_el.text = "汪金奕"
print("  Filled 撰写人: 汪金奕")

# Row 2 (index 2): Cell 3 is the 联络方式 value cell (empty)
row2_cells = rows[2].findall(tag("w", "tc"))
contact_cell = row2_cells[3]  # 4th cell = 联络方式 value
contact_para = contact_cell.find(tag("w", "p"))

new_run2 = ET.SubElement(contact_para, tag("w", "r"))
new_rPr2 = ET.SubElement(new_run2, tag("w", "rPr"))
t_el2 = ET.SubElement(new_run2, tag("w", "t"))
t_el2.text = "andyjywang@tencent.com"
print("  Filled 联络方式: andyjywang@tencent.com")

# ════════════════════════════════════════════════════════════
# TASK 3: Review OMML formulas
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 3: Review OMML formulas (nary elements)")

narys = root.findall(f".//{tag('m','nary')}")
print(f"  Found {len(narys)} <m:nary> elements:")
for i, nary in enumerate(narys):
    naryPr = nary.find(tag("m", "naryPr"))
    chr_val = ""
    if naryPr is not None:
        chr_el = naryPr.find(tag("m", "chr"))
        if chr_el is not None:
            chr_val = chr_el.get(tag("m", "val"), "∑")
        else:
            chr_val = "∑ (default)"
        # Check limLoc
        limLoc = naryPr.find(tag("m", "limLoc"))
        if limLoc is not None:
            chr_val += f" limLoc={limLoc.get(tag('m','val'))}"
        # Check supHide/subHide
        supHide = naryPr.find(tag("m", "supHide"))
        subHide = naryPr.find(tag("m", "subHide"))
        if supHide is not None:
            chr_val += f" supHide={supHide.get(tag('m','val'))}"
        if subHide is not None:
            chr_val += f" subHide={subHide.get(tag('m','val'))}"

    sub = nary.find(tag("m", "sub"))
    sup = nary.find(tag("m", "sup"))

    sub_text = "".join(e.text or "" for e in sub.iter() if e.text) if sub is not None else "<none>"
    sup_text = "".join(e.text or "" for e in sup.iter() if e.text) if sup is not None else "<none>"
    sub_children = len(list(sub)) if sub is not None else 0
    sup_children = len(list(sup)) if sup is not None else 0

    print(f"  [{i}] {chr_val}")
    print(f"      sub ({sub_children} children): \"{sub_text}\"")
    print(f"      sup ({sup_children} children): \"{sup_text}\"")

    # Check if sup is empty (has no meaningful content)
    if sup is not None and sup_children == 0 and not sup_text.strip():
        print(f"      → sup is EMPTY (subscript-only sum, this is correct for LaTeX \\sum_{{...}})")

# ════════════════════════════════════════════════════════════
# TASK 4: Fix indentation
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 4: Fix indentation (first-line indent for body paragraphs)")

# First-line indent of 2 Chinese chars = 2 * 210 twips per char at 10.5pt
# Standard: 420 twips (for 10.5pt / 五号), or 480 twips (for 12pt / 小四)
# We'll use 420 twips which is standard for 五号 Chinese font
FIRST_LINE_INDENT = "420"  # twips

body_paras = body.findall(tag("w", "p"))
# Table elements - collect paragraphs inside tables to skip them
table_paras = set()
for tbl in body.findall(f".//{tag('w','tbl')}"):
    for p in tbl.findall(f".//{tag('w','p')}"):
        table_paras.add(p)

indent_count = 0

# Section headings and special paragraphs to skip
HEADING_KEYWORDS = [
    "4、", "4.1", "4.2", "4.3", "3.2.", "5、", "1、", "2、", "3、",
    "步骤一", "步骤二", "步骤三", "步骤四", "步骤五", "步骤六", "步骤七", "步骤八",
    "步骤1", "步骤2", "步骤3", "步骤4", "步骤5", "步骤6", "步骤7", "步骤8",
    "效果一", "效果二", "效果三", "效果四", "效果五",
    "模块一", "模块二", "模块三", "模块四", "模块五",
    "方案一", "方案二", "方案三",
    "缺陷一", "缺陷二", "缺陷三", "缺陷四", "缺陷五",
    "连通域并行", "符号分解复用", "格式与早停优化",
    "[",  # references
]

for p in body_paras:
    # Skip table paragraphs
    if p in table_paras:
        continue

    text = get_para_text(p).strip()
    if not text:
        continue

    # Skip headings and section markers
    pPr = p.find(tag("w", "pPr"))
    if pPr is not None:
        pStyle = pPr.find(tag("w", "pStyle"))
        if pStyle is not None:
            style_val = pStyle.get(tag("w", "val"), "")
            if "Heading" in style_val or "TOC" in style_val:
                continue

    # Skip short labels, numbered headings, step/effect/module labels, references
    is_heading = False
    for kw in HEADING_KEYWORDS:
        if text.startswith(kw):
            is_heading = True
            break

    # Also skip the document title and very short lines (likely sub-headings)
    if "一种基于稀疏雅可比矩阵" in text and len(text) < 40:
        is_heading = True

    if is_heading:
        continue

    # Skip if the paragraph contains math formulas (oMath) - formula paragraphs shouldn't be indented
    if p.findall(f".//{tag('m','oMath')}"):
        continue

    # Apply first-line indent to body text paragraphs
    if pPr is None:
        pPr = ET.SubElement(p, tag("w", "pPr"))
        # Move pPr to be the first child
        p.remove(pPr)
        p.insert(0, pPr)

    ind = pPr.find(tag("w", "ind"))
    if ind is None:
        ind = ET.SubElement(pPr, tag("w", "ind"))

    current_fl = ind.get(tag("w", "firstLineChars"), "")
    current_fl2 = ind.get(tag("w", "firstLine"), "")
    # Only add if not already indented
    if not current_fl and not current_fl2:
        ind.set(tag("w", "firstLineChars"), "200")
        ind.set(tag("w", "firstLine"), FIRST_LINE_INDENT)
        indent_count += 1

print(f"  Applied first-line indent to {indent_count} body paragraphs")

# ════════════════════════════════════════════════════════════
# TASK 5: Insert 4 patent figures
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 5: Insert 4 patent figures")

# 5a. Copy images to media folder
os.makedirs(MEDIA_DIR, exist_ok=True)
for src_name, dst_name, _, _ in FIGURES:
    src = os.path.join(FIGURE_SRC, src_name)
    dst = os.path.join(MEDIA_DIR, dst_name)
    shutil.copy2(src, dst)
    print(f"  Copied {src_name} → {dst_name}")

# 5b. Add relationships in document.xml.rels
rels_tree = ET.parse(RELS_XML)
rels_root = rels_tree.getroot()
rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
img_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

for _, dst_name, rid, _ in FIGURES:
    rel_el = ET.SubElement(rels_root, f"{{{rel_ns}}}Relationship")
    rel_el.set("Id", rid)
    rel_el.set("Type", img_type)
    rel_el.set("Target", f"media/{dst_name}")
    print(f"  Added relationship {rid} → media/{dst_name}")

rels_tree.write(RELS_XML, xml_declaration=True, encoding="UTF-8")

# 5c. Build image paragraphs and insert at appropriate locations
# Image dimensions: width ~5 inches (4572000 EMU), height proportional
# 1 inch = 914400 EMU
IMG_WIDTH_EMU = 4572000   # ~5 inches
IMG_HEIGHT_EMU = 3429000  # ~3.75 inches (4:3 ratio)

def make_image_paragraph(rid, img_name, caption, idx):
    """Create a paragraph containing an inline image with caption below."""
    # Image paragraph
    p = ET.Element(tag("w", "p"))
    pPr = ET.SubElement(p, tag("w", "pPr"))
    jc = ET.SubElement(pPr, tag("w", "jc"))
    jc.set(tag("w", "val"), "center")

    r = ET.SubElement(p, tag("w", "r"))
    drawing = ET.SubElement(r, tag("w", "drawing"))

    inline = ET.SubElement(drawing, tag("wp", "inline"))
    inline.set("distT", "0")
    inline.set("distB", "0")
    inline.set("distL", "0")
    inline.set("distR", "0")

    extent = ET.SubElement(inline, tag("wp", "extent"))
    extent.set("cx", str(IMG_WIDTH_EMU))
    extent.set("cy", str(IMG_HEIGHT_EMU))

    effectExtent = ET.SubElement(inline, tag("wp", "effectExtent"))
    effectExtent.set("l", "0")
    effectExtent.set("t", "0")
    effectExtent.set("r", "0")
    effectExtent.set("b", "0")

    docPr = ET.SubElement(inline, tag("wp", "docPr"))
    docPr.set("id", str(idx + 10))
    docPr.set("name", f"Picture {idx}")

    cNvGraphicFramePr = ET.SubElement(inline, tag("wp", "cNvGraphicFramePr"))
    graphicFrameLocks = ET.SubElement(cNvGraphicFramePr, tag("a", "graphicFrameLocks"))
    graphicFrameLocks.set("noChangeAspect", "1")

    graphic = ET.SubElement(inline, tag("a", "graphic"))
    graphicData = ET.SubElement(graphic, tag("a", "graphicData"))
    graphicData.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/picture")

    pic_el = ET.SubElement(graphicData, tag("pic", "pic"))

    nvPicPr = ET.SubElement(pic_el, tag("pic", "nvPicPr"))
    cNvPr = ET.SubElement(nvPicPr, tag("pic", "cNvPr"))
    cNvPr.set("id", str(idx + 10))
    cNvPr.set("name", img_name)
    cNvPicPr = ET.SubElement(nvPicPr, tag("pic", "cNvPicPr"))

    blipFill = ET.SubElement(pic_el, tag("pic", "blipFill"))
    blip = ET.SubElement(blipFill, tag("a", "blip"))
    blip.set(tag("r", "embed"), rid)
    stretch = ET.SubElement(blipFill, tag("a", "stretch"))
    fillRect = ET.SubElement(stretch, tag("a", "fillRect"))

    spPr = ET.SubElement(pic_el, tag("pic", "spPr"))
    xfrm = ET.SubElement(spPr, tag("a", "xfrm"))
    off = ET.SubElement(xfrm, tag("a", "off"))
    off.set("x", "0")
    off.set("y", "0")
    ext = ET.SubElement(xfrm, tag("a", "ext"))
    ext.set("cx", str(IMG_WIDTH_EMU))
    ext.set("cy", str(IMG_HEIGHT_EMU))
    prstGeom = ET.SubElement(spPr, tag("a", "prstGeom"))
    prstGeom.set("prst", "rect")
    avLst = ET.SubElement(prstGeom, tag("a", "avLst"))

    # Caption paragraph
    cap_p = ET.Element(tag("w", "p"))
    cap_pPr = ET.SubElement(cap_p, tag("w", "pPr"))
    cap_jc = ET.SubElement(cap_pPr, tag("w", "jc"))
    cap_jc.set(tag("w", "val"), "center")

    cap_r = ET.SubElement(cap_p, tag("w", "r"))
    cap_rPr = ET.SubElement(cap_r, tag("w", "rPr"))
    cap_sz = ET.SubElement(cap_rPr, tag("w", "sz"))
    cap_sz.set(tag("w", "val"), "18")  # 9pt for caption
    cap_szCs = ET.SubElement(cap_rPr, tag("w", "szCs"))
    cap_szCs.set(tag("w", "val"), "18")

    cap_t = ET.SubElement(cap_r, tag("w", "t"))
    cap_t.text = caption

    return p, cap_p


# Find insertion points by paragraph index
# Re-enumerate body_paras as indices
body_paras = list(body)
# Build index: find paragraph indices by text
para_index = {}
for i, el in enumerate(body_paras):
    if el.tag == tag("w", "p"):
        text = get_para_text(el).strip()
        para_index[i] = text

# Insertion mapping: (search text, figure index)
# fig1 (system flow) → after "4.1产品侧" section heading (para 51), after the workflow description
# fig2 (sparse vs dense) → after "3.2.1 LBS" section (para 61), after the equations
# fig3 (vertex bone subspace) → after "3.2.3 约束条件" section
# fig4 (objective function) → after "3.2.2 目标函数定义" section

# We'll insert after specific paragraphs. Find them by text match.
insertions = []  # list of (after_element, (img_para, cap_para))

def find_para_after_text(search_text, offset=0):
    """Find the body child element whose text starts with search_text, then return index + offset."""
    for i, el in enumerate(body_paras):
        if el.tag == tag("w", "p"):
            text = get_para_text(el).strip()
            if text.startswith(search_text):
                return i + offset
    return None

# fig1: system flow → after the product-side workflow steps (after para starting with "步骤四：稀疏雅可比求解")
# That's around the end of product-side section
idx1 = find_para_after_text("步骤四：稀疏雅可比求解")
if idx1 is None:
    # Fallback: after 4.1产品侧
    idx1 = find_para_after_text("4.1产品侧", 1)
print(f"  fig1 insert after para index: {idx1}")

# fig2: sparse vs dense → after section 3.2.1 equations (after the last equation in that section)
# Find "3.2.2 目标函数定义" and insert before it
idx2 = find_para_after_text("3.2.2 目标函数定义")
if idx2 is not None:
    idx2 = idx2 - 1  # Insert before 3.2.2 heading = after the last para of 3.2.1
print(f"  fig2 insert after para index: {idx2}")

# fig3: vertex bone subspace → after "3.2.3 约束条件" content
idx3 = find_para_after_text("3.2.4 完整技术流程")
if idx3 is not None:
    idx3 = idx3 - 1  # Insert before 3.2.4 = after 3.2.3 content
print(f"  fig3 insert after para index: {idx3}")

# fig4: objective function → after the objective function description in 3.2.2
# Find the paragraph with the objective function terms explanation
idx4 = find_para_after_text("3.2.3 约束条件")
if idx4 is not None:
    idx4 = idx4 - 1  # Insert before 3.2.3 = after 3.2.2 content
print(f"  fig4 insert after para index: {idx4}")

# Create image paragraphs and sort insertions by index (descending to avoid index shift)
insert_list = []
for fig_idx, (src_name, dst_name, rid, caption) in enumerate(FIGURES):
    idx_map = {0: idx1, 1: idx2, 2: idx3, 3: idx4}
    insert_idx = idx_map[fig_idx]
    if insert_idx is not None:
        img_p, cap_p = make_image_paragraph(rid, dst_name, caption, fig_idx + 2)
        insert_list.append((insert_idx, img_p, cap_p, caption))
    else:
        print(f"  WARNING: Could not find insertion point for {caption}")

# Sort descending so we insert from bottom to top (avoids index shifting)
insert_list.sort(key=lambda x: x[0], reverse=True)

for insert_idx, img_p, cap_p, caption in insert_list:
    # Insert caption first (it will be after image once image is inserted before it)
    body.insert(insert_idx + 1, cap_p)
    body.insert(insert_idx + 1, img_p)
    print(f"  Inserted {caption} after body child index {insert_idx}")

# ════════════════════════════════════════════════════════════
# Write modified document.xml
# ════════════════════════════════════════════════════════════
tree.write(DOC_XML, xml_declaration=True, encoding="UTF-8")
print(f"\n  Wrote modified {DOC_XML}")

# ════════════════════════════════════════════════════════════
# TASK 6: Repack docx
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 6: Repack docx")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Remove old output if exists
if os.path.exists(OUTPUT_DOCX):
    os.remove(OUTPUT_DOCX)

# Create zip (docx) with proper structure
# [Content_Types].xml and _rels/.rels must be at root
with zipfile.ZipFile(OUTPUT_DOCX, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(UNPACKED):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            arcname = os.path.relpath(filepath, UNPACKED)
            zf.write(filepath, arcname)

file_size = os.path.getsize(OUTPUT_DOCX)
print(f"  Created: {OUTPUT_DOCX}")
print(f"  Size: {file_size:,} bytes")

print("\n" + "=" * 60)
print("ALL TASKS COMPLETED SUCCESSFULLY")
