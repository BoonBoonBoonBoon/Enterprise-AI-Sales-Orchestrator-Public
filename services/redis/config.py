"""
Redis Service Configuration

Environment-based configuration for Redis connection and streams.
Supports development, staging, and production environments.
"""

import os
from typing import Optional


class RedisConfig:
    """Configuration for Redis Service"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        self.redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"
        
        # Connection settings
        self.connection_pool_size = int(os.getenv("REDIS_POOL_SIZE", "20"))
        self.connection_timeout = int(os.getenv("REDIS_TIMEOUT", "5"))
        self.decode_responses = os.getenv("REDIS_DECODE_RESPONSES", "true").lower() == "true"
        
        # Streams settings
        self.max_stream_length = int(os.getenv("REDIS_MAX_STREAM_LENGTH", "100000"))
        self.stream_block_ms = int(os.getenv("REDIS_STREAM_BLOCK_MS", "5000"))
        self.consumer_group_prefix = os.getenv("REDIS_CONSUMER_GROUP_PREFIX", "agentic-system")
    
    @property
    def connection_url(self) -> str:
        """Get Redis connection URL"""
        scheme = "rediss" if self.redis_ssl else "redis"
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"{scheme}://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "environment": self.environment,
            "redis_host": self.redis_host,
            "redis_port": str(self.redis_port),
            "redis_db": str(self.redis_db),
            "redis_ssl": str(self.redis_ssl),
            "connection_pool_size": str(self.connection_pool_size),
            "connection_timeout": str(self.connection_timeout),
            "max_stream_length": str(self.max_stream_length),
            "stream_block_ms": str(self.stream_block_ms),
        }


# Global config instance
_config: Optional[RedisConfig] = None


def get_config() -> RedisConfig:
    """Get redis service configuration"""
    global _config
    if _config is None:
        _config = RedisConfig()
    return _config


def reset_config() -> None:
    """Reset configuration (for testing)"""
    global _config
    _config = None
