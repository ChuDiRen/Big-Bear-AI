from __future__ import annotations

from typing import Any

from langgraph_sdk import Auth

from big_bear_ai.auth.service import verify_token


auth = Auth()


@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    try:
        payload = verify_token(authorization)
    except ValueError as error:
        raise Auth.exceptions.HTTPException(status_code=401, detail=str(error)) from error
    return {
        "identity": payload["sub"],
        "display_name": payload.get("email", payload["sub"]),
        "permissions": [payload.get("role", "user")],
    }


@auth.on
async def scope_owned_resources(
    ctx: Auth.types.AuthContext,
    value: dict[str, Any],
) -> Auth.types.FilterType:
    metadata = value.setdefault("metadata", {})
    metadata.setdefault("owner", ctx.user.identity)
    return {"owner": ctx.user.identity}