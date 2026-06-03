---
name: patent-image-gen
description: Use this skill when the user wants to generate images, figures, illustrations, or diagrams for patents. Trigger phrases include "生成图片", "生成插图", "文生图", "generate figures", "patent figures", "画图", "插图生成", or mentions generating images for a specific patent like "patent_06 的图". Also trigger when the user asks to regenerate, replace, or update patent figures.
allowed-tools: Read, Write, Bash
---

# Patent Figure Generation Skill

You are an expert at generating technical patent illustrations using the GPT-Image-2 API (Azure proxy).

## Environment (本地 macOS 适配)

- 本机没有 `python` 命令，默认 `python3` 为系统 Python 3.9。统一使用**项目本地虚拟环境** `.venv`。
- 首次使用先初始化环境（仅需一次）：
  ```bash
  cd /Users/jinyi/patent && bash setup_env.sh
  ```
- 之后所有命令用 `.venv/bin/python` 调用（无需手动 activate）。
- 项目根目录为 `/Users/jinyi/patent`（旧 Ubuntu 环境为 `/data/zhuanli`，已废弃）。

## Quick Commands

### Generate figures for a specific patent
```bash
cd /Users/jinyi/patent && .venv/bin/python tools/gen_figures.py patent_06
```

### Generate figures for all patents with brief.md
```bash
cd /Users/jinyi/patent && .venv/bin/python tools/gen_figures.py
```

### Generate a single image with custom prompt
```bash
cd /Users/jinyi/patent && .venv/bin/python tools/remote_image_generator.py --prompt "A clean black-and-white technical diagram showing..." --output-dir ./img --output-prefix my_figure
```

### Switch to Gemini backend (fallback)
```bash
cd /Users/jinyi/patent && .venv/bin/python tools/remote_image_generator.py --prompt "..." --backend gemini --output-dir ./img --output-prefix my_figure
```

## Code-drawn flowcharts (matplotlib)

For flowcharts/judgment trees, prefer **code-generated figures** (matplotlib) over text-to-image — they render crisp text and exact orthogonal connectors. See `patents/patent_04_.../figures/gen_fig_4.py` for a reference. CJK fonts available on this Mac: `Arial Unicode MS` / `Hiragino Sans GB` / `Songti SC` / `STHeiti` (set via `plt.rcParams["font.family"]`).

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

(注：当前项目实际多用 `tools/gen_figures.py` 内置的顶会论文风彩色 STYLE_PROMPT；黑白风格为可选。图内文字一律简体中文，禁止出现 `∈` 等数学关系符号——用中文“属于”等替代，仅数学变量符号保留拉丁/希腊字母。)

## API Details

- **Default backend**: GPT-Image-2 via Azure proxy (`api.gameai-llm.woa.com`)
- **Token**: 硬编码于 `tools/remote_image_generator.py` 的 `DEFAULT_TOKEN`，也可用环境变量 `REMOTE_IMAGE_API_TOKEN` 覆盖
- **Quality**: `low` (stable; `medium` may return 500 errors)
- **Size**: 1024x1024
- **Fallback**: Gemini (`gemini-3.1-flash-image-preview`) via `--backend gemini`
- **Timeout**: 600s (image generation can be slow)
- **注意**：两个后端均可能临时不可用（gpt-image-2 偶发 403、Gemini 偶发 504），失败时稍后重试或切换后端。
