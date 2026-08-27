from sqlalchemy import text
from pymilvus import MilvusClient

from app.core.config import settings
from app.database.session import engine


def check_postgres() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:
        return False, str(exc)


def check_milvus() -> tuple[bool, str]:
    client: MilvusClient | None = None

    try:
        client = MilvusClient(uri=settings.milvus_uri)
        client.list_collections(timeout=3)
        return True, "connected"
    except Exception as exc:
        return False, str(exc)
    finally:
        if client is not None:
            client.close()