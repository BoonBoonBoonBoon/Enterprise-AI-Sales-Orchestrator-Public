"""
Persistence Service Configuration

Environment-based configuration for database operations.
Supports multiple database backends and configurations.
"""

import os
from typing import Dict, Optional, List


class PersistenceConfig:
    """Configuration for Persistence Service"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        self.database_type = os.getenv("DATABASE_TYPE", "postgresql")
        self.database_host = os.getenv("DATABASE_HOST", "localhost")
        self.database_port = int(os.getenv("DATABASE_PORT", "5432"))
        self.database_name = os.getenv("DATABASE_NAME", "agentic_system")
        self.database_user = os.getenv("DATABASE_USER", "postgres")
        self.database_password = os.getenv("DATABASE_PASSWORD", "")
        self.pool_size = int(os.getenv("DATABASE_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
        self.echo_sql = os.getenv("DATABASE_ECHO_SQL", "false").lower() == "true"
        
        # Write allowlist - tables that can be written to
        self.write_allowlist: List[str] = []
        self._load_write_allowlist()
    
    def _load_write_allowlist(self) -> None:
        """Load write allowlist from config or environment"""
        allowlist_str = os.getenv("DATABASE_WRITE_ALLOWLIST", "")
        if allowlist_str:
            self.write_allowlist = [t.strip() for t in allowlist_str.split(",")]
    
    @property
    def connection_string(self) -> str:
        """Get database connection string"""
        if self.database_type == "postgresql":
            return (
                f"postgresql://{self.database_user}:{self.database_password}@"
                f"{self.database_host}:{self.database_port}/{self.database_name}"
            )
        elif self.database_type == "duckdb":
            return f"duckdb:///{self.database_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")
    
    @property
    def sqlalchemy_url(self) -> str:
        """Get SQLAlchemy connection URL"""
        if self.database_type == "postgresql":
            return f"postgresql+psycopg2://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"
        elif self.database_type == "duckdb":
            return f"duckdb:///{self.database_name}"
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")
    
    def to_dict(self) -> Dict[str, str]:
        """Convert config to dictionary"""
        return {
            "database_type": self.database_type,
            "database_host": self.database_host,
            "database_port": str(self.database_port),
            "database_name": self.database_name,
            "pool_size": str(self.pool_size),
            "max_overflow": str(self.max_overflow),
            "echo_sql": str(self.echo_sql),
        }


# Global config instance
_config: Optional[PersistenceConfig] = None


def get_config() -> PersistenceConfig:
    """Get persistence service configuration"""
    global _config
    if _config is None:
        _config = PersistenceConfig()
    return _config


def reset_config() -> None:
    """Reset configuration (for testing)"""
    global _config
    _config = None
