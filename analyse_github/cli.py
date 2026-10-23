"""analyse-github — 一条命令分析 GitHub 开源项目，生成结构化报告（Markdown / HTML）。

用法：
    analyse-github <owner/repo 或 URL> [-o FILE] [--format md|html] [--token TOKEN] [--json]
    analyse-github --compare <A> <B> [<C> ...] [-o FILE] [--format md|html]
"""

from __future__ import annotations

import argparse
import html
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

_FOOTER_MD = "\n".join([
    "> 本报告由 [analyse-github](https://github.com/seanfalling/analyse_github) 自动生成。",
    "> 如需结合具体用途评估适用性与替代方案，请把本报告 + 你的用途发给 AI。",
])


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


def _metrics(r):
    """把 analyze() 的原始结果整理成渲染层需要的展示字段。"""
    repo = r["repo"]
    full = repo.get("full_name", "")
    pushed = repo.get("pushed_at")
    days = _days_ago(pushed) if pushed else None
    is_fork = repo.get("fork", False)

    langs = r["languages"]
    total = sum(langs.values()) or 1
    lang_line = "、".join(
        f"{k} {v * 100 // total}%"
        for k, v in sorted(langs.items(), key=lambda x: -x[1])[:6]
    ) or "-"

    community = r["community"] if isinstance(r["community"], dict) else {}
    files = community.get("files") or {}

    latest = r["latest_release"]

    health_files = [
        (label, bool(files.get(key)))
        for key, label in [
            ("readme", "README"),
            ("license", "LICENSE"),
            ("contributing", "CONTRIBUTING"),
            ("code_of_conduct", "CODE_OF_CONDUCT"),
            ("issue_template", "Issue 模板"),
            ("pull_request_template", "PR 模板"),
        ]
    ]

    return {
        "full": full,
        "url": repo.get("html_url", ""),
        "desc": repo.get("description") or "（无描述）",
        "topics": repo.get("topics") or [],
        "license": (repo.get("license") or {}).get("spdx_id") or "无",
        "homepage": repo.get("homepage") or "-",
        "pushed": _fmt_date(pushed),
        "status": _status(repo, days),
        "is_fork": is_fork,
        "parent": repo.get("parent", {}).get("full_name", "-") if is_fork else None,
        "stars": _fmt_num(repo.get("stargazers_count")),
        "forks": _fmt_num(repo.get("forks_count")),
        "watchers": _fmt_num(repo.get("subscribers_count")),
        "language": repo.get("language") or "-",
        "default_branch": repo.get("default_branch") or "-",
        "created": _fmt_date(repo.get("created_at")),
        "updated": _fmt_date(repo.get("updated_at")),
        "open_issues": _fmt_num(repo.get("open_issues_count")),
        "contributors": _fmt_num(r["contributors_count"]),
        "releases": _fmt_num(r["releases_count"]),
        "latest_tag": latest.get("tag_name") if latest else "-",
        "latest_date": _fmt_date(latest.get("published_at")) if latest else "-",
        "health": community.get("health_percentage"),
        "lang_line": lang_line,
        "health_files": health_files,
    }


def _overview_rows(m):
    rows = [
        ("Star", m["stars"]),
        ("Fork", m["forks"]),
        ("Watcher", m["watchers"]),
        ("主语言", m["language"]),
        ("License", m["license"]),
        ("主题标签", " ".join("`" + t + "`" for t in m["topics"]) if m["topics"] else "-"),
        ("主页", m["homepage"]),
        ("默认分支", m["default_branch"]),
        ("创建时间", m["created"]),
        ("最近推送", m["pushed"]),
        ("最近更新", m["updated"]),
    ]
    if m["is_fork"]:
        rows.append(("上游仓库", m["parent"]))
    return rows


# ---------------- Markdown ----------------

def _sections_md(m):
    lines = ["## 1. 项目概览", "", "| 项 | 值 |", "| --- | --- |"]
    for k, v in _overview_rows(m):
        lines.append(f"| {k} | {v} |")
    lines += [
        "", "## 2. 技术栈与语言构成", "",
        m["lang_line"], "",
        "## 3. 质量与维护度", "",
        f"- 维护状态：{m['status']}",
        f"- 未关闭 issue（含 PR）：{m['open_issues']}",
        f"- 贡献者数量：{m['contributors']}",
        f"- Releases 数量：{m['releases']}（最新 {m['latest_tag']}，{m['latest_date']}）",
        f"- 社区健康分：{m['health'] if m['health'] is not None else '-'}%",
        "",
        "## 4. 仓库健康文件", "",
        "| 文件 | 是否存在 |", "| --- | --- |",
    ]
    for label, ok in m["health_files"]:
        lines.append(f"| {label} | {'✅' if ok else '❌'} |")
    return "\n".join(lines)


def render_markdown(m):
    return "\n".join([
        f"# {m['full']} 分析报告", "",
        f"**结论（先行）**：{m['status']}", "",
        f"- 仓库：{m['url']}",
        f"- 描述：{m['desc']}", "",
        _sections_md(m), "",
        "---", "",
        _FOOTER_MD,
    ])


def _compare_rows(ms):
    def health(m):
        return m["health"] if m["health"] is not None else "-"

    specs = [
        ("维护状态", lambda m: m["status"]),
        ("Star", lambda m: m["stars"]),
        ("Fork", lambda m: m["forks"]),
        ("主语言", lambda m: m["language"]),
        ("License", lambda m: m["license"]),
        ("最近推送", lambda m: m["pushed"]),
        ("贡献者", lambda m: m["contributors"]),
        ("Releases", lambda m: m["releases"]),
        ("社区健康分", health),
    ]
    return [(label, [fn(m) for m in ms]) for label, fn in specs]


def render_markdown_compare(ms):
    title = " vs ".join(m["full"] for m in ms)
    lines = [
        f"# {title} 对比报告", "",
        "## 对比总览", "",
        "| 指标 | " + " | ".join(m["full"] for m in ms) + " |",
        "| --- | " + " | ".join("---" for _ in ms) + " |",
    ]
    for label, vals in _compare_rows(ms):
        lines.append("| " + label + " | " + " | ".join(str(v) for v in vals) + " |")
    lines += ["", "## 详细报告", ""]
    for m in ms:
        lines += [f"### {m['full']}", "", _sections_md(m), ""]
    lines += ["---", "", _FOOTER_MD]
    return "\n".join(lines)


# ---------------- HTML ----------------

def _esc(s):
    return html.escape(str(s))


_CSS = """
body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #24292f; line-height: 1.6; }
h1 { font-size: 1.7rem; border-bottom: 1px solid #d0d7de; padding-bottom: .5rem; }
h2 { font-size: 1.3rem; margin-top: 2rem; border-bottom: 1px solid #d0d7de; padding-bottom: .3rem; }
h3 { font-size: 1.1rem; margin-top: 1.5rem; }
table { border-collapse: collapse; width: 100%; margin: .8rem 0; }
th, td { border: 1px solid #d0d7de; padding: .45rem .7rem; text-align: left; font-size: .92rem; }
th { background: #f6f8fa; }
.verdict { font-size: 1.1rem; font-weight: 600; margin: .5rem 0 1rem; }
.ok { color: #1a7f37; } .no { color: #cf222e; }
.meta { color: #57606a; }
footer { color: #57606a; font-size: .85rem; margin-top: 2rem;
         border-top: 1px solid #d0d7de; padding-top: 1rem; }
"""


def _html_page(title, body):
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""


def _sections_html(m):
    rows_html = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in _overview_rows(m)
    )
    health_html = "".join(
        f"<tr><td>{_esc(label)}</td><td class=\"{'ok' if ok else 'no'}\">{'✅' if ok else '❌'}</td></tr>"
        for label, ok in m["health_files"]
    )
    health = m["health"] if m["health"] is not None else "-"
    return f"""
<h2>1. 项目概览</h2>
<table>{rows_html}</table>

<h2>2. 技术栈与语言构成</h2>
<p>{_esc(m['lang_line'])}</p>

<h2>3. 质量与维护度</h2>
<ul>
<li>维护状态：{_esc(m['status'])}</li>
<li>未关闭 issue（含 PR）：{_esc(m['open_issues'])}</li>
<li>贡献者数量：{_esc(m['contributors'])}</li>
<li>Releases 数量：{_esc(m['releases'])}（最新 {_esc(m['latest_tag'])}，{_esc(m['latest_date'])}）</li>
<li>社区健康分：{_esc(health)}%</li>
</ul>

<h2>4. 仓库健康文件</h2>
<table><tr><th>文件</th><th>是否存在</th></tr>{health_html}</table>
"""


def render_html(m):
    body = f"""
<h1>{_esc(m['full'])} 分析报告</h1>
<p class="verdict">结论（先行）：{_esc(m['status'])}</p>
<p class="meta">仓库：<a href="{_esc(m['url'])}">{_esc(m['url'])}</a> · {_esc(m['desc'])}</p>
{_sections_html(m)}
<footer>本报告由 <a href="https://github.com/seanfalling/analyse_github">analyse-github</a> 自动生成。
如需结合具体用途评估适用性与替代方案，请把本报告 + 你的用途发给 AI。</footer>
"""
    return _html_page(f"{m['full']} 分析报告", body)


def render_html_compare(ms):
    title = " vs ".join(m["full"] for m in ms)
    header_cells = "".join(f"<th>{_esc(m['full'])}</th>" for m in ms)
    rows_html = ""
    for label, vals in _compare_rows(ms):
        cells = "".join(f"<td>{_esc(v)}</td>" for v in vals)
        rows_html += f"<tr><th>{_esc(label)}</th>{cells}</tr>"
    detail = ""
    for m in ms:
        detail += f"\n<h2>详细报告 · {_esc(m['full'])}</h2>\n{_sections_html(m)}"
    body = f"""
<h1>{_esc(title)} 对比报告</h1>
<h2>对比总览</h2>
<table><tr><th>指标</th>{header_cells}</tr>{rows_html}</table>
{detail}
<footer>本报告由 <a href="https://github.com/seanfalling/analyse_github">analyse-github</a> 自动生成。</footer>
"""
    return _html_page(f"{title} 对比报告", body)


# ---------------- CLI ----------------

def main(argv=None):
    # Windows 控制台默认 GBK，无法输出 emoji/部分中文，强制 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="analyse-github",
        description="一条命令分析 GitHub 开源项目，生成结构化报告（Markdown / HTML）",
    )
    parser.add_argument("targets", nargs="*", help="仓库 owner/repo 或完整 URL；--compare 时给两个及以上")
    parser.add_argument("--compare", action="store_true", help="横向对比多个仓库（至少两个）")
    parser.add_argument("-o", "--output", help="写入文件（默认输出到 stdout）")
    parser.add_argument("--format", choices=["md", "html"],
                        help="输出格式；默认按 -o 扩展名推断，否则 md")
    parser.add_argument("--token", help="GitHub token（默认读 GITHUB_TOKEN 环境变量）")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = parser.parse_args(argv)

    if args.compare:
        if len(args.targets) < 2:
            parser.error("--compare 需要至少两个目标，例如：analyse-github --compare openai/whisper openai/gpt-2")
    elif len(args.targets) != 1:
        parser.error("请提供一个目标仓库；或加 --compare 后提供至少两个，例如：analyse-github torvalds/linux")

    token = args.token or os.environ.get("GITHUB_TOKEN") or None
    try:
        parsed = [_parse_target(t) for t in args.targets]
        results = [analyze(o, r, token) for o, r in parsed]
        metrics = [_metrics(x) for x in results]
    except (GHError, ValueError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    fmt = args.format
    if fmt is None:
        fmt = "html" if (args.output and args.output.lower().endswith(".html")) else "md"

    if args.json:
        text = json.dumps(results if args.compare else results[0], ensure_ascii=False, indent=2)
    elif args.compare:
        text = render_markdown_compare(metrics) if fmt == "md" else render_html_compare(metrics)
    else:
        text = render_markdown(metrics[0]) if fmt == "md" else render_html(metrics[0])

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"✓ 报告已写入 {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
