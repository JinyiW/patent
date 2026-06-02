---
name: patent-image-gen
description: Use this skill when the user wants to generate images, figures, illustrations, or diagrams for patents. Trigger phrases include "生成图片", "生成插图", "文生图", "generate figures", "patent figures", "画图", "插图生成", or mentions generating images for a specific patent like "patent_06 的图". Also trigger when the user asks to regenerate, replace, or update patent figures.
allowed-tools: Read, Write, Bash
---

# Patent Figure Generation Skill

You are an expert at generating technical patent illustrations using the GPT-Image-2 API (Azure proxy).

## Quick Commands

### Generate figures for a specific patent
```bash
cd /data/zhuanli && python tools/gen_figures.py patent_06
```

### Generate figures for all patents with brief.md
```bash
cd /data/zhuanli && python tools/gen_figures.py
```

### Generate a single image with custom prompt
```bash
cd /data/zhuanli && python tools/remote_image_generator.py --prompt "A clean black-and-white technical diagram showing..." --output-dir ./img --output-prefix my_figure
```

### Switch to Gemini backend (fallback)
```bash
cd /data/zhuanli && python tools/remote_image_generator.py --prompt "..." --backend gemini --output-dir ./img --output-prefix my_figure
```

## How It Works

1. **`gen_figures.py`** reads `brief.md` in each patent directory, parses the `# 图片需求` section, and calls `remote_image_generator.py` for each figure
2. **`remote_image_generator.py`** defaults to **GPT-Image-2** (Azure) backend with `quality=low`
3. Generated PNGs are saved to `patents/patent_XX/figures/`
4. Existing figures are skipped (delete to regenerate)

## brief.md Figure Spec Format

```markdown
# 图片需求
- fig_1_system_architecture: 系统整体架构图，展示各模块之间的关系
- fig_2_method_flowchart: 方法整体流程图，展示输入到输出的完整步骤
```

## Style Guidelines

For patent technical diagrams, prepend this to prompts:
> Generate a clean, black-and-white technical diagram suitable for a patent disclosure document. Use simple lines, boxes, and arrows. Label all elements in Chinese. The style should be minimalist, professional, and clearly readable when printed. Do NOT use colors, gradients, or decorative elements.

## API Details

- **Default backend**: GPT-Image-2 via Azure proxy (`api.gameai-llm.woa.com`)
- **Quality**: `low` (stable; `medium` may return 500 errors)
- **Size**: 1024x1024
- **Fallback**: Gemini (`gemini-3.1-flash-image-preview`) via `--backend gemini`
- **Timeout**: 600s (image generation can be slow)
