"""Database management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Import models to register them with SQLModel metadata
from myao2.infrastructure.persistence import models as _models  # noqa: F401


class DatabaseManager:
    """データベース管理

    SQLite データベースの初期化、エンジン生成、セッション管理を行う。
    aiosqlite を使用した非同期アクセスをサポート。
    """

    def __init__(self, database_path: str) -> None:
        """初期化

        Args:
            database_path: SQLite データベースファイルのパス
                          ":memory:" を指定するとインメモリDBを使用
        """
        self._database_path = database_path
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def get_engine(self) -> AsyncEngine:
        """SQLAlchemy 非同期エンジンを取得する

        エンジンは遅延初期化され、キャッシュされる。
        データベースファイルの親ディレクトリが存在しない場合は自動作成する。

        Returns:
            AsyncEngine インスタンス
        """
        if self._engine is not None:
            return self._engine

        # Create parent directory for non-memory databases
        if self._database_path != ":memory:":
            db_path = Path(self._database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite+aiosqlite:///{self._database_path}"
        else:
            url = "sqlite+aiosqlite:///:memory:"

        self._engine = create_async_engine(url)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        return self._engine

    async def create_tables(self) -> None:
        """テーブルを作成する

        既存のテーブルがある場合は何もしない。
        """
        engine = self.get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """セッションを取得する（async context manager）

        Yields:
            AsyncSession インスタンス
        """
        self.get_engine()  # Ensures _session_factory is initialized
        assert self._session_factory is not None
        async with self._session_factory() as session:
            yield session
