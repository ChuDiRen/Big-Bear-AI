from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services import AuthService
# fmt: off  MC8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2VmtjeWRBPT06ZDk0MmM3OTk=

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        user = await AuthService.register(db, data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
# pragma: no cover  MS8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2VmtjeWRBPT06ZDk0MmM3OTk=


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        return await AuthService.login(db, data.username, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
