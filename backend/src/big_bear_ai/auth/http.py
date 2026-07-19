from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from big_bear_ai.auth.service import (
    TOKEN_TTL_DAYS,
    authenticate_user,
    issue_token,
    public_user,
)


class Registration(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class Credentials(BaseModel):
    username: str
    password: str


app = FastAPI(title="Big Bear AI API", version="0.1.0")


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: Registration) -> dict:
    try:
        from big_bear_ai.auth.service import register_user

        return public_user(register_user(**payload.model_dump()))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/auth/login")
def login(payload: Credentials) -> dict:
    try:
        user = authenticate_user(payload.username, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {
        "access_token": issue_token(user),
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_DAYS * 24 * 60 * 60,
        "user": public_user(user),
    }