# analyse_github

一套「分析 GitHub 开源项目」的工具包：**需求模板 + AI Agent 工作流 + 命令行工具 + GitHub Action**。

> 解决痛点：每次分析 GitHub 项目都要重复说明"分析什么、产出什么、装不装要确认"。这个仓库把流程固定下来，还提供了自动出报告的工具。

[English](#english) · 中文

---

## 组件

| 组件 | 作用 |
| --- | --- |
| `analyse-github` CLI | 一条命令直接生成结构化分析报告 |
| `.github/workflows/analyse.yml` | GitHub Action，定时/手动自动生成报告 |
| `prompt/analyse-github.md` | 粘贴给 AI 的需求模板（最小输入） |
| `AGENTS.md` | AI 编码代理自动加载的工作流指令 |

## 一、CLI 工具

一条命令，直接拉取 GitHub 真实数据并生成 Markdown 报告。

### 安装
```bash
pip install git+https://github.com/seanfalling/analyse_github.git
# 或本地安装
git clone https://github.com/seanfalling/analyse_github.git
cd analyse_github && pip install .
```

### 使用
```bash
analyse-github torvalds/linux
analyse-github https://github.com/ggerganov/llama.cpp
analyse-github openai/whisper -o report.md        # 写入 Markdown
analyse-github openai/whisper -o report.html      # 写入 HTML（按扩展名自动识别）
analyse-github openai/whisper --format html        # 直接输出 HTML 到终端
analyse-github --compare openai/whisper openai/gpt-2        # 对比两个仓库
analyse-github --compare A B -o compare.html                  # 对比并输出 HTML
analyse-github openai/whisper --json              # 输出原始 JSON
```

支持 `owner/repo` 或完整 URL。`-o` 以 `.html` 结尾自动输出 HTML，否则输出 Markdown；也可用 `--format md|html` 显式指定。报告包含：

1. **项目概览** — star/fork/license/主题/时间线/是否 fork/归档
2. **技术栈与语言构成** — 语言占比
3. **质量与维护度** — 维护状态、issue 数、贡献者、releases
4. **仓库健康文件** — README/LICENSE/CONTRIBUTING 等是否齐全

> 结论先行：报告顶部直接给出维护活跃度判定（🟢🟡🟠🔴）。

### 认证（可选）
默认用匿名 API（60 次/小时）。想提高限额或分析私有仓库：
```bash
export GITHUB_TOKEN=ghp_xxx
analyse-github owner/repo
```

## 二、GitHub Action

对指定仓库自动生成分析报告，无需本地环境。

### 手动触发
在仓库 **Actions → "Analyse GitHub repository" → Run workflow**，填目标仓库即可，报告作为 Artifact 下载并展示在 Summary 里。

### 定时触发
1. Fork 本仓库
2. 在 **Settings → Secrets and variables → Actions → Variables** 添加 `TARGET_REPO`（值如 `torvalds/linux`）
3. 工作流默认每周日自动运行，报告作为 Artifact 产出

> 分析**私有**仓库时，需在 Settings → Secrets → Actions 添加带 `repo` 权限的 PAT，命名为 `GITHUB_TOKEN`（覆盖默认 token）。

## 三、需求模板 + AI 工作流

想让 AI 结合你的具体用途做判断（适用性、替代品对比），把 CLI 报告 + 你的用途一起发给 AI，或直接用：

- 粘贴 [`prompt/analyse-github.md`](prompt/analyse-github.md) 模板
- 把 [`AGENTS.md`](AGENTS.md) 放进项目根目录，AI 编码代理自动加载

### 默认流程（AI 自动执行）
1. 项目概览 → 2. 技术栈与架构 → 3. 质量与维护 → 4. 安全与合规 → 5. 适用性 → 6. 结论与建议

**确认规则**：涉及 clone/install/运行/改环境时，先给方案等确认，绝不擅自操作。

## License

[MIT](LICENSE)

---

## English

A toolkit for analyzing GitHub open-source projects: **prompt template + AI-agent workflow + CLI + GitHub Action**.

- `analyse-github <owner/repo>` — one-command structured Markdown report (stars, license, activity, languages, health files)
- `.github/workflows/analyse.yml` — scheduled/manual auto-report generation
- `prompt/analyse-github.md` + `AGENTS.md` — reusable AI workflow

```bash
pip install git+https://github.com/seanfalling/analyse_github.git
analyse-github torvalds/linux
```

MIT Licensed.
