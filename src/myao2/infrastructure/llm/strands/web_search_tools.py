"""Web Search tools for strands-agents.

Tavily API を使用したウェブ検索ツール。
"""

import logging

from strands import tool
from strands.types.tools import ToolContext
from tavily import AsyncTavilyClient

from myao2.config.models import WebSearchConfig

logger = logging.getLogger(__name__)

WEB_SEARCH_CONFIG_KEY = "web_search_config"


def get_web_search_config(tool_context: ToolContext) -> WebSearchConfig:
    """ToolContext から WebSearchConfig を取得する。

    Args:
        tool_context: ツールコンテキスト

    Returns:
        WebSearchConfig インスタンス

    Raises:
        RuntimeError: WebSearchConfig が invocation_state に存在しない場合
    """
    config = tool_context.invocation_state.get(WEB_SEARCH_CONFIG_KEY)
    if config is None:
        raise RuntimeError("WebSearchConfig not found in invocation_state")
    return config


def _truncate_content(content: str, max_length: int) -> str:
    """コンテンツを指定された長さに切り詰める。

    Args:
        content: 元のコンテンツ
        max_length: 最大文字数（0の場合は無制限）

    Returns:
        切り詰められたコンテンツ
    """
    if max_length == 0 or len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def _format_search_results(
    query: str,
    answer: str | None,
    results: list[dict],
    max_content_length: int,
) -> str:
    """検索結果をMarkdown形式にフォーマットする。

    Args:
        query: 検索クエリ
        answer: Tavilyが生成した回答（Noneの場合あり）
        results: 検索結果リスト
        max_content_length: 各結果のcontent最大文字数

    Returns:
        フォーマットされた検索結果
    """
    lines = [f'## 検索結果: "{query}"', ""]

    if answer:
        lines.extend(["### 回答", answer, ""])

    if results:
        lines.append("### 結果")
        for i, result in enumerate(results, 1):
            title = result.get("title", "")
            url = result.get("url", "")
            content = result.get("content", "")

            truncated_content = _truncate_content(content, max_content_length)

            lines.extend(
                [
                    f"{i}. **{title}**",
                    f"   URL: {url}",
                    f"   {truncated_content}",
                    "",
                ]
            )

    return "\n".join(lines)


@tool(context=True)
async def web_search(query: str, tool_context: ToolContext) -> str:
    """ウェブ検索を実行する。

    Args:
        query: 検索クエリ
        tool_context: ツールコンテキスト

    Returns:
        検索結果（タイトル、URL、要約を含む）またはエラーメッセージ
    """
    config = get_web_search_config(tool_context)

    # クエリバリデーション
    if not query or not query.strip():
        return "検索クエリを入力してください"

    logger.info("Web search: %s", query)

    try:
        client = AsyncTavilyClient(api_key=config.api_key)
        response = await client.search(
            query=query,
            search_depth=config.search_depth,
            max_results=config.max_results,
            include_answer=True,
        )

        results = response.get("results", [])
        answer = response.get("answer")

        if not results:
            logger.info("Web search no results: %s", query)
            return "検索結果が見つかりませんでした"

        formatted = _format_search_results(
            query=query,
            answer=answer,
            results=results,
            max_content_length=config.max_content_length,
        )

        logger.info("Web search success: %s (%d results)", query, len(results))
        return formatted

    except Exception as e:
        error_type = type(e).__name__
        logger.warning("Web search error: %s - %s", query, e)
        return (
            f"検索に失敗しました（エラー種別: {error_type}）。"
            "APIキーやWeb検索の設定、ネットワーク接続を確認してください。"
        )


WEB_SEARCH_TOOLS = [web_search]


class WebSearchToolsFactory:
    """Web Search ツールのファクトリ。

    設定の注入と invocation_state の構築を担当する。
    """

    def __init__(self, config: WebSearchConfig) -> None:
        """ファクトリを初期化する。

        Args:
            config: Web Search 設定
        """
        self._config = config

    def get_invocation_state(self) -> dict:
        """invocation_state を取得する。

        Returns:
            Agent に渡す invocation_state 辞書
        """
        return {WEB_SEARCH_CONFIG_KEY: self._config}

    @property
    def tools(self) -> list:
        """ツール関数のリストを取得する。

        Returns:
            Web Search ツール関数のリスト
        """
        return WEB_SEARCH_TOOLS
