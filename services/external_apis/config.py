"""
External APIs Service Configuration

Environment-based configuration for third-party API integrations.
Supports CrunchBase, LinkedIn, and future API providers.
"""

import os
from typing import Optional


class ExternalAPIsConfig:
    """Configuration for External APIs Service"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # CrunchBase configuration
        self.crunchbase_api_key = os.getenv("CRUNCHBASE_API_KEY", "")
        self.crunchbase_endpoint = os.getenv("CRUNCHBASE_ENDPOINT", "https://api.crunchbase.com/v4")
        self.crunchbase_timeout = int(os.getenv("CRUNCHBASE_TIMEOUT", "30"))
        
        # LinkedIn configuration
        self.linkedin_client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.linkedin_client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.linkedin_access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        self.linkedin_endpoint = os.getenv("LINKEDIN_ENDPOINT", "https://api.linkedin.com/v2")
        self.linkedin_timeout = int(os.getenv("LINKEDIN_TIMEOUT", "30"))
        
        # Rate limiting
        self.rate_limit_requests_per_minute = int(os.getenv("API_RATE_LIMIT_RPM", "60"))
        self.rate_limit_burst = int(os.getenv("API_RATE_LIMIT_BURST", "10"))
        
        # Retry settings
        self.max_retries = int(os.getenv("API_MAX_RETRIES", "3"))
        self.retry_backoff_factor = float(os.getenv("API_RETRY_BACKOFF", "2.0"))
    
    def to_dict(self) -> dict:
        """Convert config to dictionary (without sensitive data)"""
        return {
            "environment": self.environment,
            "crunchbase_endpoint": self.crunchbase_endpoint,
            "crunchbase_timeout": str(self.crunchbase_timeout),
            "linkedin_endpoint": self.linkedin_endpoint,
            "linkedin_timeout": str(self.linkedin_timeout),
            "rate_limit_requests_per_minute": str(self.rate_limit_requests_per_minute),
            "rate_limit_burst": str(self.rate_limit_burst),
            "max_retries": str(self.max_retries),
            "retry_backoff_factor": str(self.retry_backoff_factor),
        }


# Global config instance
_config: Optional[ExternalAPIsConfig] = None


def get_config() -> ExternalAPIsConfig:
    """Get external APIs service configuration"""
    global _config
    if _config is None:
        _config = ExternalAPIsConfig()
    return _config


def reset_config() -> None:
    """Reset configuration (for testing)"""
    global _config
    _config = None
