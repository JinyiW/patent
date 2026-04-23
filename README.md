# 专利交底书项目

## 项目概述
以 Markdown 为源文件，导出 Word DOCX（含 OMML 原生公式 + 技术插图）。支持任意技术领域的专利。

## 目录结构

```
zhuanli/
├── patents/                               # 新专利工作区
│   └── patent_<NN>_<主题>_<日期>/
│       ├── brief.md                       #   技术素材（结构化输入）
│       ├── patent_<NN>_disclosure.md      #   交底书源文件
│       ├── patent_<NN>_disclosure.docx    #   Word 交付版
│       └── figures/                       #   该专利插图
├── archive/                               # 已定版专利归档（只读）
│   ├── back.md                            #   前5件技术要点总表
│   └── patent_01~05_*/                    #   各专利完整文件
├── archive_tools/                         # 旧工具归档（仅用于前5件）
├── tools/                                 # 泛化工具
│   ├── md_to_docx.py                      #   Markdown → DOCX
│   ├── insert_figures.py                  #   插图插入
│   ├── gen_figures.py                     #   文生图
│   └── remote_image_generator.py          #   图片 API 封装
├── 专利撰写要求模板.md                    # 通用写作规范
└── 发明专利技术交底书模板.docx            # Word 模板
```

## 新增专利流程

1. 创建目录 `patents/patent_<NN>_<主题>_<日期>/`
2. 编写 `brief.md` — 技术素材（名称候选、技术问题、创新点、流程等）
3. 撰写 `patent_<NN>_disclosure.md` — 遵循 `专利撰写要求模板.md`
4. 转换并插图：

```bash
python tools/md_to_docx.py patent_06      # Markdown → DOCX
python tools/gen_figures.py patent_06     # 根据 brief.md 生成插图
python tools/insert_figures.py patent_06  # 将插图插入 DOCX
```

## brief.md 格式

```markdown
# 专利名称候选
- 一种基于xxx的xxx方法

# 技术问题
- ...

# 核心创新点
- ...

# 输入/输出
**输入：** ...
**输出：** ...

# 方法流程
1. ...

# 图片需求
- fig_1_system_flow: 系统整体流程图，展示...
- fig_2_xxx: xxx示意图，展示...
```

## 技术要点
- 公式：LaTeX → MathML → OMML（Word 原生可编辑公式）
- 依赖：`python-docx`, `latex2mathml`, `mathml2omml`, `lxml`
- 插图：黑白线条技术示意图，中文标注
