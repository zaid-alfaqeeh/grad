"""
Extractor service for orchestrating web data extraction.
Uses ONLY ChatGPT's web_search tool - NO manual scraping.
"""
import json
import os
from typing import Dict, Any, Optional, List
from config import RESOURCES_FILE
from logger import get_logger


class ExtractorService:
    """
    Orchestrates web data extraction using OpenAI service.
    
    CRITICAL: This service uses ONLY ChatGPT's web_search tool.
    NO requests, NO BeautifulSoup, NO manual scraping.
    """
    
    def __init__(self, openai_service):
        """
        Initialize extractor service.
        
        Args:
            openai_service: Instance of OpenAIService for web operations
        """
        self.openai_service = openai_service
        self.logger = get_logger()
        self.resources = self._load_resources()
    
    def _load_resources(self) -> Dict[str, str]:
        """Load resources from JSON file."""
        try:
            if os.path.exists(RESOURCES_FILE):
                with open(RESOURCES_FILE, 'r', encoding='utf-8') as f:
                    resources = json.load(f)
                    self.logger.debug(f"Loaded {len(resources)} resources from {RESOURCES_FILE}")
                    return resources
        except Exception as e:
            self.logger.error(f"Error loading resources.json: {e}")
        
        return {}
    
    # ========================================
    # RESOURCE SELECTION
    # ========================================
    
    def select_resource(self, canonical_key: str, query: str) -> Optional[str]:
        """
        Select the most relevant resource URL based on canonical key and query.
        
        Args:
            canonical_key: The canonical key for the topic
            query: Original user query
            
        Returns:
            URL string or None if no match
        """
        # Direct lookup by canonical key
        if canonical_key in self.resources:
            url = self.resources[canonical_key]
            self.logger.info(f"Selected resource URL for '{canonical_key}': {url}")
            return url
        
        # Try keyword-based fallback matching
        query_lower = query.lower()
        
        keyword_to_resource = {
            'registration': ['register', 'registration', 'enroll', 'تسجيل'],
            'fees': ['fee', 'fees', 'payment', 'cost', 'tuition', 'رسوم', 'مصاريف'],
            'admissions': ['admission', 'admissions', 'apply', 'قبول'],
            'academic_calendar': ['calendar', 'semester', 'تقويم'],
            'student_services': ['student service', 'services', 'خدمات'],
            'courses_schedule': ['schedule', 'timetable', 'جدول'],
            'admission_rules': ['rules', 'regulations', 'قواعد']
        }
        
        for resource_key, keywords in keyword_to_resource.items():
            if any(keyword in query_lower for keyword in keywords):
                if resource_key in self.resources:
                    url = self.resources[resource_key]
                    self.logger.info(f"Fallback resource match '{resource_key}': {url}")
                    return url
        
        self.logger.info(f"No resource match for '{canonical_key}', will use web search")
        return None
    
    def get_all_resources(self) -> Dict[str, str]:
        """Get all available resources."""
        return self.resources.copy()
    
    # ========================================
    # DATA EXTRACTION
    # ========================================
    
    def extract_data(self, canonical_key: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured data for a query.
        
        WORKFLOW:
        1. Select resource URL from resources.json
        2. If URL found → use ChatGPT to browse and extract
        3. If no URL → use ChatGPT web search
        4. Build structured JSON dataset
        
        Args:
            canonical_key: The canonical key for the topic
            query: Original user query
            
        Returns:
            Structured JSON dataset or None if failed
        """
        self.logger.info(f"Extracting data for: {query} (key: {canonical_key})")
        
        # Step 1: Try to select a resource URL
        url = self.select_resource(canonical_key, query)
        
        if url:
            # Step 2a: Extract from specific URL using ChatGPT browsing
            data = self.openai_service.extract_page_data(url, query)
            if data:
                data['topic'] = canonical_key
                return self._clean_dataset(data, query, canonical_key)
        
        # Step 2b: No URL match - perform general web search
        self.logger.info(f"Performing general web search for: {query}")
        search_result = self.openai_service.perform_web_search(
            f"Jordan University of Science and Technology {query}"
        )
        
        if search_result:
            # Convert search result to structured data
            data = self._parse_search_result(search_result, query, canonical_key)
            if data:
                return self._clean_dataset(data, query, canonical_key)
        
        # Step 3: Return minimal dataset if all else fails
        self.logger.warning(f"Could not extract data for: {query}")
        return {
            "topic": canonical_key,
            "query": query,
            "message": "Unable to retrieve detailed information at this time.",
            "suggestion": "Please visit the university website directly or contact student services."
        }
    
    def _parse_search_result(self, search_result: str, query: str, canonical_key: str) -> Optional[Dict[str, Any]]:
        """
        Parse web search result into structured data.
        
        Args:
            search_result: Raw text from web search
            query: Original query
            canonical_key: The canonical key
            
        Returns:
            Structured data dict or None
        """
        if not search_result or search_result == "Information not found":
            return None
        
        # Use OpenAI to structure the search result
        if self.openai_service.is_configured():
            try:
                prompt = f"""Convert this search result into structured JSON.

Search result:
{search_result[:3000]}

Original query: "{query}"

Return a JSON object with relevant fields like:
- title
- summary
- requirements (array)
- fees (object)
- deadlines (array)
- steps (array)
- contact_info (object)

Only include fields that have actual data from the search result.
Do NOT invent or hallucinate any information."""

                from openai import OpenAI
                from config import OPENAI_API_KEY, OPENAI_MODEL
                
                client = OpenAI(api_key=OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Extract structured data from text. Only include factual information."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                data = json.loads(response.choices[0].message.content)
                return data
                
            except Exception as e:
                self.logger.error(f"Failed to parse search result: {e}")
        
        # Fallback: return raw summary
        return {
            "summary": search_result[:500],
            "raw_result": True
        }
    
    def _clean_dataset(self, data: Dict[str, Any], query: str, canonical_key: str) -> Dict[str, Any]:
        """
        Clean and structure the dataset.
        
        Args:
            data: Raw extracted data
            query: Original query
            canonical_key: The canonical key
            
        Returns:
            Cleaned dataset
        """
        cleaned = {
            'topic': canonical_key,
        }
        
        # Copy standard fields if they exist
        standard_fields = [
            'url', 'title', 'summary', 'requirements', 'fees', 
            'deadlines', 'steps', 'tables', 'lists', 'contact_info',
            'departments', 'dates', 'descriptions'
        ]
        
        for field in standard_fields:
            if data.get(field):
                value = data[field]
                # Ensure arrays are arrays
                if field in ('requirements', 'deadlines', 'steps', 'dates', 'descriptions', 'departments'):
                    cleaned[field] = self._ensure_array(value)
                # Ensure objects are objects
                elif field in ('fees', 'contact_info'):
                    cleaned[field] = self._ensure_object(value)
                # Keep tables and lists as-is
                elif field in ('tables', 'lists'):
                    cleaned[field] = value
                else:
                    cleaned[field] = value
        
        # Remove empty fields
        cleaned = {k: v for k, v in cleaned.items() if v is not None and v != "" and v != [] and v != {}}
        
        return cleaned
    
    def _ensure_array(self, value: Any) -> List:
        """Ensure value is an array."""
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]
        else:
            return []
    
    def _ensure_object(self, value: Any) -> Dict:
        """Ensure value is an object/dict."""
        if isinstance(value, dict):
            return value
        else:
            return {}

