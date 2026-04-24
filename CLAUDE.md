# CODEBUDDY.md

## Project Overview
专利交底书撰写项目。以 Markdown 为源，填充到 `发明专利技术交底书模板.docx` 模板中，生成含 OMML 原生公式和技术插图的 Word 文档。支持任意技术领域。

## 已归档专利（只读）
`archive/` 下的 patent_01~05 已定版，**不得修改**，除非用户明确要求。

## 新专利工作流

### 1. 准备技术素材
在 `patents/patent_<NN>_<topic>_<date>/` 下创建 `brief.md`，结构化描述技术方案要点。

### 2. 撰写交底书
撰写 `patent_<NN>_disclosure.md`，章节结构必须匹配模板：
- `## 交底书名称`
- `## 缩略语和关键术语定义`
- `## 1、*本发明的技术关键点（欲保护点）`
- `## 2、*与本发明最相近的现有技术` → `### 2.1` / `### 2.2`
- `## 3、*本发明技术方案的详细阐述` → `### 3.1 产品侧` / `### 3.2 技术侧`
- `## 4、*技术方案所产生的有益效果`
- `## 5、发散思维...`
- `## 附件参考文献`

目标篇幅 ~5000 字。公式用 `$$...$$`（块级）和 `\(...\)`（行内）。

### 3. 生成插图（可选）
```bash
python tools/gen_figures.py patent_06     # 根据 brief.md 生成到 figures/
```

### 4. 填充模板生成 DOCX
```bash
python tools/fill_template.py patent_06   # 填充到交底书模板，图文交叉插入
python tools/fill_template.py             # 批量处理所有专利
```

`fill_template.py` 会自动：
- 将 disclosure.md 各章节内容填入模板对应位置
- 将 LaTeX 公式转为 OMML 可编辑公式
- 将 figures/ 下的图片交叉插入到 4.1/4.2 章节中
- 输出到专利目录下的 `patent_<NN>_disclosure.docx`

## 目录结构

```
zhuanli/
├── patents/                           # 新专利工作区
│   └── patent_<NN>_<topic>_<date>/
│       ├── brief.md                   #   技术素材输入
│       ├── patent_<NN>_disclosure.md  #   交底书 Markdown 源
│       ├── patent_<NN>_disclosure.docx#   Word 交付版（基于模板）
│       └── figures/                   #   该专利插图
├── archive/                           # 已定版专利（只读）
├── tools/                             # 工具
│   ├── fill_template.py               #   ★ 主工具：填充模板 + 公式 + 插图
│   ├── gen_figures.py                 #   文生图
│   ├── md_to_docx.py                  #   简易 Markdown→DOCX（无模板）
│   ├── insert_figures.py              #   独立插图工具
│   └── remote_image_generator.py      #   图片 API 封装
├── 发明专利技术交底书模板.docx        # ★ Word 模板（必需）
└── archive_tools/                     # 旧工具归档
```

每件专利独立成文，不混写技术方案。

## Markdown 写作规范
- `## Section` / `### Subsection` / `#### Sub-subsection` → 对应模板章节层级
- 块级公式 `$$...$$`，行内公式 `\(...\)`
- `**bold text**` → 加粗
- 匿名化：不出现个人姓名、手机号、邮箱

## 技术栈
- 公式：LaTeX → MathML → OMML（`latex2mathml` + `mathml2omml`）
- 模板操作：`lxml` 直接操作 OOXML
- 插图：Gemini text-to-image API，顶会论文风格（SIGGRAPH/NeurIPS 配色，白底矢量感，非黑白线条）
