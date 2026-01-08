"""Web Fetch tools for strands-agents.

外部 Web ページをスクレイピングして Markdown 形式で取得するツール。
"""

import logging

import httpx
from strands import tool
from strands.types.tools import ToolContext

from myao2.config.models import WebFetchConfig

logger = logging.getLogger(__name__)

WEB_FETCH_CONFIG_KEY = "web_fetch_config"


def get_web_fetch_config(tool_context: ToolContext) -> WebFetchConfig:
    """ToolContext から WebFetchConfig を取得する。

    Args:
        tool_context: ツールコンテキスト

    Returns:
        WebFetchConfig インスタンス

    Raises:
        RuntimeError: WebFetchConfig が invocation_state に存在しない場合
    """
    config = tool_context.invocation_state.get(WEB_FETCH_CONFIG_KEY)
    if config is None:
        raise RuntimeError("WebFetchConfig not found in invocation_state")
    return config


@tool(context=True)
async def web_fetch(url: str, tool_context: ToolContext) -> str:
    """Webページの内容を取得する。

    Args:
        url: 取得するWebページのURL
        tool_context: ツールコンテキスト

    Returns:
        ページ内容（Markdown形式）またはエラーメッセージ
    """
    config = get_web_fetch_config(tool_context)

    # URL バリデーション
    if not url.startswith(("http://", "https://")):
        return "無効なURLです。http:// または https:// で始まるURLを指定してください"

    logger.info("Web fetch: %s", url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.api_endpoint}/md",
                json={"url": url, "f": "llm", "q": None, "c": "0"},
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()

        data = response.json()

        if not data.get("success", False):
            logger.warning("Web fetch failed (API): %s", url)
            return "ページを取得できませんでした"

        markdown = data.get("markdown", "")

        # コンテンツ長制限
        if len(markdown) > config.max_content_length:
            markdown = (
                markdown[: config.max_content_length]
                + "\n\n（コンテンツが切り詰められました）"
            )

        logger.info("Web fetch success: %s", url)
        return markdown

    except httpx.TimeoutException:
        logger.warning("Web fetch timeout: %s", url)
        return "ページの取得がタイムアウトしました"
    except httpx.HTTPStatusError as e:
        logger.warning("Web fetch HTTP error: %s - %s", url, e)
        return "ページを取得できませんでした"
    except httpx.RequestError as e:
        logger.warning("Web fetch request error: %s - %s", url, e)
        return "ページを取得できませんでした"


WEB_FETCH_TOOLS = [web_fetch]


class WebFetchToolsFactory:
    """Web Fetch ツールのファクトリ。

    設定の注入と invocation_state の構築を担当する。
    """

    def __init__(self, config: WebFetchConfig) -> None:
        """ファクトリを初期化する。

        Args:
            config: Web Fetch 設定
        """
        self._config = config

    def get_invocation_state(self) -> dict:
        """invocation_state を取得する。

        Returns:
            Agent に渡す invocation_state 辞書
        """
        return {WEB_FETCH_CONFIG_KEY: self._config}

    @property
    def tools(self) -> list:
        """ツール関数のリストを取得する。

        Returns:
            Web Fetch ツール関数のリスト
        """
        return WEB_FETCH_TOOLS
