"""
OpenAI service for content generation, semantic reasoning, and alias matching.
Uses ChatGPT to provide helpful information about JUST University.
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
    - Knowledge-based search and information generation
    - Content generation for JUST University topics
    - Alias matching validation
    - Answer generation in Arabic and English
    
    Uses ChatGPT's knowledge to provide helpful information.
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
        Perform a search about JUST university using ChatGPT.
        Uses model's knowledge and provides helpful information.
        
        Args:
            query: The search query
            
        Returns:
            Search results as text, or None if failed
        """
        if not self.client:
            self.logger.warning("OpenAI client not configured")
            return None
        
        try:
            self.logger.info(f"Performing search for: {query}")
            
            # Use chat completion with specialized prompt for JUST
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """أنت مساعد متخصص في جامعة العلوم والتكنولوجيا الأردنية (JUST) - Jordan University of Science and Technology.

معلومات عن الجامعة:
- الموقع: إربد، الأردن
- تأسست: 1986
- الموقع الرسمي: https://www.just.edu.jo
- من أكبر الجامعات الأردنية وأفضلها في المجالات العلمية والتقنية

الكليات الرئيسية:
- كلية الطب
- كلية الهندسة
- كلية تكنولوجيا المعلومات وعلوم الحاسوب
- كلية الصيدلة
- كلية طب الأسنان
- كلية التمريض
- كلية العلوم
- كلية الزراعة
- كلية العمارة والتصميم

خدمات الطلاب:
- التسجيل والقبول
- السكن الجامعي
- المكتبة
- المنح الدراسية
- شؤون الطلاب

قواعد الإجابة:
1. أجب بشكل مفيد ومفصل بناءً على معرفتك
2. إذا كان السؤال عن معلومات محددة (رسوم، مواعيد)، اقترح زيارة الموقع الرسمي
3. كن ودوداً ومساعداً
4. استخدم العربية أو الإنجليزية حسب لغة السؤال"""
                    },
                    {
                        "role": "user",
                        "content": f"أجب على هذا السؤال عن جامعة العلوم والتكنولوجيا الأردنية:\n\n{query}"
                    }
                ]
            )
            
            result = response.choices[0].message.content
            self.logger.debug(f"Search completed, result length: {len(result) if result else 0}")
            return result
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return None
    
    def extract_page_data(self, url: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Generate structured data for a topic using ChatGPT.
        
        Args:
            url: Context URL (may not be directly accessible)
            query: The original query for context
            
        Returns:
            Structured JSON dataset or None if failed
        """
        if not self.client:
            self.logger.warning("OpenAI client not configured")
            return None
        
        try:
            self.logger.info(f"Generating data for query: {query}")
            
            extraction_prompt = f"""أنشئ معلومات مفيدة حول هذا الموضوع لجامعة العلوم والتكنولوجيا الأردنية:

السؤال: "{query}"
رابط مرجعي: {url}

أرجع كائن JSON بهذه الحقول (أضف فقط الحقول ذات الصلة):
{{
    "title": "عنوان الموضوع",
    "summary": "ملخص مفيد (300-500 حرف)",
    "key_points": ["النقاط الرئيسية"],
    "steps": ["الخطوات إذا كانت عملية"],
    "tips": ["نصائح مفيدة"],
    "website": "رابط الموقع الرسمي للمزيد من المعلومات",
    "contact": "معلومات التواصل إذا معروفة"
}}

ملاحظات:
- قدم معلومات مفيدة وعامة عن الموضوع
- اقترح زيارة الموقع الرسمي للتفاصيل الدقيقة (الرسوم، المواعيد)
- الموقع الرسمي: https://www.just.edu.jo"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """أنت مساعد جامعة العلوم والتكنولوجيا الأردنية (JUST).
مهمتك تقديم معلومات مفيدة للطلاب.

القواعد:
- قدم معلومات عامة مفيدة
- للمعلومات الدقيقة (رسوم، مواعيد) اقترح الموقع الرسمي
- أرجع JSON صالح فقط
- كن مساعداً وودوداً"""
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
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
                self.logger.info(f"Generated {len(data)} fields for: {query}")
                return data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Data generation failed for {query}: {e}")
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
        Generate a VERY DETAILED natural-language answer from JSON data.
        
        Args:
            json_data: The structured JSON dataset
            query: Original student query
            source: Data source ("redis" or "live_web")
            
        Returns:
            Very detailed, comprehensive student-friendly explanation
        """
        if not self.client:
            return self._generate_fallback_answer(json_data, query)
        
        try:
            # Check data source for context
            is_cached = (source == "redis")
            source_note = "📦 هذه البيانات محفوظة مسبقاً - قم بتوسيعها وإثرائها بمعرفتك" if is_cached else "🌐 بيانات جديدة"
            
            prompt = f"""أنت مساعد متخصص في جامعة العلوم والتكنولوجيا الأردنية (JUST).
قم بإنشاء إجابة مفصلة جداً ومفيدة للطالب.

{source_note}

سؤال الطالب: "{query}"

البيانات المتوفرة:
{json.dumps(json_data, indent=2, ensure_ascii=False)}

🎯 مهمتك الأساسية:
- استخدم البيانات المتوفرة كأساس
- أضف تفاصيل وشروحات إضافية من معرفتك عن الجامعة
- وسّع الإجابة لتكون شاملة ومفيدة جداً
- لا تكتفِ بنقل البيانات - اشرحها وفصّلها

⚠️ قواعد صارمة جداً:

📋 قاعدة القوائم الكاملة (مهمة جداً!):
- إذا سأل الطالب عن قائمة (تخصصات، كليات، برامج، متطلبات، مواد) يجب ذكر القائمة كاملة
- لا تقل "وغيرها" أو "والمزيد" أو "مثل" ثم تذكر 2-3 فقط
- اذكر كل عنصر في القائمة بالاسم الكامل والتفاصيل
- إذا البيانات تحتوي على قائمة، اعرضها كاملة ثم اشرح كل عنصر

📝 التنسيق والتفصيل:
1. قدم إجابة مفصلة جداً وشاملة (500+ كلمة على الأقل)
2. اشرح كل نقطة بشكل واضح ومفصل مع أمثلة
3. استخدم عناوين فرعية (##)، نقاط (-)، وقوائم مرقمة
4. أضف معلومات إضافية مفيدة من معرفتك عن JUST
5. إذا كانت هناك خطوات، اشرح كل خطوة بالتفصيل
6. إذا كانت هناك رسوم أو تكاليف، اشرحها بالتفصيل مع الأرقام
7. إذا كانت هناك متطلبات، اشرح كل متطلب على حدة
8. أضف نصائح عملية ومفيدة للطالب
9. اقترح زيارة الموقع الرسمي: https://www.just.edu.jo

🚫 ممنوع:
- لا تذكر أي تفاصيل تقنية (Redis، caching، embeddings، cache)
- لا تختصر القوائم أو تقول "وغيرها"
- لا تستخدم "مثل" للاختصار
- لا تقدم إجابات قصيرة أو سطحية

✅ مطلوب:
- كن ودوداً ومهذباً ومهتماً بمساعدة الطالب
- استخدم اللغة العربية بشكل صحيح وواضح
- قدم معلومات كاملة وشاملة ومفصلة
- أضف قيمة حقيقية للطالب بمعلومات إضافية

قم بإنشاء إجابة شاملة ومفصلة جداً تغطي جميع جوانب السؤال."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """أنت مساعد متخصص في جامعة العلوم والتكنولوجيا الأردنية (JUST).
مهمتك تقديم إجابات مفصلة جداً ومفيدة للطلاب.

قواعد صارمة يجب اتباعها دائماً:
1. كن شاملاً ومفصلاً في إجاباتك - إجابات طويلة ومفيدة (500+ كلمة)
2. إذا سأل عن قائمة (تخصصات، كليات، برامج، مواد) اذكر القائمة كاملة بالتفصيل
3. لا تقل أبداً "وغيرها" أو "مثل" أو "والمزيد" - اذكر كل شيء
4. استخدم تنظيم واضح مع عناوين (##) ونقاط (-) وقوائم مرقمة
5. أضف شروحات وأمثلة وتوضيحات عملية
6. أضف نصائح مفيدة للطالب
7. كن ودوداً ومهتماً بمساعدة الطلاب
8. استخدم معرفتك عن الجامعة لإثراء الإجابة
9. لا تذكر أي تفاصيل تقنية مثل cache أو Redis"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=4000  # Increased for longer, more complete answers
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Answer generation failed: {e}")
            return self._generate_fallback_answer(json_data, query)
    
    def generate_answer_stream(self, json_data: Dict[str, Any], query: str, source: str):
        """
        Generate a streaming answer from JSON data.
        Yields chunks of text as they are generated.
        
        Args:
            json_data: The structured JSON dataset
            query: Original student query
            source: Data source ("redis" or "live_web")
            
        Yields:
            Text chunks as they are generated
        """
        if not self.client:
            # Fallback: yield the fallback answer all at once
            fallback = self._generate_fallback_answer(json_data, query)
            yield fallback
            return
        
        try:
            # Check data source for context
            is_cached = (source == "redis")
            source_note = "📦 هذه البيانات محفوظة مسبقاً - قم بتوسيعها وإثرائها بمعرفتك" if is_cached else "🌐 بيانات جديدة"
            
            prompt = f"""أنت مساعد متخصص في جامعة العلوم والتكنولوجيا الأردنية (JUST).
قم بإنشاء إجابة مفصلة جداً ومفيدة للطالب.

{source_note}

سؤال الطالب: "{query}"

البيانات المتوفرة:
{json.dumps(json_data, indent=2, ensure_ascii=False)}

🎯 مهمتك الأساسية:
- استخدم البيانات المتوفرة كأساس
- أضف تفاصيل وشروحات إضافية من معرفتك عن الجامعة
- وسّع الإجابة لتكون شاملة ومفيدة جداً
- لا تكتفِ بنقل البيانات - اشرحها وفصّلها

⚠️ قواعد صارمة جداً:

📋 قاعدة القوائم الكاملة (مهمة جداً!):
- إذا سأل الطالب عن قائمة (تخصصات، كليات، برامج، متطلبات، مواد) يجب ذكر القائمة كاملة
- لا تقل "وغيرها" أو "والمزيد" أو "مثل" ثم تذكر 2-3 فقط
- اذكر كل عنصر في القائمة بالاسم الكامل والتفاصيل
- إذا البيانات تحتوي على قائمة، اعرضها كاملة ثم اشرح كل عنصر

📝 التنسيق والتفصيل:
1. قدم إجابة مفصلة جداً وشاملة (500+ كلمة على الأقل)
2. اشرح كل نقطة بشكل واضح ومفصل مع أمثلة
3. استخدم عناوين فرعية (##)، نقاط (-)، وقوائم مرقمة
4. أضف معلومات إضافية مفيدة من معرفتك عن JUST
5. إذا كانت هناك خطوات، اشرح كل خطوة بالتفصيل
6. إذا كانت هناك رسوم أو تكاليف، اشرحها بالتفصيل مع الأرقام
7. إذا كانت هناك متطلبات، اشرح كل متطلب على حدة
8. أضف نصائح عملية ومفيدة للطالب
9. اقترح زيارة الموقع الرسمي: https://www.just.edu.jo

🚫 ممنوع:
- لا تذكر أي تفاصيل تقنية (Redis، caching، embeddings، cache)
- لا تختصر القوائم أو تقول "وغيرها"
- لا تستخدم "مثل" للاختصار
- لا تقدم إجابات قصيرة أو سطحية

✅ مطلوب:
- كن ودوداً ومهذباً ومهتماً بمساعدة الطالب
- استخدم اللغة العربية بشكل صحيح وواضح
- قدم معلومات كاملة وشاملة ومفصلة
- أضف قيمة حقيقية للطالب بمعلومات إضافية

قم بإنشاء إجابة شاملة ومفصلة جداً تغطي جميع جوانب السؤال."""

            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """أنت مساعد متخصص في جامعة العلوم والتكنولوجيا الأردنية (JUST).
مهمتك تقديم إجابات مفصلة جداً ومفيدة للطلاب.

قواعد صارمة يجب اتباعها دائماً:
1. كن شاملاً ومفصلاً في إجاباتك - إجابات طويلة ومفيدة (500+ كلمة)
2. إذا سأل عن قائمة (تخصصات، كليات، برامج، مواد) اذكر القائمة كاملة بالتفصيل
3. لا تقل أبداً "وغيرها" أو "مثل" أو "والمزيد" - اذكر كل شيء
4. استخدم تنظيم واضح مع عناوين (##) ونقاط (-) وقوائم مرقمة
5. أضف شروحات وأمثلة وتوضيحات عملية
6. أضف نصائح مفيدة للطالب
7. كن ودوداً ومهتماً بمساعدة الطلاب
8. استخدم معرفتك عن الجامعة لإثراء الإجابة
9. لا تذكر أي تفاصيل تقنية مثل cache أو Redis"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=4000,  # Increased for longer, more complete answers
                stream=True  # Enable streaming
            )
            
            # Yield chunks as they arrive
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            self.logger.error(f"Streaming answer generation failed: {e}")
            # Fallback: yield the fallback answer
            fallback = self._generate_fallback_answer(json_data, query)
            yield fallback
    
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
        Generate exactly 10 English + 10 Arabic aliases for a canonical key.
        
        Args:
            canonical_key: The canonical key
            query: The original query
            
        Returns:
            List of 20 aliases (10 Arabic + 10 English)
        """
        if not self.client:
            return []
        
        try:
            prompt = f"""أنت مولد أسماء مستعارة لنظام معلومات جامعة العلوم والتكنولوجيا الأردنية (JUST).

الموضوع: {canonical_key}
السؤال الأصلي: "{query}"

المطلوب: توليد 20 اسم مستعار بالضبط:

10 أسماء مستعارة عربية:
- 3 بالعربية الفصحى
- 3 باللهجة الأردنية/العامية
- 2 بالعربيزي (عربي بحروف إنجليزية مثل: "kif asajel")
- 2 اختصارات أو أخطاء إملائية شائعة

10 أسماء مستعارة إنجليزية:
- 3 صيغ رسمية
- 3 صيغ عامية/مختصرة
- 2 أخطاء إملائية شائعة
- 2 اختصارات

القواعد الصارمة:
- يجب أن تكون الأسماء متعلقة مباشرة بالموضوع
- لا تكرر أي اسم
- اجعلها واقعية (أشياء يمكن للطالب أن يكتبها فعلاً)
- ركز على جامعة العلوم والتكنولوجيا الأردنية

أعد JSON بهذا الشكل بالضبط:
{{
    "arabic_aliases": ["اسم1", "اسم2", "اسم3", "اسم4", "اسم5", "اسم6", "اسم7", "اسم8", "اسم9", "اسم10"],
    "english_aliases": ["alias1", "alias2", "alias3", "alias4", "alias5", "alias6", "alias7", "alias8", "alias9", "alias10"]
}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """أنت خبير في توليد الأسماء المستعارة لجامعة العلوم والتكنولوجيا الأردنية.
تفهم اللهجة الأردنية والعربية الفصحى والإنجليزية.
تولد أسماء واقعية يمكن للطلاب استخدامها فعلاً."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            aliases = []
            
            # Collect Arabic aliases
            if 'arabic_aliases' in result:
                aliases.extend(result['arabic_aliases'][:10])
            
            # Collect English aliases  
            if 'english_aliases' in result:
                aliases.extend(result['english_aliases'][:10])
            
            # Fallback for different response formats
            if not aliases:
                if isinstance(result, list):
                    aliases = result[:20]
                elif 'aliases' in result:
                    aliases = result['aliases'][:20]
                else:
                    for value in result.values():
                        if isinstance(value, list):
                            aliases.extend(value)
                    aliases = aliases[:20]
            
            self.logger.info(f"Generated {len(aliases)} aliases for {canonical_key}")
            return aliases
            
        except Exception as e:
            self.logger.error(f"AI alias generation failed: {e}")
            return []
    
    def generate_canonical_key(self, query: str) -> str:
        """
        Generate a professional canonical key for a query using AI.
        
        Args:
            query: The user query
            
        Returns:
            A professional canonical key (snake_case, English)
        """
        if not self.client:
            return "general"
        
        try:
            prompt = f"""Generate a canonical key for this university query.

Query: "{query}"

RULES:
1. Return a single snake_case key in English
2. Key should be specific and descriptive
3. Key should be 2-4 words max
4. Examples: "course_registration", "tuition_fees", "admission_requirements", "academic_calendar"
5. DO NOT use "general" - always be specific

Return JSON:
{{"canonical_key": "your_key_here"}}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You generate canonical keys for a university information system. Keys must be specific, descriptive, and in snake_case English."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            key = result.get('canonical_key', 'general')
            
            # Ensure it's valid
            key = key.lower().replace(' ', '_').replace('-', '_')
            if not key or key == 'general':
                # Generate from query
                words = query.lower().split()[:3]
                key = '_'.join(w for w in words if w.isalnum())[:30] or 'query'
            
            self.logger.info(f"Generated canonical key: {key} for query: {query[:50]}...")
            return key
            
        except Exception as e:
            self.logger.error(f"Canonical key generation failed: {e}")
            return "general"
