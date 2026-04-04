"""接码平台 API 封装 - 多提供商抽象

支持的提供商:
- herosms: HeroSMS (SMS-Activate 协议兼容)
- smsbus: SMS-Bus (独立 REST API)
"""

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, List

import httpx

from core.constants import (
    COUNTRY_PHONE_CODES,
    HEROSMS_DEFAULT_URL,
    SMSBUS_DEFAULT_URL,
    SMS_WAIT_TIMEOUT,
    SMS_POLL_INTERVAL,
    SMS_HTTP_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _get_phone_code(country_name: str) -> str:
    """根据国家名获取电话区号"""
    code = COUNTRY_PHONE_CODES.get(country_name, "")
    if not code:
        # 模糊匹配
        name_lower = country_name.lower()
        for k, v in COUNTRY_PHONE_CODES.items():
            if k.lower() in name_lower or name_lower in k.lower():
                return v
    return code


# ── 抽象基类 ──────────────────────────────────────────

class SmsProviderBase(ABC):
    """接码提供商抽象基类"""

    def __init__(self, api_key: str, base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else self.default_base_url

    @property
    @abstractmethod
    def default_base_url(self) -> str: ...

    @abstractmethod
    def get_balance(self) -> Tuple[bool, str]:
        """返回: (成功?, 余额字符串)"""
        ...

    @abstractmethod
    def get_number(self, service: str, country: int, operator: str = "",
                   max_price: float = None) -> Tuple[bool, dict]:
        """返回: (成功?, {activation_id, phone_number, cost, ...} 或 {error: ...})"""
        ...

    @abstractmethod
    def get_status(self, activation_id: str) -> Tuple[str, str]:
        """返回: (状态码, 验证码或附加信息)
        统一状态码: WAIT / RECEIVED:<code> / CANCEL / ERROR:<msg>
        """
        ...

    @abstractmethod
    def cancel(self, activation_id: str) -> str:
        """取消激活, 返回结果文本"""
        ...

    @abstractmethod
    def finish(self, activation_id: str) -> str:
        """完成激活, 返回结果文本"""
        ...

    @abstractmethod
    def get_countries(self) -> list:
        """返回: [{id, name}]"""
        ...

    @abstractmethod
    def get_services(self) -> list:
        """返回: [{code, name}]"""
        ...

    @abstractmethod
    def get_prices_by_service(self, service: str) -> list:
        """返回: [{country_id, country_name, count, price}]"""
        ...

    def wait_for_code(self, activation_id: str, timeout: int = SMS_WAIT_TIMEOUT,
                      interval: float = SMS_POLL_INTERVAL) -> Tuple[bool, str, str]:
        """轮询等待验证码 (通用实现)
        返回: (成功?, 纯验证码, 完整短信)
        """
        start = time.time()
        while time.time() - start < timeout:
            status, info = self.get_status(activation_id)

            if status.startswith("RECEIVED:"):
                code = status.split(":", 1)[1]
                return True, code, info or code

            if status == "CANCEL":
                return False, "", "已取消"

            if status.startswith("ERROR:"):
                return False, "", info

            # WAIT → 继续轮询
            time.sleep(interval)

        return False, "", "等待验证码超时"


# ── HeroSMS 实现 (SMS-Activate 协议) ─────────────────

class HeroSmsProvider(SmsProviderBase):
    """HeroSMS - 兼容 SMS-Activate 协议"""

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key, base_url)
        self._country_cache: Optional[dict] = None  # id -> name 缓存

    @property
    def default_base_url(self) -> str:
        return HEROSMS_DEFAULT_URL

    def _get(self, action: str, **params) -> str:
        params["action"] = action
        params["api_key"] = self.api_key
        resp = httpx.get(self.base_url, params=params, timeout=SMS_HTTP_TIMEOUT)
        return resp.text.strip()

    def _get_json(self, action: str, **params) -> dict:
        params["action"] = action
        params["api_key"] = self.api_key
        resp = httpx.get(self.base_url, params=params, timeout=SMS_HTTP_TIMEOUT)
        return resp.json()

    def get_balance(self) -> Tuple[bool, str]:
        text = self._get("getBalance")
        if text.startswith("ACCESS_BALANCE:"):
            return True, text.split(":")[1]
        return False, text

    def get_number(self, service: str, country: int, operator: str = "",
                   max_price: float = None) -> Tuple[bool, dict]:
        params = {"service": service, "country": country}
        if operator:
            params["operator"] = operator
        if max_price is not None:
            params["maxPrice"] = max_price
        try:
            data = self._get_json("getNumberV2", **params)
            if "activationId" in data:
                return True, {
                    "activation_id": str(data["activationId"]),
                    "phone_number": str(data.get("phoneNumber", "")),
                    "cost": str(data.get("activationCost", "")),
                    "operator": str(data.get("activationOperator", "")),
                }
            return False, {"error": str(data)}
        except Exception:
            text = self._get("getNumber", **params)
            if text.startswith("ACCESS_NUMBER:"):
                parts = text.split(":")
                return True, {"activation_id": parts[1], "phone_number": parts[2], "cost": "", "operator": ""}
            return False, {"error": text}

    def get_status(self, activation_id: str) -> Tuple[str, str]:
        text = self._get("getStatus", id=activation_id)
        if text.startswith("STATUS_OK:"):
            code = text.split(":", 1)[1].strip()
            match = re.search(r'\d{4,8}', code)
            pure_code = match.group(0) if match else code
            return f"RECEIVED:{pure_code}", code
        if "FULL_SMS" in text:
            info = text.split(":", 1)[1] if ":" in text else text
            match = re.search(r'\d{4,8}', info)
            pure_code = match.group(0) if match else info.strip()
            return f"RECEIVED:{pure_code}", info
        if text == "STATUS_CANCEL":
            return "CANCEL", ""
        # STATUS_WAIT_CODE / STATUS_WAIT_RETRY
        return "WAIT", ""

    def cancel(self, activation_id: str) -> str:
        return self._get("cancelActivation", id=activation_id)

    def finish(self, activation_id: str) -> str:
        return self._get("finishActivation", id=activation_id)

    def get_countries(self) -> list:
        data = self._get_json("getCountries")
        result = []
        if isinstance(data, list):
            for item in data:
                name = item.get("eng", "") or item.get("chn", "") or str(item.get("id", ""))
                result.append({"id": item.get("id", 0), "name": name, "phone_code": _get_phone_code(name)})
        elif isinstance(data, dict):
            for cid, info in data.items():
                name = info.get("eng", "") or info.get("chn", "") or str(cid) if isinstance(info, dict) else str(info)
                result.append({"id": int(cid), "name": name, "phone_code": _get_phone_code(name)})
        return sorted(result, key=lambda x: x["name"])

    def get_services(self) -> list:
        data = self._get_json("getServicesList")
        result = []
        # HeroSMS 返回: {"status": "success", "services": [{code, name}, ...]}
        services_list = data.get("services", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for item in services_list:
            if isinstance(item, dict):
                result.append({"code": item.get("code", ""), "name": item.get("name", "")})
        return sorted(result, key=lambda x: x["name"])

    def get_prices_by_service(self, service: str) -> list:
        """获取某服务在各国的价格和可用数量"""
        # 缓存国家名称映射
        if self._country_cache is None:
            countries = self.get_countries()
            self._country_cache = {c["id"]: c for c in countries}
        country_map = self._country_cache

        data = self._get_json("getTopCountriesByService", service=service)
        result = []
        if isinstance(data, dict):
            for _, info in data.items():
                if not isinstance(info, dict):
                    continue
                cid = int(info.get("country", 0))
                c = country_map.get(cid, {})
                result.append({
                    "country_id": cid,
                    "country_name": c.get("name", str(cid)),
                    "phone_code": c.get("phone_code", ""),
                    "count": int(info.get("count", 0)),
                    "price": str(info.get("price", "")),
                })
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                cid = int(item.get("country", item.get("id", 0)))
                c = country_map.get(cid, {})
                result.append({
                    "country_id": cid,
                    "country_name": c.get("name", str(cid)),
                    "phone_code": c.get("phone_code", ""),
                    "count": int(item.get("count", 0)),
                    "price": str(item.get("price", "")),
                })
        return sorted(result, key=lambda x: -x["count"])


# ── SMS-Bus 实现 ─────────────────────────────────────

class SmsBusProvider(SmsProviderBase):
    """SMS-Bus - 独立 REST API"""

    @property
    def default_base_url(self) -> str:
        return SMSBUS_DEFAULT_URL

    def _get(self, path: str, **params) -> dict:
        params["token"] = self.api_key
        url = f"{self.base_url}/{path}"
        resp = httpx.get(url, params=params, timeout=SMS_HTTP_TIMEOUT)
        return resp.json()

    def get_balance(self) -> Tuple[bool, str]:
        data = self._get("get/balance")
        if data.get("code") == 200:
            balance = data.get("data", {}).get("balance", 0)
            return True, str(balance)
        return False, data.get("message", "未知错误")

    def get_number(self, service: str, country: int, operator: str = "",
                   max_price: float = None) -> Tuple[bool, dict]:
        # SMS-Bus 用 project_id (int) + country_id (int)
        # service 传过来的可能是 code 字符串, 需要转 project_id
        params = {"country_id": country, "project_id": service}
        data = self._get("get/number", **params)
        if data.get("code") == 200:
            d = data.get("data", {})
            return True, {
                "activation_id": str(d.get("request_id", "")),
                "phone_number": str(d.get("number", "")),
                "cost": "",  # SMS-Bus 买号时不返回价格
                "operator": "",
            }
        return False, {"error": data.get("message", str(data))}

    def get_status(self, activation_id: str) -> Tuple[str, str]:
        data = self._get("get/sms", request_id=activation_id)
        if data.get("code") == 200:
            code = str(data.get("data", ""))
            match = re.search(r'\d{4,8}', code)
            pure_code = match.group(0) if match else code.strip()
            return f"RECEIVED:{pure_code}", code
        msg = data.get("message", "")
        if "Not received" in msg or data.get("code") == 50101:
            return "WAIT", ""
        if "released" in msg or "timeout" in msg or data.get("code") == 50102:
            return "CANCEL", msg
        return "WAIT", ""

    def cancel(self, activation_id: str) -> str:
        data = self._get("cancel", request_id=activation_id)
        return data.get("message", str(data))

    def finish(self, activation_id: str) -> str:
        # SMS-Bus 没有显式的 finish 接口, 收到码后自动完成
        return "OK"

    def get_countries(self) -> list:
        data = self._get("list/countries")
        result = []
        if data.get("code") == 200:
            for cid, info in data.get("data", {}).items():
                result.append({"id": info.get("id", int(cid)), "name": info.get("title", str(cid))})
        return sorted(result, key=lambda x: x["name"])

    def get_services(self) -> list:
        data = self._get("list/projects")
        result = []
        if data.get("code") == 200:
            for pid, info in data.get("data", {}).items():
                result.append({"code": str(info.get("id", pid)), "name": info.get("title", str(pid))})
        return sorted(result, key=lambda x: x["name"])

    def get_prices_by_service(self, service: str) -> list:
        """SMS-Bus: 通过 list/prices 获取某服务各国的价格"""
        # SMS-Bus 没有按服务查国家的接口, 遍历所有国家的价格
        countries = self.get_countries()
        result = []
        for c in countries[:30]:  # 限制请求数
            try:
                data = self._get("list/prices", country_id=c["id"])
                if data.get("code") == 200:
                    for pid, info in data.get("data", {}).items():
                        if str(info.get("project_id")) == service:
                            result.append({
                                "country_id": c["id"],
                                "country_name": c["name"],
                                "count": int(info.get("total_count", 0)),
                                "price": str(info.get("cost", "")),
                            })
            except Exception:
                continue
        return sorted(result, key=lambda x: -x["count"])


# ── 工厂函数 ─────────────────────────────────────────

PROVIDER_TYPES = {
    "herosms": HeroSmsProvider,
    "smsbus": SmsBusProvider,
}

def create_provider(provider_type: str, api_key: str, base_url: str = "") -> SmsProviderBase:
    """根据类型创建提供商实例"""
    cls = PROVIDER_TYPES.get(provider_type)
    if not cls:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
    return cls(api_key=api_key, base_url=base_url)
