"""
Base API Client - Standardized interface for external API calls

Provides:
- Common error handling
- Rate limiting
- Retry logic with exponential backoff
- Request/response logging
- Timeout management
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standardized API response wrapper"""
    status_code: int
    data: Dict[str, Any]
    headers: Dict[str, str]
    timestamp: datetime
    elapsed_ms: float
    error: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Check if response is successful (2xx status)"""
        return 200 <= self.status_code < 300
    
    @property
    def is_error(self) -> bool:
        """Check if response is an error"""
        return self.status_code >= 400


class BaseAPIClient:
    """
    Base API Client with common functionality
    
    Handles:
    - Connection pooling
    - Retry logic with exponential backoff
    - Rate limiting
    - Timeout management
    - Request/response logging
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        rate_limit_rpm: int = 60,
        rate_limit_burst: int = 10
    ):
        """
        Initialize Base API Client.
        
        Args:
            base_url: Base URL for API endpoint
            api_key: API authentication key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            retry_backoff: Exponential backoff factor
            rate_limit_rpm: Rate limit (requests per minute)
            rate_limit_burst: Burst allowance
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        
        # Rate limiting
        self.rate_limit_rpm = rate_limit_rpm
        self.rate_limit_burst = rate_limit_burst
        self._request_times: List[float] = []
        
        # Setup session with retry strategy
        self.session = self._setup_session()
        
        logger.info(f"API Client initialized (url={base_url}, timeout={timeout}s)")
    
    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        self._set_default_headers(session)
        
        return session
    
    def _set_default_headers(self, session: requests.Session) -> None:
        """Set default headers including authentication"""
        session.headers.update({
            "User-Agent": "Agentic-System/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        if self.api_key:
            session.headers.update({
                "Authorization": f"Bearer {self.api_key}"
            })
    
    def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting"""
        now = time.time()
        
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        # Check rate limit
        if len(self._request_times) >= self.rate_limit_rpm:
            # Calculate wait time
            oldest_request = self._request_times[0]
            wait_time = 60 - (now - oldest_request)
            if wait_time > 0:
                logger.warning(f"Rate limit approaching. Waiting {wait_time:.1f}s")
                time.sleep(wait_time)
        
        # Check burst limit
        if len(self._request_times) >= self.rate_limit_burst:
            logger.debug("Burst limit reached. Enforcing rate limit check.")
        
        self._request_times.append(now)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> APIResponse:
        """
        Make HTTP request with error handling and retries.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (appended to base_url)
            **kwargs: Additional arguments for requests
        
        Returns:
            APIResponse with status, data, and metadata
        """
        # Check rate limit before request
        self._check_rate_limit()
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        start_time = time.time()
        
        try:
            logger.debug(f"{method} {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Parse response
            try:
                data = response.json()
            except ValueError:
                data = {"content": response.text}
            
            # Log response
            if response.is_error:
                logger.error(f"{method} {url} - {response.status_code}: {data}")
            else:
                logger.debug(f"{method} {url} - {response.status_code} ({elapsed_ms:.0f}ms)")
            
            return APIResponse(
                status_code=response.status_code,
                data=data,
                headers=dict(response.headers),
                timestamp=datetime.utcnow(),
                elapsed_ms=elapsed_ms
            )
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout after {self.timeout}s for {method} {url}")
            return APIResponse(
                status_code=408,
                data={"error": "Request timeout"},
                headers={},
                timestamp=datetime.utcnow(),
                elapsed_ms=(time.time() - start_time) * 1000,
                error="Timeout"
            )
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {method} {url}: {e}")
            return APIResponse(
                status_code=503,
                data={"error": "Connection error"},
                headers={},
                timestamp=datetime.utcnow(),
                elapsed_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
        
        except Exception as e:
            logger.error(f"Request failed for {method} {url}: {e}")
            return APIResponse(
                status_code=500,
                data={"error": "Internal error"},
                headers={},
                timestamp=datetime.utcnow(),
                elapsed_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    # ==================== CONVENIENCE METHODS ====================
    
    def get(self, endpoint: str, **kwargs) -> APIResponse:
        """Make GET request"""
        return self._make_request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str, json: Optional[Dict] = None, **kwargs) -> APIResponse:
        """Make POST request"""
        if json:
            kwargs["json"] = json
        return self._make_request("POST", endpoint, **kwargs)
    
    def put(self, endpoint: str, json: Optional[Dict] = None, **kwargs) -> APIResponse:
        """Make PUT request"""
        if json:
            kwargs["json"] = json
        return self._make_request("PUT", endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> APIResponse:
        """Make DELETE request"""
        return self._make_request("DELETE", endpoint, **kwargs)
    
    def close(self) -> None:
        """Close session"""
        self.session.close()
        logger.info("API session closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
