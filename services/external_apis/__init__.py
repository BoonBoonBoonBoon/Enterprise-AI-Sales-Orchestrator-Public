"""
External APIs Service - Third-party API integrations

Provides unified interface for external API integrations with standardized patterns.

Supported APIs:
- **CrunchBase**: Company research, funding data, valuations
- **LinkedIn**: Person profiles, company profiles, experience history
- Future: Slack, GitHub, Zapier, etc.

Architecture:
- BaseAPIClient: Abstract base with common functionality
  - Request retry with exponential backoff
  - Rate limiting (requests per minute)
  - Automatic timeout handling
  - Session management and connection pooling
  - Request/response logging

- CrunchBaseClient: Company enrichment from CrunchBase
  - Methods: lookup_company, get_funding_data, get_company_valuation
  - Batch operations: enrich_companies_batch
  - Returns: Structured data with confidence scores

- LinkedInClient: Professional data from LinkedIn
  - Methods: lookup_person, get_person_experience, lookup_company, get_company_employees
  - Search by: name, email, LinkedIn URL
  - Batch operations: enrich_people_batch
  - Returns: Profile data with confidence scores

Features:
- Standardized API client pattern (BaseAPIClient)
- Rate limiting and adaptive backoff
- Error handling and automatic retries
- Response validation and parsing
- Timeout management (default 30s)
- Request/response logging for debugging
- Confidence scoring for all results
- Batch operations for efficiency
- Session pooling and connection reuse

Configuration:
Environment variables for each API:
- CRUNCHBASE_API_KEY: CrunchBase API authentication
- LINKEDIN_ACCESS_TOKEN: LinkedIn OAuth token
- LINKEDIN_CLIENT_ID: LinkedIn OAuth client ID
- LINKEDIN_CLIENT_SECRET: LinkedIn OAuth secret
- API_RATE_LIMIT_RPM: Rate limit (default: 60 requests/min)
- API_RATE_LIMIT_BURST: Burst allowance (default: 10)
- API_MAX_RETRIES: Retry attempts (default: 3)
- API_RETRY_BACKOFF: Backoff multiplier (default: 2.0)

Usage:

    from services.external_apis import CrunchBaseClient, LinkedInClient
    
    # CrunchBase company lookup and enrichment
    crunchbase = CrunchBaseClient()
    company_info = crunchbase.lookup_company("Acme Corporation")
    funding_data = crunchbase.get_funding_data("Acme Corporation")
    
    # LinkedIn person lookup and experience
    linkedin = LinkedInClient()
    person = linkedin.lookup_person(
        first_name="John",
        last_name="Doe"
    )
    experience = linkedin.get_person_experience(person["linkedin_id"])
    
    # Batch operations
    companies = ["Company A", "Company B", "Company C"]
    enriched = crunchbase.enrich_companies_batch(companies, include_funding=True)

Exported Components:
- CrunchBaseClient: CrunchBase API client
- LinkedInClient: LinkedIn API client
- BaseAPIClient: Base client for API integrations
- APIResponse: Response wrapper dataclass
- get_config, reset_config: Configuration management
"""

from .base_client import BaseAPIClient, APIResponse
from .crunchbase import CrunchBaseClient
from .linkedin import LinkedInClient
from .config import get_config, reset_config

__all__ = [
    # Clients
    "BaseAPIClient",
    "CrunchBaseClient",
    "LinkedInClient",
    # Response types
    "APIResponse",
    # Configuration
    "get_config",
    "reset_config",
    # Sub-modules
    "base_client",
    "crunchbase",
    "linkedin",
    "config",
]

