"""Memory repository protocol."""

from typing import Protocol

from myao2.domain.entities.memory import Memory, MemoryScope, MemoryType


class MemoryRepository(Protocol):
    """記憶リポジトリ"""

    async def save(self, memory: Memory) -> None:
        """記憶を保存（upsert）

        同じ scope, scope_id, memory_type の記憶が存在する場合は更新する。

        Args:
            memory: 保存する記憶
        """
        ...

    async def find_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> Memory | None:
        """スコープ、スコープID、タイプで記憶を検索

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID
            memory_type: 記憶の種類

        Returns:
            見つかった記憶、または None
        """
        ...

    async def find_all_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> list[Memory]:
        """スコープとスコープIDで全記憶を取得

        同じスコープ・スコープIDでも、memory_type が異なる記憶
        （LONG_TERM と SHORT_TERM）が複数存在する可能性があるため
        リストを返す。

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID

        Returns:
            該当する記憶のリスト（最大2件: LONG_TERM と SHORT_TERM）
        """
        ...

    async def delete_by_scope_and_type(
        self,
        scope: MemoryScope,
        scope_id: str,
        memory_type: MemoryType,
    ) -> None:
        """スコープ、スコープID、タイプで記憶を削除

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID
            memory_type: 記憶の種類
        """
        ...

    async def delete_by_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
    ) -> None:
        """スコープとスコープIDで記憶を削除

        Args:
            scope: 記憶のスコープ
            scope_id: スコープ固有の ID
        """
        ...
