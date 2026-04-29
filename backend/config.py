"""应用配置模块 - 集中管理所有配置项"""
import os
from pathlib import Path

# 加载 .env 文件（如果存在）
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# JWT 配置
SECRET_KEY = os.environ.get("GAM_SECRET_KEY", "accops-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("GAM_TOKEN_EXPIRE_MINUTES", "480"))  # 默认 8 小时

# 数据库配置
DATABASE_URL = os.environ.get(
    "GAM_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/gam",
)

# CORS 配置
DEFAULT_CORS_ORIGINS = "http://localhost:17894,http://127.0.0.1:17894"
CORS_ORIGINS = [origin.strip() for origin in os.environ.get("GAM_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if origin.strip()]

# 服务器配置
HOST = os.environ.get("GAM_HOST", "127.0.0.1")
PORT = int(os.environ.get("GAM_PORT", "17893"))
