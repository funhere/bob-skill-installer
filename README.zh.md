# bob-skill-installer

> **一条命令，任意技能，直达 IBM Bob。**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-141%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)]()
[![ruff](https://img.shields.io/badge/ruff-passing-blue.svg)]()

[English](README.md) | [日本語](README.ja.md)

---

`bob-skill-installer` 是驱动 IBM Bob `/install-skill` 斜杠命令的引擎。  
只需将 GitHub / GitLab / Git 仓库或 ZIP 链接传给它，工具将自动完成获取、解析、转换、验证、安装的全流程——零手动操作。

```bash
install-skill https://github.com/obra/superpowers --project
```

就这一行。

---

## 功能亮点

- **广泛的来源支持** — GitHub、GitLab、通用 Git、直接 ZIP URL、本地目录
- **7 种格式转换** — Claude、Cursor、Windsurf、Cline、RooCode、OpenAI GPT、通用 Prompt 仓库
- **全保真安装** — 所有文件按原始路径保留，二进制安全
- **安全门控** — 在任何文件写入前，检测并阻断 `curl | bash`、凭证窃取、破坏性 Shell、MCP 自动信任
- **原子性安装** — 暂存区 → 原子替换；`--upgrade` 保留 `.bak`；崩溃不损坏已有技能
- **IBM Bob 斜杠命令** — 确认优先的对话流程，结合 `anysearch` 驱动的仓库语义理解
- **工程级质量** — `mypy --strict`、`ruff`、141 个测试、覆盖率 92%

---

## 快速开始

### 前置条件

- Python 3.12 或更高版本
- [`uv`](https://docs.astral.sh/uv/)（推荐）或 `pip`
- Git（用于克隆远程仓库）

### 安装

```bash
git clone https://github.com/funhere/bob-skill-installer
cd bob-skill-installer
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 安装第一个技能

```bash
# 安装到项目范围（./.bob/skills/）
install-skill https://github.com/obra/superpowers

# 安装到全局范围（~/.bob/skills/）
install-skill https://github.com/obra/superpowers --global

# 预览所有阶段，不写入磁盘
install-skill https://github.com/obra/superpowers --dry-run

# 在 IBM Bob 中使用斜杠命令
/install-skill https://github.com/obra/superpowers --project
```

---

## 工作原理

流水线包含 8 个独立的、类型化的阶段：

```
      URL
       │
       ▼
┌──────────────┐
│    parse     │  解析源 URL → ParsedSource
└──────┬───────┘
       ▼
┌──────────────┐
│    fetch     │  浅克隆 / ZIP 解压 / 本地复制 → 本地目录
└──────┬───────┘
       ▼
┌──────────────┐
│   analyze    │  遍历文件树，对格式打分 → RepoAnalysis
└──────┬───────┘
       ▼
┌──────────────┐
│   security   │  静态模式扫描 → SecurityReport
└──────┬───────┘   REJECTED → 立即停止，不写入任何内容
       ▼
┌──────────────┐
│   convert    │  格式转换 → BobSkill + SKILL.md
└──────┬───────┘
       ▼
┌──────────────┐
│   validate   │  结构 · 元数据 · Markdown · 链接检查
└──────┬───────┘   FAILED → 中止安装
       ▼
┌──────────────┐
│   install    │  原子写入 → 技能目录
└──────┬───────┘
       ▼
┌──────────────┐
│   report     │  Rich 面板或纯文本摘要
└──────────────┘
```

每个阶段以 Pydantic 模型作为数据契约，可独立测试、独立替换。

| 阶段 | 模块 | 职责 |
|---|---|---|
| parse | `github/url_parser.py` | URL → `ParsedSource` |
| fetch | `github/fetcher.py` | 克隆 / ZIP / 本地复制 |
| analyze | `analyzer/` | 文件清单 + 格式评分 |
| security | `security/scanner.py` | 模式扫描，清点脚本与敏感文件 |
| convert | `converters/` | 7 种格式转换器 + Jinja2 模板 |
| validate | `validators/` | 结构、元数据、Markdown、链接 |
| install | `installer/installer.py` | 原子写入，`--force`/`--upgrade` |
| report | `report.py` | Rich + 纯文本报告 |

---

## 支持的来源与格式

### 来源（优先级顺序）

| 来源 | 示例 |
|---|---|
| GitHub 仓库 | `https://github.com/org/repo` |
| GitHub 子树 | `https://github.com/org/repo/tree/main/skills/writer` |
| GitLab 仓库 | `https://gitlab.com/org/repo` |
| 通用 Git | `https://git.example.com/repo.git` |
| 直接 ZIP URL | `https://example.com/skill.zip` |
| 本地目录 | `./examples/sample-claude-skill` |

### 转换格式（优先级顺序）

| 格式 | 检测标记 |
|---|---|
| **Claude** | `CLAUDE.md`、`SKILL.md`、`.claude/skills/` |
| **Cursor** | `.cursorrules`、`.cursor/rules/*.mdc` |
| **Windsurf** | `.windsurfrules`、`.windsurf/` |
| **Cline** | `.clinerules`、`.cline/` |
| **RooCode** | `.roomodes`、`.roo/` |
| **OpenAI GPT** | `instructions.md`、`prompt.md` |
| **通用** | `README.md`、`prompts/` |

格式检测基于证据评分机制：多个标记加权累分，混合仓库也能精准识别最优格式。

---

## 生成的技能目录结构

```text
.bob/skills/<name>/
├── SKILL.md           ← 转换后的技能（YAML 前置元数据 + Markdown 正文）
├── docs/              ← Bob 标准脚手架目录
├── examples/
├── templates/
├── assets/
├── <原始文件>          ← 所有源文件按原始路径保留
└── scripts/           ← 默认包含（使用 --no-scripts 可排除）
```

**默认全保真。** 源仓库中的所有文件——包括脚本、`.env`、配置、图片、数据——均按原始相对路径保留，技能内部链接不会失效。

> ⚠️ **敏感文件说明：** 若源仓库包含真实的 `.env` 或私钥，默认会被复制。报告会显示醒目的 `SECURITY:` 警告。对于计划分享或发布的技能，请务必使用 `--no-secrets`。

### 生成的 `SKILL.md` 示例

```yaml
---
name: react-architect
description: 'Expert React architecture: patterns, state management, and performance.'
version: 2.1.0
source: https://github.com/org/react-skill
author: Jane Dev
converted_from: claude
created_at: 2026-06-02T09:01:07Z
---

# React Architect

## Role
你是一位资深 React 架构师，负责审查组件设计。

## Objective
帮助工程师构建可扩展的 React 应用结构。

## Workflow
1. 检查组件树
2. 识别状态管理问题
3. 提出最小化重构方案

## Constraints
- 不推荐类组件
- 避免过早的 memoization
```

前置元数据通过 `yaml.safe_dump` 生成，因此包含冒号、引号或非 ASCII 字符的描述始终是合法的 YAML。

---

## 安全模型

安全扫描在转换和安装**之前**执行。只要发现一个阻断性问题，立即触发 `REJECTED`——什么都不会被写入。

### 阻断性检测（安装停止）

| 类别 | 示例 |
|---|---|
| `remote-exec` | `curl … \| bash`、`wget … \| sh`、`bash <(curl …)`、`eval "$(curl …)"` |
| `remote-exec` | PowerShell `IEX (… DownloadString …)` |
| `destructive-shell` | `rm -rf /`、`rm -rf ~`、`rm -rf $HOME` |
| `credential-harvesting` | 读取 `~/.ssh/id_*`、`~/.aws/credentials`、`id_rsa` |
| `secret-exfiltration` | `printenv \| curl`、通过网络发送 `$TOKEN`/`$SECRET` |
| `mcp-auto-trust` | `mcp install … --yes`、`"autoApprove": true` |

### 仅警告（安装继续）

| 类别 | 含义 |
|---|---|
| `browser-automation` | 未经审批启动无头浏览器 |
| 脚本策略 | 默认包含（`--no-scripts` 可排除） |
| 敏感文件策略 | 默认包含并显示 `SECURITY:` 警告（`--no-secrets` 可排除） |

来自源仓库的任何文件都不会被执行。脚本仅作为文本读取。

---

## CLI 参考

```text
install-skill [URL] [OPTIONS]
```

| 选项 | 缩写 | 默认值 | 说明 |
|---|---|---|---|
| `--global` | `-g` | — | 安装到 `~/.bob/skills/` |
| `--project` | `-p` | ✓ | 安装到 `./.bob/skills/` |
| `--name TEXT` | | 自动推断 | 覆盖技能名称（slug） |
| `--author TEXT` | | 来自源 | 覆盖作者名 |
| `--skill-version TEXT` | | 来自源 | 覆盖版本号 |
| `--force` | `-f` | — | 覆盖已有技能 |
| `--upgrade` | `-u` | — | 保留 `.bak` 的替换 |
| `--no-scripts` | | — | 排除可执行脚本 |
| `--no-secrets` | | — | 排除 `.env` / 密钥文件 |
| `--dry-run` | | — | 执行所有阶段但不写入 |
| `--json` | | — | 输出纯文本报告 |
| `--verbose` | `-v` | — | 启用调试日志 |
| `--log-file PATH` | | — | 同时写入滚动日志文件 |
| `--version` | | — | 显示版本后退出 |

### 退出码

| 代码 | 含义 |
|---|---|
| `0` | 成功（有无警告均可） |
| `2` | 无效 URL 或参数冲突 |
| `3` | 获取失败（克隆、网络、ZIP 错误） |
| `7` | 生成的技能验证失败 |
| `8` | 被安全扫描拒绝 |

### 安装报告示例

```
╭──────────────────────── Installation Report ─────────────────────────────╮
│         Status  SUCCESS                                                   │
│          Skill  react-architect                                           │
│        Version  2.1.0                                                     │
│         Source  https://github.com/org/react-skill                        │
│ Converted From  claude                                                    │
│   Installed To  .bob/skills/react-architect                               │
│       Warnings  None                                                      │
╰───────────────────────────────────────────────────────────────────────────╯
```

### Real operation use cases
<img width="1454" height="275" alt="image" src="https://github.com/user-attachments/assets/3e43f00a-ffb2-4d9e-ad53-64856bf52f3e" />
。。。
<img width="1323" height="220" alt="image" src="https://github.com/user-attachments/assets/a343c664-b551-4dea-8425-65f81f27ff82" />
...
<img width="1454" height="270" alt="image" src="https://github.com/user-attachments/assets/8e039b0f-dade-42f7-aa81-468e8a21f781" />
...
<img width="277" height="668" alt="image" src="https://github.com/user-attachments/assets/f351f014-3c9a-4e4c-ac56-63f6d7d0d3e2" />


---

## IBM Bob 斜杠命令

`.bob/commands/install-skill.md` 定义的斜杠命令提供确认优先的对话流程：

1. **解析** — 从用户消息中提取 URL 和作用域
2. **确认** — 向用户确认安装目标和覆盖策略
3. **理解** — 调用 `anysearch` 对仓库进行摘要
4. **安全审查** — Agent 自身对内容进行检查
5. **转换与安装** — 调用 CLI
6. **报告** — 向用户呈现安装结果

```text
/install-skill https://github.com/org/react-skill --project
/install-skill https://github.com/org/react-skill --global --no-secrets
```


### 真实执行用例
<img width="606" height="787" alt="image" src="https://github.com/user-attachments/assets/a79f44c6-eba9-49cd-96b9-52467497700d" />

```text
┌─────────────────┐
│ install-skill   │
│ mcp-builder     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ mcp-builder     │
│ Skill実行       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ slack_mcp       │
│ MCP生成         │
└─────────────────┘
```
先ほどインストールした mcp-builder Skill を呼び出し、slack_mcp を生成します。

<img width="588" height="683" alt="image" src="https://github.com/user-attachments/assets/157f8d72-2b02-4635-8679-d3b3dfb85253" />
...
<img width="561" height="631" alt="image" src="https://github.com/user-attachments/assets/ca7da473-1eac-46cd-8859-e1ea08f6f826" />



---

## 项目结构

```text
bob-skill-installer/
├── src/bob_skill_installer/
│   ├── models.py              ← 全流水线共享的 Pydantic 模型（数据契约）
│   ├── exceptions.py          ← 带 exit_code 的类型化异常层次
│   ├── logging_config.py      ← 基于 Rich 的日志（控制台 + 滚动文件）
│   ├── report.py              ← Rich + 纯文本安装报告
│   ├── github/                ← URL 解析 + 克隆 / ZIP / 本地复制
│   ├── analyzer/              ← 文件清单 + 证据评分格式检测
│   ├── converters/            ← 7 种格式转换器 + Jinja2 模板
│   ├── security/              ← 模式扫描器 + 敏感文件检测
│   ├── validators/            ← 结构 / 元数据 / Markdown / 链接检查
│   ├── installer/             ← 原子安装 + 8 阶段流水线编排
│   ├── templates/             ← skill_md.j2 Jinja2 模板
│   └── cli/                   ← Typer CLI
├── tests/
│   ├── unit/                  ← 9 个单元测试文件
│   └── integration/           ← 2 个集成测试文件（离线，使用 patched fetcher）
├── .bob/
│   ├── commands/install-skill.md  ← Bob 斜杠命令定义
│   └── skills/                    ← 项目范围安装目标
├── docs/
│   ├── architecture.md
│   ├── security.md
│   └── blog-note.md           ← 技术深度解析（日文）
└── examples/
    ├── sample-claude-skill/
    └── sample-cursor-skill/
```

---

## anysearch 配置

[`anysearch`](https://github.com/anysearch-ai/anysearch-skill) 是驱动斜杠命令第 3 步的实时搜索技能，负责在转换前抓取并摘要目标仓库，让 Agent 理解其语义意图。**已预装在 `.bob/skills/anysearch/`**，只需配置 API Key 即可使用。

### 获取 API Key

访问 **<https://anysearch.com/console/api-keys>** 注册并创建免费的 API Key。

### 配置方式

**方式 A — `.env` 文件（推荐用于项目）**

```bash
cp .bob/skills/anysearch/.env.example .bob/skills/anysearch/.env
# 编辑文件并填入：
# ANYSEARCH_API_KEY=<your_api_key_here>
```

**方式 B — 环境变量（推荐用于 CI / 全局使用）**

```bash
# Linux / macOS
export ANYSEARCH_API_KEY=<your_api_key_here>

# Windows CMD
set ANYSEARCH_API_KEY=<your_api_key_here>

# Windows PowerShell
$env:ANYSEARCH_API_KEY="<your_api_key_here>"
```

**方式 C — CLI 参数（临时使用）**

```bash
# 通过斜杠命令传入 --api_key
/install-skill https://github.com/org/skill --project
```

> **优先级顺序：** `--api_key` CLI 参数 › `.env` 文件 › 环境变量 › 匿名访问（有频率限制）

不配置 API Key 也可以匿名访问，但有频率限制。日常使用建议申请免费 API Key。

更多详情请参阅 [anysearch-skill 仓库](https://github.com/anysearch-ai/anysearch-skill)。

---

## 开发

```bash
# 安装（含开发依赖）
uv pip install -e ".[dev]"

# 运行测试
uv run pytest

# 带覆盖率的测试
uv run pytest --cov

# 类型检查（strict 模式）
uv run mypy src

# 代码检查
uv run ruff check .

# 使用内置示例测试（无需网络）
install-skill ./examples/sample-claude-skill --name demo-architect
```

### 质量指标

| 指标 | 数值 |
|---|---|
| 测试数量 | 141 个通过 |
| 覆盖率 | 92% |
| 类型检查 | `mypy --strict` — 通过 |
| 代码检查 | `ruff` — 通过 |
| Python 版本 | 3.12+ |

---

## 许可证

[Apache-2.0](LICENSE) — Copyright 2026 bob-skill-installer contributors.

---

## 相关资源

- [`docs/architecture.md`](docs/architecture.md) — 完整流水线设计
- [`docs/security.md`](docs/security.md) — 安全模型与保证
- [`docs/blog-note.md`](docs/blog-note.md) — 技术深度解析（日文）
- [anysearch-skill](https://github.com/anysearch-ai/anysearch-skill) — 实时搜索技能（预装依赖技能）
- [IBM Bob 文档](https://bob.ibm.com/)
