import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str = "localhost"
    port: int = 5432
    database: str = "bid_analysis"
    username: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class DifyConfig:
    """Dify LLM配置"""
    app_id: str = ""
    token: str = ""
    url: str = "https://api.dify.ai/v1/workflows/run"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

@dataclass
class FileConfig:
    """文件处理配置"""
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = field(default_factory=lambda: [".docx"])
    upload_dir: str = "uploads"
    temp_dir: str = "temp"
    max_files_per_request: int = 5

@dataclass
class ProcessingConfig:
    """处理配置"""
    max_concurrent_llm: int = 5
    chunk_size: int = 1000
    overlap_size: int = 100
    max_text_length: int = 1000000  # 1MB text
    timeout_seconds: int = 300

@dataclass
class SecurityConfig:
    """安全配置"""
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    rate_limit_per_minute: int = 60
    cors_origins: list = field(default_factory=lambda: ["*"])

@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/app.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True

@dataclass
class RuleConfig:
    """规则引擎配置"""
    rules_file: str = "rules.yaml"
    auto_reload: bool = True
    check_interval: int = 60  # seconds
    max_rules: int = 1000
    default_priority: float = 1.0

class Config:
    """应用配置管理器"""
    
    def __init__(self):
        # 加载.env文件
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path)
        
        self.database = DatabaseConfig()
        self.dify = DifyConfig()
        self.file = FileConfig()
        self.processing = ProcessingConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.rule = RuleConfig()
        
        # 应用基础配置
        self.app_name = "招标廉政体检系统"
        self.app_version = "1.0.0"
        self.debug = False
        self.host = "0.0.0.0"
        self.port = 8000
        
        # 加载配置
        self.load_from_env()
        self.validate_config()
    
    def load_from_env(self):
        """从环境变量加载配置"""
        # 应用基础配置
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.host = os.getenv("HOST", self.host)
        self.port = int(os.getenv("PORT", self.port))
        
        # 数据库配置
        self.database.host = os.getenv("DB_HOST", self.database.host)
        self.database.port = int(os.getenv("DB_PORT", self.database.port))
        self.database.database = os.getenv("DB_NAME", self.database.database)
        self.database.username = os.getenv("DB_USER", self.database.username)
        self.database.password = os.getenv("DB_PASSWORD", self.database.password)
        
        # Dify配置
        self.dify.app_id = os.getenv("DIFY_APPID", self.dify.app_id)
        self.dify.token = os.getenv("DIFY_TOKEN", self.dify.token)
        self.dify.url = os.getenv("DIFY_URL", self.dify.url)
        self.dify.timeout = int(os.getenv("DIFY_TIMEOUT", self.dify.timeout))
        self.dify.max_retries = int(os.getenv("MAX_RETRIES", self.dify.max_retries))
        self.dify.retry_delay = float(os.getenv("RETRY_DELAY", self.dify.retry_delay))
        
        # 文件配置
        self.file.max_file_size = int(os.getenv("MAX_FILE_SIZE", self.file.max_file_size))
        self.file.upload_dir = os.getenv("UPLOAD_DIR", self.file.upload_dir)
        self.file.temp_dir = os.getenv("TEMP_DIR", self.file.temp_dir)
        
        # 处理配置
        self.processing.max_concurrent_llm = int(os.getenv("MAX_CONCURRENT_LLM", self.processing.max_concurrent_llm))
        self.processing.chunk_size = int(os.getenv("CHUNK_SIZE", self.processing.chunk_size))
        self.processing.timeout_seconds = int(os.getenv("PROCESSING_TIMEOUT", self.processing.timeout_seconds))
        
        # 安全配置
        self.security.secret_key = os.getenv("SECRET_KEY", self.security.secret_key)
        self.security.rate_limit_per_minute = int(os.getenv("RATE_LIMIT", self.security.rate_limit_per_minute))
        
        # 日志配置
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)
        self.logging.file_path = os.getenv("LOG_FILE", self.logging.file_path)
        
        # 规则配置
        self.rule.rules_file = os.getenv("RULES_FILE", self.rule.rules_file)
        self.rule.auto_reload = os.getenv("RULES_AUTO_RELOAD", "true").lower() == "true"
        
        # CORS配置
        cors_origins = os.getenv("CORS_ORIGINS")
        if cors_origins:
            self.security.cors_origins = [origin.strip() for origin in cors_origins.split(",")]
    
    def validate_config(self):
        """验证配置"""
        errors = []
        
        # 验证必需的Dify配置
        if not self.dify.app_id:
            errors.append("DIFY_APPID环境变量未设置")
        if not self.dify.token:
            errors.append("DIFY_TOKEN环境变量未设置")
        
        # 验证文件大小限制
        if self.file.max_file_size <= 0:
            errors.append("文件大小限制必须大于0")
        
        # 验证并发限制
        if self.processing.max_concurrent_llm <= 0:
            errors.append("LLM并发数必须大于0")
        
        # 验证端口
        if not (1 <= self.port <= 65535):
            errors.append(f"端口号{self.port}无效")
        
        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level.upper() not in valid_log_levels:
            errors.append(f"日志级别{self.logging.level}无效")
        
        # 验证规则文件
        rules_path = Path(self.rule.rules_file)
        if not rules_path.is_absolute():
            rules_path = Path(__file__).parent / self.rule.rules_file
        if not rules_path.exists():
            errors.append(f"规则文件不存在: {rules_path}")
        
        if errors:
            error_msg = "配置验证失败:\n" + "\n".join(f"- {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("配置验证通过")
    
    def get_dify_headers(self) -> Dict[str, str]:
        """获取Dify API请求头"""
        return {
            "Authorization": f"Bearer {self.dify.token}",
            "Content-Type": "application/json"
        }
    
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        return f"postgresql://{self.database.username}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.database}"
    
    def create_directories(self):
        """创建必要的目录"""
        directories = [
            self.file.upload_dir,
            self.file.temp_dir,
            Path(self.logging.file_path).parent
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.debug(f"确保目录存在: {directory}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "debug": self.debug,
            "host": self.host,
            "port": self.port,
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "database": self.database.database,
                "username": self.database.username,
                # 不包含密码
            },
            "dify": {
                "url": self.dify.url,
                "timeout": self.dify.timeout,
                "max_retries": self.dify.max_retries,
                "retry_delay": self.dify.retry_delay,
                # 不包含敏感信息
            },
            "file": {
                "max_file_size": self.file.max_file_size,
                "allowed_extensions": self.file.allowed_extensions,
                "max_files_per_request": self.file.max_files_per_request,
            },
            "processing": {
                "max_concurrent_llm": self.processing.max_concurrent_llm,
                "chunk_size": self.processing.chunk_size,
                "timeout_seconds": self.processing.timeout_seconds,
            },
            "security": {
                "rate_limit_per_minute": self.security.rate_limit_per_minute,
                "cors_origins": self.security.cors_origins,
            },
            "logging": {
                "level": self.logging.level,
                "file_path": self.logging.file_path,
            },
            "rule": {
                "rules_file": self.rule.rules_file,
                "auto_reload": self.rule.auto_reload,
                "max_rules": self.rule.max_rules,
            }
        }
    
    def setup_logging(self):
        """设置日志配置"""
        from logging.handlers import RotatingFileHandler
        import sys
        
        # 创建日志目录
        log_file = Path(self.logging.file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.logging.level.upper()))
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 创建格式器
        formatter = logging.Formatter(self.logging.format)
        
        # 文件处理器
        file_handler = RotatingFileHandler(
            self.logging.file_path,
            maxBytes=self.logging.max_file_size,
            backupCount=self.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 控制台处理器
        if self.logging.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        logger.info(f"日志系统初始化完成，级别: {self.logging.level}")

# 全局配置实例
_config = None

def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = Config()
    return _config

def reload_config() -> Config:
    """重新加载配置"""
    global _config
    _config = Config()
    return _config

# 便捷函数
def get_dify_config() -> DifyConfig:
    """获取Dify配置"""
    return get_config().dify

def get_file_config() -> FileConfig:
    """获取文件配置"""
    return get_config().file

def get_processing_config() -> ProcessingConfig:
    """获取处理配置"""
    return get_config().processing

def get_security_config() -> SecurityConfig:
    """获取安全配置"""
    return get_config().security

def is_debug() -> bool:
    """是否为调试模式"""
    return get_config().debug