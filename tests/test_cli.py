"""analyse-github 的单元测试（只测纯逻辑，不依赖网络）。"""

import pytest

from analyse_github import cli


def make_r():
    """构造一个 analyze() 的假返回结果。"""
    return {
        "repo": {
            "full_name": "openai/whisper",
            "html_url": "https://github.com/openai/whisper",
            "description": "Robust Speech Recognition",
            "topics": ["asr", "audio"],
            "license": {"spdx_id": "MIT"},
            "homepage": None,
            "pushed_at": "2026-08-31T00:00:00Z",
            "updated_at": "2026-10-23T00:00:00Z",
            "created_at": "2022-09-16T00:00:00Z",
            "stargazers_count": 111000,
            "forks_count": 13500,
            "subscribers_count": 797,
            "language": "Python",
            "default_branch": "main",
            "open_issues_count": 178,
            "archived": False,
            "disabled": False,
            "fork": False,
        },
        "languages": {"Python": 1000000},
        "community": {
            "health_percentage": 37,
            "files": {
                "readme": {"a": 1},
                "license": {"a": 1},
                "contributing": None,
                "code_of_conduct": None,
                "issue_template": None,
                "pull_request_template": None,
            },
        },
        "contributors_count": 84,
        "releases_count": 13,
        "latest_release": {"tag_name": "v20250625", "published_at": "2025-06-26T00:00:00Z"},
    }


@pytest.fixture
def m():
    return cli._metrics(make_r())


# ---------------- 目标解析 ----------------

def test_parse_target_owner_repo():
    assert cli._parse_target("torvalds/linux") == ("torvalds", "linux")


def test_parse_target_url():
    assert cli._parse_target("https://github.com/openai/whisper") == ("openai", "whisper")


def test_parse_target_url_trailing_and_query():
    assert cli._parse_target("https://github.com/openai/whisper/") == ("openai", "whisper")
    assert cli._parse_target("https://github.com/openai/whisper?tab=readme") == ("openai", "whisper")


@pytest.mark.parametrize("bad", ["nonsense", "a/b/c", "http://example.com/a/b", ""])
def test_parse_target_invalid(bad):
    with pytest.raises(ValueError):
        cli._parse_target(bad)


# ---------------- 格式化 ----------------

def test_fmt_num():
    assert cli._fmt_num(None) == "-"
    assert cli._fmt_num(999) == "999"
    assert cli._fmt_num(1000) == "1.0k"
    assert cli._fmt_num(25000) == "25.0k"
    assert cli._fmt_num(105000) == "105.0k"


def test_fmt_date():
    assert cli._fmt_date("2026-08-31T12:00:00Z") == "2026-08-31"
    assert cli._fmt_date(None) == "-"


def test_last_page():
    link = ('<https://api.github.com/x?per_page=1&page=2>; rel="next", '
            '<https://api.github.com/x?per_page=1&page=84>; rel="last"')
    assert cli._last_page(link) == 84


def test_last_page_absent():
    assert cli._last_page("") is None
    assert cli._last_page('<https://api.github.com/x?page=2>; rel="next"') is None


def test_days_ago_positive():
    assert cli._days_ago("2020-01-01T00:00:00Z") > 0


# ---------------- 维护状态判定 ----------------

def test_status_boundaries():
    assert "🟢" in cli._status({}, 0)
    assert "🟢" in cli._status({}, 30)
    assert "🟡" in cli._status({}, 31)
    assert "🟡" in cli._status({}, 180)
    assert "🟠" in cli._status({}, 181)
    assert "🟠" in cli._status({}, 365)
    assert "🔴" in cli._status({}, 366)


def test_status_archived_disabled_unknown():
    assert "已归档" in cli._status({"archived": True}, 0)
    assert "已禁用" in cli._status({"disabled": True}, 0)
    assert "未知" in cli._status({}, None)


# ---------------- 指标提取 ----------------

def test_metrics(m):
    assert m["full"] == "openai/whisper"
    assert m["stars"] == "111.0k"
    assert m["license"] == "MIT"
    assert m["health"] == 37
    assert m["lang_line"] == "Python 100%"
    files = dict(m["health_files"])
    assert files["README"] is True
    assert files["CONTRIBUTING"] is False


# ---------------- 渲染 ----------------

def test_render_markdown(m):
    out = cli.render_markdown(m)
    assert "# openai/whisper 分析报告" in out
    assert "MIT" in out
    assert "111.0k" in out
    assert "| 项 | 值 |" in out


def test_render_html(m):
    out = cli.render_html(m)
    assert "<title>openai/whisper 分析报告</title>" in out
    assert "<h1>openai/whisper 分析报告</h1>" in out
    assert "<table>" in out


def test_render_html_escapes_special_chars():
    r = make_r()
    r["repo"]["description"] = 'a<b>&"c"'
    out = cli.render_html(cli._metrics(r))
    assert "a&lt;b&gt;&amp;" in out


def test_render_markdown_compare_two():
    m1 = cli._metrics(make_r())
    r2 = make_r()
    r2["repo"]["full_name"] = "openai/gpt-2"
    r2["repo"]["html_url"] = "https://github.com/openai/gpt-2"
    r2["repo"]["archived"] = True
    m2 = cli._metrics(r2)
    out = cli.render_markdown_compare([m1, m2])
    assert "openai/whisper vs openai/gpt-2" in out
    assert "| 指标 | openai/whisper | openai/gpt-2 |" in out
    assert "已归档" in out


def test_render_markdown_compare_three_columns():
    ms = []
    for name in ["a/x", "b/y", "c/z"]:
        r = make_r()
        r["repo"]["full_name"] = name
        ms.append(cli._metrics(r))
    out = cli.render_markdown_compare(ms)
    assert "# a/x vs b/y vs c/z 对比报告" in out
    assert "| 指标 | a/x | b/y | c/z |" in out


def test_render_html_compare():
    m1 = cli._metrics(make_r())
    r2 = make_r()
    r2["repo"]["full_name"] = "openai/gpt-2"
    m2 = cli._metrics(r2)
    out = cli.render_html_compare([m1, m2])
    assert "<h1>openai/whisper vs openai/gpt-2 对比报告</h1>" in out
    assert "<th>openai/whisper</th>" in out
    assert "<th>openai/gpt-2</th>" in out
