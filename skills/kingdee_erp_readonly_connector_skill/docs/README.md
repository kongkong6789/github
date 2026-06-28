# 金蝶只读运行说明

项目运行时不直接加载桌面版金蝶写入脚本。本目录只保留只读 Skill 描述和环境变量模板，后端 connector 会按 Tool Registry / MCP policy 的只读白名单访问金蝶 WebAPI。

如需查看历史桌面包、导入模板或写入脚本，请到 `vendor/reference-only/kingdee_erp_desktop_skill` 人工查阅；该目录不参与 Agent 运行时治理扫描。
