"""
CrunchBase API Client

Provides company and lead enrichment from CrunchBase database.
Retrieves:
- Company information (headquarters, industry, employee count)
- Funding history (rounds, amounts, dates)
- Leadership team
- Valuation and exit information

Documentation: https://www.crunchbase.com/api/
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from .base_client import BaseAPIClient, APIResponse

logger = logging.getLogger(__name__)


@dataclass
class CompanyInfo:
    """Structured company information from CrunchBase"""
    name: str
    crunchbase_id: str
    website: Optional[str]
    industry: Optional[str]
    founded_date: Optional[str]
    headquarters_city: Optional[str]
    headquarters_country: Optional[str]
    employee_count: Optional[int]
    description: Optional[str]
    confidence: float = 0.8


@dataclass
class FundingRound:
    """Funding round information"""
    round_type: str
    raised_amount: float
    currency: str
    announced_date: Optional[str]
    lead_investors: List[str]


class CrunchBaseClient(BaseAPIClient):
    """
    CrunchBase API Client
    
    Provides company lookup and enrichment from CrunchBase.
    Requires CRUNCHBASE_API_KEY environment variable.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = "https://api.crunchbase.com/v4",
        timeout: int = 30,
        **kwargs
    ):
        """
        Initialize CrunchBase Client.
        
        Args:
            api_key: CrunchBase API key (defaults to CRUNCHBASE_API_KEY env)
            endpoint: CrunchBase API endpoint
            timeout: Request timeout in seconds
            **kwargs: Additional args for BaseAPIClient
        """
        import os
        api_key = api_key or os.getenv("CRUNCHBASE_API_KEY")
        
        if not api_key:
            logger.warning("CRUNCHBASE_API_KEY not set. CrunchBase API calls will fail.")
        
        super().__init__(
            base_url=endpoint,
            api_key=api_key,
            timeout=timeout,
            **kwargs
        )
    
    # ==================== COMPANY OPERATIONS ====================
    
    def lookup_company(self, company_name: str) -> Dict[str, Any]:
        """
        Look up company information by name.
        
        Args:
            company_name: Company name to search
        
        Returns:
            Dict with company information and confidence score
        """
        try:
            logger.info(f"CrunchBase lookup: company='{company_name}'")
            
            # Build search query
            query = {
                "query": {
                    "type": "Company",
                    "query_string": company_name
                }
            }
            
            # Search companies
            response = self.post("/searches", json=query)
            
            if not response.is_success:
                logger.error(f"CrunchBase search failed: {response.status_code} - {response.data}")
                return {
                    "status": "error",
                    "company_name": company_name,
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            # Extract first result
            results = response.data.get("entities", [])
            if not results:
                return {
                    "status": "not_found",
                    "company_name": company_name,
                    "confidence": 0.0
                }
            
            company_data = results[0]
            
            # Extract company details
            company_info = {
                "status": "success",
                "company_name": company_name,
                "crunchbase_id": company_data.get("uuid"),
                "name": company_data.get("name"),
                "website": company_data.get("website"),
                "industry": company_data.get("primary_job_title"),  # Placeholder
                "founded_date": company_data.get("founded_on"),
                "headquarters": {
                    "city": company_data.get("location", {}).get("city"),
                    "country": company_data.get("location", {}).get("country"),
                },
                "employee_count": company_data.get("employee_count"),
                "description": company_data.get("description"),
                "confidence": 0.85
            }
            
            logger.info(f"CrunchBase lookup successful: {company_data.get('name')}")
            return company_info
        
        except Exception as e:
            logger.error(f"CrunchBase lookup failed: {e}")
            return {
                "status": "error",
                "company_name": company_name,
                "error": str(e),
                "confidence": 0.0
            }
    
    def get_funding_data(self, company_name: str) -> Dict[str, Any]:
        """
        Get funding history for a company.
        
        Args:
            company_name: Company name
        
        Returns:
            Dict with funding rounds and total funding amount
        """
        try:
            logger.info(f"Getting funding data for: {company_name}")
            
            # First, lookup company to get ID
            company_lookup = self.lookup_company(company_name)
            
            if company_lookup["status"] != "success":
                return {
                    "status": "error",
                    "company_name": company_name,
                    "error": "Company not found",
                    "confidence": 0.0
                }
            
            company_id = company_lookup.get("crunchbase_id")
            if not company_id:
                return {
                    "status": "error",
                    "company_name": company_name,
                    "error": "No CrunchBase ID",
                    "confidence": 0.0
                }
            
            # Get funding rounds
            response = self.get(f"/companies/{company_id}/funding")
            
            if not response.is_success:
                logger.warning(f"Failed to get funding data: {response.status_code}")
                return {
                    "status": "partial",
                    "company_name": company_name,
                    "funding_rounds": [],
                    "total_funding": 0,
                    "confidence": 0.6
                }
            
            # Parse funding rounds
            funding_rounds = []
            total_funding = 0
            
            for round_data in response.data.get("funding_rounds", []):
                try:
                    amount = float(round_data.get("raised_amount_usd", 0))
                    total_funding += amount
                    
                    funding_rounds.append({
                        "round_type": round_data.get("funding_type"),
                        "raised_amount": amount,
                        "currency": "USD",
                        "announced_date": round_data.get("announced_on"),
                        "lead_investors": [
                            inv.get("name") for inv in round_data.get("investors", [])
                        ]
                    })
                except (ValueError, KeyError):
                    logger.warning(f"Failed to parse funding round: {round_data}")
            
            return {
                "status": "success",
                "company_name": company_name,
                "funding_rounds": funding_rounds,
                "total_funding": total_funding,
                "currency": "USD",
                "confidence": 0.8
            }
        
        except Exception as e:
            logger.error(f"Get funding data failed: {e}")
            return {
                "status": "error",
                "company_name": company_name,
                "error": str(e),
                "confidence": 0.0
            }
    
    def get_company_valuation(self, company_name: str) -> Dict[str, Any]:
        """
        Get company valuation and funding status.
        
        Args:
            company_name: Company name
        
        Returns:
            Dict with valuation information
        """
        try:
            logger.info(f"Getting valuation for: {company_name}")
            
            # Lookup company
            company_lookup = self.lookup_company(company_name)
            
            if company_lookup["status"] != "success":
                return {
                    "status": "error",
                    "company_name": company_name,
                    "error": "Company not found",
                    "confidence": 0.0
                }
            
            company_id = company_lookup.get("crunchbase_id")
            
            # Try to get valuation from company details
            response = self.get(f"/companies/{company_id}")
            
            if not response.is_success:
                return {
                    "status": "error",
                    "company_name": company_name,
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            company_data = response.data.get("entity", {})
            
            return {
                "status": "success",
                "company_name": company_name,
                "valuation": company_data.get("last_funding_size_usd"),
                "valuation_currency": "USD",
                "status": company_data.get("status"),  # operating, acquired, ipo, etc.
                "growth_stage": company_data.get("growth_stage"),
                "confidence": 0.75
            }
        
        except Exception as e:
            logger.error(f"Get valuation failed: {e}")
            return {
                "status": "error",
                "company_name": company_name,
                "error": str(e),
                "confidence": 0.0
            }
    
    # ==================== BATCH OPERATIONS ====================
    
    def enrich_companies_batch(
        self,
        company_names: List[str],
        include_funding: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple companies.
        
        Args:
            company_names: List of company names
            include_funding: Whether to include funding data
        
        Returns:
            List of enriched company dicts
        """
        results = []
        
        for name in company_names:
            try:
                company_info = self.lookup_company(name)
                
                if include_funding and company_info.get("status") == "success":
                    funding_data = self.get_funding_data(name)
                    company_info["funding"] = funding_data
                
                results.append(company_info)
            except Exception as e:
                logger.error(f"Failed to enrich {name}: {e}")
                results.append({
                    "status": "error",
                    "company_name": name,
                    "error": str(e),
                    "confidence": 0.0
                })
        
        return results
