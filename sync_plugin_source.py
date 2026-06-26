#!/usr/bin/env python3
"""
AstrBot 官方插件源提交记录抓取脚本
从 https://github.com/AstrBotDevs/AstrBot_Plugins_Collection/issues 获取所有 open 的提交，
解析 issue body 中的 JSON 模板，生成 plugin_source.json（最新），同时复制带日期的到 backup/。
"""
import urllib.request
import json
import os
import shutil
import re
from datetime import date

API_BASE = "https://api.github.com/repos/AstrBotDevs/AstrBot_Plugins_Collection/issues"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
LATEST_FILE = os.path.join(BASE_DIR, "plugin_source.json")


def ensure_dirs():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def fetch_all_issues():
    page = 1
    all_issues = []
    while True:
        url = f"{API_BASE}?state=open&per_page=100&page={page}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "astrbot-plugin-source-backup")
        data = json.loads(urllib.request.urlopen(req).read())
        if not data:
            break
        all_issues.extend(data)
        page += 1
    return all_issues


def extract_json_from_body(body):
    """从 issue body 中提取 ```json ... ``` 块并解析"""
    if not body:
        return None
    match = re.search(r"```json\s*\n(.*?)\n```", body, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def build_source(issues):
    source = {}
    for issue in issues:
        title = issue["title"].replace("[Plugin] ", "").strip()
        if not title or title == "YOUR PLUGIN NAME":
            continue

        author = issue["user"]["login"]
        info = extract_json_from_body(issue.get("body", ""))

        if info:
            # 优先用 body 中的字段
            entry = {
                "display_name": info.get("display_name", ""),
                "desc": info.get("desc", ""),
                "author": info.get("author", author),
                "repo": info.get("repo", f"https://github.com/{author}/{title}"),
            }
            tags = info.get("tags")
            if tags:
                entry["tags"] = tags
        else:
            # 退化：从标题和作者构造
            entry = {
                "display_name": "",
                "desc": "",
                "author": author,
                "repo": f"https://github.com/{author}/{title}",
            }

        source[title] = entry

    return source


def main():
    ensure_dirs()

    print("正在抓取官方插件源提交记录...")
    issues = fetch_all_issues()
    print(f"抓到 {len(issues)} 条记录")

    source = build_source(issues)

    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)
    print(f"已保存: plugin_source.json  ({len(source)} 个插件)")

    today = date.today().strftime("%Y-%m-%d")
    backup_name = f"plugin_source_{today}.json"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(LATEST_FILE, backup_path)
    print(f"已存档: backup/{backup_name}")

    print("订阅地址: https://raw.githubusercontent.com/konley/astrbot-plugin-source-backup/main/plugin_source.json")


if __name__ == "__main__":
    main()
