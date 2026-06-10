# bob-skill-installer

> **コマンド一つで、あらゆるスキルを IBM Bob へ。**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-141%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen.svg)]()
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)]()
[![ruff](https://img.shields.io/badge/ruff-passing-blue.svg)]()

[English](README.md) | [中文](README.zh.md)

---

`bob-skill-installer` は IBM Bob の `/install-skill` スラッシュコマンドを動かすエンジンです。  
GitHub / GitLab / Git リポジトリや ZIP の URL を渡すだけで、ソース取得・形式解析・変換・検証・インストールまでを自動で完結します。手作業ゼロ。

```bash
install-skill https://github.com/awesome-skills/react-architect --project
```

以上です。

---

## 機能一覧

- **ソース対応幅の広さ** — GitHub・GitLab・汎用 Git・直接 ZIP URL・ローカルディレクトリ
- **7種のフォーマット変換** — Claude・Cursor・Windsurf・Cline・RooCode・OpenAI GPT・汎用プロンプトリポジトリ
- **完全保真インストール** — 全ファイルを元のパスでバイナリ安全に保持
- **セキュリティゲート** — `curl | bash`・認証情報窃取・破壊的シェル・MCP 自動信任を書き込み前に検出・遮断
- **アトミックインストール** — ステージング→スワップ方式。クラッシュしても既存スキルは無傷
- **IBM Bob スラッシュコマンド** — 確認優先フローと `anysearch` によるリポジトリ理解
- **エンタープライズ品質** — `mypy --strict`・`ruff`・141テスト・カバレッジ 92%

---

## クイックスタート

### 前提条件

- Python 3.12 以上
- [`uv`](https://docs.astral.sh/uv/)（推奨）または `pip`
- Git（リモートリポジトリのクローン用）

### インストール

```bash
git clone https://github.com/funhere/bob-skill-installer
cd bob-skill-installer
uv pip install -e ".[dev]"
```

### はじめてのスキルインストール

```bash
# プロジェクトスコープ（./.bob/skills/）にインストール
install-skill https://github.com/org/react-skill

# グローバルスコープ（~/.bob/skills/）にインストール
install-skill https://github.com/org/react-skill --global

# 書き込みなしで全ステージを確認（dry-run）
install-skill https://github.com/org/react-skill --dry-run

# IBM Bob スラッシュコマンドから実行
/install-skill https://github.com/org/react-skill --project
```

---

## 動作の仕組み

パイプラインは独立した8ステージで構成されています：

```
URL
 │
 ▼
┌──────────────┐
│    parse     │  URL を分類 → ParsedSource
└──────┬───────┘
       ▼
┌──────────────┐
│    fetch     │  git clone / ZIP 展開 / ローカルコピー → ローカルディレクトリ
└──────┬───────┘
       ▼
┌──────────────┐
│   analyze    │  ファイルツリー走査・形式スコアリング → RepoAnalysis
└──────┬───────┘
       ▼
┌──────────────┐
│   security   │  静的パターンスキャン → SecurityReport
└──────┬───────┘   REJECTED → 以降の処理を全停止
       ▼
┌──────────────┐
│   convert    │  フォーマット変換 → BobSkill + SKILL.md 生成
└──────┬───────┘
       ▼
┌──────────────┐
│   validate   │  構造・メタデータ・Markdown・リンク検証
└──────┬───────┘   FAILED → インストール中止
       ▼
┌──────────────┐
│   install    │  アトミック書き込み → スキルディレクトリ
└──────┬───────┘
       ▼
┌──────────────┐
│   report     │  Rich パネルまたはプレーンテキストレポート
└──────────────┘
```

各ステージは Pydantic モデルを契約として独立してテスト・交換可能です。

| ステージ | モジュール | 役割 |
|---|---|---|
| parse | `github/url_parser.py` | URL → `ParsedSource` |
| fetch | `github/fetcher.py` | clone / ZIP / ローカルコピー |
| analyze | `analyzer/` | ファイル棚卸し・形式スコアリング |
| security | `security/scanner.py` | パターンスキャン・スクリプト/秘匿ファイル棚卸し |
| convert | `converters/` | 7種のコンバーター + Jinja2 テンプレート |
| validate | `validators/` | 構造・メタデータ・Markdown・リンク |
| install | `installer/installer.py` | アトミック書き込み・`--force`/`--upgrade` |
| report | `report.py` | Rich + プレーンテキストレポート |

---

## 対応ソース・フォーマット

### 取得元（優先順）

| ソース | 例 |
|---|---|
| GitHub リポジトリ | `https://github.com/org/repo` |
| GitHub サブツリー | `https://github.com/org/repo/tree/main/skills/writer` |
| GitLab リポジトリ | `https://gitlab.com/org/repo` |
| 汎用 Git | `https://git.example.com/repo.git` |
| 直接 ZIP URL | `https://example.com/skill.zip` |
| ローカルディレクトリ | `./examples/sample-claude-skill` |

### 変換元フォーマット（優先順）

| フォーマット | 検出マーカー |
|---|---|
| **Claude** | `CLAUDE.md`、`SKILL.md`、`.claude/skills/` |
| **Cursor** | `.cursorrules`、`.cursor/rules/*.mdc` |
| **Windsurf** | `.windsurfrules`、`.windsurf/` |
| **Cline** | `.clinerules`、`.cline/` |
| **RooCode** | `.roomodes`、`.roo/` |
| **OpenAI GPT** | `instructions.md`、`prompt.md` |
| **Generic** | `README.md`、`prompts/` |

形式検出は証拠スコアリング方式。複数マーカーが加点され、混在リポジトリでも最適な形式が選ばれます。

---

## 生成されるスキル構造

```text
.bob/skills/<name>/
├── SKILL.md           ← 変換済みスキル（YAMLフロントマター + Markdownボディ）
├── docs/              ← Bob 標準スキャフォールド
├── examples/
├── templates/
├── assets/
├── <元のファイル>      ← 全ソースファイルを元のパスで保持
└── scripts/           ← デフォルトで含まれる（--no-scripts で除外可）
```

**デフォルトは完全保真。** スクリプト・`.env`・設定ファイル・画像・データなど全ファイルを元の相対パスで保持します。スキル内部の相対リンクが壊れません。

> ⚠️ **秘匿ファイルについて：** ソースに実際の `.env` や秘密鍵が含まれる場合、デフォルトでコピーされます。レポートに `SECURITY:` 警告が表示されます。配布・公開するスキルには必ず `--no-secrets` を使用してください。

### 生成される `SKILL.md` の例

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
シニア React アーキテクトとして、コンポーネント設計をレビューします。

## Objective
スケーラブルな React アプリケーションの構造化を支援します。

## Workflow
1. コンポーネントツリーを確認する
2. ステート管理のにおいを特定する
3. 最小限のリファクタを提案する
```

フロントマターは `yaml.safe_dump` で生成されるため、コロンや非 ASCII 文字を含む値も常に正しい YAML として出力されます。

---

## セキュリティモデル

セキュリティスキャナーは変換・インストールの**前**に実行されます。ブロッキング検出が1件でもあれば `REJECTED` で即停止し、何も書き込まれません。

### ブロッキング検出（インストール停止）

| カテゴリ | 例 |
|---|---|
| `remote-exec` | `curl … \| bash`、`wget … \| sh`、`bash <(curl …)`、`eval "$(curl …)"` |
| `remote-exec` | PowerShell `IEX (… DownloadString …)` |
| `destructive-shell` | `rm -rf /`、`rm -rf ~`、`rm -rf $HOME` |
| `credential-harvesting` | `~/.ssh/id_*`、`~/.aws/credentials`、`id_rsa` への読み取り |
| `secret-exfiltration` | `printenv \| curl`、`$TOKEN`/`$SECRET` のネットワーク送信 |
| `mcp-auto-trust` | `mcp install … --yes`、`"autoApprove": true` |

### 警告のみ（インストール継続）

| カテゴリ | 内容 |
|---|---|
| `browser-automation` | 承認なしのヘッドレスブラウザ起動 |
| スクリプトポリシー | デフォルトで含まれる（`--no-scripts` で除外可） |
| 秘匿ファイルポリシー | デフォルトで含まれ `SECURITY:` 警告を表示（`--no-secrets` で除外可） |

ソースのいかなるファイルも実行されません。スクリプトはテキストとして読まれるだけです。

---

## CLI リファレンス

```text
install-skill [URL] [OPTIONS]
```

| オプション | 短縮形 | デフォルト | 説明 |
|---|---|---|---|
| `--global` | `-g` | — | `~/.bob/skills/` にインストール |
| `--project` | `-p` | ✓ | `./.bob/skills/` にインストール |
| `--name TEXT` | | 自動推定 | スキル名をオーバーライド |
| `--author TEXT` | | ソースから | 著者名をオーバーライド |
| `--skill-version TEXT` | | ソースから | バージョンをオーバーライド |
| `--force` | `-f` | — | 既存スキルを上書き |
| `--upgrade` | `-u` | — | `.bak` を保持して置換 |
| `--no-scripts` | | — | 実行スクリプトを除外 |
| `--no-secrets` | | — | `.env` / 鍵ファイルを除外 |
| `--dry-run` | | — | 書き込みなしで全ステージ実行 |
| `--json` | | — | プレーンテキストレポート出力 |
| `--verbose` | `-v` | — | デバッグログを有効化 |
| `--log-file PATH` | | — | ログをローテーションファイルに出力 |
| `--version` | | — | バージョン表示して終了 |

### 終了コード

| コード | 意味 |
|---|---|
| `0` | 成功（警告あり・なし） |
| `2` | 無効なURL・引数エラー |
| `3` | ソース取得失敗（clone・ネットワーク・ZIP）|
| `7` | 生成スキルのバリデーション失敗 |
| `8` | セキュリティスキャンによる REJECTED |

### 実行レポートの例

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

---

## IBM Bob スラッシュコマンド

`.bob/commands/install-skill.md` で定義されるスラッシュコマンドは、確認優先フローを持ちます：

1. **解析** — メッセージから URL とスコープを抽出
2. **確認** — インストール先・上書き可否をユーザーに確認
3. **理解** — `anysearch` でリポジトリを要約
4. **セキュリティレビュー** — エージェント自身による内容確認
5. **変換・インストール** — CLI を呼び出す
6. **レポート** — 結果をユーザーに提示

```text
/install-skill https://github.com/org/react-skill --project
/install-skill https://github.com/org/react-skill --global --no-secrets
```

---

## プロジェクト構成

```text
bob-skill-installer/
├── src/bob_skill_installer/
│   ├── models.py              ← パイプライン全体の Pydantic モデル契約
│   ├── exceptions.py          ← exit_code 付き型付き例外
│   ├── logging_config.py      ← Rich ベースのログ（コンソール + ローテーションファイル）
│   ├── report.py              ← Rich + プレーンテキストレポート
│   ├── github/                ← URL解析 + clone / ZIP / ローカルコピー
│   ├── analyzer/              ← ファイル棚卸し + スコアリング形式検出
│   ├── converters/            ← 7種コンバーター + Jinja2 テンプレート
│   ├── security/              ← パターンスキャナー + 秘匿ファイル検出
│   ├── validators/            ← 構造・メタデータ・Markdown・リンク検証
│   ├── installer/             ← アトミックインストール + 8ステージパイプライン
│   ├── templates/             ← skill_md.j2 Jinja2 テンプレート
│   └── cli/                   ← Typer CLI
├── tests/
│   ├── unit/                  ← 9ファイルの単体テスト
│   └── integration/           ← 2ファイルの統合テスト（オフライン）
├── .bob/
│   ├── commands/install-skill.md  ← Bob スラッシュコマンド定義
│   └── skills/                    ← プロジェクトスコープのインストール先
├── docs/
│   ├── architecture.md
│   ├── security.md
│   └── blog-note.md           ← 技術ブログ（日本語）
└── examples/
    ├── sample-claude-skill/
    └── sample-cursor-skill/
```

---

## 開発

```bash
# 開発依存込みでインストール
uv pip install -e ".[dev]"

# テスト実行
uv run pytest

# カバレッジ付きテスト
uv run pytest --cov

# 型チェック（strict）
uv run mypy src

# リント
uv run ruff check .

# バンドルサンプルで試す（ネットワーク不要）
install-skill ./examples/sample-claude-skill --name demo-architect
```

### 品質指標

| 指標 | 値 |
|---|---|
| テスト数 | 141件パス |
| カバレッジ | 92% |
| 型チェック | `mypy --strict` — クリーン |
| リント | `ruff` — クリーン |
| 対応 Python | 3.12 以上 |

---

## ライセンス

[Apache-2.0](LICENSE) — Copyright 2026 bob-skill-installer contributors.

---

## 関連ドキュメント

- [`docs/architecture.md`](docs/architecture.md) — パイプラインの全体設計
- [`docs/security.md`](docs/security.md) — セキュリティモデルと保証
- [`docs/blog-note.md`](docs/blog-note.md) — 技術解説ブログ（日本語）
- [IBM Bob ドキュメント](https://bob.ibm.com/)
