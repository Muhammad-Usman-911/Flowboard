"""Enums shared by models and schemas."""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        """Higher rank = more power. Used for "at least this role" checks."""
        return {"viewer": 0, "member": 1, "admin": 2, "owner": 3}[self.value]

    def at_least(self, other: "Role") -> bool:
        return self.rank >= other.rank


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
