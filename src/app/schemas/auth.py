import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# pylint: disable  MC8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2ZFU5M1RBPT06NGY5NDkxZTY=

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    display_name: str | None
    is_active: bool
    role: str
    created_at: datetime.datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
# pragma: no cover  MS8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2ZFU5M1RBPT06NGY5NDkxZTY=
