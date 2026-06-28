# JackYun OpenAPI 文档抓取

不要再通过页面肉眼看参数，更不要猜字段。统一使用：

`python scripts/fetch_jackyun_openapi_docs.py`

支持几种输入方式：

1. 直接传方法名

```bash
python scripts/fetch_jackyun_openapi_docs.py --method erp.allocate.create --method erp.warehouse.get
```

2. 直接传网页文档链接

```bash
python scripts/fetch_jackyun_openapi_docs.py --url "https://open.jackyun.com/developer/apidocinfo.html?from=self&value=undefined&id=erp.allocate.create&name=true"
```

3. 批量文件输入

```bash
python scripts/fetch_jackyun_openapi_docs.py --urls-file methods.txt
python scripts/fetch_jackyun_openapi_docs.py --methods-file methods.txt
```

4. 拉取开放平台全部公开方法

```bash
python scripts/fetch_jackyun_openapi_docs.py --all-methods --output-dir dist/jackyun_all_docs
```

输出内容：

- `*.raw.json`: 官方文档接口原始返回
- `*.summary.json`: 提炼后的方法摘要、请求参数、响应参数
- `index.json`: 本次抓取的方法索引
- `failures.json`: 抓取失败列表

默认输出目录：

`dist/jackyun_openapi_docs`
