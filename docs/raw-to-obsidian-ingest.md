# Raw 资料自动入库 Obsidian

## 你要做什么

把资料放到：

```text
<A2A_PROJECT_ROOT>/raw
```

支持：

```text
.txt
.md
.markdown
.csv
.tsv
.xlsx
.xlsm
.docx
.pdf
.pptx
.json
.jsonl
.html
.htm
.xml
.yaml
.yml
.log
```

然后在前端说：

```text
请把 raw 目录里的资料整理进 Obsidian 知识库
```

或者指定文件：

```text
请把 raw/sample-supplier-note.txt 整理进 Obsidian 知识库
```

系统会生成 Markdown 页面到：

```text
<A2A_PROJECT_ROOT>/wiki
```

并自动更新：

```text
<A2A_PROJECT_ROOT>/wiki/index.md
```

## 当前实现方式

当前入库工具会：

1. 读取 raw 文件。
2. 解析常见办公文档：Excel 多 sheet、有效行列扫描、字段识别、公式提示；Word 段落和表格；PPT 幻灯片文本和备注；PDF 页面文本。
3. 根据文件名和内容自动分类到 products / suppliers / sop / platform-rules / ad-strategy / decisions / logs。
4. 生成 Markdown 页面。
5. 在页面里保留 YAML frontmatter、source、summary、key facts、raw extract。
6. 更新 wiki 首页。
7. 写入一条 decisions 记录作为入库日志。

## 注意

- 不要把 API Key、密码、银行信息放入 raw。
- 大型 PDF 建议先拆分或转换成文本。
- 扫描版 PDF 或图片型 PPT 需要 OCR，当前只提取可复制文本。
- 入库后的页面最好在 Obsidian 中人工快速扫一眼，补充双链和业务判断。
