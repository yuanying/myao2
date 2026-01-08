# Phase 5: ツール機能

## 概要

LLMが使用できるツールを実装する。

## 前提条件

Phase 4 で以下が実装済みであること：

- 記憶システム（Memory エンティティ、MemoryRepository）
- strands-agents 移行（StrandsResponseGenerator 等）
- Context エンティティの記憶フィールド
- Jinja2 テンプレートによるプロンプト生成

---

## 機能一覧

| # | 機能 | 仕様書 | 説明 |
|---|------|-------|------|
| 01 | メモ帳ツール | [01-memo-tool.md](./01-memo-tool.md) | LLMが自発的に重要情報を記憶するツール |
| 02 | 動的待機時間 | [02-dynamic-wait.md](./02-dynamic-wait.md) | 活発なチャンネルでは応答待機時間を短縮 |
| 03 | Web Fetch ツール | [03-web-fetch-tool.md](./03-web-fetch-tool.md) | 外部WebページをMarkdown形式で取得するツール |

---

## 検証方法

```bash
# テスト実行
uv run pytest

# Linter
uv run ruff check .
uv run ruff format .

# 型チェック
uv run ty check
```
