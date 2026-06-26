#!/usr/bin/env python3
"""
AstrBot 完整插件源生成脚本
- 从 Issues 抓取插件列表（基础字段）
- 并行抓取每个插件的 metadata.yaml（version, astrbot_version, support_platforms）
- 并行抓取 GitHub Repo API（stars, updated_at）
- 构造 logo URL
- 输出完整插件源 JSON

用法:
  python sync_plugin_source.py                 # 自动读取 .config 或环境变量
  python sync_plugin_source.py --token ghp_xxx # 临时指定 token（单次有效）

首次运行会自动创建 .config 文件，你只需粘贴 token 进去即可。

Token 获取地址: https://github.com/settings/tokens
需要权限: public_repo 即可
"""
import urllib.request
import urllib.error
import json
import os
import re
import shutil
import sys
import argparse
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ==== 方式一：直接在这里填入 token（适合个人使用，git 提交时注意不要暴露）====
# GITHUB_TOKEN = "ghp_你的token"
# =========================================================================
_INLINE_TOKEN = ""

API_BASE = "https://api.github.com/repos/AstrBotDevs/AstrBot_Plugins_Collection/issues"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
LATEST_FILE = os.path.join(BASE_DIR, "plugin_source.json")
CONFIG_FILE = os.path.join(BASE_DIR, ".config")

MAX_WORKERS = 20
REQUEST_TIMEOUT = 15

_CLI_TOKEN = ""


def get_token():
    """读取 GitHub Token，优先级: --token > 脚本内联 > 环境变量 > .config 文件"""
    if _CLI_TOKEN:
        return _CLI_TOKEN
    if _INLINE_TOKEN:
        return _INLINE_TOKEN
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token
    try:
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if token:
                        return token
    except (FileNotFoundError, OSError):
        pass
    return ""


def get_headers():
    headers = {"User-Agent": "astrbot-plugin-source-backup"}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ensure_dirs():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers=get_headers())
        return urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT).read().decode("utf-8")
    except Exception as e:
        return None


def fetch_json(url):
    data = fetch_url(url)
    if data:
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    return None


def fetch_all_issues():
    page = 1
    all_issues = []
    while True:
        url = f"{API_BASE}?state=open&per_page=100&page={page}"
        data = fetch_json(url)
        if not data:
            break
        all_issues.extend(data)
        page += 1
        print(f"  page {page - 1}: {len(data)} issues (total {len(all_issues)})")
    return all_issues


def extract_json_from_body(body):
    if not body:
        return None
    match = re.search(r"```json\s*\n(.*?)\n```", body, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def parse_metadata_yaml(text):
    """Parse metadata.yaml for version, astrbot_version, support_platforms"""
    result = {}
    if HAS_YAML:
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                for key in ("version", "astrbot_version"):
                    val = data.get(key)
                    if val:
                        result[key] = str(val)
                platforms = data.get("support_platforms")
                if platforms and isinstance(platforms, list):
                    result["support_platforms"] = platforms
                return result
        except Exception:
            pass
    # Regex fallback
    for key in ("version", "astrbot_version"):
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
        if m:
            result[key] = m.group(1).strip().strip('"').strip("'")
    platforms = []
    in_section = False
    for line in text.split("\n"):
        if re.match(r"^support_platforms:", line):
            in_section = True
            continue
        if in_section:
            m = re.match(r"^\s*-\s*(.+)$", line)
            if m:
                platforms.append(m.group(1).strip().strip('"').strip("'"))
            elif re.match(r"^\w+:", line):
                in_section = False
    if platforms:
        result["support_platforms"] = platforms
    return result


def parse_repo(repo_url):
    """Extract (owner, repo_name) from a GitHub repo URL"""
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if match:
        return match.group(1), match.group(2).replace(".git", "")
    return None, None


def enrich_plugin(title, info, author):
    """Fetch extra data for one plugin: metadata.yaml + GitHub API"""
    def clean(s):
        return s.strip() if isinstance(s, str) else s

    entry = {
        "display_name": clean(info.get("display_name", title)) if info else title,
        "desc": clean(info.get("desc", "")) if info else "",
        "author": clean(info.get("author", author)) if info else author,
        "repo": clean(info.get("repo", f"https://github.com/{author}/{title}")) if info else f"https://github.com/{author}/{title}",
    }

    tags = info.get("tags") if info else None
    if tags:
        entry["tags"] = tags

    # social_link — not standard in issue body, default to author GitHub profile
    social_link = clean(info.get("social_link", "")) if info else ""
    if not social_link:
        social_link = f"https://github.com/{entry['author'].split(' ')[0]}"
    entry["social_link"] = social_link

    repo_url = entry["repo"]
    owner, repo_name = parse_repo(repo_url)
    if not owner or not repo_name:
        return entry

    # Try to fetch metadata.yaml
    for branch in ("main", "master"):
        yaml_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/metadata.yaml"
        yaml_text = fetch_url(yaml_url)
        if yaml_text:
            meta = parse_metadata_yaml(yaml_text)
            if meta.get("version"):
                entry["version"] = meta["version"]
            if meta.get("astrbot_version"):
                entry["astrbot_version"] = meta["astrbot_version"]
            if meta.get("support_platforms"):
                entry["support_platforms"] = meta["support_platforms"]
            break

    # Fetch GitHub API for stars, updated_at
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    repo_data = fetch_json(api_url)
    if repo_data:
        stars = repo_data.get("stargazers_count")
        if stars is not None:
            entry["stars"] = stars
        updated = repo_data.get("pushed_at") or repo_data.get("updated_at")
        if updated:
            entry["updated_at"] = updated

    # Construct logo URL
    for branch in ("main", "master"):
        logo_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/logo.png"
        # Quick HEAD request to check existence
        try:
            req = urllib.request.Request(logo_url, method="HEAD", headers=get_headers())
            with urllib.request.urlopen(req, timeout=5):
                entry["logo"] = logo_url
                break
        except Exception:
            continue

    return entry


def build_source(issues):
    # First pass: collect basic info from issue body
    plugins = []
    for issue in issues:
        title = issue["title"].replace("[Plugin] ", "").strip()
        if not title or title == "YOUR PLUGIN NAME":
            continue
        author = issue["user"]["login"]
        info = extract_json_from_body(issue.get("body", ""))
        plugins.append((title, info, author))

    print(f"基础信息解析完成，共 {len(plugins)} 个插件，开始并行抓取扩展数据...")

    # Second pass: parallel enrichment
    source = {}
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(enrich_plugin, title, info, author): title
                   for title, info, author in plugins}
        for future in as_completed(futures):
            title = futures[future]
            try:
                entry = future.result()
                source[title] = entry
            except Exception as e:
                # Fallback: keep basic data
                source[title] = {"display_name": "", "desc": "", "author": "", "repo": ""}
            done += 1
            if done % 50 == 0:
                print(f"  [{done}/{len(plugins)}]")

    return source


def _ensure_config_file():
    """如果 .config 不存在则创建模板"""
    if os.path.exists(CONFIG_FILE):
        return

    # 确保 .config 被 gitignore
    gitignore = os.path.join(BASE_DIR, ".gitignore")
    gitignore_content = ""
    if os.path.exists(gitignore):
        with open(gitignore, encoding="utf-8") as f:
            gitignore_content = f.read()
    if ".config" not in gitignore_content:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n.config\n")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("# GitHub Personal Access Token\n")
        f.write("# Get one at: https://github.com/settings/tokens\n")
        f.write("# Required scope: public_repo\n")
        f.write('GITHUB_TOKEN="your_token_here"\n')


def main():
    ensure_dirs()

    # 检查 token 是否可用
    if not get_token():
        _ensure_config_file()
        print("=" * 55)
        print("  No GitHub token found.")
        print("  First time setup:")
        print("  1. Go to https://github.com/settings/tokens")
        print("  2. Generate a classic token with scope: public_repo")
        print("  3. Edit .config file and paste your token:")
        print(f"     {CONFIG_FILE}")
        print("  4. Re-run: python sync_plugin_source.py")
        print("=" * 55)
        sys.exit(1)

    print("=== 步骤 1: 抓取插件提交记录 ===")
    issues = fetch_all_issues()
    print(f"抓到 {len(issues)} 条记录\n")

    print("=== 步骤 2: 构建完整插件源 ===")
    source = build_source(issues)
    print(f"完成: {len(source)} 个插件\n")

    print("=== 步骤 3: 写入文件 ===")
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)
    print(f"已保存: plugin_source.json  ({len(source)} 个插件)")

    today = date.today().strftime("%Y-%m-%d")
    backup_name = f"plugin_source_{today}.json"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(LATEST_FILE, backup_path)
    print(f"已存档: backup/{backup_name}")

    print("\n订阅地址: https://raw.githubusercontent.com/konley/astrbot-plugin-source-backup/main/plugin_source.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AstrBot 插件源生成脚本")
    parser.add_argument("--token", help="GitHub Personal Access Token（临时使用，单次有效）")
    args = parser.parse_args()

    _CLI_TOKEN = args.token or ""
    main()
