"""
OpenAI service for web search, content extraction, and semantic reasoning.
Uses ONLY ChatGPT's built-in web_search tool - NO manual scraping.
"""
import json
import time
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, MAX_RETRIES, RETRY_DELAY
from logger import get_logger


def retry_on_error(max_retries: int = None, delay: float = None):
    """Decorator for retrying failed API calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = max_retries or MAX_RETRIES
            wait = delay or RETRY_DELAY
            last_error = None
            
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < retries - 1:
                        time.sleep(wait * (attempt + 1))  # Exponential backoff
                    continue
            
            # Log final failure
            logger = get_logger()
            logger.error(f"{func.__name__} failed after {retries} attempts: {last_error}")
            return None
        return wrapper
    return decorator


class OpenAIService:
    """
    Handles all OpenAI operations including:
    - Web search and browsing
    - Content extraction
    - Alias matching validation
    - Answer generation
    
    CRITICAL: This service uses ONLY ChatGPT's web_search tool.
    NO requests, NO BeautifulSoup, NO manual scraping.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(OpenAIService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize OpenAI client."""
        self.logger = get_logger()
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
        self.model = OPENAI_MODEL
        
        if self.client:
            self.logger.info(f"OpenAI service initialized with model: {self.model}")
        else:
            self.logger.warning("OpenAI API key not configured - web search disabled")
    
    def is_configured(self) -> bool:
        """Check if OpenAI is configured."""
        return self.client is not None
    
    # ========================================
    # ALIAS MATCHING VALIDATION (STEP 1)
    # ========================================
    
    def validate_alias_match(
        self, 
        query: str, 
        candidate_aliases: List[Dict[str, Any]],
        similarity_scores: List[float]
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Use ChatGPT to validate or pick the best alias match.
        Called when cosine similarity is uncertain (below threshold).
        
        Args:
            query: User query
            candidate_aliases: List of {alias, canonical_key} candidates
            similarity_scores: Corresponding similarity scores
            
        Returns:
            Tuple of (best_alias, canonical_key, confidence)
            Returns (None, None, 0) if no match found
        """
        if not self.client or not candidate_aliases:
            return None, None, 0.0
        
        try:
            # Build candidates list for prompt
            candidates_text = "\n".join([
                f"- Alias: '{c['alias']}' → Key: '{c['canonical_key']}' (similarity: {similarity_scores[i]:.2f})"
                for i, c in enumerate(candidate_aliases)
            ])
            
            prompt = f"""You are a semantic matching assistant for a university information system.

User Query: "{query}"

Candidate Aliases (with similarity scores):
{candidates_text}

TASK:
1. Analyze the user's query semantically
2. Determine which alias (if any) is the best match
3. Consider both semantic meaning and the similarity score

RULES:
- If a candidate clearly matches the query's intent, select it
- If no candidate matches, respond with "NO_MATCH"
- Be strict - only match if the semantic meaning aligns

Respond in JSON format:
{{
    "match": true/false,
    "selected_alias": "alias text or null",
    "canonical_key": "key or null",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a semantic matching expert. Analyze queries and determine the best alias match."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if result.get('match') and result.get('canonical_key'):
                self.logger.info(
                    f"ChatGPT validated match: '{query}' -> '{result['selected_alias']}' "
                    f"(key: {result['canonical_key']}, confidence: {result['confidence']})"
                )
                return (
                    result.get('selected_alias'),
                    result.get('canonical_key'),
                    result.get('confidence', 0.8)
                )
            else:
                self.logger.info(f"ChatGPT found no match for: '{query}'")
                return None, None, 0.0
                
        except Exception as e:
            self.logger.error(f"Alias validation failed: {e}")
            return None, None, 0.0
    
    def select_best_resource(
        self, 
        query: str, 
        resources: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Use ChatGPT to select the best resource URL for a query.
        
        Args:
            query: User query
            resources: Dict of {key: url}
            
        Returns:
            Tuple of (resource_key, url) or (None, None)
        """
        if not self.client or not resources:
            return None, None
        
        try:
            resources_text = "\n".join([
                f"- {key}: {url}" for key, url in resources.items()
            ])
            
            prompt = f"""You are a resource selector for a university information system.

User Query: "{query}"

Available Resources:
{resources_text}

TASK:
Select the most appropriate resource URL for this query.
If no resource matches, respond with null.

Respond in JSON:
{{
    "selected_key": "key or null",
    "selected_url": "url or null",
    "reasoning": "brief explanation"
}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a resource selector. Match queries to the most relevant university resource."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if result.get('selected_url'):
                self.logger.info(f"Selected resource: {result['selected_key']} for query: '{query}'")
                return result.get('selected_key'), result.get('selected_url')
            
            return None, None
            
        except Exception as e:
            self.logger.error(f"Resource selection failed: {e}")
            return None, None
    
    # ========================================
    # WEB SEARCH OPERATIONS
    # ========================================
    
    def perform_web_search(self, query: str) -> Optional[str]:
        """
        Perform a general web search using ChatGPT's web_search tool.
        
        Args:
            query: The search query
            
        Returns:
            Search results as text, or None if failed
        """
        if not self.client:
            self.logger.warning("OpenAI client not configured")
            return None
        
        try:
            self.logger.info(f"Performing web search for: {query}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a web search assistant for a university information system.
Search the web for the requested information and return ONLY factual data.

CRITICAL RULES:
- Return ONLY information found in search results
- Do NOT hallucinate or invent any data
- Do NOT make up numbers, dates, or fees
- If information is not found, say "Information not found"
- Be concise and factual"""
                    },
                    {
                        "role": "user",
                        "content": f"Search the web for: {query}"
                    }
                ],
                tools=[{"type": "web_search"}],
                tool_choice="auto"
            )
            
            result = response.choices[0].message.content
            self.logger.debug(f"Web search completed, result length: {len(result) if result else 0}")
            return result
            
        except Exception as e:
            self.logger.error(f"Web search failed: {e}")
            return None
    
    def extract_page_data(self, url: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured data from a URL using ChatGPT's web browsing.
        
        CRITICAL: This uses ChatGPT to browse and extract - NO manual scraping.
        
        Args:
            url: The URL to extract data from
            query: The original query for context
            
        Returns:
            Structured JSON dataset or None if failed
        """
        if not self.client:
            self.logger.warning("OpenAI client not configured")
            return None
        
        try:
            self.logger.info(f"Extracting data from URL: {url}")
            
            extraction_prompt = f"""Browse this URL and extract structured information: {url}

Original query: "{query}"

CRITICAL EXTRACTION RULES:
1. Extract ONLY factual information that exists on the page
2. Do NOT hallucinate, invent, or guess any data
3. Do NOT make up numbers, fees, dates, or requirements
4. If a field is not found on the page, DO NOT include it
5. Return ONLY valid JSON with no explanations

Extract and return a JSON object with these fields (only if present on the page):
{{
    "title": "Page title",
    "summary": "Brief factual summary (max 500 chars)",
    "requirements": ["list", "of", "requirements"] (if any),
    "fees": {{"type": "amount"}} (if any fee information exists),
    "deadlines": ["list of deadlines/dates"] (if any),
    "steps": ["step 1", "step 2"] (if process steps exist),
    "tables": [["header1", "header2"], ["row1col1", "row1col2"]] (if tables exist),
    "lists": [["item1", "item2"]] (if bullet lists exist),
    "contact_info": {{"phone": "...", "email": "..."}} (if contact details exist),
    "departments": ["list of departments"] (if mentioned),
    "dates": ["important dates"] (if any)
}}

IMPORTANT: Return ONLY the JSON object. No markdown, no explanations, no code blocks."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a strict data extraction assistant for a university information system.
You browse web pages and extract ONLY factual information that exists on the page.

ABSOLUTE RULES:
- NEVER hallucinate or invent data
- NEVER guess missing information
- NEVER make up numbers, dates, fees, or requirements
- If data is not on the page, do not include that field
- Return ONLY valid JSON
- Be 100% faithful to the source content"""
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                tools=[{"type": "web_search"}],
                tool_choice="auto",
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            
            if not content:
                self.logger.warning("Empty response from extraction")
                return None
            
            # Parse JSON response
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = self._extract_json_from_text(content)
            
            if data:
                data['url'] = url
                data['source_query'] = query
                data = {k: v for k, v in data.items() if v is not None and v != "" and v != [] and v != {}}
                self.logger.info(f"Extracted {len(data)} fields from {url}")
                return data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Page extraction failed for {url}: {e}")
            return None
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text that might contain markdown or other content."""
        import re
        
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    # ========================================
    # ANSWER GENERATION
    # ========================================
    
    def generate_answer(self, json_data: Dict[str, Any], query: str, source: str) -> str:
        """
        Generate a natural-language answer from JSON data.
        
        Args:
            json_data: The structured JSON dataset
            query: Original student query
            source: Data source ("redis" or "live_web")
            
        Returns:
            Student-friendly explanation
        """
        if not self.client:
            return self._generate_fallback_answer(json_data, query)
        
        try:
            prompt = f"""Generate a clear, friendly answer for a student based on this data.

Student's question: "{query}"

Data:
{json.dumps(json_data, indent=2, ensure_ascii=False)}

RULES:
1. Be helpful and student-friendly
2. Summarize the key information clearly
3. Do NOT mention Redis, caching, embeddings, or technical details
4. Do NOT mention web search or internal architecture
5. Format with bullet points or numbered lists where helpful
6. Keep it concise but complete"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful university assistant. Generate clear, friendly answers for students."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Answer generation failed: {e}")
            return self._generate_fallback_answer(json_data, query)
    
    def _generate_fallback_answer(self, json_data: Dict[str, Any], query: str) -> str:
        """Generate a basic answer without AI."""
        parts = ["Here's the information you're looking for:\n"]
        
        if json_data.get('title'):
            parts.append(f"**{json_data['title']}**\n")
        
        if json_data.get('summary'):
            parts.append(f"{json_data['summary']}\n")
        
        if json_data.get('requirements'):
            parts.append("\n**Requirements:**")
            for req in json_data['requirements']:
                parts.append(f"• {req}")
        
        if json_data.get('fees'):
            parts.append("\n**Fees:**")
            for key, value in json_data['fees'].items():
                parts.append(f"• {key}: {value}")
        
        if json_data.get('steps'):
            parts.append("\n**Steps:**")
            for i, step in enumerate(json_data['steps'], 1):
                parts.append(f"{i}. {step}")
        
        if json_data.get('deadlines'):
            parts.append("\n**Deadlines:**")
            for deadline in json_data['deadlines']:
                parts.append(f"• {deadline}")
        
        if json_data.get('url'):
            parts.append(f"\nFor more details, visit: {json_data['url']}")
        
        return "\n".join(parts)
    
    # ========================================
    # ALIAS GENERATION
    # ========================================
    
    def generate_aliases_with_ai(self, canonical_key: str, query: str) -> List[str]:
        """
        Use AI to generate aliases for a canonical key.
        
        Args:
            canonical_key: The canonical key
            query: The original query
            
        Returns:
            List of generated aliases
        """
        if not self.client:
            return []
        
        try:
            prompt = f"""Generate aliases for this university topic.

Canonical key: {canonical_key}
Original query: "{query}"

Generate aliases in these categories:
1. Arabic MSA (Modern Standard Arabic)
2. Arabic colloquial/dialect variations
3. English variations
4. Transliteration (Arabizi - Arabic written in English letters)
5. Common typos
6. Short forms and abbreviations

Return as JSON:
{{"aliases": ["alias1", "alias2", "alias3", ...]}}

Generate 10-15 relevant aliases. Do NOT include duplicates."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an alias generator for a university information system. Generate relevant aliases in Arabic and English."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'aliases' in result:
                return result['aliases']
            elif isinstance(result, dict):
                aliases = []
                for value in result.values():
                    if isinstance(value, list):
                        aliases.extend(value)
                    elif isinstance(value, str):
                        aliases.append(value)
                return aliases
            
            return []
            
        except Exception as e:
            self.logger.error(f"AI alias generation failed: {e}")
            return []
