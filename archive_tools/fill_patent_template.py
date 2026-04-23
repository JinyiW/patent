#!/usr/bin/env python3
"""Fill patent disclosure template with patent 01 content."""

import re
import copy
import lxml.etree as ET
import latex2mathml.converter
import mathml2omml

# ── Namespaces ──────────────────────────────────────────────────────────
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W14_NS = 'http://schemas.microsoft.com/office/word/2010/wordml'
OMML_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

NSMAP = {
    'w': W_NS,
    'w14': W14_NS,
    'm': OMML_NS,
    'r': R_NS,
}

def qn(ns_prefix, local):
    """Qualified name helper."""
    ns_map = {
        'w': W_NS,
        'w14': W14_NS,
        'm': OMML_NS,
        'r': R_NS,
    }
    return f'{{{ns_map[ns_prefix]}}}{local}'


# ── LaTeX → OMML ───────────────────────────────────────────────────────
def latex_to_omml_element(latex_str):
    """Convert a LaTeX string to an OMML lxml Element."""
    try:
        # Pre-process: simplify unsupported constructs
        processed = latex_str
        # Remove \underbrace{...}{text} → just the content
        # Pattern: \underbrace{content}_{label}
        processed = re.sub(r'\\underbrace\{([^}]*)\}_\{[^}]*\}', r'\1', processed)
        processed = re.sub(r'\\underbrace\{([^}]*)\}', r'\1', processed)
        # Remove \text{...} → just the text (wrap in \mathrm)
        processed = re.sub(r'\\text\{([^}]*)\}', r'\\mathrm{\1}', processed)
        # Remove \tag{...}
        processed = re.sub(r'\\tag\{[^}]*\}', '', processed)
        # Remove \; \, \quad etc spacing commands that might cause issues
        processed = processed.replace('\\;', ' ')

        mathml = latex2mathml.converter.convert(processed)
        omml_str = mathml2omml.convert(mathml)
        # Ensure namespace declarations
        omml_str = omml_str.replace(
            '<m:oMath>',
            f'<m:oMath xmlns:m="{OMML_NS}" xmlns:w="{W_NS}">',
            1,
        )
        return ET.fromstring(omml_str.encode())
    except Exception as e:
        print(f"  [WARN] LaTeX→OMML failed for: {latex_str[:60]}... → {e}")
        return None


# ── XML paragraph builders ─────────────────────────────────────────────
def make_rpr(color='0000FF', bold=False):
    """Build a <w:rPr> element with 微软雅黑 9pt."""
    rpr = ET.SubElement(ET.Element('dummy'), qn('w', 'rPr'))
    fonts = ET.SubElement(rpr, qn('w', 'rFonts'))
    fonts.set(qn('w', 'ascii'), '微软雅黑')
    fonts.set(qn('w', 'eastAsia'), '微软雅黑')
    fonts.set(qn('w', 'hAnsi'), '微软雅黑')
    if bold:
        ET.SubElement(rpr, qn('w', 'b'))
        ET.SubElement(rpr, qn('w', 'bCs'))
    c = ET.SubElement(rpr, qn('w', 'color'))
    c.set(qn('w', 'val'), color)
    sz = ET.SubElement(rpr, qn('w', 'sz'))
    sz.set(qn('w', 'val'), '18')
    szcs = ET.SubElement(rpr, qn('w', 'szCs'))
    szcs.set(qn('w', 'val'), '18')
    return rpr


def make_ppr(color='0000FF'):
    """Build a <w:pPr> element matching template style."""
    ppr = ET.Element(qn('w', 'pPr'))
    sp = ET.SubElement(ppr, qn('w', 'spacing'))
    sp.set(qn('w', 'line'), '276')
    sp.set(qn('w', 'lineRule'), 'auto')
    rpr = ET.SubElement(ppr, qn('w', 'rPr'))
    fonts = ET.SubElement(rpr, qn('w', 'rFonts'))
    fonts.set(qn('w', 'ascii'), '微软雅黑')
    fonts.set(qn('w', 'eastAsia'), '微软雅黑')
    fonts.set(qn('w', 'hAnsi'), '微软雅黑')
    c = ET.SubElement(rpr, qn('w', 'color'))
    c.set(qn('w', 'val'), color)
    sz_ = ET.SubElement(rpr, qn('w', 'sz'))
    sz_.set(qn('w', 'val'), '18')
    szcs_ = ET.SubElement(rpr, qn('w', 'szCs'))
    szcs_.set(qn('w', 'val'), '18')
    return ppr


def make_text_run(text, color='0000FF', bold=False):
    """Create a <w:r> element with text."""
    r = ET.Element(qn('w', 'r'))
    rpr = make_rpr(color, bold)
    r.append(rpr)
    t = ET.SubElement(r, qn('w', 't'))
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    return r


def make_paragraph(runs=None, color='0000FF'):
    """Create a <w:p> element with optional runs."""
    p = ET.Element(qn('w', 'p'))
    p.append(make_ppr(color))
    if runs:
        for r in runs:
            p.append(r)
    return p


def make_empty_paragraph():
    """Create an empty <w:p> matching template style."""
    return make_paragraph([], '0000FF')


# ── Markdown parsing ───────────────────────────────────────────────────
def parse_md(md_text):
    """Extract sections from the patent markdown."""
    sections = {}

    # 交底书名称
    m = re.search(r'## 交底书名称\s*\n\s*(.+)', md_text)
    if m:
        sections['name'] = m.group(1).strip()

    # 关键术语
    m = re.search(r'## 缩略语和关键术语定义\s*\n(.*?)(?=\n---|\n## )', md_text, re.S)
    if m:
        sections['keywords'] = m.group(1).strip()

    # 发明构思 (section 1)
    m = re.search(r'## 1、\*本发明的技术关键点（欲保护点）\s*\n(.*?)(?=\n---|\n## )', md_text, re.S)
    if m:
        sections['concept'] = m.group(1).strip()

    # 3.1 现有技术的技术方案
    m = re.search(r'### 2\.1 现有技术的技术方案\s*\n(.*?)(?=\n### )', md_text, re.S)
    if m:
        sections['bg_tech'] = m.group(1).strip()

    # Include the intro paragraph before 2.1 as well
    m_intro = re.search(r'## 2、\*与本发明最相近的现有技术\s*\n(.*?)(?=\n### )', md_text, re.S)
    if m_intro and sections.get('bg_tech'):
        intro = m_intro.group(1).strip()
        if intro:
            sections['bg_tech'] = intro + '\n\n' + sections['bg_tech']

    # 3.2 现有技术缺点
    m = re.search(r'### 2\.2 现有技术缺点及本发明解决的问题\s*\n(.*?)(?=\n---|\n## )', md_text, re.S)
    if m:
        sections['bg_defect'] = m.group(1).strip()

    # 4.1 产品侧
    m = re.search(r'### 3\.1 产品侧\s*\n(.*?)(?=\n### )', md_text, re.S)
    if m:
        sections['product'] = m.group(1).strip()

    # 4.2 技术侧
    m = re.search(r'### 3\.2 技术侧\s*\n(.*?)(?=\n---|\n## )', md_text, re.S)
    if m:
        sections['tech'] = m.group(1).strip()

    # 4.3 有益效果
    m = re.search(r'## 4、\*技术方案所产生的有益效果\s*\n(.*?)(?=\n---|\n## )', md_text, re.S)
    if m:
        sections['benefits'] = m.group(1).strip()

    # 5 参考文献
    m = re.search(r'## 附件参考文献.*?\n(.*?)$', md_text, re.S)
    if m:
        sections['references'] = m.group(1).strip()

    return sections


# ── Convert markdown text to list of Word paragraphs ───────────────────
def md_to_paragraphs(md_text, color='0000FF'):
    """Convert markdown text (with LaTeX) to a list of Word XML <w:p> elements.

    Handles:
    - Bold: **text**
    - Inline LaTeX: \\(…\\)
    - Display LaTeX: $$ … $$ (block)
    - Sub-headings: #### and **bold prefix**
    - Bullet items: - text
    - Paragraph breaks (blank lines)
    """
    paragraphs = []

    # First, split on display math blocks $$ ... $$ to handle them separately
    # This regex splits the text into alternating text and display-math segments
    parts = re.split(r'(\$\$.*?\$\$)', md_text, flags=re.S)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if this is a display math block
        if part.startswith('$$') and part.endswith('$$'):
            math_content = part[2:-2].strip()
            # Create a paragraph with the OMML formula
            p = ET.Element(qn('w', 'p'))
            p.append(make_ppr(color))
            omml_elem = latex_to_omml_element(math_content)
            if omml_elem is not None:
                omath_para = ET.Element(f'{{{OMML_NS}}}oMathPara')
                omath_para.append(omml_elem)
                p.append(omath_para)
            else:
                r = make_text_run(f'[公式] {math_content}', color)
                p.append(r)
            paragraphs.append(p)
            continue

        # For non-math text blocks, split into paragraphs by double newline
        blocks = re.split(r'\n\n+', part)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Check if it's a sub-heading line (#### ...)
            if block.startswith('####'):
                heading_text = re.sub(r'^#+\s*', '', block)
                p = make_paragraph([make_text_run(heading_text, color, bold=True)], color)
                paragraphs.append(p)
                continue

            # Otherwise it may be multi-line text (possibly with bullet items)
            lines = block.split('\n')

            # Check if all lines are bullet items
            if all(line.strip().startswith('- ') for line in lines if line.strip()):
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    line_text = line[2:]  # remove "- "
                    runs = text_to_runs(line_text, color)
                    p = make_paragraph(runs, color)
                    paragraphs.append(p)
                continue

            # Regular paragraph - join lines
            full_text = '\n'.join(l.strip() for l in lines)
            # But if it contains structured lines (steps, numbered items), keep separate
            # Detect if lines are individual structured items
            structured_lines = []
            current_item = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if current_item:
                        structured_lines.append('\n'.join(current_item))
                        current_item = []
                    continue
                # Check if this line starts a new structured item
                if re.match(r'^(\*\*[^*]+\*\*|步骤|方案|缺陷|效果|\[?\d+\])', stripped):
                    if current_item:
                        structured_lines.append('\n'.join(current_item))
                        current_item = []
                current_item.append(stripped)
            if current_item:
                structured_lines.append('\n'.join(current_item))

            if len(structured_lines) > 1:
                for item in structured_lines:
                    runs = text_to_runs(item.replace('\n', ' '), color)
                    p = make_paragraph(runs, color)
                    paragraphs.append(p)
            else:
                runs = text_to_runs(full_text.replace('\n', ' '), color)
                p = make_paragraph(runs, color)
                paragraphs.append(p)

    return paragraphs


def text_to_runs(text, color='0000FF'):
    """Convert a single line of markdown text (with inline LaTeX & bold) to w:r runs."""
    runs = []
    # Pattern to match inline LaTeX \(...\) or bold **...**
    # Process left to right
    pattern = re.compile(
        r'(\\\(.*?\\\))'      # inline LaTeX
        r'|(\*\*.*?\*\*)'     # bold
    )
    pos = 0
    for m in pattern.finditer(text):
        # Add plain text before this match
        if m.start() > pos:
            plain = text[pos:m.start()]
            if plain:
                runs.append(make_text_run(plain, color))

        if m.group(1):
            # Inline LaTeX
            latex_str = m.group(1)[2:-2]  # strip \( and \)
            omml_elem = latex_to_omml_element(latex_str)
            if omml_elem is not None:
                runs.append(omml_elem)
            else:
                runs.append(make_text_run(latex_str, color))
        elif m.group(2):
            # Bold text
            bold_text = m.group(2)[2:-2]  # strip ** **
            runs.append(make_text_run(bold_text, color, bold=True))

        pos = m.end()

    # Remaining text after last match
    if pos < len(text):
        remaining = text[pos:]
        if remaining:
            runs.append(make_text_run(remaining, color))

    if not runs:
        runs.append(make_text_run(text, color))

    return runs


# ── Main fill logic ────────────────────────────────────────────────────
def fill_table_cell(tree, label_text, value_text, color='0000FF'):
    """Find a table cell by its label in the preceding cell, and fill value."""
    body = tree.find(qn('w', 'body'))
    tbl = body.find(qn('w', 'tbl'))
    norm_label = re.sub(r'\s+', '', label_text)

    for tr in tbl.findall(qn('w', 'tr')):
        tcs = tr.findall(qn('w', 'tc'))
        # Look for label_text in any cell
        for i, tc in enumerate(tcs):
            all_text = ''.join(tc.itertext())
            norm_all = re.sub(r'\s+', '', all_text)
            if norm_label in norm_all:
                # The value cell is the next one (or same row, target empty cell)
                for j, val_tc in enumerate(tcs):
                    if j <= i:
                        continue
                    val_text_content = ''.join(val_tc.itertext()).strip()
                    if not val_text_content:
                        # Found the empty cell - fill it
                        for p in val_tc.findall(qn('w', 'p')):
                            p_text = ''.join(p.itertext()).strip()
                            if not p_text:
                                r = make_text_run(value_text, color)
                                p.append(r)
                                print(f"  Filled '{label_text}' = '{value_text[:40]}...'")
                                return True
    return False


def find_section_heading(body, text_marker):
    """Find a paragraph that contains the given text marker. Return its index.
    Normalizes whitespace for matching."""
    paragraphs = list(body)
    # Normalize the marker: collapse all whitespace
    norm_marker = re.sub(r'\s+', '', text_marker)
    for idx, elem in enumerate(paragraphs):
        if elem.tag == qn('w', 'p'):
            all_text = ''.join(elem.itertext())
            # Normalize the paragraph text too
            norm_text = re.sub(r'\s+', '', all_text)
            if norm_marker in norm_text:
                return idx
    return None


def find_empty_paragraphs_after(body, start_idx, end_idx=None):
    """Find consecutive empty <w:p> elements after start_idx (exclusive) until end_idx or non-empty."""
    children = list(body)
    empty_indices = []
    for idx in range(start_idx + 1, end_idx if end_idx else len(children)):
        elem = children[idx]
        if elem.tag == qn('w', 'p'):
            all_text = ''.join(elem.itertext()).strip()
            if not all_text:
                empty_indices.append(idx)
            else:
                break
        elif elem.tag == qn('w', 'tbl'):
            break
        else:
            break
    return empty_indices


def replace_empty_with_content(body, empty_indices, content_paragraphs):
    """Replace empty placeholder paragraphs with content paragraphs."""
    if not empty_indices:
        return

    children = list(body)
    ref_elem = children[empty_indices[0]]

    # Remove all empty placeholders
    for idx in reversed(empty_indices):
        elem = children[idx]
        body.remove(elem)

    # Insert content paragraphs at the position of the first empty one
    for i, p in enumerate(content_paragraphs):
        ref_elem.getparent()  # body
        # Find insertion point: where the first empty was
        # Since we removed them, we insert before the element that was after them
        remaining = list(body)
        # The element that was at empty_indices[0] is now gone
        # We need to insert at that position
        insert_pos = empty_indices[0]
        if insert_pos + i < len(remaining):
            remaining[insert_pos + i - 1 if insert_pos + i > 0 else 0]
        body.insert(insert_pos + i, p)


def fill_section(body, heading_marker, next_heading_marker, md_content, color='0000FF'):
    """Fill a section between heading_marker and next_heading_marker with md_content."""
    heading_idx = find_section_heading(body, heading_marker)
    if heading_idx is None:
        print(f"  [WARN] Could not find heading: {heading_marker}")
        return

    # Find the next section heading index
    next_idx = None
    if next_heading_marker:
        next_idx = find_section_heading(body, next_heading_marker)

    # Find empty paragraphs between heading and next section
    empty_indices = find_empty_paragraphs_after(body, heading_idx, next_idx)
    if not empty_indices:
        print(f"  [WARN] No empty paragraphs found after: {heading_marker}")
        return

    # Convert md content to paragraphs
    content_paras = md_to_paragraphs(md_content, color)
    if not content_paras:
        print(f"  [WARN] No content paragraphs generated for: {heading_marker}")
        return

    print(f"  Filling {heading_marker}: replacing {len(empty_indices)} empty paras with {len(content_paras)} content paras")

    # Remove empty paragraphs and insert content
    children = list(body)
    insert_before_idx = empty_indices[0]

    # Remove empty paras in reverse order
    for idx in reversed(empty_indices):
        body.remove(children[idx])

    # Insert content at the position
    for i, p in enumerate(content_paras):
        body.insert(insert_before_idx + i, p)


def main():
    # Read patent markdown
    with open('/data/zhuanli/output/patent_01_sparse_jacobian_solver_20260228/patent_01_disclosure.md', 'r') as f:
        md_text = f.read()

    sections = parse_md(md_text)
    print("Parsed sections:", list(sections.keys()))

    # Read template XML
    xml_path = '/data/zhuanli/unpacked_template/word/document.xml'
    parser = ET.XMLParser(remove_blank_text=False)
    tree = ET.parse(xml_path, parser)
    root = tree.getroot()
    body = root.find(qn('w', 'body'))

    # ── Fill header table cells ──
    print("\nFilling header table...")
    fill_table_cell(tree, '交底书名称', sections['name'])
    fill_table_cell(tree, '涉及产品和技术', '三维角色动画蒙皮权重优化')

    # ── Fill Section 1: 关键术语 ──
    print("\nFilling sections...")
    fill_section(
        body,
        '【关键术语】',
        '【发明构思】',
        sections['keywords'],
    )

    # ── Fill Section 2: 发明构思 ──
    fill_section(
        body,
        '【发明构思】',
        '【背景技术】',
        sections['concept'],
    )

    # ── Fill Section 3.1: 背景技术方案 ──
    fill_section(
        body,
        '相关背景描述，以及现有技术的技术方案',
        '现有技术的缺点或尚未解决的问题',
        sections['bg_tech'],
    )

    # ── Fill Section 3.2: 现有技术缺点 ──
    fill_section(
        body,
        '现有技术的缺点或尚未解决的问题',
        '【发明内容】',
        sections['bg_defect'],
    )

    # ── Fill Section 4.1: 产品侧 ──
    fill_section(
        body,
        '.1产品侧',
        '.2技术侧',
        sections['product'],
    )

    # ── Fill Section 4.2: 技术侧 ──
    fill_section(
        body,
        '.2技术侧',
        '.3专利方案所产生的有益效果',
        sections['tech'],
    )

    # ── Fill Section 4.3: 有益效果 ──
    fill_section(
        body,
        '.3专利方案所产生的有益效果',
        '参考文献',
        sections['benefits'],
    )

    # ── Fill Section 5: 参考文献 ──
    fill_section(
        body,
        '参考文献（如：专利/论文/网页/期刊）',
        None,  # Last section
        sections['references'],
    )

    # ── Write output ──
    print("\nWriting output XML...")
    tree.write(xml_path, xml_declaration=True, encoding='UTF-8', standalone=True)
    print("Done! Template filled successfully.")


if __name__ == '__main__':
    main()
