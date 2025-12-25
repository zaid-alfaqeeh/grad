"""
Extractor service for JUST University Assistant.
خدمة استخراج البيانات لمساعد جامعة العلوم والتكنولوجيا

PRIMARY FUNCTION: Search and generate university information
Uses ChatGPT to provide helpful answers about JUST University.
"""
import json
import os
from typing import Dict, Any, Optional, List
from config import RESOURCES_FILE
from logger import get_logger


class ExtractorService:
    """
    Orchestrates web data extraction using OpenAI service.
    
    CORE PHILOSOPHY:
    - ALWAYS search for information (primary job)
    - Use resource URLs as context/helpers (secondary)
    - Never fail silently - always try to help
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
    
    def extract_data(self, canonical_key: str, query: str, resource_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Extract structured data for a query - ALWAYS tries to answer.
        
        WORKFLOW:
        1. If resource_url provided, try that first
        2. Try resources.json URLs
        3. ALWAYS fall back to web search (primary job)
        4. Build structured JSON dataset
        
        Args:
            canonical_key: The canonical key for the topic
            query: Original user query
            resource_url: Optional helper URL for context
            
        Returns:
            Structured JSON dataset (always returns something useful)
        """
        self.logger.info(f"استخراج بيانات لـ: {query} (المفتاح: {canonical_key})")
        
        # Try 1: Use provided resource URL if available
        if resource_url:
            self.logger.info(f"Trying provided resource URL: {resource_url}")
            data = self.openai_service.extract_page_data(resource_url, query)
            if data and data.get('title'):
                data['topic'] = canonical_key
                return self._clean_dataset(data, query, canonical_key)
        
        # Try 2: Select resource URL from resources.json
        url = self.select_resource(canonical_key, query)
        
        if url:
            self.logger.info(f"Trying resources.json URL: {url}")
            data = self.openai_service.extract_page_data(url, query)
            if data and data.get('title'):
                data['topic'] = canonical_key
                return self._clean_dataset(data, query, canonical_key)
        
        # Try 3: ALWAYS perform web search (this is the PRIMARY JOB)
        self.logger.info(f"Performing web search for JUST: {query}")
        
        # Build a comprehensive search query
        search_queries = [
            f"جامعة العلوم والتكنولوجيا الأردنية {query}",
            f"Jordan University of Science and Technology JUST {query}",
        ]
        
        data = None
        for search_query in search_queries:
            search_result = self.openai_service.perform_web_search(search_query)
            
            if search_result and search_result != "Information not found":
                # Convert search result to structured data
                data = self._parse_search_result(search_result, query, canonical_key)
                if data and (data.get('summary') or data.get('title')):
                    self.logger.info(f"Successfully extracted data via web search")
                    return self._clean_dataset(data, query, canonical_key)
        
        # Always return something useful
        self.logger.warning(f"Could not extract detailed data for: {query}")
        return {
            "topic": canonical_key,
            "query": query,
            "title": f"معلومات عن {canonical_key.replace('_', ' ')}",
            "message": "يرجى زيارة موقع جامعة العلوم والتكنولوجيا الأردنية للحصول على معلومات تفصيلية",
            "suggestion": "قم بزيارة https://www.just.edu.jo أو تواصل مع خدمات الطلاب",
            "university_website": "https://www.just.edu.jo"
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

