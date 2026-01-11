"""Configuration schemas for workers and infrastructure."""
from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RedisConfig(BaseModel):
    """Redis connection configuration"""
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    password: Optional[str] = Field(None, description="Redis password")
    use_tls: bool = Field(default=False, description="Use TLS/SSL connection")
    namespace: str = Field(default="agentic", min_length=1, description="Key namespace prefix")
    max_connections: int = Field(default=50, ge=1, le=1000, description="Connection pool size")
    socket_timeout: int = Field(default=5, ge=1, le=300, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, ge=1, le=300, description="Connection timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry commands on timeout")
    health_check_interval: int = Field(default=30, ge=1, description="Health check interval in seconds")
    
    @validator('namespace')
    def validate_namespace(cls, v):
        """Ensure namespace is alphanumeric"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Namespace must be alphanumeric with hyphens/underscores: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "host": "redis.example.com",
                    "port": 6379,
                    "db": 0,
                    "password": "***",
                    "use_tls": True,
                    "namespace": "agentic-prod",
                    "max_connections": 100
                }
            ]
        }


class DatabaseConfig(BaseModel):
    """Database connection configuration"""
    provider: str = Field(..., description="Database provider (supabase, postgresql, etc.)")
    url: str = Field(..., min_length=1, description="Connection URL or endpoint")
    api_key: Optional[str] = Field(None, description="API key (for Supabase, etc.)")
    pool_size: int = Field(default=20, ge=1, le=1000, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=100, description="Max connections above pool size")
    pool_timeout: int = Field(default=30, ge=1, le=300, description="Pool checkout timeout in seconds")
    pool_recycle: int = Field(default=3600, ge=60, description="Recycle connections after N seconds")
    echo_sql: bool = Field(default=False, description="Log all SQL queries")
    
    @validator('url')
    def validate_url_format(cls, v):
        """Basic URL validation"""
        if not any(v.startswith(proto) for proto in ['http://', 'https://', 'postgresql://', 'postgres://']):
            raise ValueError(f"Invalid database URL format: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "provider": "supabase",
                    "url": "https://xxx.supabase.co",
                    "api_key": "***",
                    "pool_size": 20,
                    "max_overflow": 10
                }
            ]
        }


class WorkerConfig(BaseModel):
    """Worker process configuration"""
    worker_id: Optional[str] = Field(None, description="Worker identifier (auto-generated if None)")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts per message")
    retry_backoff_ms: int = Field(default=1000, ge=0, le=60000, description="Retry backoff in milliseconds")
    shutdown_timeout: int = Field(default=30, ge=1, le=300, description="Graceful shutdown timeout in seconds")
    heartbeat_enabled: bool = Field(default=True, description="Enable heartbeat publishing")
    heartbeat_interval: int = Field(default=10, ge=1, le=300, description="Heartbeat interval in seconds")
    heartbeat_ttl: int = Field(default=30, ge=1, le=600, description="Heartbeat TTL in seconds")
    block_ms: int = Field(default=5000, ge=100, le=60000, description="Redis XREADGROUP block time")
    batch_size: int = Field(default=1, ge=1, le=100, description="Messages to process per batch")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_workflow_tracking: bool = Field(default=True, description="Enable workflow progress tracking")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "examples": [
                {
                    "worker_id": "rag-worker-1",
                    "max_retries": 3,
                    "retry_backoff_ms": 1000,
                    "shutdown_timeout": 30,
                    "heartbeat_enabled": True,
                    "heartbeat_interval": 10,
                    "log_level": "info",
                    "enable_tracing": True,
                    "enable_metrics": True
                }
            ]
        }


class StreamConfig(BaseModel):
    """Redis Stream configuration"""
    name: str = Field(..., min_length=1, description="Stream name")
    maxlen: Optional[int] = Field(10000, ge=100, description="Max stream length (approximate)")
    consumer_group: str = Field(..., min_length=1, description="Consumer group name")
    consumer_name: Optional[str] = Field(None, description="Consumer name (auto-generated if None)")
    claim_min_idle_ms: int = Field(default=300000, ge=1000, description="Min idle time before claiming stuck messages")
    max_pending: int = Field(default=100, ge=1, description="Alert threshold for pending messages")
    max_lag: int = Field(default=1000, ge=1, description="Alert threshold for consumer lag")
    enable_dlq: bool = Field(default=True, description="Enable dead-letter queue")
    dlq_stream: Optional[str] = Field(None, description="DLQ stream name (auto-generated if None)")
    
    @validator('name', 'consumer_group')
    def validate_stream_name(cls, v):
        """Ensure stream/group names are safe"""
        if not v.replace('_', '').replace('-', '').replace(':', '').isalnum():
            raise ValueError(f"Invalid stream/group name: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "rag:tasks",
                    "maxlen": 10000,
                    "consumer_group": "rag-workers",
                    "consumer_name": "worker-1",
                    "max_pending": 100,
                    "max_lag": 500,
                    "enable_dlq": True,
                    "dlq_stream": "rag:dlq"
                }
            ]
        }


class TracingConfig(BaseModel):
    """Distributed tracing configuration"""
    enabled: bool = Field(default=False, description="Enable tracing")
    exporter: str = Field(default="console", description="Exporter type (jaeger, otlp, console)")
    service_name: Optional[str] = Field(None, description="Service name for traces")
    jaeger_endpoint: Optional[str] = Field(None, description="Jaeger collector endpoint")
    otlp_endpoint: Optional[str] = Field(None, description="OTLP collector endpoint")
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Sampling rate (0.0-1.0)")
    
    @validator('jaeger_endpoint', 'otlp_endpoint')
    def validate_endpoint_format(cls, v):
        """Basic endpoint URL validation"""
        if v and not any(v.startswith(proto) for proto in ['http://', 'https://']):
            raise ValueError(f"Invalid endpoint URL: {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "enabled": True,
                    "exporter": "jaeger",
                    "service_name": "rag-worker",
                    "jaeger_endpoint": "http://jaeger:14268/api/traces",
                    "sample_rate": 0.1
                }
            ]
        }
