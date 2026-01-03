from typing import List, Optional
from pydantic import BaseModel

from app.care_sessions.schemas import CareSessionResponse


class CareSessionReportPage(BaseModel):
    """Cursor-paginated report response."""
    items: List[CareSessionResponse]
    next_cursor: Optional[str] = None
