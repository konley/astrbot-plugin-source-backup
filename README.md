# AstrBot 插件源提交记录备份

自动抓取 [AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection) 中所有开放的插件提交 issue，生成插件索引 JSON。

## 订阅地址

```
https://raw.githubusercontent.com/konley/astrbot-plugin-source-backup/main/plugin_source.json
```

可在 AstrBot WebUI 的「插件源管理」中添加此地址作为第三方插件源。

## 文件结构

```
├── .config                       # GitHub Token 配置文件（已 gitignore）
├── plugin_source.json            # 最新 JSON 数据（固定名，用于订阅）
├── plugin_source.md              # 最新 Markdown 表格（方便预览）
├── sync_plugin_source.py         # 抓取脚本
└── backup/
    ├── plugin_source_YYYY-MM-DD.json  # 每日 JSON 快照
    └── plugin_source_YYYY-MM-DD.md    # 每日 MD 快照
```

## Token 配置

脚本需要 GitHub Token 才能调用 API（未认证仅 60 次/小时，认证后 5000 次/小时）。

**方式一：`.config` 文件**（推荐）

首次运行脚本会自动生成 `.config` 文件模板。编辑它：
```ini
GITHUB_TOKEN="ghp_your_token_here"
```

Token 获取地址：https://github.com/settings/tokens（需要 `public_repo` 权限）

**方式二：脚本内联填入**

打开 `sync_plugin_source.py`，在文件头找到：
```python
# GITHUB_TOKEN = "ghp_你的token"
```
去掉注释，填入你的 token。

**方式三：命令行临时指定**

```bash
python sync_plugin_source.py --token ghp_xxx
```

## 使用方式

```bash
python sync_plugin_source.py
```

脚本会自动：
1. 抓取所有 open issue
2. 解析 issue body 中的 Plugin Info JSON
3. 并行抓取每个插件的 metadata.yaml 和 GitHub API 数据
4. 生成 `plugin_source.json`（完整字段：version, stars, logo, updated_at 等）
5. 复制一份带日期的快照到 `backup/`

## 数据来源

GitHub Issues: [AstrBotDevs/AstrBot_Plugins_Collection](https://github.com/AstrBotDevs/AstrBot_Plugins_Collection/issues)
