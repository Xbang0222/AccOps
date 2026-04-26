"""通用入参解析工具"""
from typing import List


def parse_int_list(raw: str) -> List[int]:
    """解析逗号分隔的整数列表，跳过空值与非法值。

    例: "1,2,foo,,3" -> [1, 2, 3]
    """
    if not raw:
        return []
    result: List[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            result.append(int(piece))
        except ValueError:
            continue
    return result
