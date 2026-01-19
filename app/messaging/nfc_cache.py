from typing import Optional
from uuid import UUID


class NFCTagCache:
    def __init__(self):
        self._cache: dict[str, str] = {}
    
    def store(self, tag_id: str, patient_id: str) -> None:
        """Store tag_id -> patient_id mapping (global, no tenant namespace)"""
        self._cache[tag_id] = patient_id
    
    def get_patient_id(self, tag_id: str) -> Optional[UUID]:
        """Get patient_id by tag_id (global lookup, no tenant context needed)"""
        patient_id = self._cache.get(tag_id)
        return UUID(patient_id) if patient_id else None


_cache: Optional[NFCTagCache] = None

def get_nfc_cache() -> NFCTagCache:
    global _cache
    if _cache is None:
        _cache = NFCTagCache()
    return _cache
