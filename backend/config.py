"""应用配置模块 - 集中管理所有配置项"""
import os

DEFAULT_SECRET_KEY = "accops-local-dev-secret-key"

# JWT 配置
SECRET_KEY = os.environ.get("GAM_SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("GAM_TOKEN_EXPIRE_MINUTES", "480"))  # 默认 8 小时

# 数据库配置
DATABASE_URL = os.environ.get(
    "GAM_DATABASE_URL",
    "postgresql://root:123456@127.0.0.1:5432/gam",
)

# CORS 配置
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [origin.strip() for origin in os.environ.get("GAM_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if origin.strip()]

# 服务器配置
HOST = os.environ.get("GAM_HOST", "127.0.0.1")
PORT = int(os.environ.get("GAM_PORT", "8000"))
