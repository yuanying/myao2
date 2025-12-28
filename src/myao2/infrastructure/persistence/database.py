"""Database management."""

from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

# Import models to register them with SQLModel metadata
from myao2.infrastructure.persistence import models as _models  # noqa: F401


class DatabaseManager:
    """データベース管理

    SQLite データベースの初期化、エンジン生成、セッション管理を行う。
    """

    def __init__(self, database_path: str) -> None:
        """初期化

        Args:
            database_path: SQLite データベースファイルのパス
                          ":memory:" を指定するとインメモリDBを使用
        """
        self._database_path = database_path
        self._engine: Engine | None = None

    def get_engine(self) -> Engine:
        """SQLAlchemy エンジンを取得する

        エンジンは遅延初期化され、キャッシュされる。
        データベースファイルの親ディレクトリが存在しない場合は自動作成する。

        Returns:
            Engine インスタンス
        """
        if self._engine is not None:
            return self._engine

        # Create parent directory for non-memory databases
        if self._database_path != ":memory:":
            db_path = Path(self._database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{self._database_path}"
        else:
            url = "sqlite:///:memory:"

        self._engine = create_engine(url)
        return self._engine

    def create_tables(self) -> None:
        """テーブルを作成する

        既存のテーブルがある場合は何もしない。
        """
        engine = self.get_engine()
        SQLModel.metadata.create_all(engine)

    def get_session(self) -> Session:
        """セッションを取得する

        Returns:
            Session インスタンス
        """
        engine = self.get_engine()
        return Session(engine)
