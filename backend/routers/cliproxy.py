"""CLIProxyAPI 集成路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from deps import verify_token
from models.database import get_db
from services import cliproxy as svc

router = APIRouter(
    prefix="/cliproxy",
    tags=["CLIProxyAPI 集成"],
    dependencies=[Depends(verify_token)],
)


class UploadRequest(BaseModel):
    account_ids: list[int]


class UploadItem(BaseModel):
    account_id: int
    email: str
    success: bool
    message: str


class UploadResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    items: list[UploadItem]


@router.post("/upload", response_model=UploadResponse)
async def upload(req: UploadRequest, db: Session = Depends(get_db)):
    if not req.account_ids:
        raise HTTPException(400, "account_ids 不能为空")
    try:
        results = await svc.upload_accounts(db, req.account_ids)
    except ValueError as e:
        raise HTTPException(400, str(e))
    items = [
        UploadItem(
            account_id=r.account_id,
            email=r.email,
            success=r.success,
            message=r.message,
        )
        for r in results
    ]
    return UploadResponse(
        total=len(items),
        succeeded=sum(1 for x in items if x.success),
        failed=sum(1 for x in items if not x.success),
        items=items,
    )


@router.get("/status")
async def status(db: Session = Depends(get_db)):
    return await svc.check_status(db)
