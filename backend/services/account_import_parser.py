"""账号导入行解析器。"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedAccountImportLine:
    email: str
    password: str
    recovery_email: str = ""
    totp_secret: str = ""
    group_name: str = ""
    notes: str = ""


def looks_like_totp_secret(value: str) -> bool:
    """判断字段是否像 TOTP 密钥。"""
    if " " in value or len(value) < 12:
        return False
    return bool(re.match(r"^[A-Za-z2-7=]+$", value))


def parse_account_import_line(
    line: str,
    *,
    default_group_name: str = "",
    default_notes: str = "",
) -> ParsedAccountImportLine:
    delimiter = "----" if "----" in line else "|"
    parts = [part.strip() for part in line.split(delimiter)]

    email = parts[0] if parts else ""
    if not email:
        raise ValueError("邮箱为空")

    password = parts[1] if len(parts) > 1 else ""
    recovery_email = ""
    totp_secret = ""
    links: list[str] = []
    extra_notes: list[str] = []

    for field in parts[2:]:
        if not field:
            continue
        if "@" in field and not field.startswith("http"):
            recovery_email = field
            continue
        if field.startswith("http://") or field.startswith("https://"):
            links.append(field)
            continue
        if looks_like_totp_secret(field) and not totp_secret:
            totp_secret = field
            continue
        extra_notes.append(field)

    notes_parts: list[str] = []
    if links:
        links_text = "\n".join(links)
        notes_parts.append(f"验证链接: {links_text}")
    if default_notes:
        notes_parts.append(default_notes)
    if extra_notes:
        notes_parts.append(", ".join(extra_notes))

    return ParsedAccountImportLine(
        email=email,
        password=password,
        recovery_email=recovery_email,
        totp_secret=totp_secret,
        group_name=default_group_name,
        notes="\n".join(notes_parts),
    )
