#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_figures.py
根据专利 brief.md 中的"图片需求"段落，调用文生图 API 生成插图。

brief.md 中的图片需求格式：
  # 图片需求
  - fig_1_system_flow: 系统整体流程图，展示...
  - fig_2_xxx: 描述...

用法:
  python tools/gen_figures.py patent_06    # 为 patent_06 生成图片
  python tools/gen_figures.py              # 为所有含 brief.md 的专利生成图片
"""

import glob
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from remote_image_generator import generate_images_with_remote_api

PATENTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'patents')

# 通用前缀 prompt（顶会论文风格：SIGGRAPH/NeurIPS 配色）
STYLE_PROMPT = (
    "Create a high-quality technical figure in the style of a top-tier computer graphics "
    "conference paper (SIGGRAPH/NeurIPS). "
    "Use a clean white background with soft, modern color palette: "
    "light blue (#4A90D9), warm orange (#E8A849), soft green (#5CB85C), "
    "muted purple (#9B59B6), and light gray (#F0F0F0) for backgrounds. "
    "Use clean vector-style boxes with rounded corners, neat arrows, "
    "and professional sans-serif typography. Label all text in English. "
    "The diagram should look publication-ready, with consistent spacing, "
    "alignment, and visual hierarchy. "
    "Do NOT use hand-drawn style, 3D effects, or decorative elements. "
    "Keep it minimal and elegant. "
)


def parse_figure_specs(brief_path):
    """解析 brief.md 中的图片需求段落。

    返回 list of (fig_name, description)。
    """
    with open(brief_path, encoding='utf-8') as f:
        content = f.read()

    # 找到 "# 图片需求" 段落
    match = re.search(r'#\s*图片需求[^\n]*\n(.*?)(?=\n#\s|\Z)', content, re.DOTALL)
    if not match:
        return []

    specs = []
    for line in match.group(1).strip().splitlines():
        line = line.strip()
        if not line or not line.startswith('-'):
            continue
        line = line.lstrip('-').strip()
        # 格式: fig_name: description 或 fig_name — description
        m = re.match(r'(fig_\w+)\s*[:：—\-]\s*(.*)', line)
        if m:
            specs.append((m.group(1), m.group(2).strip()))
        else:
            # 没有 fig_ 前缀的，自动编号
            idx = len(specs) + 1
            specs.append((f'fig_{idx}', line))
    return specs


def discover_patents(filter_name=None):
    """发现含有 brief.md 的专利目录。"""
    pattern = os.path.join(os.path.abspath(PATENTS_DIR), 'patent_*')
    dirs = sorted(glob.glob(pattern))
    results = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        if filter_name and filter_name not in os.path.basename(d):
            continue
        brief = os.path.join(d, 'brief.md')
        if os.path.isfile(brief):
            results.append((d, brief))
    return results


def generate_for_patent(patent_dir, brief_path):
    """为单个专利生成图片。"""
    patent_name = os.path.basename(patent_dir)
    figures_dir = os.path.join(patent_dir, 'figures')
    os.makedirs(figures_dir, exist_ok=True)

    specs = parse_figure_specs(brief_path)
    if not specs:
        print(f"  {patent_name}: brief.md 中未找到图片需求段落，跳过")
        return 0

    print(f"\n{patent_name}: 共 {len(specs)} 张图片待生成")
    ok = 0
    for fig_name, desc in specs:
        output_path = os.path.join(figures_dir, f'{fig_name}_0.png')
        if os.path.exists(output_path):
            print(f"  ✓ 已存在，跳过: {fig_name}")
            ok += 1
            continue

        prompt = f"{STYLE_PROMPT}\nDiagram description: {desc}"
        print(f"  生成中: {fig_name} ...")
        try:
            paths = generate_images_with_remote_api(
                prompt=prompt,
                output_dir=figures_dir,
                output_name_prefix=fig_name,
            )
            if paths:
                ok += 1
                print(f"  ✓ 成功: {fig_name}")
            else:
                print(f"  ✗ 未返回图片: {fig_name}")
            time.sleep(2)  # 避免 API 限速
        except Exception as e:
            print(f"  ✗ 失败: {fig_name}: {e}")

    print(f"  {patent_name} 完成: {ok}/{len(specs)}")
    return ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description='根据 brief.md 生成专利插图')
    parser.add_argument('filter', nargs='?', default=None,
                        help='可选：只处理匹配的专利，如 patent_06')
    args = parser.parse_args()

    print("=" * 60)
    print("专利插图生成工具")
    print("=" * 60)

    patents = discover_patents(args.filter)
    if not patents:
        print("  未发现含 brief.md 的专利目录。")
        print(f"  搜索路径: {os.path.abspath(PATENTS_DIR)}/patent_*/")
        sys.exit(1)

    total = 0
    for patent_dir, brief_path in patents:
        count = generate_for_patent(patent_dir, brief_path)
        total += count

    print()
    print("=" * 60)
    print(f"完成！共生成 {total} 张插图。")
    print("=" * 60)


if __name__ == '__main__':
    main()
