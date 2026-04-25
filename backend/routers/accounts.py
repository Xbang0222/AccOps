"""账号路由 - 账号 CRUD、分组/标签查询、TOTP、批量导入"""
import time
import pyotp
from fastapi import APIRouter, HTTPException, Depends, status

from deps import verify_token, get_account_service
from models.schemas import AccountCreate, AccountUpdate, AccountImportRequest
from services.account import AccountService
from services.account_import_parser import parse_account_import_line

router = APIRouter(prefix="/accounts", tags=["账号"], dependencies=[Depends(verify_token)])


@router.get("")
def list_accounts(
    search: str = "",
    group: str = "",
    page: int = 1,
    page_size: int = 20,
    owner_only: bool = False,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    svc: AccountService = Depends(get_account_service),
):
    """获取账号列表（支持搜索/筛选/分页/排序）"""
    accounts, total = svc.get_all(
        search, group, page, page_size, owner_only, sort_by, sort_order,
    )
    return {"accounts": accounts, "total": total, "page": page, "page_size": page_size}


@router.get("/groups")
def list_groups(svc: AccountService = Depends(get_account_service)):
    """获取所有分组"""
    return {"groups": svc.get_all_groups()}


@router.get("/available")
def list_available_accounts(
    search: str = "",
    svc: AccountService = Depends(get_account_service),
):
    """获取未加入家庭组的可用账号（仅返回 id + email，供邀请选择）"""
    accounts = svc.get_available(search)
    return {"accounts": accounts}


@router.get("/{account_id}")
def get_account(account_id: int, svc: AccountService = Depends(get_account_service)):
    """获取单个账号"""
    account = svc.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return account


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(
    data: AccountCreate,
    svc: AccountService = Depends(get_account_service),
):
    """创建账号"""
    account_id = svc.create(
        email=data.email,
        password=data.password,
        recovery_email=data.recovery_email,
        totp_secret=data.totp_secret,
        group_name=data.group_name,
        family_group_id=data.group_id,
        notes=data.notes,
    )
    return {"id": account_id, "message": "账号创建成功"}


@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_accounts(
    data: AccountImportRequest,
    svc: AccountService = Depends(get_account_service),
):
    """批量导入账号

    支持多种格式 (用 ---- 分隔), 智能识别字段类型:
    - 格式1: 邮箱----密码----辅助邮箱----2FA密钥----短信验证链接
    - 格式2: 邮箱----密码----辅助邮箱----webhook链接
    - 格式3: 邮箱----密码----辅助邮箱
    - 格式4: 邮箱----密码

    字段识别规则 (第3个字段起):
    - 含 @ → 辅助邮箱
    - 以 http:// 或 https:// 开头 → 链接 (记录到备注)
    - 其他 → 2FA 密钥
    """
    lines = [line.strip() for line in data.text.strip().splitlines() if line.strip()]
    if not lines:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="导入内容为空")

    results = {"success": 0, "skipped": 0, "failed": 0, "details": []}

    for line in lines:
        try:
            parsed = parse_account_import_line(
                line,
                default_group_name=data.group_name or "",
                default_notes=data.notes or "",
            )
        except ValueError as exc:
            results["failed"] += 1
            results["details"].append({"line": line, "status": "failed", "reason": str(exc)})
            continue

        # 检查邮箱是否已存在
        existing = svc.find_by_email(parsed.email)
        if existing:
            results["skipped"] += 1
            results["details"].append({"email": parsed.email, "status": "skipped", "reason": "邮箱已存在"})
            continue

        try:
            account_id = svc.create(
                email=parsed.email,
                password=parsed.password,
                recovery_email=parsed.recovery_email,
                totp_secret=parsed.totp_secret,
                group_name=parsed.group_name,
                notes=parsed.notes,
            )
            results["success"] += 1
            results["details"].append({"email": parsed.email, "status": "success", "id": account_id})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"email": parsed.email, "status": "failed", "reason": str(e)})

    return {
        "message": f"导入完成: 成功 {results['success']}, 跳过 {results['skipped']}, 失败 {results['failed']}",
        **results,
    }


@router.put("/{account_id}")
def update_account(
    account_id: int,
    data: AccountUpdate,
    svc: AccountService = Depends(get_account_service),
):
    """更新账号"""
    svc.update(
        account_id=account_id,
        email=data.email,
        password=data.password,
        recovery_email=data.recovery_email,
        totp_secret=data.totp_secret,
        group_name=data.group_name,
        family_group_id=data.group_id,
        notes=data.notes,
    )
    return {"message": "账号更新成功"}


@router.delete("/{account_id}")
def delete_account(account_id: int, svc: AccountService = Depends(get_account_service)):
    """删除账号"""
    svc.delete(account_id)
    return {"message": "账号删除成功"}


@router.post("/{account_id}/mark-unusable")
def mark_unusable(account_id: int, svc: AccountService = Depends(get_account_service)):
    """手动标记账号为「无法使用」"""
    if not svc.mark_unusable(account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"message": "已标记为无法使用"}


@router.post("/{account_id}/clear-status")
def clear_status(account_id: int, svc: AccountService = Depends(get_account_service)):
    """清除状态标记，恢复正常"""
    if not svc.clear_status(account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    return {"message": "已恢复正常状态"}


@router.get("/{account_id}/totp")
def get_totp_code(account_id: int, svc: AccountService = Depends(get_account_service)):
    """获取账号的 TOTP 验证码"""
    account = svc.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    if not account.get("totp_secret"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号未设置2FA密钥")

    try:
        totp = pyotp.TOTP(account["totp_secret"].replace(' ', ''))
        code = totp.now()
        remaining = 30 - (int(time.time()) % 30)
        return {"code": code, "remaining": remaining, "formatted": f"{code[:3]} {code[3:]}"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"生成验证码失败: {e}")
