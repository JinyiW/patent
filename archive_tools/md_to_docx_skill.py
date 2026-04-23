#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [DEPRECATED] 仅用于 patent_01~05（已定版）。新专利请使用 tools/fill_template.py。
"""
md_to_docx_skill.py
将中文专利 Markdown 文件转换为格式规范的 Word DOCX。

字体规范:
  ## Heading 1  → 黑体 16pt
  ### Heading 2 → 黑体 14pt
  #### Heading 3→ 黑体 12pt
  #####         → 黑体 11pt（加粗段落，非标题样式）
  普通段落      → 宋体 12pt
  $$...$$       → 等宽 10pt（公式块）
  \(...\)       → 保留 LaTeX 文字，宋体 12pt
  **bold**      → 黑体 加粗
  - / *  列表   → 列表段落，宋体 12pt
  ---           → 跳过
"""

import glob
import os
import re
import sys

import latex2mathml.converter
import mathml2omml
import lxml.etree as ET

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_ALIGN_PARAGRAPH

OMML_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


# ──────────────────────────────────────────────
# LaTeX → OMML 转换
# ──────────────────────────────────────────────

def latex_to_omml_element(latex_str: str):
    """将 LaTeX 公式字符串转换为 OMML lxml Element。转换失败返回 None。"""
    try:
        mathml = latex2mathml.converter.convert(latex_str)
        omml_str = mathml2omml.convert(mathml)
        # 修复 mathml2omml 的已知 bug：\underbrace/\overbrace/\begin{cases} 等
        # 会生成 </m:groupChr> 来关闭 <m:groupChrPr>，导致 XML 不合法
        omml_str = omml_str.replace('</m:groupChr><m:e>', '</m:groupChrPr><m:e>')
        omml_str = omml_str.replace(
            '<m:oMath>',
            f'<m:oMath xmlns:m="{OMML_NS}" xmlns:w="{W_NS}">',
            1,
        )
        el = ET.fromstring(omml_str.encode())
        # 将 groupChr (bar/hat/tilde) 转换为 acc，避免 Word 中内容缩小为下标大小
        _fix_groupchr_to_acc(el)
        return el
    except Exception:
        return None


# bar / hat / tilde 字符集
_BAR_CHARS = frozenset(('\u00AF', '\u0304', '\u0305'))
_HAT_CHARS = frozenset(('\u0302', '\u005E', '\u0311'))
_TILDE_CHARS = frozenset(('\u0303', '\u007E'))
_ALL_TOP_ACCENTS = _BAR_CHARS | _HAT_CHARS | _TILDE_CHARS

def _fix_groupchr_to_acc(root):
    """将 m:groupChr（顶部 bar/hat/tilde）替换为 m:acc，使 Word 以正常字号渲染。"""
    MNS = OMML_NS
    replacements = []
    for gc in root.iter(qn('m:groupChr')):
        pr = gc.find(qn('m:groupChrPr'))
        e = gc.find(qn('m:e'))
        if pr is None or e is None:
            continue
        chr_el = pr.find(qn('m:chr'))
        pos_el = pr.find(qn('m:pos'))
        if chr_el is None:
            continue
        char_val = chr_el.get(qn('m:val'), '')
        pos_val = pos_el.get(qn('m:val'), '') if pos_el is not None else ''
        if pos_val == 'top' and char_val in _ALL_TOP_ACCENTS:
            if char_val in _BAR_CHARS:
                target = '\u0305'
            elif char_val in _HAT_CHARS:
                target = '\u0302'
            else:
                target = '\u0303'
            replacements.append((gc, e, target))

    for gc, e, target in replacements:
        acc = OxmlElement('m:acc')
        accPr_el = OxmlElement('m:accPr')
        chr_new = OxmlElement('m:chr')
        chr_new.set(qn('m:val'), target)
        accPr_el.append(chr_new)
        acc.append(accPr_el)

        new_e = OxmlElement('m:e')
        box = e.find(qn('m:box'))
        if box is not None:
            box_e = box.find(qn('m:e'))
            src = box_e if box_e is not None else box
        else:
            src = e
        for child in list(src):
            new_e.append(child)
        acc.append(new_e)

        parent = gc.getparent()
        if parent is not None:
            idx = list(parent).index(gc)
            parent.remove(gc)
            parent.insert(idx, acc)


# ──────────────────────────────────────────────
# 字体工具
# ──────────────────────────────────────────────

def _set_east_asia_font(run, font_name: str):
    """同时设置西文字体与中文字体（eastAsia）。"""
    rPr = run._r.get_or_add_rPr()
    # 删除已有 w:rFonts 再重建，避免重复
    for old in rPr.findall(qn('w:rFonts')):
        rPr.remove(old)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'),    font_name)
    rFonts.set(qn('w:hAnsi'),    font_name)
    rFonts.set(qn('w:eastAsia'), font_name)
    rFonts.set(qn('w:cs'),       font_name)
    rPr.insert(0, rFonts)


def set_run_font(run, font_name: str, size_pt: float, bold: bool = False):
    """设置 run 的字体、字号、加粗，同时处理中文字体。"""
    run.font.name  = font_name
    run.font.size  = Pt(size_pt)
    run.font.bold  = bold
    _set_east_asia_font(run, font_name)


def set_para_font(para, font_name: str, size_pt: float, bold: bool = False):
    """通过段落默认 run 格式设置整段字体（pPr 级）。"""
    pPr = para._p.get_or_add_pPr()
    rPr = para._p.get_or_add_pPr().get_or_add_rPr() \
          if hasattr(pPr, 'get_or_add_rPr') else OxmlElement('w:rPr')

    # 用 paragraph.style 级别不够精细，改用段落默认 rPr
    # 这里直接依赖 add_run 时手动设置每个 run


# ──────────────────────────────────────────────
# 行内元素解析（**bold**、\(...\) 公式）
# ──────────────────────────────────────────────

def parse_inline_runs(para, text: str,
                      body_font: str = '宋体', body_size: float = 12.0):
    """
    将含有 **bold** 和 \\(...\\) 标记的文本分段添加到 para 中。
    \\(...\\) 内的 LaTeX 转换为 OMML 可编辑公式。
    支持 **bold \\(latex\\)** 嵌套。
    """

    def _add_latex_or_fallback(inner_latex):
        """尝试将 LaTeX 转 OMML，失败则纯文本 fallback。"""
        omml = latex_to_omml_element(inner_latex)
        if omml is not None:
            para._element.append(omml)
        else:
            run = para.add_run(inner_latex)
            set_run_font(run, 'Courier New', body_size - 1, bold=False)
            _set_east_asia_font(run, '宋体')

    def _process_segment_for_latex(seg_text, is_bold):
        """处理一段文本中的 \\(...\\) 公式，其余部分用指定字体输出。"""
        latex_parts = re.split(r'(\\\(.*?\\\))', seg_text, flags=re.DOTALL)
        for part in latex_parts:
            if not part:
                continue
            if part.startswith('\\(') and part.endswith('\\)'):
                inner = part[2:-2]
                _add_latex_or_fallback(inner)
            else:
                if is_bold:
                    run = para.add_run(part)
                    set_run_font(run, '黑体', body_size, bold=True)
                else:
                    run = para.add_run(part)
                    set_run_font(run, body_font, body_size)

    # 先按 **...** 分割（可能内含 \(...\)）
    bold_segments = re.split(r'(\*\*(?:(?!\*\*).)*?\*\*)', text, flags=re.DOTALL)

    for seg in bold_segments:
        if not seg:
            continue
        if seg.startswith('**') and seg.endswith('**') and len(seg) > 4:
            inner = seg[2:-2]
            _process_segment_for_latex(inner, is_bold=True)
        else:
            _process_segment_for_latex(seg, is_bold=False)


# ──────────────────────────────────────────────
# 段落间距工具
# ──────────────────────────────────────────────

def set_para_spacing(para, before_pt: float = 0, after_pt: float = 0,
                     line_rule: str = 'auto', line_val: int = 240):
    """设置段落前后间距和行间距。"""
    pPr = para._p.get_or_add_pPr()
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    if before_pt:
        spacing.set(qn('w:before'), str(int(before_pt * 20)))
    if after_pt:
        spacing.set(qn('w:after'), str(int(after_pt * 20)))
    spacing.set(qn('w:lineRule'), line_rule)
    spacing.set(qn('w:line'), str(line_val))


def set_list_indent(para, level: int = 0):
    """给列表段落设置缩进。"""
    pPr = para._p.get_or_add_pPr()
    ind = pPr.find(qn('w:ind'))
    if ind is None:
        ind = OxmlElement('w:ind')
        pPr.append(ind)
    left = 360 + level * 360   # 每级 360 twips ≈ 0.63 cm
    ind.set(qn('w:left'), str(left))
    ind.set(qn('w:hanging'), '180')


# ──────────────────────────────────────────────
# 标题段落
# ──────────────────────────────────────────────

def add_heading_para(doc: Document, text: str, level: int):
    """
    level: 1=## (16pt), 2=### (14pt), 3=#### (12pt), 4=##### (11pt)
    """
    size_map = {1: 16.0, 2: 14.0, 3: 12.0, 4: 11.0}
    size = size_map.get(level, 12.0)

    # 不使用内置 Heading 样式，避免编号/自动目录干扰
    para = doc.add_paragraph()
    run  = para.add_run(text.strip())
    set_run_font(run, '黑体', size, bold=True)
    before = {1: 12, 2: 9, 3: 6, 4: 4}.get(level, 4)
    set_para_spacing(para, before_pt=before, after_pt=3, line_val=360)
    return para


# ──────────────────────────────────────────────
# 主转换函数
# ──────────────────────────────────────────────

def convert_md_to_docx(md_path: str, docx_path: str):
    print(f"  Converting: {os.path.basename(md_path)}")
    with open(md_path, encoding='utf-8') as f:
        lines = f.readlines()

    doc = Document()

    # 全局页边距
    for section in doc.sections:
        section.top_margin    = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin   = Inches(1.2)
        section.right_margin  = Inches(1.2)

    # 默认正文样式（Normal）
    normal_style = doc.styles['Normal']
    normal_style.font.name = '宋体'
    normal_style.font.size = Pt(12)
    # 设置 Normal 样式的 eastAsia 字体
    style_elem = normal_style.element
    rPr = style_elem.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        style_elem.append(rPr)
    for old in rPr.findall(qn('w:rFonts')):
        rPr.remove(old)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'),    '宋体')
    rFonts.set(qn('w:hAnsi'),    '宋体')
    rFonts.set(qn('w:eastAsia'), '宋体')
    rFonts.set(qn('w:cs'),       '宋体')
    rPr.insert(0, rFonts)

    in_formula_block = False
    formula_lines: list[str] = []

    def _add_block_formula(content: str):
        """将块级 LaTeX 公式作为 OMML 插入文档，失败则 fallback 纯文本。"""
        para = doc.add_paragraph()
        set_para_spacing(para, before_pt=4, after_pt=4, line_val=240)
        omml = latex_to_omml_element(content)
        if omml is not None:
            oMathPara = ET.SubElement(para._element, qn('m:oMathPara'))
            oMathPara.append(omml)
        else:
            # fallback: 纯文本
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = para.add_run(content)
            run.font.name = 'Courier New'
            run.font.size = Pt(10)
            _set_east_asia_font(run, '宋体')
            pPr = para._p.get_or_add_pPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'),   'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'),  'F2F2F2')
            pPr.append(shd)

    def flush_formula():
        nonlocal formula_lines
        content = '\n'.join(formula_lines).strip()
        formula_lines = []
        if not content:
            return
        _add_block_formula(content)

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip('\n')
        i += 1

        # ── 公式块开始/结束 ──────────────────────────
        if line.strip() == '$$':
            if in_formula_block:
                in_formula_block = False
                flush_formula()
            else:
                in_formula_block = True
            continue

        if line.strip().startswith('$$') and line.strip().endswith('$$') \
                and len(line.strip()) > 4:
            # 单行 $$...$$ 公式
            content = line.strip()[2:-2].strip()
            _add_block_formula(content)
            continue

        if in_formula_block:
            formula_lines.append(line)
            continue

        # ── 分隔线 ───────────────────────────────────
        if line.strip() == '---':
            continue

        # ── Markdown 图片语法（跳过，图片由 insert_figures_into_docx.py 单独插入）
        if re.match(r'^!\[.*?\]\(.*?\)\s*$', line.strip()):
            continue

        # ── 空行 ─────────────────────────────────────
        if line.strip() == '':
            # 空行：在 Word 里加一个小间距空段（可选，或直接 continue）
            # doc.add_paragraph()  # 会产生多余空行，改为靠间距控制
            continue

        # ── 标题 ─────────────────────────────────────
        heading_match = re.match(r'^(#{1,5})\s+(.*)', line)
        if heading_match:
            hashes = heading_match.group(1)
            title  = heading_match.group(2).strip()
            level  = len(hashes)
            if level == 1:
                # # 单井号当作超大标题（文档标题）
                para = doc.add_paragraph()
                run  = para.add_run(title)
                set_run_font(run, '黑体', 18, bold=True)
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_para_spacing(para, before_pt=6, after_pt=6, line_val=360)
            else:
                # ## → level 1, ### → level 2, etc.
                add_heading_para(doc, title, level - 1)
            continue

        # ── 列表项 ───────────────────────────────────
        list_match = re.match(r'^(\s*)([-*])\s+(.*)', line)
        if list_match:
            indent_str = list_match.group(1)
            text_part  = list_match.group(3)
            level      = len(indent_str) // 2  # 每2空格一级

            para = doc.add_paragraph()
            set_para_spacing(para, before_pt=1, after_pt=1, line_val=280)
            set_list_indent(para, level)

            # 列表符号
            bullet_run = para.add_run('• ')
            set_run_font(bullet_run, '宋体', 12)

            parse_inline_runs(para, text_part, '宋体', 12.0)
            continue

        # ── 有序列表（1. 2. ...）────────────────────
        ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        if ordered_match:
            indent_str = ordered_match.group(1)
            num        = ordered_match.group(2)
            text_part  = ordered_match.group(3)
            level      = len(indent_str) // 2

            para = doc.add_paragraph()
            set_para_spacing(para, before_pt=1, after_pt=1, line_val=280)
            set_list_indent(para, level)

            num_run = para.add_run(f'{num}. ')
            set_run_font(num_run, '宋体', 12)

            parse_inline_runs(para, text_part, '宋体', 12.0)
            continue

        # ── 普通段落 ─────────────────────────────────
        para = doc.add_paragraph()
        set_para_spacing(para, before_pt=2, after_pt=2, line_val=320)
        parse_inline_runs(para, line, '宋体', 12.0)

    # 若文件末尾仍在公式块中，强制关闭
    if in_formula_block and formula_lines:
        flush_formula()

    doc.save(docx_path)
    size_kb = os.path.getsize(docx_path) / 1024
    print(f"  ✓ Saved: {os.path.basename(docx_path)}  ({size_kb:.1f} KB)")
    return size_kb


# ──────────────────────────────────────────────
# 自动发现并批量转换
# ──────────────────────────────────────────────

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')


def discover_patents():
    """自动发现 output/ 下所有 patent_*_disclosure.md，返回 (md_path, docx_path) 列表。"""
    pattern = os.path.join(os.path.abspath(OUTPUT_DIR), 'patent_*', 'patent_*_disclosure.md')
    md_files = sorted(glob.glob(pattern))
    patents = []
    for md_path in md_files:
        docx_path = md_path.replace('_disclosure.md', '_disclosure_skill.docx')
        patents.append((md_path, docx_path))
    return patents


def main():
    print("=" * 60)
    print("专利 Markdown → DOCX 批量转换")
    print("=" * 60)
    patents = discover_patents()
    if not patents:
        print("  未发现任何 patent_*_disclosure.md 文件。")
        print(f"  搜索路径: {os.path.abspath(OUTPUT_DIR)}/patent_*/")
        sys.exit(1)
    print(f"  发现 {len(patents)} 个专利文件\n")
    results = []
    for md_path, docx_path in patents:
        if not os.path.isfile(md_path):
            print(f"  ✗ 源文件不存在: {md_path}")
            results.append((os.path.basename(docx_path), False, 0))
            continue
        try:
            kb = convert_md_to_docx(md_path, docx_path)
            results.append((os.path.basename(docx_path), True, kb))
        except Exception as e:
            print(f"  ✗ 转换失败: {e}")
            import traceback; traceback.print_exc()
            results.append((os.path.basename(docx_path), False, 0))

    print()
    print("=" * 60)
    print("汇总结果")
    print("=" * 60)
    all_ok = True
    for name, ok, kb in results:
        status = '✓' if ok else '✗'
        info   = f'{kb:.1f} KB' if ok else '失败'
        print(f"  {status}  {name:<50s}  {info}")
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print(f"全部 {len(results)} 个 DOCX 文件生成成功！")
    else:
        print("部分文件生成失败，请检查上方错误信息。")
        sys.exit(1)


if __name__ == '__main__':
    main()
