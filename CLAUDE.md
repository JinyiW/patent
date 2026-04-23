# CODEBUDDY.md

## Project Overview
专利交底书撰写项目。以 Markdown 为源，转换为 Word DOCX（含 OMML 原生可编辑公式 + 技术插图）。支持任意技术领域，不限主题。

## 已归档专利（只读）
`archive/` 下的 patent_01~05 已定版，**不得修改**，除非用户明确要求。

## 新专利工作流

### 1. 准备技术素材
在 `patents/patent_<NN>_<topic>_<date>/` 下创建 `brief.md`，结构化描述：
- 名称候选、技术问题、核心创新点、输入/输出、方法流程
- 可选：图片需求（用于文生图）

### 2. 撰写交底书
按 `专利撰写要求模板.md` 撰写 `patent_<NN>_disclosure.md`（12 必要章节，~5000 字）。

### 3. 转换为 DOCX
```bash
python tools/md_to_docx.py                # 转换所有新专利
python tools/md_to_docx.py patent_06      # 只转换指定专利
```

### 4. 生成并插入插图（可选）
```bash
python tools/gen_figures.py patent_06     # 根据 brief.md 生成图片到 figures/
python tools/insert_figures.py patent_06  # 将 figures/ 中的图片插入 DOCX
```

## 目录结构

```
zhuanli/
├── patents/                           # 新专利工作区
│   └── patent_<NN>_<topic>_<date>/
│       ├── brief.md                   #   技术素材输入
│       ├── patent_<NN>_disclosure.md  #   交底书源文件
│       ├── patent_<NN>_disclosure.docx#   Word 交付版
│       └── figures/                   #   该专利图片
├── archive/                           # 已定版专利（只读）
├── tools/                             # 泛化工具
│   ├── md_to_docx.py                  #   Markdown → DOCX
│   ├── insert_figures.py              #   插图插入
│   ├── gen_figures.py                 #   文生图
│   └── remote_image_generator.py      #   图片 API 封装
├── 专利撰写要求模板.md                # 通用写作规范
└── 发明专利技术交底书模板.docx        # Word 模板
```

每件专利独立成文，不混写技术方案。

## Markdown Authoring Conventions
- `## Section` → Heading 1 (黑体 16pt), `### Subsection` → Heading 2 (黑体 14pt)
- `#### Sub-subsection` → Heading 3 (黑体 12pt)
- Block formulas: `$$...$$`; inline formulas: `\(...\)`
- `**bold text**` → bold runs in DOCX
- Anonymization is mandatory: no personal names, phone numbers, emails

## 技术栈
- 公式：LaTeX → MathML → OMML（`latex2mathml` + `mathml2omml`）
- 文档：`python-docx` + `lxml`
- 插图：Gemini text-to-image API
