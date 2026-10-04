from __future__ import annotations

from fastapi import HTTPException, status

ROLE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "admin": (
        "balances:read",
        "balances:write",
        "usage:read",
        "workspaces:read",
        "workspaces:manage",
        "total_balances:read",
        "users:manage",
        "preferences:timezone:write",
    ),
    "member": (
        "balances:read",
        "usage:read",
        "workspaces:read",
        "total_balances:read",
        "preferences:timezone:write",
    ),
    "user": (
        "balances:read",
        "balances:write",
        "usage:read",
        "workspaces:read",
        "total_balances:read",
        "preferences:timezone:write",
    ),
}


def capabilities_for_role(role: str) -> list[str]:
    return list(ROLE_CAPABILITIES.get(role, ()))


def require_capability(user: dict, capability: str) -> None:
    if capability not in user.get("capabilities", ()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
