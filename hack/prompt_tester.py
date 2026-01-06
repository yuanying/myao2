#!/usr/bin/env python3
"""Prompt tester script for myao2.

LLM処理のシステムプロンプトを確認・テストするCLIツール。

Usage:
    uv run python hack/prompt_tester.py generate --channel general --dry-run
    uv run python hack/prompt_tester.py judgment --channel C01234567 --thread 1.2
    uv run python hack/prompt_tester.py summarize --scope workspace --type long_term
    uv run python hack/prompt_tester.py summarize --channel general --scope channel
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_dotenv(env_path: Path) -> None:
    """シンプルな .env ファイル読み込み

    Args:
        env_path: .env ファイルのパス
    """
    if not env_path.exists():
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 空行とコメントをスキップ
            if not line or line.startswith("#"):
                continue
            # KEY=VALUE 形式をパース
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # クォートを除去
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                # 既存の環境変数は上書きしない
                if key not in os.environ:
                    os.environ[key] = value


from myao2.application.use_cases.helpers import (  # noqa: E402
    WORKSPACE_SCOPE_ID,
    build_context_with_memory,
)
from myao2.config.loader import load_config  # noqa: E402
from myao2.domain.entities import LLMMetrics  # noqa: E402
from myao2.domain.entities.memory import MemoryScope, MemoryType  # noqa: E402
from myao2.infrastructure.llm.strands import (  # noqa: E402
    StrandsMemorySummarizer,
    StrandsResponseGenerator,
    StrandsResponseJudgment,
    create_model,
)
from myao2.infrastructure.persistence import (  # noqa: E402
    DatabaseManager,
    SQLiteChannelRepository,
    SQLiteMemoryRepository,
    SQLiteMessageRepository,
)


def print_prompt(title: str, prompt: str) -> None:
    """システムプロンプトを整形して出力"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print(prompt)
    print("=" * 60 + "\n")


def print_response(title: str, response: str | dict) -> None:
    """LLM応答を整形して出力"""
    print("\n" + "-" * 60)
    print(f"  {title}")
    print("-" * 60)
    if isinstance(response, dict):
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        print(response)
    print("-" * 60 + "\n")


def print_metrics(metrics: LLMMetrics | None) -> None:
    """LLMMetricsを整形して出力"""
    if metrics is None:
        print("(Metrics not available)")
        return

    print("\n" + "+" * 60)
    print("  Metrics")
    print("+" * 60)

    # Token usage
    print(f"  Input tokens:  {metrics.input_tokens:>8}")
    print(f"  Output tokens: {metrics.output_tokens:>8}")
    print(f"  Total tokens:  {metrics.total_tokens:>8}")

    # Performance
    print(f"  Total cycles:  {metrics.total_cycles:>8}")
    print(f"  Duration:      {metrics.total_duration:.2f}s")

    # Latency
    if metrics.latency_ms:
        print(f"  Latency:       {metrics.latency_ms:>8}ms")

    # Tool usage
    if metrics.tool_usage:
        print("\n  Tool Usage:")
        for tool_name, stats in metrics.tool_usage.items():
            exec_stats = stats.get("execution_stats", {})
            print(f"    - {tool_name}:")
            print(f"        Calls: {exec_stats.get('call_count', 0)}")
            print(f"        Success rate: {exec_stats.get('success_rate', 0):.1%}")
            print(f"        Avg time: {exec_stats.get('average_time', 0):.3f}s")

    print("+" * 60 + "\n")


async def resolve_channel(
    channel_repository: SQLiteChannelRepository,
    channel_identifier: str,
) -> tuple[str, str]:
    """チャネル名またはIDからチャネル情報を解決

    Args:
        channel_repository: チャネルリポジトリ
        channel_identifier: チャネル名またはチャネルID

    Returns:
        (channel_id, channel_name) のタプル

    Raises:
        SystemExit: チャネルが見つからない、または複数見つかった場合
    """
    # まずIDとして検索
    channel = await channel_repository.find_by_id(channel_identifier)
    if channel:
        return channel.id, channel.name

    # 名前として検索
    all_channels = await channel_repository.find_all()
    matches = [ch for ch in all_channels if ch.name == channel_identifier]

    if not matches:
        print(f"Error: Channel not found: {channel_identifier}", file=sys.stderr)
        print("\nAvailable channels:", file=sys.stderr)
        for ch in all_channels:
            print(f"  - {ch.name} ({ch.id})", file=sys.stderr)
        sys.exit(1)

    if len(matches) > 1:
        print(
            f"Error: Multiple channels found with name '{channel_identifier}':",
            file=sys.stderr,
        )
        for ch in matches:
            print(f"  - {ch.id}", file=sys.stderr)
        print("\nPlease specify by channel ID.", file=sys.stderr)
        sys.exit(1)

    return matches[0].id, matches[0].name


async def run_generate(
    args: argparse.Namespace,
    config,
    message_repository: SQLiteMessageRepository,
    memory_repository: SQLiteMemoryRepository,
    channel_repository: SQLiteChannelRepository,
) -> None:
    """generate サブコマンドを実行"""
    # チャネル解決
    channel_id, channel_name = await resolve_channel(channel_repository, args.channel)
    channel = await channel_repository.find_by_id(channel_id)
    if not channel:
        print(f"Error: Channel not found: {channel_id}", file=sys.stderr)
        sys.exit(1)

    print(f"Channel: {channel_name} ({channel_id})")
    if args.thread:
        print(f"Thread: {args.thread}")

    # Context構築
    context = await build_context_with_memory(
        memory_repository=memory_repository,
        message_repository=message_repository,
        channel_repository=channel_repository,
        persona=config.persona,
        channel=channel,
        target_thread_ts=args.thread,
    )

    # Create model and generator
    response_model = create_model(config.agents["response"])
    generator = StrandsResponseGenerator(response_model)

    # プロンプト構築
    system_prompt = generator.build_system_prompt(context)
    query_prompt = generator.build_query_prompt(context)
    print_prompt("Response Generator System Prompt", system_prompt)
    print_prompt("Response Generator Query Prompt", query_prompt)

    if not args.dry_run:
        print("Calling LLM...")
        result = await generator.generate(context)
        print_response("Generated Response", result.text)
        print_metrics(result.metrics)


async def run_judgment(
    args: argparse.Namespace,
    config,
    message_repository: SQLiteMessageRepository,
    memory_repository: SQLiteMemoryRepository,
    channel_repository: SQLiteChannelRepository,
) -> None:
    """judgment サブコマンドを実行"""
    # チャネル解決
    channel_id, channel_name = await resolve_channel(channel_repository, args.channel)
    channel = await channel_repository.find_by_id(channel_id)
    if not channel:
        print(f"Error: Channel not found: {channel_id}", file=sys.stderr)
        sys.exit(1)

    print(f"Channel: {channel_name} ({channel_id})")
    if args.thread:
        print(f"Thread: {args.thread}")

    # Context構築
    context = await build_context_with_memory(
        memory_repository=memory_repository,
        message_repository=message_repository,
        channel_repository=channel_repository,
        persona=config.persona,
        channel=channel,
        target_thread_ts=args.thread,
    )

    # Create model and judgment
    judgment_model = create_model(config.agents["judgment"])
    judgment = StrandsResponseJudgment(judgment_model)

    # プロンプト構築
    system_prompt = judgment.build_system_prompt(context)
    query_prompt = judgment.build_query_prompt(context)
    print_prompt("Response Judgment System Prompt", system_prompt)
    print_prompt("Response Judgment Query Prompt", query_prompt)

    if not args.dry_run:
        print("Calling LLM...")
        result = await judgment.judge(context)
        print_response(
            "Judgment Result",
            {
                "should_respond": result.should_respond,
                "reason": result.reason,
                "confidence": result.confidence,
            },
        )
        print_metrics(result.metrics)


async def run_summarize(
    args: argparse.Namespace,
    config,
    message_repository: SQLiteMessageRepository,
    memory_repository: SQLiteMemoryRepository,
    channel_repository: SQLiteChannelRepository,
) -> None:
    """summarize サブコマンドを実行"""
    scope = MemoryScope(args.scope)
    memory_type = MemoryType(args.type)

    # 引数検証
    if scope == MemoryScope.WORKSPACE:
        if args.channel:
            print("Warning: --channel is ignored for workspace scope", file=sys.stderr)
        channel = None
        channel_id = None
        channel_name = None
    elif scope == MemoryScope.CHANNEL:
        if not args.channel:
            print("Error: --channel is required for channel scope", file=sys.stderr)
            sys.exit(1)
        channel_id, channel_name = await resolve_channel(
            channel_repository, args.channel
        )
        channel = await channel_repository.find_by_id(channel_id)
    else:  # THREAD
        if not args.channel:
            print("Error: --channel is required for thread scope", file=sys.stderr)
            sys.exit(1)
        if not args.thread:
            print("Error: --thread is required for thread scope", file=sys.stderr)
            sys.exit(1)
        channel_id, channel_name = await resolve_channel(
            channel_repository, args.channel
        )
        channel = await channel_repository.find_by_id(channel_id)

    print(f"Scope: {scope.value}")
    print(f"Memory Type: {memory_type.value}")
    if channel_name:
        print(f"Channel: {channel_name} ({channel_id})")
    if args.thread:
        print(f"Thread: {args.thread}")

    # Context構築
    context = await build_context_with_memory(
        memory_repository=memory_repository,
        message_repository=message_repository,
        channel_repository=channel_repository,
        persona=config.persona,
        channel=channel,
        target_thread_ts=args.thread if scope == MemoryScope.THREAD else None,
    )

    # 既存メモリの取得（長期記憶更新用）
    existing_memory = None
    if memory_type == MemoryType.LONG_TERM:
        if scope == MemoryScope.WORKSPACE:
            mem = await memory_repository.find_by_scope_and_type(
                MemoryScope.WORKSPACE, WORKSPACE_SCOPE_ID, MemoryType.LONG_TERM
            )
            existing_memory = mem.content if mem else None
        elif scope == MemoryScope.CHANNEL and channel_id:
            mem = await memory_repository.find_by_scope_and_type(
                MemoryScope.CHANNEL, channel_id, MemoryType.LONG_TERM
            )
            existing_memory = mem.content if mem else None

    # Create model and summarizer
    memory_model = create_model(config.agents["memory"])
    summarizer = StrandsMemorySummarizer(model=memory_model, config=config.memory)

    # プロンプト構築
    system_prompt = summarizer.build_system_prompt(context, scope, memory_type)
    query_prompt = summarizer.build_query_prompt(
        context, scope, memory_type, existing_memory
    )
    print_prompt("Memory Summarizer System Prompt", system_prompt)
    print_prompt("Memory Summarizer Query Prompt", query_prompt)

    if not args.dry_run:
        print("Calling LLM...")
        result = await summarizer.summarize(
            context, scope, memory_type, existing_memory
        )
        print_response("Generated Memory", result.text)
        print_metrics(result.metrics)


def create_parser() -> argparse.ArgumentParser:
    """CLIパーサーを作成"""
    parser = argparse.ArgumentParser(
        description="myao2 プロンプトテスター",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 共通オプション
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="config.yaml のパス (default: config.yaml)",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="チャネルID または チャネル名",
    )
    parser.add_argument(
        "--thread",
        default=None,
        help="スレッドTS (オプション)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プロンプト表示のみ、LLM呼び出しなし",
    )

    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # generate サブコマンド
    subparsers.add_parser("generate", help="応答生成プロンプトをテスト")

    # judgment サブコマンド
    subparsers.add_parser("judgment", help="応答判定プロンプトをテスト")

    # summarize サブコマンド
    summarize_parser = subparsers.add_parser(
        "summarize", help="要約生成プロンプトをテスト"
    )
    summarize_parser.add_argument(
        "--scope",
        required=True,
        choices=["thread", "channel", "workspace"],
        help="メモリスコープ",
    )
    summarize_parser.add_argument(
        "--type",
        required=True,
        choices=["short_term", "long_term"],
        help="メモリタイプ",
    )

    return parser


async def main() -> None:
    """メインエントリポイント"""
    # プロジェクトルートの .env を読み込み
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")

    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 設定読み込み
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)

    # データベースファイルの存在確認
    db_path = config.memory.database_path
    if db_path != ":memory:" and not Path(db_path).exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # DatabaseManager を初期化
    db_manager = DatabaseManager(db_path)
    await db_manager.create_tables()

    # リポジトリ初期化
    message_repository = SQLiteMessageRepository(db_manager.get_session)
    memory_repository = SQLiteMemoryRepository(db_manager.get_session)
    channel_repository = SQLiteChannelRepository(db_manager.get_session)

    try:
        if args.command == "generate":
            if not args.channel:
                print("Error: --channel is required for generate", file=sys.stderr)
                sys.exit(1)
            await run_generate(
                args, config, message_repository, memory_repository, channel_repository
            )

        elif args.command == "judgment":
            if not args.channel:
                print("Error: --channel is required for judgment", file=sys.stderr)
                sys.exit(1)
            await run_judgment(
                args, config, message_repository, memory_repository, channel_repository
            )

        elif args.command == "summarize":
            await run_summarize(
                args, config, message_repository, memory_repository, channel_repository
            )

    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
