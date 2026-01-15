"""Shared repository base helpers."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class BaseRepository:
    """Base repository with common DB helpers."""

    def __init__(self, db: AsyncSession, tenant_schema: str, include_public: bool = False):
        self.db = db
        self.tenant_schema = tenant_schema
        self.include_public = include_public

    async def _set_search_path(self):
        """Set PostgreSQL search_path to tenant schema."""
        if self.include_public:
            await self.db.execute(text(f'SET search_path TO "{self.tenant_schema}", public'))
        else:
            await self.db.execute(text(f'SET search_path TO "{self.tenant_schema}"'))
