# 专利交底书项目

## 项目概述
以 Markdown 为源文件，填充到 `发明专利技术交底书模板.docx` 模板中，生成含 OMML 原生公式和技术插图的 Word 文档。支持任意技术领域。

## 目录结构

```
zhuanli/
├── patents/                               # 新专利工作区
│   └── patent_<NN>_<主题>_<日期>/
│       ├── brief.md                       #   技术素材（结构化输入）
│       ├── patent_<NN>_disclosure.md      #   交底书 Markdown 源
│       ├── patent_<NN>_disclosure.docx    #   Word 交付版（基于模板）
│       └── figures/                       #   该专利插图
├── archive/                               # 已定版专利归档（只读）
├── tools/                                 # 工具
│   ├── fill_template.py                   #   ★ 主工具：填充模板+公式+插图
│   ├── gen_figures.py                     #   文生图
│   ├── md_to_docx.py                      #   简易 Markdown→DOCX（无模板）
│   ├── insert_figures.py                  #   独立插图工具
│   └── remote_image_generator.py          #   图片 API 封装
├── 发明专利技术交底书模板.docx            #   ★ Word 模板（必需）
└── archive_tools/                         # 旧工具归档
```

## 新增专利流程

1. 创建目录 `patents/patent_<NN>_<主题>_<日期>/`
2. 编写 `brief.md` — 技术素材
3. 撰写 `patent_<NN>_disclosure.md` — 章节必须匹配模板结构
4. 生成插图并填充模板：

```bash
python tools/gen_figures.py patent_06      # 根据 brief.md 生成插图到 figures/
python tools/fill_template.py patent_06    # 填充模板，图文交叉插入，输出 DOCX
```

## disclosure.md 章节结构

必须包含以下章节（与模板一一对应）：

```
## 交底书名称
## 缩略语和关键术语定义
## 1、*本发明的技术关键点（欲保护点）
## 2、*与本发明最相近的现有技术
### 2.1 现有技术的技术方案
### 2.2 现有技术缺点及本发明解决的问题
## 3、*本发明技术方案的详细阐述
### 3.1 产品侧
### 3.2 技术侧
## 4、*技术方案所产生的有益效果
## 5、发散思维，针对3中的技术方案，是否还有其他别的替代方案
## 附件参考文献
```

目标篇幅 ~5000 字。公式用 `$$...$$`（块级）和 `\(...\)`（行内）。

## 技术要点
- 公式：LaTeX → MathML → OMML（Word 原生可编辑公式）
- 模板操作：`lxml` 直接操作 OOXML
- 依赖：`latex2mathml`, `mathml2omml`, `lxml`
- 插图：Gemini text-to-image API，黑白线条技术示意图
