# analyse_github

一套用于「分析 GitHub 开源项目」的**标准需求模板 + AI Agent 工作流**。

> 解决痛点：每次让 AI 分析 GitHub 项目时，都要重复说明"分析什么、产出什么、装不装要确认"。这个仓库把流程固定下来，以后只给 URL + 一句话即可。

[English](#english) · 中文

---

## 这是什么

- **`prompt/analyse-github.md`** — 你粘贴给 AI 的需求模板（最小输入）
- **`AGENTS.md`** — 给 AI 编码代理（Claude Code / Cursor / Codex / Gemini CLI 等）自动加载的工作流指令

## 三种用法

### 用法 1：直接粘贴模板（任何 AI 都可用）
把 [`prompt/analyse-github.md`](prompt/analyse-github.md) 的内容发给 AI，填上仓库 URL 和用途即可。

### 用法 2：放入你的项目，AI 自动生效
```bash
cp AGENTS.md /你的项目/AGENTS.md
```
AI 编码代理会自动读取项目根目录的 `AGENTS.md`。

### 用法 3：写入 AI 的全局配置，永久生效
- **Claude Code / pi**：把 `AGENTS.md` 内容追加到全局 `CLAUDE.md`
- **Cursor**：写入 `.cursor/rules`
- **Codex / Gemini CLI**：写入 `AGENTS.md`

## 默认流程（AI 会自动执行）

1. **项目概览** — 做什么、star/fork、最近提交、license、是否活跃
2. **技术栈与架构** — 语言、框架、模块结构、关键依赖
3. **质量与维护** — 文档、测试、CI、issue/PR 活跃度
4. **安全与合规** — 依赖漏洞、敏感信息、license 适用性
5. **适用性** — 是否符合需求、与替代品对比、上手成本
6. **结论与建议** — 结论先行：值不值得用、风险、替代方案

**产出**：结论 → 分项 → 风险 → 建议（若要安装，附安装步骤 + 依赖 + 坑）

**确认规则**：涉及 clone/install/运行/改环境时，先给方案等确认，绝不擅自操作。

## 最小输入示例

```
项目：https://github.com/xxx/yyy
用途：想用它做本地知识库检索
方式：分析（默认）
```

## License

[MIT](LICENSE)

---

## English

A standard **prompt template + AI-agent workflow** for analyzing GitHub open-source projects.

Stop repeating "what to analyze / what to produce / ask before installing" every time. Just give the repo URL and one sentence about your use case — the workflow handles the rest.

- `prompt/analyse-github.md` — paste-ready requirement template
- `AGENTS.md` — auto-loaded workflow for AI coding agents (Claude Code / Cursor / Codex / Gemini CLI / etc.)

MIT Licensed.
