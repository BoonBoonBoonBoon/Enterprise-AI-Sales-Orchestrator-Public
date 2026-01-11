"""
Harness Configuration Management

Central configuration object for the entire Agent Harness.
Enables environment-specific behavior and easy testing.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import os
import json
from pathlib import Path


@dataclass
class HarnessConfig:
    """
    Configuration for agent harness.
    
    Controls:
    - Retry strategy and parameters
    - Observability backend selection
    - Checkpointing backend selection
    - Quota management backend selection
    - Timeout settings
    
    Examples:
        # Development config (fast iteration)
        config = HarnessConfig.for_development()
        
        # Production config (reliability)
        config = HarnessConfig.for_production()
        
        # Custom config
        config = HarnessConfig(
            max_retries=3,
            retry_strategy="exponential",
            observability_backend="datadog"
        )
    """
    
    # ==================== Retry Configuration ====================
    max_retries: int = 3
    """Maximum number of retries (0 = no retries)"""
    
    retry_strategy: str = "exponential"
    """Retry strategy: 'exponential', 'linear', 'jittered'"""
    
    base_delay: float = 1.0
    """Base delay in seconds before first retry"""
    
    max_delay: float = 60.0
    """Maximum delay between retries (capped at this value)"""
    
    exponential_base: float = 2.0
    """Exponential backoff multiplier (for exponential strategy)"""
    
    jitter_factor: float = 0.5
    """Jitter factor for randomization (for jittered strategy)"""
    
    # ==================== Observability Configuration ====================
    observability_backend: str = "simple"
    """
    Observability backend: 'simple', 'opentelemetry', 'datadog'
    
    - simple: Plain logging to stderr (development)
    - opentelemetry: CNCF standard (staging/prod)
    - datadog: Datadog APM (production with Datadog)
    """
    
    service_name: str = "agentic-system"
    """Service name for observability (sent to backend)"""
    
    trace_sample_rate: float = 1.0
    """Trace sampling rate (0.0-1.0). 1.0 = trace all, 0.1 = trace 10%"""
    
    # ==================== Checkpointing Configuration ====================
    enable_checkpointing: bool = False
    """Enable state checkpointing (for task resumption)"""
    
    checkpoint_backend: Optional[str] = None
    """
    Checkpoint backend: None, 'redis', 's3', 'postgres'
    
    - None: No checkpointing (development, fast operations)
    - redis: In-memory checkpoint with 24h TTL (staging)
    - s3: Cloud storage checkpoint (production, audit trail)
    - postgres: Database checkpoint (analytics, queryable)
    """
    
    checkpoint_ttl: int = 86400
    """Checkpoint TTL in seconds (24 hours = 86400)"""
    
    checkpoint_bucket: Optional[str] = None
    """S3 bucket for S3 checkpointer"""
    
    checkpoint_connection_string: Optional[str] = None
    """PostgreSQL connection string for PostgreSQL checkpointer"""
    
    # ==================== Quota Configuration ====================
    enable_quota: bool = False
    """Enable quota enforcement (rate limiting)"""
    
    quota_backend: Optional[str] = None
    """
    Quota backend: None, 'redis', 'memory'
    
    - None: No quota (development, testing)
    - memory: In-memory quota (single process)
    - redis: Distributed quota (production with load balancer)
    """
    
    requests_per_hour: int = 1000
    """Request quota limit per hour"""
    
    burst_size: int = 100
    """Burst size (for token bucket algorithm)"""
    
    # ==================== Timeout Configuration ====================
    timeout_seconds: int = 300
    """Execution timeout in seconds (5 minutes = 300)"""
    
    # ==================== Meta ====================
    @classmethod
    def for_development(cls) -> "HarnessConfig":
        """
        Development configuration: Fast iteration, minimal features.
        
        - 1 retry (fast failure)
        - Simple logging
        - No checkpointing
        - No quota limits
        - Short timeout (60s)
        """
        return cls(
            max_retries=1,
            retry_strategy="linear",
            base_delay=0.1,
            max_delay=5.0,
            observability_backend="simple",
            enable_checkpointing=False,
            enable_quota=False,
            timeout_seconds=60,
            trace_sample_rate=1.0  # Trace all in development
        )
    
    @classmethod
    def for_staging(cls) -> "HarnessConfig":
        """
        Staging configuration: Balanced reliability and speed.
        
        - 3 retries (moderate)
        - OpenTelemetry tracing
        - Redis checkpointing (temporary)
        - Redis quota (distributed)
        - Medium timeout (120s)
        """
        return cls(
            max_retries=3,
            retry_strategy="exponential",
            base_delay=1.0,
            max_delay=30.0,
            observability_backend="opentelemetry",
            enable_checkpointing=True,
            checkpoint_backend="redis",
            checkpoint_ttl=3600,  # 1 hour
            enable_quota=True,
            quota_backend="redis",
            requests_per_hour=5000,  # Higher limit for testing
            timeout_seconds=120,
            trace_sample_rate=0.5  # Sample 50% to reduce volume
        )
    
    @classmethod
    def for_production(cls) -> "HarnessConfig":
        """
        Production configuration: Maximum reliability.
        
        - 5 retries (aggressive)
        - Jittered backoff (prevent thundering herd)
        - Datadog tracing
        - S3 checkpointing (persistent audit trail)
        - Redis quota (distributed rate limiting)
        - Long timeout (300s)
        """
        return cls(
            max_retries=5,
            retry_strategy="jittered",
            base_delay=1.0,
            max_delay=60.0,
            jitter_factor=0.3,
            observability_backend="datadog",
            enable_checkpointing=True,
            checkpoint_backend="s3",
            checkpoint_ttl=2592000,  # 30 days
            enable_quota=True,
            quota_backend="redis",
            requests_per_hour=1000,
            burst_size=100,
            timeout_seconds=300,
            trace_sample_rate=0.1  # Sample 10% to reduce costs
        )
    
    @classmethod
    def from_env(cls) -> "HarnessConfig":
        """
        Load configuration from environment variables.
        
        Examples:
            ENVIRONMENT=production
            HARNESS_MAX_RETRIES=5
            HARNESS_OBSERVABILITY_BACKEND=datadog
            
        Precedence:
        1. Environment variables (HARNESS_*)
        2. Environment preset (ENVIRONMENT=development|staging|production)
        3. Defaults
        """
        env = os.getenv("ENVIRONMENT", "development").lower()
        
        # Load preset based on environment
        if env == "production":
            config = cls.for_production()
        elif env == "staging":
            config = cls.for_staging()
        else:
            config = cls.for_development()
        
        # Override with environment variables
        override_mapping = {
            "HARNESS_MAX_RETRIES": ("max_retries", int),
            "HARNESS_RETRY_STRATEGY": ("retry_strategy", str),
            "HARNESS_BASE_DELAY": ("base_delay", float),
            "HARNESS_OBSERVABILITY_BACKEND": ("observability_backend", str),
            "HARNESS_SERVICE_NAME": ("service_name", str),
            "HARNESS_ENABLE_CHECKPOINTING": ("enable_checkpointing", bool),
            "HARNESS_CHECKPOINT_BACKEND": ("checkpoint_backend", str),
            "HARNESS_CHECKPOINT_BUCKET": ("checkpoint_bucket", str),
            "HARNESS_ENABLE_QUOTA": ("enable_quota", bool),
            "HARNESS_QUOTA_BACKEND": ("quota_backend", str),
            "HARNESS_REQUESTS_PER_HOUR": ("requests_per_hour", int),
            "HARNESS_TIMEOUT_SECONDS": ("timeout_seconds", int),
        }
        
        for env_var, (field, type_func) in override_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                if type_func == bool:
                    value = value.lower() in ("true", "1", "yes", "on")
                else:
                    value = type_func(value)
                setattr(config, field, value)
        
        return config
    
    @classmethod
    def from_file(cls, filepath: str) -> "HarnessConfig":
        """
        Load configuration from JSON file.
        
        Example JSON:
            {
                "max_retries": 5,
                "retry_strategy": "jittered",
                "observability_backend": "datadog",
                "enable_checkpointing": true,
                "checkpoint_backend": "s3"
            }
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert config to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def save_to_file(self, filepath: str):
        """Save config to JSON file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def __repr__(self) -> str:
        """String representation"""
        return (
            f"HarnessConfig(\n"
            f"  retry={self.max_retries}x {self.retry_strategy}, "
            f"base_delay={self.base_delay}s\n"
            f"  observability={self.observability_backend}, "
            f"service={self.service_name}\n"
            f"  checkpointing={self.enable_checkpointing} "
            f"({self.checkpoint_backend})\n"
            f"  quota={self.enable_quota} "
            f"({self.requests_per_hour}/hour)\n"
            f"  timeout={self.timeout_seconds}s\n"
            f")"
        )


# Configuration presets for common scenarios

DEVELOPMENT_CONFIG = HarnessConfig.for_development()
STAGING_CONFIG = HarnessConfig.for_staging()
PRODUCTION_CONFIG = HarnessConfig.for_production()

__all__ = [
    "HarnessConfig",
    "DEVELOPMENT_CONFIG",
    "STAGING_CONFIG",
    "PRODUCTION_CONFIG",
]
