"""
LinkedIn API Client

Provides person and company profile data from LinkedIn.
Retrieves:
- Person profiles (current role, experience, education)
- Company profiles (size, industry, specialties)
- Professional connection information

Note: LinkedIn Official API has limited public access.
This implementation provides patterns for integration.

Documentation: https://learn.microsoft.com/en-us/linkedin/shared/api-v2/
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from .base_client import BaseAPIClient, APIResponse

logger = logging.getLogger(__name__)


@dataclass
class PersonProfile:
    """LinkedIn person profile data"""
    linkedin_id: str
    first_name: str
    last_name: str
    headline: Optional[str]
    current_title: Optional[str]
    current_company: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    confidence: float = 0.7


class LinkedInClient(BaseAPIClient):
    """
    LinkedIn API Client
    
    Provides person and company profile data from LinkedIn.
    Uses OAuth 2.0 or access token authentication.
    
    Note: LinkedIn API access is limited and requires approval.
    """
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        endpoint: str = "https://api.linkedin.com/v2",
        timeout: int = 30,
        **kwargs
    ):
        """
        Initialize LinkedIn Client.
        
        Args:
            access_token: OAuth access token
            client_id: OAuth client ID
            client_secret: OAuth client secret
            endpoint: LinkedIn API endpoint
            timeout: Request timeout in seconds
            **kwargs: Additional args for BaseAPIClient
        """
        import os
        
        access_token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN")
        client_id = client_id or os.getenv("LINKEDIN_CLIENT_ID")
        client_secret = client_secret or os.getenv("LINKEDIN_CLIENT_SECRET")
        
        if not access_token and not (client_id and client_secret):
            logger.warning("LinkedIn credentials not set. LinkedIn API calls will fail.")
        
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        
        super().__init__(
            base_url=endpoint,
            api_key=access_token,
            timeout=timeout,
            **kwargs
        )
    
    # ==================== PERSON OPERATIONS ====================
    
    def lookup_person(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        linkedin_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up person profile by name or email.
        
        Args:
            first_name: Person's first name
            last_name: Person's last name
            email: Person's email address
            linkedin_url: Person's LinkedIn profile URL
        
        Returns:
            Dict with person profile and confidence score
        """
        try:
            if linkedin_url:
                logger.info(f"LinkedIn lookup by URL: {linkedin_url}")
                return self._lookup_by_url(linkedin_url)
            
            elif email:
                logger.info(f"LinkedIn lookup by email: {email}")
                return self._lookup_by_email(email)
            
            elif first_name and last_name:
                logger.info(f"LinkedIn lookup: {first_name} {last_name}")
                return self._lookup_by_name(first_name, last_name)
            
            else:
                return {
                    "status": "error",
                    "error": "Must provide name, email, or LinkedIn URL",
                    "confidence": 0.0
                }
        
        except Exception as e:
            logger.error(f"LinkedIn lookup failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "confidence": 0.0
            }
    
    def _lookup_by_url(self, linkedin_url: str) -> Dict[str, Any]:
        """Look up person by LinkedIn profile URL"""
        try:
            # Extract LinkedIn ID from URL
            # Expected format: https://www.linkedin.com/in/{id}/
            linkedin_id = linkedin_url.strip("/").split("/")[-1]
            
            # Get profile data
            response = self.get(f"/me/profile/")
            
            if not response.is_success:
                logger.warning(f"Failed to get LinkedIn profile: {response.status_code}")
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            profile = response.data
            
            return {
                "status": "success",
                "linkedin_id": linkedin_id,
                "first_name": profile.get("localizedFirstName"),
                "last_name": profile.get("localizedLastName"),
                "headline": profile.get("headline", {}).get("localized", {}).get("en_US"),
                "location": profile.get("geoLocation", {}).get("city"),
                "confidence": 0.85
            }
        
        except Exception as e:
            logger.error(f"Lookup by URL failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "confidence": 0.0
            }
    
    def _lookup_by_email(self, email: str) -> Dict[str, Any]:
        """Look up person by email address"""
        try:
            # Note: LinkedIn doesn't have a direct email lookup API
            # This is a placeholder for integration patterns
            logger.warning("Email lookup not supported by LinkedIn API")
            
            return {
                "status": "not_supported",
                "email": email,
                "note": "Email lookup requires LinkedIn Recruiter or Sales Navigator",
                "confidence": 0.0
            }
        
        except Exception as e:
            logger.error(f"Email lookup failed: {e}")
            return {
                "status": "error",
                "email": email,
                "error": str(e),
                "confidence": 0.0
            }
    
    def _lookup_by_name(self, first_name: str, last_name: str) -> Dict[str, Any]:
        """Look up person by name"""
        try:
            # Build search query
            query = f"{first_name} {last_name}"
            
            # Search people
            response = self.get(
                "/search/people",
                params={
                    "q": query,
                    "count": 1
                }
            )
            
            if not response.is_success:
                logger.warning(f"LinkedIn name search failed: {response.status_code}")
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            results = response.data.get("elements", [])
            if not results:
                return {
                    "status": "not_found",
                    "first_name": first_name,
                    "last_name": last_name,
                    "confidence": 0.0
                }
            
            person = results[0]
            
            return {
                "status": "success",
                "first_name": first_name,
                "last_name": last_name,
                "linkedin_id": person.get("id"),
                "headline": person.get("headline"),
                "distance": person.get("distance"),
                "confidence": 0.7
            }
        
        except Exception as e:
            logger.error(f"Name lookup failed: {e}")
            return {
                "status": "error",
                "first_name": first_name,
                "last_name": last_name,
                "error": str(e),
                "confidence": 0.0
            }
    
    def get_person_experience(self, linkedin_id: str) -> Dict[str, Any]:
        """
        Get person's work experience.
        
        Args:
            linkedin_id: LinkedIn person ID
        
        Returns:
            Dict with experience history
        """
        try:
            response = self.get(f"/people/{linkedin_id}/experience")
            
            if not response.is_success:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            positions = []
            for position in response.data.get("elements", []):
                positions.append({
                    "title": position.get("title"),
                    "company": position.get("company", {}).get("name"),
                    "start_date": position.get("startDate"),
                    "end_date": position.get("endDate"),
                    "description": position.get("description")
                })
            
            return {
                "status": "success",
                "linkedin_id": linkedin_id,
                "positions": positions,
                "confidence": 0.8
            }
        
        except Exception as e:
            logger.error(f"Get experience failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "confidence": 0.0
            }
    
    # ==================== COMPANY OPERATIONS ====================
    
    def lookup_company(self, company_name: str) -> Dict[str, Any]:
        """
        Look up company profile by name.
        
        Args:
            company_name: Company name to search
        
        Returns:
            Dict with company profile and confidence score
        """
        try:
            logger.info(f"LinkedIn company lookup: {company_name}")
            
            # Search companies
            response = self.get(
                "/search/companies",
                params={
                    "q": company_name,
                    "count": 1
                }
            )
            
            if not response.is_success:
                logger.warning(f"LinkedIn company search failed: {response.status_code}")
                return {
                    "status": "error",
                    "company_name": company_name,
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            results = response.data.get("elements", [])
            if not results:
                return {
                    "status": "not_found",
                    "company_name": company_name,
                    "confidence": 0.0
                }
            
            company = results[0]
            
            return {
                "status": "success",
                "company_name": company_name,
                "linkedin_id": company.get("id"),
                "name": company.get("name"),
                "headline": company.get("headline"),
                "industry": company.get("industryCode"),
                "company_size": company.get("employeeCountRange"),
                "confidence": 0.8
            }
        
        except Exception as e:
            logger.error(f"Company lookup failed: {e}")
            return {
                "status": "error",
                "company_name": company_name,
                "error": str(e),
                "confidence": 0.0
            }
    
    def get_company_employees(self, linkedin_company_id: str) -> Dict[str, Any]:
        """
        Get company employees and leadership.
        
        Args:
            linkedin_company_id: Company LinkedIn ID
        
        Returns:
            Dict with employee/leadership information
        """
        try:
            response = self.get(f"/companies/{linkedin_company_id}/employees")
            
            if not response.is_success:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "confidence": 0.0
                }
            
            employees = []
            for employee in response.data.get("elements", []):
                employees.append({
                    "name": employee.get("name"),
                    "title": employee.get("headline"),
                    "linkedin_id": employee.get("id")
                })
            
            return {
                "status": "success",
                "company_id": linkedin_company_id,
                "employee_count": len(employees),
                "employees": employees[:10],  # Top 10 employees
                "confidence": 0.7
            }
        
        except Exception as e:
            logger.error(f"Get employees failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "confidence": 0.0
            }
    
    # ==================== BATCH OPERATIONS ====================
    
    def enrich_people_batch(self, people: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Enrich multiple people with LinkedIn data.
        
        Args:
            people: List of dicts with name/email info
        
        Returns:
            List of enriched profiles
        """
        results = []
        
        for person in people:
            try:
                profile = self.lookup_person(
                    first_name=person.get("first_name"),
                    last_name=person.get("last_name"),
                    email=person.get("email")
                )
                
                if profile.get("status") == "success":
                    linkedin_id = profile.get("linkedin_id")
                    experience = self.get_person_experience(linkedin_id)
                    profile["experience"] = experience
                
                results.append(profile)
            except Exception as e:
                logger.error(f"Failed to enrich person: {e}")
                results.append({
                    "status": "error",
                    "error": str(e),
                    "confidence": 0.0
                })
        
        return results
