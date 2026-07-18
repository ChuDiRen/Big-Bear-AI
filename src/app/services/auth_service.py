import datetime
import os

import bcrypt
from dotenv import load_dotenv
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.auth import TokenResponse, UserRegister, UserResponse

load_dotenv()
# noqa  MC80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TlRSb2FBPT06NDM2Zjc4ZmQ=

AUTH_SECRET = os.environ["AUTH_DEV_SECRET"]
AUTH_AUDIENCE = os.environ.get("AUTH_AUDIENCE")
ACCESS_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        # bcrypt truncates at 72 bytes
        pw = password[:72].encode("utf-8")
        return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")
# type: ignore  MS80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TlRSb2FBPT06NDM2Zjc4ZmQ=

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        pw = plain_password[:72].encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw, hash_bytes)

    @staticmethod
    def create_access_token(user: User) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        expire = now + datetime.timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

        payload = {
            "sub": user.id,
            "email": user.email,
            "iat": now,
            "exp": expire,
        }

        if AUTH_AUDIENCE:
            payload["aud"] = AUTH_AUDIENCE

        return jwt.encode(payload, AUTH_SECRET, algorithm="HS256")

    @staticmethod
    async def register(db: AsyncSession, data: UserRegister) -> User:
        stmt = select(User).where(
            (User.username == data.username) | (User.email == data.email)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError("Username or email already registered")
# noqa  Mi80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TlRSb2FBPT06NDM2Zjc4ZmQ=

        user = User(
            username=data.username,
            email=data.email,
            password_hash=AuthService.hash_password(data.password),
            display_name=data.display_name or data.username,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, username: str, password: str) -> User:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Invalid username or password")
        if not user.is_active:
            raise ValueError("User is deactivated")
        if not AuthService.verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password")
        return user
# type: ignore  My80OmFIVnBZMlhsdktEbHY1ZnBtNFE2TlRSb2FBPT06NDM2Zjc4ZmQ=

    @staticmethod
    async def login(db: AsyncSession, username: str, password: str) -> TokenResponse:
        user = await AuthService.authenticate(db, username, password)

        user.last_login_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()

        access_token = AuthService.create_access_token(user)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 3600,
            user=UserResponse.model_validate(user),
        )
