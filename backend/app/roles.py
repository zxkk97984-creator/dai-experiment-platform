from typing import Final, Literal, TypeAlias


UserRole: TypeAlias = Literal["student", "teacher", "admin"]
SUPPORTED_ROLES: Final[tuple[str, ...]] = ("student", "teacher", "admin")
VALID_ROLES: Final[frozenset[str]] = frozenset(SUPPORTED_ROLES)


def is_supported_role(role: str | None) -> bool:
    """Return whether a persisted/token role is supported by the application."""

    return role in VALID_ROLES
