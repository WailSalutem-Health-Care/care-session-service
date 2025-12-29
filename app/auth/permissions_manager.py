"""Permissions Management"""
import yaml
from pathlib import Path
from typing import Dict, List


class PermissionsManager:
    """Manages role-to-permissions mapping from permissions.yml"""
    
    def __init__(self, permissions_file_path: str = None):
        if permissions_file_path is None:
            # Default to permissions.yml in project root
            permissions_file_path = Path(__file__).parent.parent.parent / "permissions.yml"
        
        self.role_permissions = self._load_permissions(permissions_file_path)
    
    def _load_permissions(self, file_path: Path) -> Dict[str, List[str]]:
        """Load role-to-permissions mapping from YAML file"""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('roles', {})
        except Exception:
            return {}
    
    def get_permissions_for_roles(self, roles: List[str]) -> List[str]:
        """Convert list of roles to list of permissions"""
        permissions = set()
        for role in roles:
            role_perms = self.role_permissions.get(role, [])
            permissions.update(role_perms)
        return list(permissions)
