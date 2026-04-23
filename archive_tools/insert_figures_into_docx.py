#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
insert_figures_into_docx.py
将已生成的插图插入到对应的专利 DOCX 文档中。

策略：
  直接修改已有的 _disclosure_skill.docx 文件，
  在对应章节标题之后插入图片和图片标题。
"""

import glob
import os
import re
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_ALIGN_PARAGRAPH


FIGURE_DIR = '/data/zhuanli/output/imagegen/patent_figures'

# 图片宽度（英寸）
IMG_WIDTH = Inches(5.5)


def set_para_spacing(para, before_pt=0, after_pt=0, line_val=240):
    """设置段落间距。"""
    pPr = para._p.get_or_add_pPr()
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    if before_pt:
        spacing.set(qn('w:before'), str(int(before_pt * 20)))
    if after_pt:
        spacing.set(qn('w:after'), str(int(after_pt * 20)))
    spacing.set(qn('w:lineRule'), 'auto')
    spacing.set(qn('w:line'), str(line_val))


def _set_east_asia_font(run, font_name):
    rPr = run._r.get_or_add_rPr()
    for old in rPr.findall(qn('w:rFonts')):
        rPr.remove(old)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:eastAsia'), font_name)
    rFonts.set(qn('w:cs'), font_name)
    rPr.insert(0, rFonts)


def get_paragraph_text(para):
    """获取段落的纯文本内容。"""
    return para.text.strip()


def find_section_heading_index(doc, keyword):
    """
    在文档中查找包含 keyword 的段落索引。
    返回第一个匹配的段落索引，找不到返回 -1。
    """
    for idx, para in enumerate(doc.paragraphs):
        text = get_paragraph_text(para)
        if keyword in text:
            return idx
    return -1


def find_next_heading_index(doc, start_idx):
    """
    从 start_idx+1 开始找下一个标题段落的索引。
    标题判定：字号>=12pt且加粗，或者段落文本匹配 "X.X.X" / "## " 等模式。
    简化判定：找下一个加粗的短段落（通常是标题）。
    """
    for idx in range(start_idx + 1, len(doc.paragraphs)):
        para = doc.paragraphs[idx]
        text = get_paragraph_text(para)
        if not text:
            continue
        # 检查是否有加粗 run 且文本较短（标题特征）
        runs = para.runs
        if runs and runs[0].bold and len(text) < 100:
            return idx
    return len(doc.paragraphs)


def insert_figure_after_paragraph(doc, para_index, img_path, caption_text, fig_number):
    """
    在指定段落之后插入图片和图注。
    
    由于 python-docx 没有直接的 insert_paragraph_after(index) API，
    我们通过操作底层 XML 在指定位置插入。
    """
    body = doc.element.body
    
    # 获取参考段落的 XML 元素
    ref_para = doc.paragraphs[para_index]._element
    
    # 创建图注段落（先创建图注，后面会调整顺序）
    caption_para = OxmlElement('w:p')
    # 图注段落属性
    caption_pPr = OxmlElement('w:pPr')
    caption_jc = OxmlElement('w:jc')
    caption_jc.set(qn('w:val'), 'center')
    caption_pPr.append(caption_jc)
    # 间距
    caption_spacing = OxmlElement('w:spacing')
    caption_spacing.set(qn('w:before'), str(int(4 * 20)))
    caption_spacing.set(qn('w:after'), str(int(8 * 20)))
    caption_spacing.set(qn('w:lineRule'), 'auto')
    caption_spacing.set(qn('w:line'), '280')
    caption_pPr.append(caption_spacing)
    caption_para.append(caption_pPr)
    
    # 图注 run
    caption_r = OxmlElement('w:r')
    caption_rPr = OxmlElement('w:rPr')
    # 字体
    caption_rFonts = OxmlElement('w:rFonts')
    caption_rFonts.set(qn('w:ascii'), '宋体')
    caption_rFonts.set(qn('w:hAnsi'), '宋体')
    caption_rFonts.set(qn('w:eastAsia'), '宋体')
    caption_rFonts.set(qn('w:cs'), '宋体')
    caption_rPr.append(caption_rFonts)
    # 字号 10.5pt = 21 half-pt
    caption_sz = OxmlElement('w:sz')
    caption_sz.set(qn('w:val'), '21')
    caption_rPr.append(caption_sz)
    caption_szCs = OxmlElement('w:szCs')
    caption_szCs.set(qn('w:val'), '21')
    caption_rPr.append(caption_szCs)
    caption_r.append(caption_rPr)
    caption_t = OxmlElement('w:t')
    caption_t.text = caption_text
    caption_r.append(caption_t)
    caption_para.append(caption_r)
    
    # 插入图注（在参考段落之后）
    ref_para.addnext(caption_para)
    
    # 创建图片段落 — 使用 python-docx 的高级 API 先创建再移动
    # 先用 doc.add_paragraph() 在末尾添加，然后把 XML 元素移动到正确位置
    temp_para = doc.add_paragraph()
    temp_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_para_spacing(temp_para, before_pt=8, after_pt=4, line_val=240)
    
    run = temp_para.add_run()
    run.add_picture(img_path, width=IMG_WIDTH)
    
    # 把图片段落移动到参考段落之后（图注之前）
    temp_element = temp_para._element
    body.remove(temp_element)
    ref_para.addnext(temp_element)
    
    return True


def process_patent(docx_path, figures_config):
    """
    处理单个专利文档，插入多张图片。
    
    figures_config: list of dict, each with:
        - keyword: 用于定位章节的关键字
        - img_file: 图片文件名
        - caption: 图注文字
        - fig_num: 图编号
        - insert_at: 'after_heading' (在标题后) 或 'end_of_section' (在章节末尾)
    """
    print(f"\n处理: {os.path.basename(docx_path)}")
    doc = Document(docx_path)
    
    # 按图片编号倒序插入（从后往前），避免索引偏移
    figures_sorted = sorted(figures_config, key=lambda x: x['fig_num'], reverse=True)
    
    inserted_count = 0
    for fig in figures_sorted:
        img_path = os.path.join(FIGURE_DIR, fig['img_file'])
        if not os.path.exists(img_path):
            print(f"  ✗ 图片不存在: {fig['img_file']}")
            continue
        
        keyword = fig['keyword']
        insert_at = fig.get('insert_at', 'end_of_section')

        if insert_at == 'end_of_doc' or keyword is None:
            # 追加到文档末尾
            target_idx = len(doc.paragraphs) - 1
        else:
            idx = find_section_heading_index(doc, keyword)
            if idx < 0:
                print(f"  ✗ 未找到章节: '{keyword}'")
                continue

            if insert_at == 'after_heading':
                # 在标题段落后直接插入
                target_idx = idx
            elif insert_at == 'end_of_section':
                # 在该章节的末尾（下一个标题之前）插入
                next_heading = find_next_heading_index(doc, idx)
                target_idx = next_heading - 1
            else:
                target_idx = idx
        
        # 确保索引有效
        if target_idx < 0:
            target_idx = idx
        if target_idx >= len(doc.paragraphs):
            target_idx = len(doc.paragraphs) - 1
            
        success = insert_figure_after_paragraph(
            doc, target_idx, img_path, fig['caption'], fig['fig_num']
        )
        if success:
            inserted_count += 1
            location = f"在 '{keyword}' 后" if keyword else "文档末尾"
            print(f"  ✓ 插入 {fig['caption']} ({location})")
        else:
            print(f"  ✗ 插入失败: {fig['caption']}")
    
    # 保存
    doc.save(docx_path)
    size_kb = os.path.getsize(docx_path) / 1024
    print(f"  保存完成: {size_kb:.1f} KB, 插入 {inserted_count} 张图片")
    return inserted_count


# ──────────────────────────────────────────────
# 已有专利的图片插入配置（按 keyword 精确定位）
# 新增专利无需修改此处，会自动追加到文末
# ──────────────────────────────────────────────

PATENT_FIGURES = {
    '/data/zhuanli/output/patent_01_sparse_jacobian_solver_20260228/patent_01_disclosure_skill.docx': [
        {
            'keyword': '3.1 产品侧',
            'img_file': 'fig_1_1_system_flow_0.png',
            'caption': '图1 稀疏雅可比反向蒙皮权重求解系统整体流程图',
            'fig_num': 1,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.1 LBS 模型与线性化推导',
            'img_file': 'fig_1_2_sparse_vs_dense_0.png',
            'caption': '图2 稀疏与稠密雅可比矩阵结构对比示意图',
            'fig_num': 2,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.4 完整技术流程',
            'img_file': 'fig_1_3_vertex_bone_subspace_0.png',
            'caption': '图3 局部受影响顶点与候选骨骼子空间示意图',
            'fig_num': 3,
            'insert_at': 'after_heading',
        },
        {
            'keyword': '3.2.2 目标函数定义',
            'img_file': 'fig_1_4_objective_function_0.png',
            'caption': '图4 约束优化目标函数构成示意图',
            'fig_num': 4,
            'insert_at': 'end_of_section',
        },
    ],

    '/data/zhuanli/output/patent_02_no_gt_quality_closedloop_20260228/patent_02_disclosure_skill.docx': [
        {
            'keyword': '3.1 产品侧',
            'img_file': 'fig_2_1_system_arch_0.png',
            'caption': '图1 无真值蒙皮质量评估与数据闭环系统架构图',
            'fig_num': 1,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.2 可插拔指标计算',
            'img_file': 'fig_2_2_pluggable_arch_0.png',
            'caption': '图2 可插拔指标计算架构示意图',
            'fig_num': 2,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.6 数据闭环执行',
            'img_file': 'fig_2_3_data_loop_0.png',
            'caption': '图3 数据闭环迭代流程图',
            'fig_num': 3,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.1 产品侧',
            'img_file': 'fig_2_4_quality_gate_arch_0.png',
            'caption': '图4 质量闸门三级部署架构图',
            'fig_num': 4,
            'insert_at': 'end_of_section',
        },
    ],

    '/data/zhuanli/output/patent_03_sat_collinearity_metric_20260228/patent_03_disclosure_skill.docx': [
        {
            'keyword': '3.1 产品侧',
            'img_file': 'fig_3_3_detection_pipeline_0.png',
            'caption': '图1 SAT共线与形变异常检测流程总览图',
            'fig_num': 1,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.1 输入定义与检测对象构建',
            'img_file': 'fig_3_2_detection_objects_0.png',
            'caption': '图2 边链与面簇检测对象构建示意图',
            'fig_num': 2,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.3 SAT投影特征计算',
            'img_file': 'fig_3_1_sat_projection_0.png',
            'caption': '图3 分离轴定理投影原理示意图',
            'fig_num': 3,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.6 跨帧持续性判定',
            'img_file': 'fig_3_4_temporal_persistence_0.png',
            'caption': '图4 跨帧持续性判定时序示意图',
            'fig_num': 4,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.3 SAT投影特征计算',
            'img_file': 'fig_3_5_sat_collinear_principle_0.png',
            'caption': '图5 SAT多轴投影共线检测原理示意图',
            'fig_num': 5,
            'insert_at': 'end_of_section',
        },
    ],

    '/data/zhuanli/output/patent_04_insertion_sticking_metric_20260228/patent_04_disclosure_skill.docx': [
        {
            'keyword': '3.1 产品侧',
            'img_file': 'fig_4_1_dual_phase_framework_0.png',
            'caption': '图1 双阶段穿插粘连检测框架流程图',
            'fig_num': 1,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.4 穿插评分模型',
            'img_file': 'fig_4_2_penetration_0.png',
            'caption': '图2 穿插检测几何特征示意图',
            'fig_num': 2,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.5 粘连评分模型',
            'img_file': 'fig_4_3_sticking_0.png',
            'caption': '图3 粘连检测几何与运动特征示意图',
            'fig_num': 3,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.6 正常接触区分规则',
            'img_file': 'fig_4_4_valid_contact_0.png',
            'caption': '图4 有效接触与粘连区分的三重抑制规则',
            'fig_num': 4,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.6 正常接触区分规则',
            'img_file': 'fig_4_5_pen_vs_stick_comparison_0.png',
            'caption': '图5 穿插与粘连特征对比示意图',
            'fig_num': 5,
            'insert_at': 'end_of_section',
        },
    ],

    '/data/zhuanli/output/patent_05_longtail_cloth_postprocess_20260228/patent_05_disclosure_skill.docx': [
        {
            'keyword': '3.1 产品侧',
            'img_file': 'fig_5_1_closed_loop_pipeline_0.png',
            'caption': '图1 长尾布料确定性后处理闭环流程图',
            'fig_num': 1,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.1 异常区域构建',
            'img_file': 'fig_5_2_anomaly_region_0.png',
            'caption': '图2 异常区域拓扑扩展与锚定边界示意图',
            'fig_num': 2,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.2 期望几何平滑目标求解',
            'img_file': 'fig_5_3_smoothing_comparison_0.png',
            'caption': '图3 布料表面平滑处理前后对比示意图',
            'fig_num': 3,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.6 退化重试与回退',
            'img_file': 'fig_5_4_rollback_decision_tree_0.png',
            'caption': '图4 降级重试与回滚决策树',
            'fig_num': 4,
            'insert_at': 'end_of_section',
        },
        {
            'keyword': '3.2.6 退化重试与回退',
            'img_file': 'fig_5_5_retry_rollback_flow_0.png',
            'caption': '图5 确定性后处理重试与回退决策流程图',
            'fig_num': 5,
            'insert_at': 'end_of_section',
        },
    ],
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')


def discover_new_patents():
    """发现 PATENT_FIGURES 中未配置的新专利 docx，自动匹配其图片。

    对于新专利，按 fig_<NN>_* 前缀匹配图片，按文件名排序后
    依次追加到文档末尾（insert_at='end_of_doc'）。
    """
    configured = set(os.path.abspath(p) for p in PATENT_FIGURES)
    pattern = os.path.join(os.path.abspath(OUTPUT_DIR), 'patent_*', 'patent_*_disclosure_skill.docx')
    all_docx = sorted(glob.glob(pattern))
    new_patents = {}
    for docx_path in all_docx:
        if os.path.abspath(docx_path) in configured:
            continue
        # 从路径中提取专利编号，如 patent_06 → "06" → 6
        m = re.search(r'patent_(\d+)', os.path.basename(docx_path))
        if not m:
            continue
        patent_num = int(m.group(1))
        # 查找 fig_<NN>_* 图片
        fig_pattern = os.path.join(FIGURE_DIR, f'fig_{patent_num}_*')
        figs = sorted(glob.glob(fig_pattern))
        if not figs:
            print(f"  [新专利] {os.path.basename(docx_path)}: 未找到匹配图片 (fig_{patent_num}_*)，跳过插图")
            continue
        fig_entries = []
        for i, fig_path in enumerate(figs, 1):
            fig_name = os.path.basename(fig_path)
            # 从文件名生成简短的 caption
            caption_parts = fig_name.replace('.png', '').split('_')[3:]  # 去掉 fig_N_M_ 前缀
            caption_text = ' '.join(caption_parts).rstrip(' 0123456789')
            fig_entries.append({
                'keyword': None,  # None 表示追加到文末
                'img_file': fig_name,
                'caption': f'图{i} {caption_text}',
                'fig_num': i,
                'insert_at': 'end_of_doc',
            })
        new_patents[docx_path] = fig_entries
        print(f"  [新专利] {os.path.basename(docx_path)}: 发现 {len(fig_entries)} 张图片")
    return new_patents


def main():
    print("=" * 60)
    print("专利 DOCX 插图插入工具")
    print("=" * 60)

    # 合并已配置的 + 自动发现的新专利
    all_patents = dict(PATENT_FIGURES)
    new_patents = discover_new_patents()
    all_patents.update(new_patents)

    total = 0
    doc_count = 0
    for docx_path, figures in sorted(all_patents.items()):
        if not os.path.exists(docx_path):
            print(f"\n✗ 文件不存在: {docx_path}")
            continue
        count = process_patent(docx_path, figures)
        total += count
        doc_count += 1

    print()
    print("=" * 60)
    print(f"完成！共插入 {total} 张插图到 {doc_count} 个专利文档中。")
    print("=" * 60)


if __name__ == '__main__':
    main()
