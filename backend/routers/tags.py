"""标签路由 - 用户自定义标签 CRUD"""
from fastapi import APIRouter, Depends, HTTPException, status

from deps import verify_token, get_tag_service
from models.schemas import (
    MessageOut,
    TagCreate,
    TagCreateOut,
    TagListOut,
    TagOut,
    TagUpdate,
)
from services.tag import TagService

router = APIRouter(prefix="/tags", tags=["标签"], dependencies=[Depends(verify_token)])


@router.get("", response_model=TagListOut)
def list_tags(svc: TagService = Depends(get_tag_service)):
    """获取所有标签 (含关联账号数)"""
    return {"tags": svc.list_all()}


@router.get("/{tag_id}", response_model=TagOut)
def get_tag(tag_id: int, svc: TagService = Depends(get_tag_service)):
    """查询单个标签"""
    tag = svc.get_by_id(tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return tag


@router.post("", response_model=TagCreateOut, status_code=status.HTTP_201_CREATED)
def create_tag(data: TagCreate, svc: TagService = Depends(get_tag_service)):
    """创建标签"""
    try:
        tag_id = svc.create(data.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"id": tag_id, "message": "标签创建成功"}


@router.put("/{tag_id}", response_model=MessageOut)
def update_tag(tag_id: int, data: TagUpdate, svc: TagService = Depends(get_tag_service)):
    """更新标签"""
    try:
        ok = svc.update(tag_id, data.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return {"message": "标签更新成功"}


@router.delete("/{tag_id}", response_model=MessageOut)
def delete_tag(tag_id: int, svc: TagService = Depends(get_tag_service)):
    """删除标签 (账号关联自动清理)"""
    if not svc.delete(tag_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return {"message": "标签删除成功"}
