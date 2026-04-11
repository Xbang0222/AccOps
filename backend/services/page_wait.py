"""DrissionPage 页面等待与重试工具

解决 "The page is refreshed. Please wait until the page is refreshed or loaded." 异常。

核心问题: 裸 time.sleep() 无法保证页面加载完成，DrissionPage 在页面刷新中
操作元素会抛异常。本模块提供:
  1. wait_page_stable()  — 等待页面加载稳定 (替代裸 time.sleep)
  2. retry_on_refresh()  — 自动重试被页面刷新打断的操作
  3. safe_navigate()     — 导航 + 等待加载完成
  4. safe_ele()          — 查找元素 (自动处理页面刷新)
  5. safe_click()        — 点击元素 (自动重试, 刷新后重新获取元素)
  6. safe_input()        — 输入内容 (自动重试, 刷新后重新获取元素)
"""

import logging
import time
from functools import wraps
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# DrissionPage 页面刷新/元素不可用异常的关键词
_REFRESH_KEYWORDS = (
    "page is refreshed",
    "Please wait until the page",
    "is loading",
    "has no location or size",  # 元素存在但不可见/不可交互
)

# 默认重试配置
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
PAGE_STABLE_TIMEOUT = 15
# readyState == 'complete' 后的额外缓冲 (Google c-wiz JS 框架初始化)
_POST_READY_BUFFER = 0.3


def _is_refresh_error(exc: Exception) -> bool:
    """判断异常是否为页面刷新/加载中导致的"""
    msg = str(exc)
    return any(kw in msg for kw in _REFRESH_KEYWORDS)


def wait_page_stable(page, timeout: float = PAGE_STABLE_TIMEOUT,
                     check_interval: float = 0.5) -> bool:
    """等待页面加载稳定 (替代裸 time.sleep)

    使用 document.readyState 检测，比固定 sleep 更可靠:
    - 页面加载快时立即返回 (不浪费时间)
    - 页面加载慢时继续等待 (不会操作到未就绪的页面)

    Args:
        page: DrissionPage 页面对象
        timeout: 最大等待秒数
        check_interval: 检查间隔

    Returns:
        True = 页面已稳定, False = 超时或异常
    """
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            state = page.run_js("return document.readyState")
            if state == "complete":
                time.sleep(_POST_READY_BUFFER)
                return True
        except Exception as e:
            if _is_refresh_error(e):
                logger.debug("页面刷新中, 继续等待...")
            else:
                logger.warning(f"wait_page_stable 异常: {e}")
                return False
        time.sleep(check_interval)

    logger.warning(f"wait_page_stable 超时 ({timeout}s)")
    return False


def safe_navigate(page, url: str, timeout: float = PAGE_STABLE_TIMEOUT,
                  min_wait: float = 1.0) -> bool:
    """安全导航: page.get() + 等待页面稳定

    替代 page.get(url); time.sleep(N) 的模式。

    Args:
        page: DrissionPage 页面对象
        url: 目标 URL
        timeout: 页面加载等待超时
        min_wait: 最少等待秒数 (Google 页面有些 JS 需要时间初始化)

    Returns:
        True = 导航成功且页面稳定
    """
    start = time.monotonic()
    try:
        page.get(url)
    except Exception as e:
        if _is_refresh_error(e):
            logger.debug(f"导航触发页面刷新: {url}")
        else:
            logger.warning(f"导航异常: {url} - {e}")

    result = wait_page_stable(page, timeout=timeout)

    # 确保至少等了 min_wait (Google 页面的 c-wiz 组件需要 JS 初始化)
    elapsed = time.monotonic() - start
    remaining = min_wait - elapsed
    if remaining > 0:
        time.sleep(remaining)

    return result


def safe_ele(page, selector: str, timeout: float = 10,
             retries: int = DEFAULT_RETRIES,
             retry_delay: float = DEFAULT_RETRY_DELAY):
    """安全查找元素 — 自动处理页面刷新

    Args:
        page: DrissionPage 页面对象
        selector: CSS 选择器或 DrissionPage 选择器语法
        timeout: 元素查找超时
        retries: 页面刷新时的重试次数
        retry_delay: 重试间隔

    Returns:
        元素对象, 或 None
    """
    for attempt in range(retries):
        try:
            ele = page.ele(selector, timeout=timeout)
            return ele
        except Exception as e:
            if _is_refresh_error(e) and attempt < retries - 1:
                logger.debug(f"查找元素被页面刷新打断 (尝试 {attempt + 1}/{retries}): {selector}")
                wait_page_stable(page, timeout=5)
                time.sleep(retry_delay)
            else:
                if _is_refresh_error(e):
                    logger.warning(f"查找元素因页面刷新失败 (已重试 {retries} 次): {selector}")
                    return None
                raise
    return None


def safe_click(ele, retries: int = DEFAULT_RETRIES,
               retry_delay: float = DEFAULT_RETRY_DELAY,
               page=None) -> bool:
    """安全点击元素 — 自动重试页面刷新

    刷新后会通过 page 重新获取元素再点击, 避免操作失效的旧元素引用。

    Args:
        ele: DrissionPage 元素对象
        retries: 重试次数
        retry_delay: 重试间隔
        page: 页面对象 (刷新后重新获取元素必需)

    Returns:
        True = 点击成功
    """
    if not ele:
        return False

    current_ele = ele

    for attempt in range(retries):
        try:
            current_ele.click()
            return True
        except Exception as e:
            if _is_refresh_error(e) and attempt < retries - 1:
                logger.debug(f"点击被页面刷新打断 (尝试 {attempt + 1}/{retries})")
                if page:
                    wait_page_stable(page, timeout=5)
                    # 重新获取元素: 从原始元素提取定位器
                    loc = _extract_selector(ele)
                    if loc:
                        refreshed = safe_ele(page, loc, timeout=3, retries=1)
                        if refreshed:
                            current_ele = refreshed
                            continue
                time.sleep(retry_delay)
            else:
                if _is_refresh_error(e):
                    logger.warning(f"点击因页面刷新失败 (已重试 {retries} 次)")
                    return False
                raise
    return False


def safe_input(ele, text: str, retries: int = DEFAULT_RETRIES,
               retry_delay: float = DEFAULT_RETRY_DELAY,
               page=None, clear_first: bool = False) -> bool:
    """安全输入内容 — 自动重试页面刷新

    刷新后会通过 page 重新获取元素再输入, 避免操作失效的旧元素引用。

    Args:
        ele: DrissionPage 元素对象
        text: 要输入的文本
        retries: 重试次数
        retry_delay: 重试间隔
        page: 页面对象 (刷新后重新获取元素必需)
        clear_first: 输入前是否清空

    Returns:
        True = 输入成功
    """
    if not ele:
        return False

    current_ele = ele

    for attempt in range(retries):
        try:
            if clear_first:
                current_ele.clear()
            current_ele.input(text)
            return True
        except Exception as e:
            if _is_refresh_error(e) and attempt < retries - 1:
                logger.debug(f"输入被页面刷新打断 (尝试 {attempt + 1}/{retries})")
                if page:
                    wait_page_stable(page, timeout=5)
                    loc = _extract_selector(ele)
                    if loc:
                        refreshed = safe_ele(page, loc, timeout=3, retries=1)
                        if refreshed:
                            current_ele = refreshed
                            continue
                time.sleep(retry_delay)
            else:
                if _is_refresh_error(e):
                    logger.warning(f"输入因页面刷新失败 (已重试 {retries} 次)")
                    return False
                raise
    return False


def _extract_selector(ele):
    """尝试从 DrissionPage 元素对象提取可复用的定位器

    DrissionPage 元素的 ._loc 属性存储 (定位方式, 值) 元组,
    page.ele() 可直接接受此元组进行查找。
    """
    try:
        # DrissionPage 4.x: ele._loc = ('css selector', '#foo') 或 ('text', 'Login')
        loc = getattr(ele, "_loc", None)
        if loc and isinstance(loc, (tuple, list)) and len(loc) >= 2:
            return tuple(loc)  # 返回完整元组, 保留定位模式
    except Exception:
        pass
    return None


def retry_on_refresh(func: Optional[Callable[..., T]] = None, *,
                     retries: int = DEFAULT_RETRIES,
                     delay: float = DEFAULT_RETRY_DELAY) -> Callable[..., T]:
    """装饰器: 自动重试被页面刷新打断的操作

    用法:
        @retry_on_refresh
        def do_something(page):
            ...

        @retry_on_refresh(retries=5, delay=2.0)
        def do_something_else(page):
            ...
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(retries):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    if _is_refresh_error(e) and attempt < retries - 1:
                        logger.info(
                            f"{fn.__name__} 被页面刷新打断 "
                            f"(尝试 {attempt + 1}/{retries}), "
                            f"{delay}s 后重试..."
                        )
                        time.sleep(delay)
                    else:
                        raise
            # 理论上不可达 (retries >= 1 时循环体必定 return 或 raise)
            raise RuntimeError(f"{fn.__name__}: 重试逻辑异常")
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
