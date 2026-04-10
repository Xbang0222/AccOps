"""分组路由 - 分组 CRUD、成员管理、号池管理"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List

from deps import verify_token, get_group_service
from models.schemas import GroupCreate, GroupUpdate
from services.group import GroupService

router = APIRouter(
    prefix="/groups", tags=["分组"], dependencies=[Depends(verify_token)]
)


@router.get("")
def list_groups(
    search: str = "",
    svc: GroupService = Depends(get_group_service),
):
    """获取所有分组 (支持按子号邮箱搜索)"""
    return {"groups": svc.get_all(search=search)}


@router.get("/{group_id}")
def get_group(group_id: int, svc: GroupService = Depends(get_group_service)):
    """获取分组详情（含成员）"""
    group = svc.get_with_accounts(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组不存在")
    return group


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(
    data: GroupCreate,
    svc: GroupService = Depends(get_group_service),
):
    """创建分组"""
    group_id = svc.create(name=data.name, notes=data.notes)
    return {"id": group_id, "message": "分组创建成功"}


@router.put("/{group_id}")
def update_group(
    group_id: int,
    data: GroupUpdate,
    svc: GroupService = Depends(get_group_service),
):
    """更新分组"""
    svc.update(
        group_id=group_id,
        name=data.name,
        main_account_id=data.main_account_id,
        notes=data.notes,
    )
    return {"message": "分组更新成功"}


@router.delete("/{group_id}")
def delete_group(
    group_id: int, svc: GroupService = Depends(get_group_service)
):
    """删除分组"""
    svc.delete(group_id)
    return {"message": "分组删除成功"}


@router.post("/{group_id}/accounts/{account_id}")
def add_account(
    group_id: int,
    account_id: int,
    svc: GroupService = Depends(get_group_service),
):
    """将账号添加到分组"""
    try:
        svc.add_account(group_id, account_id)
        return {"message": "账号已添加到分组"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/accounts/{account_id}")
def remove_account(
    account_id: int,
    svc: GroupService = Depends(get_group_service),
):
    """将账号从分组移除"""
    svc.remove_account(account_id)
    return {"message": "账号已从分组移除"}


@router.put("/{group_id}/main-account/{account_id}")
def set_main_account(
    group_id: int,
    account_id: int,
    svc: GroupService = Depends(get_group_service),
):
    """设置分组主号"""
    try:
        svc.set_main_account(group_id, account_id)
        return {"message": "主号设置成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── 号池管理 ──


class PoolAccountIds(BaseModel):
    account_ids: List[int]


@router.get("/{group_id}/pool")
def get_pool_accounts(
    group_id: int,
    svc: GroupService = Depends(get_group_service),
):
    """获取分组号池中的可用账号"""
    accounts = svc.get_pool_accounts(group_id)
    return {"accounts": accounts}


@router.post("/{group_id}/pool")
def add_to_pool(
    group_id: int,
    data: PoolAccountIds,
    svc: GroupService = Depends(get_group_service),
):
    """将账号批量添加到分组号池"""
    count = svc.add_to_pool(group_id, data.account_ids)
    return {"message": f"已添加 {count} 个账号到号池"}


@router.delete("/{group_id}/pool")
def remove_from_pool(
    group_id: int,
    data: PoolAccountIds,
    svc: GroupService = Depends(get_group_service),
):
    """将账号批量从号池移除"""
    count = svc.remove_from_pool(group_id, data.account_ids)
    return {"message": f"已从号池移除 {count} 个账号"}


# ── 号池状态标记 ──


@router.post("/pool/mark-unusable/{account_id}")
def mark_pool_unusable(
    account_id: int,
    svc: GroupService = Depends(get_group_service),
):
    """标记号池账号为「无法使用」（地区限制等原因）"""
    if not svc.mark_pool_unusable(account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"message": "已标记为无法使用"}


@router.post("/pool/clear-status/{account_id}")
def clear_pool_status(
    account_id: int,
    svc: GroupService = Depends(get_group_service),
):
    """清除号池状态标记，恢复正常"""
    if not svc.clear_pool_status(account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"message": "已恢复正常状态"}
