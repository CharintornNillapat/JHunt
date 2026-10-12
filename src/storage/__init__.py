# src/storage/__init__.py
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union

from .db import DatabaseManager, DEFAULT_DB_PATH
from .turso_client import TursoClient

logger = logging.getLogger(__name__)


def get_storage(
    database_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
    force_sqlite: bool = False,
    require_cloud: Optional[bool] = None,
) -> Union[TursoClient, DatabaseManager]:
    """
    Factory that returns the active unified storage provider.
    - If TURSO_DATABASE_URL is present and force_sqlite is False,
      instantiates and returns a TursoClient connected to the cloud database.
    - If Turso credentials are missing or connection fails, gracefully falls back
      to local DatabaseManager (SQLite) unless cloud is required.
    - If require_cloud is True (or JHUNT_REQUIRE_TURSO=1 in env) and Turso is unavailable,
      raises RuntimeError instead of falling back to ephemeral SQLite.
    """
    if require_cloud is None:
        require_cloud = (os.getenv("JHUNT_REQUIRE_TURSO") or "").strip().lower() in ("1", "true", "yes", "on")

    if not force_sqlite:
        url = (database_url or os.getenv("TURSO_DATABASE_URL") or "").strip().strip('"').strip("'")
        token = (auth_token or os.getenv("TURSO_AUTH_TOKEN") or "").strip().strip('"').strip("'")
        if url:
            try:
                turso = TursoClient(database_url=url, auth_token=token)
                if turso.is_available:
                    return turso
                logger.info("[Storage] Turso client unavailable. Falling back to local SQLite.")
            except Exception as e:
                logger.warning(f"[Storage] Failed to initialize Turso client ({e}). Falling back to local SQLite.")

    if require_cloud:
        raise RuntimeError(
            "JHUNT_REQUIRE_TURSO is set but Turso is unavailable; refusing to write to ephemeral local SQLite."
        )

    return DatabaseManager(db_path=db_path)


__all__ = ["DatabaseManager", "DEFAULT_DB_PATH", "TursoClient", "get_storage"]
