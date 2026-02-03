"""
Extractor service for JUST University Assistant.
خدمة استخراج البيانات لمساعد جامعة العلوم والتكنولوجيا

ROBUST extraction service with:
- Advanced PDF extraction with retry and fallback
- Smart URL handling with content-type detection
- Multi-strategy data extraction
- Comprehensive error recovery
- Arabic text optimization
"""
import json
import os
import io
import re
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse, unquote
from config import RESOURCES_FILE
from logger import get_logger

# PDF and HTTP imports with graceful fallback
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HTTP_SUPPORT = True
except ImportError:
    HTTP_SUPPORT = False

try:
    from PyPDF2 import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class ExtractorService:
    """
    ROBUST data extraction service for JUST University Assistant.
    
    Features:
    - Multi-strategy extraction (PDF, Web, Search)
    - Automatic retry with exponential backoff
    - Content-type detection and smart routing
    - Arabic text optimization
    - Comprehensive error handling
    - Performance caching
    """
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    REQUEST_TIMEOUT = 45  # seconds
    MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_PDF_PAGES = 100
    MAX_TEXT_LENGTH = 50000  # characters
    
    # HTTP Session for connection pooling
    _session = None
    
    def __init__(self, openai_service):
        """
        Initialize extractor service with OpenAI integration.
        
        Args:
            openai_service: Instance of OpenAIService for AI operations
        """
        self.openai_service = openai_service
        self.logger = get_logger()
        self.resources = self._load_resources()
        self._pdf_cache = {}  # Cache for extracted PDF content
        self._init_http_session()
        
        self.logger.info(f"ExtractorService initialized | PDF: {PDF_SUPPORT} | HTTP: {HTTP_SUPPORT}")
    
    def _init_http_session(self):
        """Initialize HTTP session with retry strategy."""
        if not HTTP_SUPPORT:
            return
        
        if ExtractorService._session is None:
            ExtractorService._session = requests.Session()
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=self.MAX_RETRIES,
                backoff_factor=self.RETRY_DELAY,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            ExtractorService._session.mount("https://", adapter)
            ExtractorService._session.mount("http://", adapter)
            
            # Set default headers
            ExtractorService._session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
                'Accept-Language': 'ar,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            })
    
    def _load_resources(self) -> Dict[str, str]:
        """Load resources from JSON file with validation."""
        try:
            if os.path.exists(RESOURCES_FILE):
                with open(RESOURCES_FILE, 'r', encoding='utf-8') as f:
                    resources = json.load(f)
                    
                    # Validate URLs
                    valid_resources = {}
                    for key, url in resources.items():
                        if self._is_valid_url(url):
                            valid_resources[key] = url
                        else:
                            self.logger.warning(f"Invalid URL for {key}: {url}")
                    
                    self.logger.info(f"Loaded {len(valid_resources)} valid resources")
                    return valid_resources
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in resources.json: {e}")
        except Exception as e:
            self.logger.error(f"Error loading resources.json: {e}")
        
        return {}
    
    # ========================================
    # URL UTILITIES
    # ========================================
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        if not url or not isinstance(url, str):
            return False
        try:
            result = urlparse(url)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False
    
    def _is_pdf_url(self, url: str) -> bool:
        """
        Check if URL points to a PDF file.
        Uses multiple detection methods.
        """
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Method 1: Check file extension
        if url_lower.endswith('.pdf'):
            return True
        
        # Method 2: Check for PDF in URL path
        parsed = urlparse(url_lower)
        if '.pdf' in parsed.path:
            return True
        
        # Method 3: Check URL parameters
        if 'pdf' in parsed.query.lower():
            return True
        
        return False
    
    def _detect_content_type(self, url: str) -> str:
        """
        Detect content type of URL using HEAD request.
        
        Returns:
            'pdf', 'html', 'unknown'
        """
        if not HTTP_SUPPORT:
            return 'unknown'
        
        try:
            response = self._session.head(url, timeout=10, allow_redirects=True)
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'pdf' in content_type:
                return 'pdf'
            elif 'html' in content_type or 'text' in content_type:
                return 'html'
            else:
                return 'unknown'
        except Exception as e:
            self.logger.debug(f"Content-type detection failed: {e}")
            return 'unknown'
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    # ========================================
    # ROBUST PDF EXTRACTION
    # ========================================
    
    def _download_with_retry(self, url: str, max_retries: int = None) -> Optional[bytes]:
        """
        Download content with retry and error handling.
        
        Args:
            url: URL to download
            max_retries: Maximum retry attempts
            
        Returns:
            Content bytes or None
        """
        if not HTTP_SUPPORT:
            self.logger.error("HTTP support not available")
            return None
        
        retries = max_retries or self.MAX_RETRIES
        last_error = None
        
        for attempt in range(retries):
            try:
                self.logger.debug(f"Download attempt {attempt + 1}/{retries}: {url[:80]}...")
                
                response = self._session.get(
                    url,
                    timeout=self.REQUEST_TIMEOUT,
                    allow_redirects=True,
                    stream=True
                )
                response.raise_for_status()
                
                # Check content length
                content_length = int(response.headers.get('Content-Length', 0))
                if content_length > self.MAX_PDF_SIZE:
                    self.logger.warning(f"File too large: {content_length} bytes")
                    return None
                
                # Download content
                content = response.content
                self.logger.info(f"Downloaded {len(content)} bytes from {url[:50]}...")
                return content
                
            except requests.exceptions.Timeout:
                last_error = "Connection timeout"
                self.logger.warning(f"Timeout on attempt {attempt + 1}")
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP error: {e.response.status_code}"
                self.logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if e.response.status_code in [403, 404]:
                    break  # Don't retry on these errors
            except requests.exceptions.ConnectionError as e:
                last_error = "Connection failed"
                self.logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Download error on attempt {attempt + 1}: {e}")
            
            # Wait before retry with exponential backoff
            if attempt < retries - 1:
                wait_time = self.RETRY_DELAY * (2 ** attempt)
                self.logger.debug(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        self.logger.error(f"Download failed after {retries} attempts: {last_error}")
        return None
    
    def _extract_pdf_text(self, url: str) -> Optional[str]:
        """
        Extract text from PDF with robust error handling.
        
        Features:
        - Retry logic
        - Memory-efficient processing
        - Arabic text handling
        - Page-by-page extraction
        - Error recovery per page
        
        Args:
            url: PDF URL
            
        Returns:
            Extracted text or None
        """
        if not PDF_SUPPORT:
            self.logger.warning("PDF support not available. Install PyPDF2.")
            return None
        
        # Check cache first
        cache_key = self._get_cache_key(url)
        if cache_key in self._pdf_cache:
            self.logger.info(f"Using cached PDF content for: {url[:50]}...")
            return self._pdf_cache[cache_key]
        
        self.logger.info(f"📄 Extracting PDF: {url[:80]}...")
        
        # Download PDF
        content = self._download_with_retry(url)
        if not content:
            return None
        
        try:
            # Read PDF from memory
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)
            
            total_pages = len(reader.pages)
            if total_pages > self.MAX_PDF_PAGES:
                self.logger.warning(f"PDF has {total_pages} pages, limiting to {self.MAX_PDF_PAGES}")
                total_pages = self.MAX_PDF_PAGES
            
            self.logger.info(f"Processing {total_pages} pages...")
            
            # Extract text from each page
            text_parts = []
            failed_pages = []
            
            for page_num in range(total_pages):
                try:
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    if page_text:
                        # Clean the text
                        cleaned_text = self._clean_pdf_text(page_text)
                        if cleaned_text.strip():
                            text_parts.append(f"=== الصفحة {page_num + 1} ===\n{cleaned_text}")
                except Exception as e:
                    failed_pages.append(page_num + 1)
                    self.logger.debug(f"Failed to extract page {page_num + 1}: {e}")
                    continue
            
            if failed_pages:
                self.logger.warning(f"Failed to extract pages: {failed_pages}")
            
            if not text_parts:
                self.logger.warning("No text extracted from PDF (might be scanned/image-based)")
                return None
            
            # Combine all text
            full_text = "\n\n".join(text_parts)
            
            # Truncate if too long
            if len(full_text) > self.MAX_TEXT_LENGTH:
                full_text = full_text[:self.MAX_TEXT_LENGTH] + "\n\n... [تم اختصار المحتوى - الملف طويل جداً]"
            
            # Cache the result
            self._pdf_cache[cache_key] = full_text
            
            self.logger.info(f"✅ Extracted {len(full_text)} chars from {len(text_parts)} pages")
            return full_text
            
        except Exception as e:
            self.logger.error(f"PDF parsing failed: {e}")
            return None
    
    def _clean_pdf_text(self, text: str) -> str:
        """
        Clean and normalize PDF extracted text.
        
        Handles:
        - Arabic text normalization
        - Extra whitespace
        - Special characters
        - Line breaks
        """
        if not text:
            return ""
        
        # Remove null characters
        text = text.replace('\x00', '')
        
        # Normalize Arabic characters
        arabic_normalizations = {
            'أ': 'ا', 'إ': 'ا', 'آ': 'ا',  # Alef variations
            'ة': 'ه',  # Ta marbuta (optional)
            'ى': 'ي',  # Alef maksura
        }
        # Keep original Arabic for accuracy, just clean whitespace
        
        # Fix common PDF extraction issues
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)  # Single newlines to space
        
        # Remove excessive punctuation
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'-{3,}', '---', text)
        
        # Clean up
        text = text.strip()
        
        return text
    
    def _summarize_pdf_content(self, pdf_text: str, query: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Use AI to analyze and structure PDF content.
        
        Args:
            pdf_text: Extracted PDF text
            query: User's question
            url: Source URL
            
        Returns:
            Structured data dictionary
        """
        if not self.openai_service.is_configured():
            self.logger.warning("OpenAI not configured for PDF summarization")
            return self._create_basic_pdf_summary(pdf_text, url)
        
        try:
            # Prepare text (limit for API)
            max_chars = 20000
            truncated = len(pdf_text) > max_chars
            text_to_analyze = pdf_text[:max_chars] if truncated else pdf_text
            
            prompt = f"""أنت محلل مستندات متخصص في جامعة العلوم والتكنولوجيا الأردنية (JUST).

📄 تم استخراج النص التالي من ملف PDF رسمي:

{text_to_analyze}

{'⚠️ ملاحظة: تم اختصار المحتوى لأن الملف طويل جداً' if truncated else ''}

❓ سؤال الطالب: "{query}"

📋 مهمتك:
1. حلل المحتوى بعناية
2. استخرج كل المعلومات المتعلقة بسؤال الطالب
3. نظم البيانات بشكل مفيد وكامل

⚠️ قواعد صارمة:
- اذكر كل المواد والساعات إذا كانت خطة دراسية
- اذكر كل الرسوم والمبالغ إذا كان جدول رسوم
- لا تختصر - قدم كل المعلومات الموجودة
- إذا السؤال عن شيء غير موجود، اذكر ذلك بوضوح
- حافظ على الأرقام والتفاصيل الدقيقة

أرجع JSON بالحقول المناسبة:
{{
    "title": "عنوان المستند",
    "document_type": "نوع المستند (خطة دراسية/جدول رسوم/نظام/غيره)",
    "summary": "ملخص شامل",
    "study_plan": {{ // للخطط الدراسية
        "program_name": "اسم البرنامج",
        "total_credit_hours": "إجمالي الساعات",
        "duration": "مدة الدراسة",
        "courses_by_semester": [{{
            "semester": "الفصل",
            "courses": [{{ "name": "اسم المادة", "hours": "الساعات", "type": "إجباري/اختياري" }}]
        }}],
        "graduation_requirements": ["متطلبات التخرج"]
    }},
    "fees": {{ // لجداول الرسوم
        "fee_items": [{{ "item": "البند", "amount": "المبلغ" }}],
        "total": "المجموع",
        "notes": ["ملاحظات"]
    }},
    "key_points": ["النقاط الرئيسية"],
    "requirements": ["المتطلبات"],
    "important_dates": ["التواريخ المهمة"],
    "contact_info": {{ "phone": "", "email": "", "office": "" }},
    "source_url": "{url}"
}}"""

            from openai import OpenAI
            from config import OPENAI_API_KEY, OPENAI_MODEL
            
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """أنت محلل مستندات خبير لجامعة العلوم والتكنولوجيا الأردنية.
مهمتك استخراج المعلومات بدقة وشمولية من ملفات PDF.
لا تختصر أي معلومات - قدم كل التفاصيل الموجودة في المستند.
حافظ على الأرقام والبيانات الدقيقة كما هي."""
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.3  # Lower temperature for accuracy
            )
            
            data = json.loads(response.choices[0].message.content)
            data['url'] = url
            data['source_type'] = 'pdf'
            
            self.logger.info("✅ PDF content analyzed successfully")
            return data
            
        except Exception as e:
            self.logger.error(f"PDF analysis failed: {e}")
            return self._create_basic_pdf_summary(pdf_text, url)
    
    def _create_basic_pdf_summary(self, pdf_text: str, url: str) -> Dict[str, Any]:
        """Create basic summary without AI."""
        return {
            "title": "محتوى PDF",
            "summary": pdf_text[:1000] + "..." if len(pdf_text) > 1000 else pdf_text,
            "url": url,
            "source_type": "pdf",
            "note": "تم استخراج النص بدون تحليل AI"
        }
    
    def _extract_and_process_pdf(self, url: str, query: str, canonical_key: str) -> Optional[Dict[str, Any]]:
        """
        Complete PDF processing pipeline.
        
        Args:
            url: PDF URL
            query: User query
            canonical_key: Topic key
            
        Returns:
            Structured data or None
        """
        self.logger.info(f"🔄 Processing PDF: {url[:60]}...")
        
        # Step 1: Extract text
        pdf_text = self._extract_pdf_text(url)
        
        if not pdf_text:
            self.logger.warning(f"Could not extract text from PDF")
            return None
        
        # Step 2: Analyze and structure
        data = self._summarize_pdf_content(pdf_text, query, url)
        
        if data:
            data['topic'] = canonical_key
            data['source_type'] = 'pdf'
            return self._clean_dataset(data, query, canonical_key)
        
        return None
    
    # ========================================
    # WEB PAGE EXTRACTION
    # ========================================
    
    def _extract_web_page(self, url: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Extract data from web page using OpenAI.
        
        Args:
            url: Web page URL
            query: User query
            
        Returns:
            Extracted data or None
        """
        return self.openai_service.extract_page_data(url, query)
    
    # ========================================
    # SMART RESOURCE SELECTION
    # ========================================
    
    def select_resource(self, canonical_key: str, query: str) -> Optional[str]:
        """
        Intelligently select the best resource URL.
        
        Uses:
        - Direct key matching
        - Keyword-based matching
        - Fuzzy matching for Arabic
        
        Args:
            canonical_key: Topic key
            query: User query
            
        Returns:
            Best matching URL or None
        """
        # Method 1: Direct lookup
        if canonical_key in self.resources:
            url = self.resources[canonical_key]
            self.logger.info(f"Direct match: {canonical_key} -> {url[:50]}...")
            return url
        
        # Method 2: Keyword matching
        query_lower = query.lower()
        query_arabic = query  # Keep original for Arabic matching
        
        # Comprehensive keyword mappings
        keyword_mappings = {
            # Fees and Payments
            'Fees': [
                'fee', 'fees', 'payment', 'cost', 'tuition', 'price',
                'رسوم', 'مصاريف', 'تكلفة', 'سعر', 'اقساط', 'دفع',
                'رسم', 'تكاليف', 'كم سعر', 'كم رسوم'
            ],
            
            # Study Plans
            'Computer_Science_Plan': [
                'computer science', 'cs', 'comp sci',
                'علوم حاسوب', 'علوم الحاسوب', 'حاسوب', 'كمبيوتر',
                'كمبيوتر ساينس', 'خطة علوم الحاسوب', 'خطة cs'
            ],
            'Software_Engineering_Plan': [
                'software engineering', 'se', 'soft eng', 'software',
                'هندسة برمجيات', 'هندسة البرمجيات', 'سوفت وير',
                'برمجيات', 'خطة هندسة البرمجيات', 'سوفتوير'
            ],
            'Artificial_Intelligence_Plan': [
                'artificial intelligence', 'ai', 'machine learning', 'ml',
                'ذكاء اصطناعي', 'الذكاء الاصطناعي', 'ذكاء صناعي',
                'خطة الذكاء الاصطناعي', 'تخصص ai'
            ],
            'Cybersecurity_Plan': [
                'cybersecurity', 'cyber security', 'security', 'infosec',
                'امن سيبراني', 'الأمن السيبراني', 'سايبر سكيورتي',
                'أمن المعلومات', 'حماية', 'سايبر'
            ],
            'Robotics_Plan': [
                'robotics', 'robot', 'robots', 'automation',
                'روبوتات', 'الروبوتات', 'روبوتيكس', 'روبوت',
                'هندسة الروبوتات', 'خطة الروبوتات'
            ],
            
            # Faculties and Departments
            'Faculties_and_Departments': [
                'faculty', 'faculties', 'department', 'departments', 'college',
                'كلية', 'كليات', 'قسم', 'أقسام', 'الكليات', 'الأقسام'
            ],
            'Software_Engineering': [
                'se department', 'software dept',
                'قسم هندسة البرمجيات', 'قسم السوفت وير'
            ],
            
            # Scholarships and Rewards
            'Scholarships': [
                'scholarship', 'scholarships', 'financial aid', 'grant',
                'منحة', 'منح', 'منح دراسية', 'المنح', 'دعم مالي'
            ],
            'Rewards': [
                'reward', 'rewards', 'compensation', 'bonus',
                'مكافأة', 'مكافآت', 'تعويض', 'المكافآت', 'صندوق الادخار'
            ],
        }
        
        # Check for matches
        for resource_key, keywords in keyword_mappings.items():
            for keyword in keywords:
                # Check in lowercase query
                if keyword.lower() in query_lower:
                    if resource_key in self.resources:
                        url = self.resources[resource_key]
                        self.logger.info(f"Keyword match '{keyword}' -> {resource_key}")
                        return url
                
                # Check in original query (for Arabic)
                if keyword in query_arabic:
                    if resource_key in self.resources:
                        url = self.resources[resource_key]
                        self.logger.info(f"Arabic match '{keyword}' -> {resource_key}")
                        return url
        
        # Method 3: Check for plan/study keywords
        plan_indicators = ['خطة', 'plan', 'study plan', 'خطة دراسية', 'مواد', 'courses', 'منهج']
        has_plan_keyword = any(ind in query_lower or ind in query_arabic for ind in plan_indicators)
        
        if has_plan_keyword:
            # Try to find any matching study plan
            for key in self.resources:
                if 'Plan' in key:
                    for word in query_lower.split():
                        if word in key.lower():
                            self.logger.info(f"Plan keyword match: {key}")
                            return self.resources[key]
        
        self.logger.debug(f"No resource match for: {query[:50]}...")
        return None
    
    def get_all_resources(self) -> Dict[str, str]:
        """Get all available resources."""
        return self.resources.copy()
    
    # ========================================
    # MAIN EXTRACTION PIPELINE
    # ========================================
    
    def extract_data(self, canonical_key: str, query: str, resource_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        ROBUST data extraction with multiple fallback strategies.
        
        Pipeline:
        1. Try provided URL (detect PDF vs HTML)
        2. Try resources.json URL (detect PDF vs HTML)
        3. Try web search as fallback
        4. Return helpful default if all fail
        
        Args:
            canonical_key: Topic identifier
            query: User's question
            resource_url: Optional direct URL
            
        Returns:
            Structured data (always returns something useful)
        """
        self.logger.info(f"🔍 Extracting data for: {query[:50]}... (key: {canonical_key})")
        
        extraction_attempts = []
        
        # ==========================================
        # STRATEGY 1: Use provided resource URL
        # ==========================================
        if resource_url and self._is_valid_url(resource_url):
            self.logger.info(f"Strategy 1: Trying provided URL")
            
            data = self._try_extract_from_url(resource_url, query, canonical_key)
            if data:
                return data
            extraction_attempts.append(f"Provided URL failed: {resource_url[:50]}")
        
        # ==========================================
        # STRATEGY 2: Select from resources.json
        # ==========================================
        selected_url = self.select_resource(canonical_key, query)
        
        if selected_url and selected_url != resource_url:
            self.logger.info(f"Strategy 2: Trying resources.json URL")
            
            data = self._try_extract_from_url(selected_url, query, canonical_key)
            if data:
                return data
            extraction_attempts.append(f"Resources URL failed: {selected_url[:50]}")
        
        # ==========================================
        # STRATEGY 3: Web search fallback
        # ==========================================
        self.logger.info(f"Strategy 3: Web search fallback")
        
        data = self._try_web_search(query, canonical_key)
        if data:
            return data
        extraction_attempts.append("Web search failed")
        
        # ==========================================
        # STRATEGY 4: Return helpful default
        # ==========================================
        self.logger.warning(f"All strategies failed: {extraction_attempts}")
        
        return self._create_fallback_response(canonical_key, query, extraction_attempts)
    
    def _try_extract_from_url(self, url: str, query: str, canonical_key: str) -> Optional[Dict[str, Any]]:
        """
        Try to extract data from URL with automatic type detection.
        
        Args:
            url: URL to extract from
            query: User query
            canonical_key: Topic key
            
        Returns:
            Extracted data or None
        """
        # Check if PDF by URL pattern
        is_pdf = self._is_pdf_url(url)
        
        # If not obvious, check content type
        if not is_pdf:
            content_type = self._detect_content_type(url)
            is_pdf = (content_type == 'pdf')
        
        if is_pdf:
            self.logger.info(f"📄 Detected PDF, using PDF extractor")
            data = self._extract_and_process_pdf(url, query, canonical_key)
        else:
            self.logger.info(f"🌐 Detected web page, using web extractor")
            data = self._extract_web_page(url, query)
            if data and data.get('title'):
                data['topic'] = canonical_key
                data = self._clean_dataset(data, query, canonical_key)
        
        return data if data and (data.get('title') or data.get('summary')) else None
    
    def _try_web_search(self, query: str, canonical_key: str) -> Optional[Dict[str, Any]]:
        """
        Try web search as fallback.
        
        Args:
            query: Search query
            canonical_key: Topic key
            
        Returns:
            Search results or None
        """
        search_queries = [
            f"جامعة العلوم والتكنولوجيا الأردنية {query}",
            f"JUST Jordan University {query}",
        ]
        
        for search_query in search_queries:
            result = self.openai_service.perform_web_search(search_query)
            
            if result and result != "Information not found" and len(result) > 50:
                data = self._parse_search_result(result, query, canonical_key)
                if data and (data.get('summary') or data.get('title')):
                    return self._clean_dataset(data, query, canonical_key)
        
        return None
    
    def _create_fallback_response(self, canonical_key: str, query: str, attempts: List[str]) -> Dict[str, Any]:
        """Create helpful fallback response."""
        return {
            "topic": canonical_key,
            "query": query,
            "title": f"معلومات عن {canonical_key.replace('_', ' ')}",
            "summary": "لم نتمكن من استخراج معلومات تفصيلية حالياً",
            "suggestion": "يرجى زيارة موقع جامعة العلوم والتكنولوجيا الأردنية الرسمي",
            "university_website": "https://www.just.edu.jo",
            "helpful_links": [
                "https://www.just.edu.jo/FacultiesandDepartments",
                "https://www.just.edu.jo/Admission",
                "https://www.just.edu.jo/StudentServices"
            ],
            "contact": "يمكنك التواصل مع خدمات الطلاب للمساعدة",
            "_debug_attempts": attempts if self.logger.level <= 10 else None
        }
    
    def _parse_search_result(self, search_result: str, query: str, canonical_key: str) -> Optional[Dict[str, Any]]:
        """Parse web search result into structured data."""
        if not search_result or search_result == "Information not found":
            return None
        
        if self.openai_service.is_configured():
            try:
                prompt = f"""Convert this search result into structured JSON.

Search result:
{search_result[:4000]}

Original query: "{query}"

Return JSON with relevant fields:
- title: Main topic
- summary: Key information
- requirements: List if applicable
- fees: Fee information if applicable
- steps: Steps if applicable
- contact_info: Contact details if found
- key_points: Main points

Only include fields with actual data. Do NOT invent information."""

                from openai import OpenAI
                from config import OPENAI_API_KEY, OPENAI_MODEL
                
                client = OpenAI(api_key=OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Extract structured data from search results. Be accurate and factual."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=2000
                )
                
                return json.loads(response.choices[0].message.content)
                
            except Exception as e:
                self.logger.error(f"Failed to parse search result: {e}")
        
        return {
            "summary": search_result[:500],
            "source_type": "web_search"
        }
    
    # ========================================
    # DATA CLEANING
    # ========================================
    
    def _clean_dataset(self, data: Dict[str, Any], query: str, canonical_key: str) -> Dict[str, Any]:
        """Clean and normalize extracted data."""
        cleaned = {'topic': canonical_key}
        
        # All possible fields
        all_fields = [
            # Standard fields
            'url', 'title', 'summary', 'requirements', 'fees',
            'deadlines', 'steps', 'tables', 'lists', 'contact_info',
            'departments', 'dates', 'descriptions', 'source_type',
            'key_points', 'source_url', 'document_type',
            # PDF/Study plan fields
            'study_plan', 'courses', 'semesters', 'total_hours',
            'required_courses', 'elective_courses', 'total_credit_hours',
            'program_name', 'graduation_requirements', 'courses_by_semester',
            # Additional fields
            'important_dates', 'helpful_links', 'suggestion', 'note',
            'university_website', 'contact', 'fee_items'
        ]
        
        array_fields = {
            'requirements', 'deadlines', 'steps', 'dates', 'descriptions',
            'departments', 'key_points', 'required_courses', 'elective_courses',
            'courses', 'semesters', 'graduation_requirements', 'important_dates',
            'helpful_links', 'courses_by_semester', 'fee_items'
        }
        
        object_fields = {'fees', 'contact_info', 'study_plan', 'contact'}
        
        for field in all_fields:
            if data.get(field) is not None:
                value = data[field]
                
                if field in array_fields:
                    cleaned[field] = self._ensure_array(value)
                elif field in object_fields:
                    cleaned[field] = self._ensure_object(value)
                elif field in ('tables', 'lists'):
                    cleaned[field] = value
                else:
                    cleaned[field] = value
        
        # Remove empty values
        cleaned = {k: v for k, v in cleaned.items() 
                   if v is not None and v != "" and v != [] and v != {}}
        
        return cleaned
    
    def _ensure_array(self, value: Any) -> List:
        """Ensure value is a list."""
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value] if value.strip() else []
        elif value is None:
            return []
        else:
            return [str(value)]
    
    def _ensure_object(self, value: Any) -> Dict:
        """Ensure value is a dictionary."""
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"value": value} if value.strip() else {}
        else:
            return {}
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def clear_cache(self):
        """Clear PDF cache."""
        self._pdf_cache.clear()
        self.logger.info("PDF cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "pdf_cache_size": len(self._pdf_cache),
            "pdf_cache_keys": list(self._pdf_cache.keys())[:10]
        }
