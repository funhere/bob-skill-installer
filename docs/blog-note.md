# AIスキルを"ワンコマンド"でIBM Bobに移植する ── bob-skill-installer 設計と実装の全貌

**公開日：2026年6月　|　読了時間：約15分　|　対象読者：AIエージェント開発者・IBM Bob ユーザー**

---

## はじめに ── なぜこのツールが必要か

AIエージェントのエコシステムは今、かつてないスピードで分散している。

Claude Code のスキル、Cursor のルール、Windsurf の設定、Cline のモード定義、RooCode のプロンプト……それぞれのツールが独自のスキルフォーマットを持ち、優れたプロンプト資産は各プラットフォームのサイロに閉じ込められている。

一方、IBM Bob はスラッシュコマンドとスキルによってエージェントの能力を拡張できるが、他プラットフォームのスキルをそのまま流用することはできなかった。

**`bob-skill-installer` はその橋渡しをするツールだ。**

GitHub のリポジトリURL を一行渡すだけで、自動的にソースを取得・解析・変換・検証・インストールまで完結する。手作業でのコピー&ペーストも、フォーマット変換の知識も不要。

```bash
install-skill https://github.com/awesome-skills/react-architect --project
```

これだけで動く。

---

## 対象読者

この記事は以下のような方を想定しています：

- **IBM Bob を使っているエンジニア** で、外部スキルを手軽に取り込みたい方
- **Claude Code / Cursor のスキルを開発している方** で、他プラットフォームへの移植を検討している方
- **セキュリティを意識したOSSツールの設計に興味がある方**
- **Python で CLI ツールや変換パイプラインを作る実装例を探している方**

---

## ツールの全体像

### アーキテクチャ：8ステージ・パイプライン

`bob-skill-installer` の核心は、直列に連なる8つのステージだ。各ステージは独立してテスト可能なモジュールで実装されており、Pydantic モデルがステージ間のデータ契約を保証する。

```
URL
 │
 ▼
┌────────────┐
│   parse    │  URL を解析 → ParsedSource
└─────┬──────┘
      ▼
┌────────────┐
│   fetch    │  git clone / ZIP展開 → ローカルディレクトリ
└─────┬──────┘
      ▼
┌────────────┐
│  analyze   │  ファイルツリーを走査 → RepoAnalysis + 形式スコアリング
└─────┬──────┘
      ▼
┌────────────┐
│  security  │  パターンスキャン → SecurityReport
└─────┬──────┘    ※ ブロッキング検出 → REJECTED（以降全停止）
      ▼
┌────────────┐
│  convert   │  フォーマット変換 → BobSkill + SKILL.md 生成
└─────┬──────┘
      ▼
┌────────────┐
│  validate  │  構造・メタデータ・Markdownチェック → ValidationResult
└─────┬──────┘    ※ ブロッキング検出 → FAILED（インストール中止）
      ▼
┌────────────┐
│  install   │  アトミック書き込み → スキルディレクトリ
└─────┬──────┘
      ▼
┌────────────┐
│  report    │  インストールレポート（Rich / プレーンテキスト）
└────────────┘
```

このパイプラインは `installer/pipeline.py` の `run_install()` 関数が一本で取りまとめる。CLI も、Bob スラッシュコマンドも、このひとつの関数を呼ぶだけだ。

---

## 対応ソース・フォーマット

### 取得元（優先順）

| ソース | 例 |
|---|---|
| GitHub リポジトリ | `https://github.com/org/repo` |
| GitHub ツリー（サブパス） | `https://github.com/org/repo/tree/main/skills/writer` |
| GitLab リポジトリ | `https://gitlab.com/org/repo` |
| 任意の Git | `https://git.example.com/repo.git` |
| 直接 ZIP URL | `https://example.com/skill.zip` |
| ローカルディレクトリ | `./examples/sample-claude-skill` |

ローカルパス対応はオフラインでのテストや既存スキルの変換に便利だ。

### 変換元フォーマット（優先順）

| フォーマット | 検出マーカー | 代表ツール |
|---|---|---|
| **Claude** | `CLAUDE.md` / `SKILL.md` / `.claude/skills/` | Claude Code |
| **Cursor** | `.cursorrules` / `.cursor/rules/*.mdc` | Cursor IDE |
| **Windsurf** | `.windsurfrules` / `.windsurf/` | Windsurf |
| **Cline** | `.clinerules` / `.cline/` | Cline |
| **RooCode** | `.roomodes` / `.roo/` | RooCode |
| **OpenAI GPT** | `instructions.md` / `prompt.md` | GPT Builder |
| **Generic** | `README.md` / `prompts/` | 汎用プロンプトリポジトリ |

形式検出は証拠スコアリング方式を採用している。各マーカーの存在が加点され、最高スコアのフォーマットが採用される。スコアが低くても Generic フォーマットへのフォールバックがあるため、「検出不能で失敗」はほぼ起きない。

---

## 実際に動かしてみる

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/your-org/bob-skill-installer
cd bob-skill-installer

# 依存パッケージをインストール（Python 3.12 以上）
uv pip install -e ".[dev]"

# バージョン確認
install-skill --version
# → bob-skill-installer 0.1.0
```

### 基本的な使い方

```bash
# プロジェクトスコープにインストール（デフォルト）
install-skill https://github.com/org/react-skill --project

# グローバルスコープにインストール
install-skill https://github.com/org/react-skill --global

# スキル名をオーバーライド
install-skill https://github.com/org/react-skill --name my-react-expert

# 書き込まずに動作確認（dry-run）
install-skill https://github.com/org/react-skill --dry-run
```

### 実行時の出力例

コマンド実行後、以下のようなリッチなレポートが表示される：

```
╭──────────────────────────── Installation Report ─────────────────────────────╮
│         Status  SUCCESS                                                       │
│          Skill  react-architect                                               │
│        Version  2.1.0                                                         │
│         Source  https://github.com/org/react-skill                            │
│ Converted From  claude                                                        │
│   Installed To  .bob/skills/react-architect                                   │
│       Warnings  None                                                          │
╰───────────────────────────────────────────────────────────────────────────────╯
```

失敗した場合も同じフォーマットで `FAILED` / `REJECTED` が表示され、原因がすぐわかる。

---

## インストール先とスキル構造

### インストールスコープ

```bash
.bob/skills/<name>/    # --project（プロジェクトローカル・デフォルト）
~/.bob/skills/<name>/  # --global（ユーザー全体）
```

### 生成されるスキル構造

```text
.bob/skills/react-architect/
├── SKILL.md            ← 変換・生成されたメインドキュメント
├── docs/               ← Bob 標準スキャフォールド
├── examples/
├── templates/
├── assets/
├── references/         ← 元リポジトリのファイルを原パスで保持
├── scripts/            ← 実行スクリプト（--no-scripts で除外可能）
└── .env, *.json など   ← 全支持ファイルをバイナリ安全に保持
```

**完全保真（Full Fidelity）** がデフォルトの設計思想だ。元リポジトリのファイル構造を可能な限りそのまま維持することで、スキル内部の相対リンクが壊れない。

### 生成される SKILL.md の例

```markdown
---
name: react-architect
description: Expert React architecture guidance.
version: 2.1.0
source: https://github.com/org/react-skill
author: Jane Dev
converted_from: claude
created_at: 2026-06-02T09:01:07Z
---

# React Architect

> Converted into an IBM Bob skill from a **claude** source.

## Role

You are a senior React architect who reviews component design.

## Objective

Help engineers structure scalable React applications.

## Workflow

1. Inspect the component tree
2. Identify state-management smells
3. Propose a refactor

## Constraints

- Do not recommend class components
- Avoid premature memoization
```

フロントマターは `yaml.safe_dump` で生成するため、`description: Code review: find bugs...` のようなコロンを含む値も確実に正しく処理される（ナイーブなテンプレート文字列では YAML パースエラーになる）。

---

## セキュリティ設計

`bob-skill-installer` は第三者のコードを取り込むツールであるため、セキュリティは設計の核心に位置する。

### ブロッキング検出（インストール阻止）

以下のパターンが検出された場合、`REJECTED` で即座に停止する：

| カテゴリ | 検出パターン例 |
|---|---|
| **remote-exec** | `curl … \| bash`、`wget … \| sh`、`bash <(curl …)` |
| **remote-exec** | `eval "$(curl …)"`、PowerShell `IEX (DownloadString ...)` |
| **destructive-shell** | `rm -rf /`、`rm -rf ~`、`rm -rf $HOME` |
| **credential-harvesting** | `~/.ssh/id_*`、`~/.aws/credentials`、`id_rsa` への読み取り |
| **secret-exfiltration** | `printenv \| curl`、`$TOKEN` / `$SECRET` のネットワーク送信 |
| **mcp-auto-trust** | `mcp install … --yes`、`"autoApprove": true` |

### ファイル取り込みポリシー

> **デフォルトは完全保真** ── スクリプトも秘匿ファイルも含めてすべてコピーする。  
> `--no-scripts` / `--no-secrets` で除外できる。

```bash
# スクリプトと秘密ファイルを除外してインストール（配布用スキルを作る場合）
install-skill https://github.com/org/skill --no-scripts --no-secrets
```

`.env` など秘密ファイルが含まれる場合は、報告書に **`SECURITY:` 警告** が表示される：

```
Warnings:
  - SECURITY: 1 potential secret file(s) (e.g. .env / keys) were COPIED
    into the skill. Do NOT share or publish it. Use --no-secrets to exclude.
```

スキャンは **コンテンツのパターンマッチのみ**で、何も実行しない。これはツールの鉄則だ。

---

## プロジェクト構成

### ディレクトリ構造

```text
bob-skill-installer/
├── src/bob_skill_installer/
│   ├── models.py           ← 全ステージ共有の Pydantic モデル
│   ├── exceptions.py       ← 型付き例外階層（exit_code 付き）
│   ├── logging_config.py   ← Rich ベースのロギング設定
│   ├── report.py           ← インストールレポート（Rich + プレーンテキスト）
│   ├── github/             ← URL解析・ソース取得（git clone / ZIP展開）
│   ├── analyzer/           ← リポジトリ解析・フォーマット検出
│   ├── converters/         ← 形式別コンバーター + レジストリ
│   ├── security/           ← セキュリティスキャナー
│   ├── validators/         ← 生成スキルの検証
│   ├── installer/          ← アトミックインストール + パイプライン
│   ├── templates/          ← Jinja2 SKILL.md テンプレート
│   └── cli/                ← Typer CLI
├── tests/
│   ├── unit/               ← 各モジュールの単体テスト（9ファイル）
│   └── integration/        ← パイプライン統合テスト（2ファイル）
├── .bob/
│   ├── commands/install-skill.md  ← IBM Bob スラッシュコマンド定義
│   └── skills/                    ← インストール先（プロジェクトスコープ）
├── docs/                   ← アーキテクチャ・セキュリティドキュメント
└── examples/               ← 変換元サンプルスキル
```

### 技術スタック

| ライブラリ | 用途 |
|---|---|
| **Pydantic v2** | ステージ間データモデル・バリデーション |
| **Typer** | CLI インターフェース |
| **Rich** | ターミナル出力・ログ・インストールレポート |
| **GitPython** | git clone 実装 |
| **Jinja2** | SKILL.md テンプレートレンダリング |
| **PyYAML** | フロントマター解析・安全なシリアライズ |
| **httpx** | ZIP ダウンロード（ストリーミング・サイズ制限付き） |
| **pytest + coverage** | テスト・カバレッジ（141テスト / 92%） |

---

## IBM Bob スラッシュコマンドとの連携

このツールは **CLI単体** としても動くが、真価を発揮するのは IBM Bob の `/install-skill` スラッシュコマンドとの連携だ。

### コマンド定義（`.bob/commands/install-skill.md`）

スラッシュコマンドは以下の9ステップのワークフローを持つ：

1. **invocation 解析** ── URL とスコープを抽出
2. **ユーザー確認** ── インストール先・上書きの確認（`AskUserQuestion`）
3. **anysearch によるリポジトリ理解** ── 役割・目的・ワークフローを AI で要約
4. **セキュリティレビュー** ── エージェント自身によるコンテンツ確認
5. **変換・検証・インストール** ── CLI を呼び出す
6. **レポート表示** ── 結果をユーザーに提示

> **設計ポイント：** `anysearch` スキルによるリポジトリ理解（モデル駆動）と、Python パイプライン（決定論的変換）を分離している。前者はスキルの意味を理解し、後者は確実に変換を実行する。両者の責任領域を明確に分けることで、パイプラインは完全にオフラインでテスト可能になっている。

---

## コンバーター設計の詳細

### 基底クラスとフォーマット別サブクラス

すべてのコンバーターは `BaseConverter` を継承し、`primary_sources()` メソッドだけを実装する：

```python
class ClaudeConverter(BaseConverter):
    source_format = SkillFormat.CLAUDE

    def primary_sources(self, analysis: RepoAnalysis) -> list[Path]:
        root = analysis.root
        sources = []
        for name in ("SKILL.md", "CLAUDE.md"):
            if (root / name).is_file():
                sources.append(root / name)
        sources.extend(sorted(root.glob("skills/**/SKILL.md")))
        return dedupe_paths(sources)
```

「どのファイルがスキルの本体か」を答えるだけでよい。抽出・メタデータ構築・SKILL.md レンダリング・ファイル収集はすべて基底クラスが担う。

### コンテンツ抽出のロジック

見出しキーワードマッピングで各セクションを分類する：

```python
_SECTION_KEYWORDS = {
    "role":         ("role", "you are", "persona", "identity"),
    "objective":    ("objective", "goal", "purpose", "overview"),
    "workflow":     ("workflow", "steps", "process", "pipeline"),
    "instructions": ("instruction", "rule", "guideline", "how to"),
    "constraints":  ("constraint", "limitation", "do not", "avoid"),
    "tools":        ("tool", "command", "function", "skill"),
}
```

構造化された frontmatter がなくても、ほとんどの Markdown スキルから役割・目的・ワークフローを自動抽出できる。

---

## 実装上のこだわり：アトミックインストール

スキルのインストールは **ステージング → スワップ** の二段階で行われる：

```python
def _swap_into_place(self, staging: Path, target: Path, *, upgrade: bool) -> None:
    backup = None
    if target.exists():
        if upgrade:
            backup = target.with_name(target.name + ".bak")
            target.rename(backup)
        else:
            shutil.rmtree(target)
    try:
        staging.rename(target)       # アトミック（同一ファイルシステム）
    except OSError:
        shutil.copytree(staging, target)  # クロスデバイス時のフォールバック
        shutil.rmtree(staging, ignore_errors=True)
    if backup:
        shutil.rmtree(backup, ignore_errors=True)
```

書き込み途中でクラッシュしても、既存スキルを壊さない。`--upgrade` フラグ使用時は `.bak` を保持し、インストール成功後に自動削除する。

---

## 品質指標

```
テスト数      : 141件
カバレッジ    : 92.32%
型チェック    : mypy --strict パス（31ファイル）
リント        : ruff パス（ゼロエラー）
対応 Python   : 3.12 以上
```

テストは完全オフラインで動作する。`patch_fetcher` フィクスチャが `SourceFetcher` をスタブに差し替えることで、ネットワーク不要でパイプライン全体を検証できる：

```python
@pytest.fixture
def patch_fetcher(monkeypatch):
    def _patch(fixture_root: Path) -> None:
        class _FakeFetcher:
            def __init__(self, *args, **kwargs): ...
            def __enter__(self) -> Path: return fixture_root
            def __exit__(self, *exc): ...
        monkeypatch.setattr(
            "bob_skill_installer.installer.pipeline.SourceFetcher",
            _FakeFetcher
        )
    return _patch
```

---

## CLIオプション一覧

| オプション | 短縮形 | 説明 |
|---|---|---|
| `--global` | `-g` | グローバルスコープにインストール（`~/.bob/skills/`） |
| `--project` | `-p` | プロジェクトスコープにインストール（`./.bob/skills/`、デフォルト） |
| `--name` | | スキル名をオーバーライド |
| `--author` | | 著者名をオーバーライド |
| `--skill-version` | | スキルバージョンをオーバーライド |
| `--force` | `-f` | 既存スキルを上書き |
| `--upgrade` | `-u` | 既存スキルを `.bak` 保持で置換 |
| `--no-scripts` | | 実行スクリプトを除外（デフォルトは含む） |
| `--no-secrets` | | `.env` / 鍵ファイルを除外（デフォルトは含む） |
| `--dry-run` | | 書き込みなしで全ステージを実行 |
| `--json` | | レポートをプレーンテキストで出力 |
| `--verbose` | `-v` | デバッグログを有効化 |
| `--log-file` | | ログをローテーションファイルにも出力 |

### 終了コード

| コード | 意味 |
|---|---|
| `0` | 成功（警告あり・なし） |
| `2` | 無効なURL / 引数エラー |
| `3` | ソース取得失敗（clone / download エラー） |
| `7` | 生成スキルのバリデーション失敗 |
| `8` | セキュリティスキャンによる REJECTED |

---

## ハマりやすいポイントと対策

### YAML フロントマターの特殊文字問題

以下のような `description` はナイーブな文字列テンプレートでは YAML として不正になる：

```yaml
# ❌ コロン+スペースで YAML パースエラー
description: Code review: find bugs, smells, and risks
```

`bob-skill-installer` では `yaml.safe_dump` でフロントマターを生成するため、自動でクォートされる：

```yaml
# ✅ yaml.safe_dump が適切にクォート
description: 'Code review: find bugs, smells, and risks'
```

この問題は実際に GitHub 上のスキルで遭遇し、修正した実際のバグだ。

### ファイル保全の重要性

初期実装では Markdown ファイルのみを `docs/` に集約していたが、これは2つの問題を生む：

1. **サイレントな情報欠落** ── JSON / YAML / 画像 / 設定ファイルが失われる
2. **内部リンクの破損** ── `docs/docs/plans/...` のような多重ネストで相対パスが壊れる

現在の実装は全ファイルを**元のパス**に保持する完全保真アプローチを採る。

---

## おわりに

`bob-skill-installer` は「URLを渡すだけでスキルが入る」という体験を実現する。

設計上のこだわりはシンプルだ：

- **段階ごとに型付きモデルで契約する** ── どのステージでも何が入ってくるかが明確
- **セキュリティを変換より前に置く** ── 悪意あるコンテンツは変換すら許さない
- **完全保真をデフォルトに** ── ユーザーが意図的に除外するまで情報は失わない
- **ネットワークなしでテスト可能** ── フィクスチャで全パイプラインを検証

OSSの AI スキルが増え続ける中、「発見したスキルを即座に使える環境」を作ることが生産性の鍵になる。このツールがその一助になれば幸いだ。

---

## リソース

- **リポジトリ：** `bob-skill-installer/`（本記事と同一リポジトリに同梱）
- **アーキテクチャ詳細：** `docs/architecture.md`
- **セキュリティモデル：** `docs/security.md`
- **サンプルスキル：** `examples/sample-claude-skill/`、`examples/sample-cursor-skill/`

```bash
# すぐに試す
uv pip install -e ".[dev]"
install-skill ./examples/sample-claude-skill --name demo
```

---

*このツールは Python 3.12、Pydantic v2、Typer、Rich で実装されています。*  
*MIT ライセンスの OSS スキルに対応しています。*

---

#AIエージェント #IBMBob #ClaudeCode #Python #OSS #スキル変換 #開発ツール #プロンプトエンジニアリング
