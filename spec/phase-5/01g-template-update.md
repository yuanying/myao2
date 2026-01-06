# 01g: テンプレート更新

## 目的

Jinja2 テンプレートを更新し、短期記憶履歴を表示する。ワークスペース短期記憶の表示を削除する。

---

## 実装するファイル

| ファイル | 説明 |
|---------|------|
| `src/myao2/infrastructure/llm/templates/response_query.j2` | 履歴表示対応（修正） |
| `src/myao2/infrastructure/llm/templates/judgment_query.j2` | 履歴表示対応（修正） |
| `src/myao2/infrastructure/llm/templates/memory_query.j2` | WS 短期記憶削除（修正） |
| `tests/infrastructure/llm/strands/test_response_generator.py` | テスト追加（修正） |

---

## 変更内容

### 1. response_query.j2 の変更

#### ワークスペース短期記憶の削除

```jinja2
{# 変更前 #}
{% if workspace_long_term_memory %}
## ワークスペースの歴史
{{ workspace_long_term_memory }}
{% endif %}

{% if workspace_short_term_memory %}
## ワークスペースの直近の出来事
{{ workspace_short_term_memory }}
{% endif %}

{# 変更後 #}
{% if workspace_long_term_memory %}
## ワークスペースの歴史
{{ workspace_long_term_memory }}
{% endif %}

{# workspace_short_term_memory は削除 #}
```

#### チャンネル短期記憶履歴の表示

```jinja2
{# 変更前 #}
{% for channel in channel_memories.values() %}
{% if channel.long_term_memory or channel.short_term_memory %}
### #{{ channel.channel_name }}

{% if channel.long_term_memory %}
#### 歴史
{{ channel.long_term_memory }}
{% endif %}

{% if channel.short_term_memory %}
#### 直近の出来事
{{ channel.short_term_memory }}
{% endif %}
{% endif %}
{% endfor %}

{# 変更後 #}
{% for channel in channel_memories.values() %}
{% if channel.long_term_memory or channel.short_term_memory_history %}
### #{{ channel.channel_name }}

{% if channel.long_term_memory %}
#### 歴史
{{ channel.long_term_memory }}

{% endif %}
{% if channel.short_term_memory_history %}
#### 最近の出来事
{% for memory in channel.short_term_memory_history %}
##### {{ loop.index }}つ前の記憶
{{ memory }}

{% endfor %}
{% endif %}
{% endif %}
{% endfor %}
```

---

### 2. judgment_query.j2 の変更

response_query.j2 と同様の変更を適用：

- ワークスペース短期記憶の削除
- チャンネル短期記憶履歴の表示

---

### 3. memory_query.j2 の変更

記憶生成用テンプレートからワークスペース短期記憶関連を削除：

```jinja2
{# WORKSPACE スコープの場合 #}
{% if scope == 'workspace' %}
  {# 変更前: 短期記憶生成ブロック削除 #}
  {% if memory_type == 'short_term' %}
  ## 各チャンネルの短期記憶
  {% for channel in channel_memories.values() %}
  ...
  {% endfor %}
  {% endif %}

  {# 変更後: WORKSPACE の SHORT_TERM は存在しないため、このブロックは削除 #}
{% endif %}
```

---

## プロンプト配置

### 変更後の配置順序

```
1. ワークスペース長期記憶
   ↓
2. チャンネル記憶（チャンネルごとにグループ化）
   2-1. チャンネル長期記憶（歴史）
   2-2. チャンネル短期記憶履歴（最近の出来事）
        - 1つ前の記憶
        - 2つ前の記憶
        - ...
        - 5つ前の記憶（最新）
   ↓
3. スレッド記憶
   ↓
4. 会話履歴
```

### 表示例

```markdown
## ワークスペースの歴史
このワークスペースでは、2024年1月からプロジェクトXの開発が行われています...

## 各チャンネルの記憶

### #general

#### 歴史
generalチャンネルでは、日々の雑談や全体連絡が行われています...

#### 最近の出来事
##### 1つ前の記憶
12月1日、年末の予定について話し合いがありました...

##### 2つ前の記憶
12月2日、忘年会の企画が始まりました...

##### 3つ前の記憶
12月3日、プレゼントの相談がありました...

##### 4つ前の記憶
12月4日、会場の候補が挙がりました...

##### 5つ前の記憶
12月5日、最終的に会場が決定しました...

### #development

#### 歴史
developmentチャンネルでは、技術的な議論が行われています...

#### 最近の出来事
##### 1つ前の記憶
バグ修正の議論がありました...

...

## 会話履歴
...
```

---

## 履歴のラベル

履歴の各項目には「1つ前の記憶」「2つ前の記憶」のようなラベルを付ける。

### 理由

1. **時系列の明確化**: 古い記憶から新しい記憶への流れが分かりやすい
2. **参照のしやすさ**: LLM が特定の記憶を参照しやすくなる
3. **コンテキストの把握**: どの程度前の出来事かが直感的に分かる

### 代替案

- 日付表示: `2024-12-01 の記憶` → 記憶に日付情報がない場合がある
- version 番号: `記憶 v1` → ユーザーにとって分かりにくい
- 序数: `1番目の記憶` → 「1つ前の記憶」の方が相対的で分かりやすい

---

## テストケース

### response_query.j2

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| WS 短期記憶なし | workspace_short_term_memory 未使用 | エラーなし |
| 履歴なし | short_term_memory_history が空 | 「最近の出来事」セクションなし |
| 履歴 1 件 | history に 1 件 | 「1つ前の記憶」のみ表示 |
| 履歴 5 件 | history に 5 件 | 5 件が古い順で表示 |
| 複数チャンネル | 2 チャンネル分の履歴 | 各チャンネルでグループ化して表示 |

### 後方互換性

| テスト | シナリオ | 期待結果 |
|--------|---------|---------|
| short_term_memory のみ | 履歴なし、従来の短期記憶のみ | エラーなし（空リストとして扱う） |

---

## 完了基準

- [ ] response_query.j2 から workspace_short_term_memory が削除されている
- [ ] response_query.j2 で short_term_memory_history が表示される
- [ ] judgment_query.j2 も同様に更新されている
- [ ] memory_query.j2 から WS SHORT_TERM 関連が削除されている
- [ ] 履歴は古い順で表示される
- [ ] 各履歴に「Nつ前の記憶」のラベルが付く
- [ ] 全テストケースが通過する
