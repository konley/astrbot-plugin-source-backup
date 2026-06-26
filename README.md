# AstrBot 插件源提交记录备份

自动抓取 [AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection) 中所有开放的插件提交 issue，生成插件索引 JSON。

## 订阅地址

```
https://raw.githubusercontent.com/konley/astrbot-plugin-source-backup/main/plugin_source.json
```

可在 AstrBot WebUI 的「插件源管理」中添加此地址作为第三方插件源。

## 文件结构

```
├── plugin_source.json              # 最新数据（固定名，用于订阅）
├── sync_plugin_source.py           # 抓取脚本
└── backup/
    └── plugin_source_YYYY-MM-DD.json  # 每日快照
```

## 使用方式

```bash
python sync_plugin_source.py
```

脚本会自动：
1. 抓取所有 open issue
2. 解析 issue body 中的 Plugin Info JSON
3. 生成 `plugin_source.json`
4. 复制一份带日期的快照到 `backup/`

## 数据来源

GitHub Issues: [AstrBotDevs/AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection/issues)
