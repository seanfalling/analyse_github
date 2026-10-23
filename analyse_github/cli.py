"""analyse-github — 一条命令分析 GitHub 开源项目，生成结构化 Markdown 报告。

用法：
    analyse-github <owner/repo 或 URL> [-o FILE] [--token TOKEN] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
_BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "analyse-github",
}


class GHError(Exception):
    """GitHub API 或网络相关错误。"""


def _headers(token):
    h = dict(_BASE_HEADERS)
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def _get(path, token):
    req = urllib.request.Request(API + path, headers=_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), resp.headers.get("Link", "")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        if e.code == 404:
            raise GHError(f"仓库不存在或无权访问（404）：{path}") from e
        if e.code == 403:
            raise GHError("GitHub API 限流（匿名 60 次/小时）或权限不足，请设置 GITHUB_TOKEN 或 --token 重试。") from e
        raise GHError(f"GitHub API 错误 {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise GHError(f"网络错误：{e.reason}") from e


def _parse_target(raw):
    raw = (raw or "").strip().rstrip("/")
    m = re.match(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/?#]+)", raw)
    if m:
        return m.group(1), m.group(2)
    if "/" in raw and ":" not in raw:
        parts = raw.split("/")
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1]
    raise ValueError("无法解析目标，请使用 owner/repo 或完整 URL，例如：torvalds/linux")


def _last_page(link):
    m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link or "")
    return int(m.group(1)) if m else None


def _days_ago(iso):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def _fmt_date(iso):
    return iso[:10] if iso else "-"


def _fmt_num(n):
    if n is None:
        return "-"
    if isinstance(n, int) and n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def analyze(owner, repo, token):
    data, _ = _get(f"/repos/{owner}/{repo}", token)
    languages, _ = _get(f"/repos/{owner}/{repo}/languages", token)
    contributors, clink = _get(f"/repos/{owner}/{repo}/contributors?per_page=1&anon=true", token)
    releases, rlink = _get(f"/repos/{owner}/{repo}/releases?per_page=1", token)
    try:
        community, _ = _get(f"/repos/{owner}/{repo}/community/profile", token)
    except GHError:
        community = {}

    return {
        "repo": data,
        "languages": languages or {},
        "community": community or {},
        "contributors_count": _last_page(clink) if clink else len(contributors),
        "releases_count": _last_page(rlink) if rlink else len(releases),
        "latest_release": releases[0] if releases else None,
    }


def _status(repo, days):
    if repo.get("archived"):
        return "🔴 已归档（archived），不再维护"
    if repo.get("disabled"):
        return "🔴 已禁用（disabled）"
    if days is None:
        return "⚪ 未知"
    if days <= 30:
        return f"🟢 活跃（最近提交 {days} 天前）"
    if days <= 180:
        return f"🟡 一般（最近提交 {days} 天前）"
    if days <= 365:
        return f"🟠 低频（最近提交 {days} 天前）"
    return f"🔴 停更（最近提交 {days} 天前）"


def render_markdown(r):
    repo = r["repo"]
    full = repo.get("full_name", "")
    url = repo.get("html_url", "")
    desc = repo.get("description") or "（无描述）"
    topics = repo.get("topics") or []
    lic = (repo.get("license") or {}).get("spdx_id") or "无"
    homepage = repo.get("homepage") or "-"
    pushed = repo.get("pushed_at")
    days = _days_ago(pushed) if pushed else None
    status = _status(repo, days)
    is_fork = repo.get("fork", False)

    langs = r["languages"]
    total = sum(langs.values()) or 1
    lang_line = "、".join(
        f"{k} {v * 100 // total}%"
        for k, v in sorted(langs.items(), key=lambda x: -x[1])[:6]
    ) or "-"

    community = r["community"] if isinstance(r["community"], dict) else {}
    files = community.get("files") or {}
    health = community.get("health_percentage")

    latest = r["latest_release"]
    latest_tag = latest.get("tag_name") if latest else "-"
    latest_date = _fmt_date(latest.get("published_at")) if latest else "-"

    lines = [
        f"# {full} 分析报告",
        "",
        f"**结论（先行）**：{status}",
        "",
        f"- 仓库：{url}",
        f"- 描述：{desc}",
        "",
        "## 1. 项目概览",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| Star | {_fmt_num(repo.get('stargazers_count'))} |",
        f"| Fork | {_fmt_num(repo.get('forks_count'))} |",
        f"| Watcher | {_fmt_num(repo.get('subscribers_count'))} |",
        f"| 主语言 | {repo.get('language') or '-'} |",
        f"| License | {lic} |",
        f"| 主题标签 | {' '.join('`' + t + '`' for t in topics) if topics else '-'} |",
        f"| 主页 | {homepage} |",
        f"| 默认分支 | {repo.get('default_branch') or '-'} |",
        f"| 创建时间 | {_fmt_date(repo.get('created_at'))} |",
        f"| 最近推送 | {_fmt_date(pushed)} |",
        f"| 最近更新 | {_fmt_date(repo.get('updated_at'))} |",
    ]
    if is_fork:
        lines.append(f"| 上游仓库 | {repo.get('parent', {}).get('full_name', '-')} |")
    lines += [
        "",
        "## 2. 技术栈与语言构成",
        "",
        lang_line,
        "",
        "## 3. 质量与维护度",
        "",
        f"- 维护状态：{status}",
        f"- 未关闭 issue（含 PR）：{_fmt_num(repo.get('open_issues_count'))}",
        f"- 贡献者数量：{_fmt_num(r['contributors_count'])}",
        f"- Releases 数量：{_fmt_num(r['releases_count'])}（最新 {latest_tag}，{latest_date}）",
        f"- 社区健康分：{health if health is not None else '-'}%",
        "",
        "## 4. 仓库健康文件",
        "",
        "| 文件 | 是否存在 |",
        "| --- | --- |",
    ]
    for key, label in [
        ("readme", "README"),
        ("license", "LICENSE"),
        ("contributing", "CONTRIBUTING"),
        ("code_of_conduct", "CODE_OF_CONDUCT"),
        ("issue_template", "Issue 模板"),
        ("pull_request_template", "PR 模板"),
    ]:
        lines.append(f"| {label} | {'✅' if files.get(key) else '❌'} |")
    lines += [
        "",
        "---",
        "",
        "> 本报告由 [analyse-github](https://github.com/seanfalling/analyse_github) 自动生成。",
        "> 如需结合具体用途评估适用性与替代方案，请把本报告 + 你的用途发给 AI。",
    ]
    return "\n".join(lines)


def main(argv=None):
    # Windows 控制台默认 GBK，无法输出 emoji/部分中文，强制 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="analyse-github",
        description="一条命令分析 GitHub 开源项目，生成结构化 Markdown 报告",
    )
    parser.add_argument("target", help="仓库 owner/repo 或完整 URL，例如 torvalds/linux")
    parser.add_argument("-o", "--output", help="写入文件（默认输出到 stdout）")
    parser.add_argument("--token", help="GitHub token（默认读 GITHUB_TOKEN 环境变量）")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = parser.parse_args(argv)

    token = args.token or os.environ.get("GITHUB_TOKEN") or None
    try:
        owner, repo = _parse_target(args.target)
        result = analyze(owner, repo, token)
    except (GHError, ValueError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    text = json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_markdown(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"✓ 报告已写入 {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
