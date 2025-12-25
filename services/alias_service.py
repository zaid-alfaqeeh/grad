"""
Alias service for JUST University Assistant.
خدمة الأسماء المستعارة لمساعد جامعة العلوم والتكنولوجيا

Handles normalization, multilingual support, alias generation and validation.
NEVER uses 'general' - always generates specific keys.
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple
from logger import get_logger


class AliasService:
    """
    Maps student queries to canonical Redis keys and generates aliases.
    
    PHILOSOPHY:
    - NEVER use 'general' as a key
    - Generate specific, descriptive keys
    - Support Arabic and English
    """
    
    # Canonical keys that exist in the system (extensible)
    CANONICAL_KEYS = {
        'plan_software_engineering',
        'plan_computer_science',
        'plan_data_science',
        'plan_electrical_engineering',
        'plan_mechanical_engineering',
        'plan_civil_engineering',
        'course_registration',
        'tuition_fees',
        'payment_methods',
        'admissions',
        'admission_requirements',
        'academic_calendar',
        'exam_schedule',
        'course_schedule',
        'student_services',
        'scholarships',
        'financial_aid',
        'student_housing',
        'departments',
        'faculties',
        'library_services',
        'graduation_requirements',
        'gpa_calculation',
        'transfer_students',
        'international_students',
        'campus_facilities',
        'contact_info',
        'university_info'
    }
    
    # Arabic to English mappings for common terms
    ARABIC_MAPPINGS = {
        'خطة': 'plan',
        'هندسة': 'engineering',
        'البرمجيات': 'software',
        'علوم': 'science',
        'الحاسوب': 'computer',
        'البيانات': 'data',
        'تسجيل': 'registration',
        'مصاريف': 'fees',
        'رسوم': 'fees',
        'قبول': 'admission',
        'قبولات': 'admissions',
        'تقويم': 'calendar',
        'أكاديمي': 'academic',
        'جدول': 'schedule',
        'مواعيد': 'schedule',
        'خدمات': 'services',
        'طالب': 'student',
        'قواعد': 'rules',
        'منح': 'scholarships',
        'سكن': 'housing',
        'أقسام': 'departments',
        'مكتبة': 'library'
    }
    
    # Keyword mappings for canonical key detection (extended)
    KEYWORD_MAPPINGS = {
        'plan_software_engineering': [
            'software engineering', 'هندسة البرمجيات', 'se plan', 'se curriculum', 
            'خطة se', 'software engineer', 'هندسة سوفت وير', 'سوفت وير', 'برمجيات'
        ],
        'plan_computer_science': [
            'computer science', 'علوم الحاسوب', 'cs plan', 'cs curriculum', 
            'خطة cs', 'علوم حاسوب', 'كمبيوتر ساينس'
        ],
        'plan_data_science': [
            'data science', 'علوم البيانات', 'ds plan', 'ds curriculum', 'خطة ds',
            'بيانات', 'داتا ساينس'
        ],
        'course_registration': [
            'register', 'registration', 'تسجيل', 'enroll', 'enrollment', 'تسجيل المواد',
            'سجل', 'اسجل', 'كيف اسجل', 'طريقة التسجيل', 'موعد التسجيل'
        ],
        'tuition_fees': [
            'fee', 'fees', 'مصاريف', 'رسوم', 'payment', 'cost', 'tuition', 'price', 
            'تكلفة', 'كم الرسوم', 'رسوم الجامعة', 'سعر الساعة', 'ساعة معتمدة'
        ],
        'admissions': [
            'admission', 'admissions', 'قبول', 'قبولات', 'apply', 'application', 
            'طلب قبول', 'شروط القبول', 'معدل القبول', 'acceptance'
        ],
        'academic_calendar': [
            'calendar', 'تقويم', 'academic calendar', 'semester dates', 'مواعيد الفصل', 
            'semester', 'تقويم أكاديمي', 'بداية الفصل', 'نهاية الفصل', 'متى يبدأ'
        ],
        'exam_schedule': [
            'exam', 'امتحان', 'امتحانات', 'جدول الامتحانات', 'final exam', 'midterm',
            'نص الفصل', 'نهائي', 'موعد الامتحان'
        ],
        'course_schedule': [
            'schedule', 'جدول', 'schedules', 'timetable', 'class schedule', 'مواعيد', 
            'جدول الحصص', 'courses schedule', 'جدول المحاضرات'
        ],
        'student_services': [
            'student service', 'خدمات الطالب', 'student services', 'support', 'خدمات',
            'شؤون الطلاب', 'عمادة شؤون الطلبة'
        ],
        'scholarships': [
            'scholarship', 'منح', 'scholarships', 'financial aid', 'منحة', 'منحة دراسية',
            'دعم مالي', 'مساعدة مالية'
        ],
        'student_housing': [
            'housing', 'سكن', 'dorm', 'accommodation', 'residence', 'سكن طلابي',
            'سكن الجامعة', 'dormitory', 'اسكان'
        ],
        'departments': [
            'department', 'أقسام', 'departments', 'قسم', 'الأقسام الأكاديمية'
        ],
        'faculties': [
            'faculty', 'كلية', 'كليات', 'faculties', 'college'
        ],
        'library_services': [
            'library', 'مكتبة', 'libraries', 'مكتبة الجامعة', 'استعارة كتب'
        ],
        'graduation_requirements': [
            'graduation', 'تخرج', 'متطلبات التخرج', 'graduate', 'شروط التخرج'
        ],
        'gpa_calculation': [
            'gpa', 'معدل', 'المعدل التراكمي', 'حساب المعدل', 'grade point'
        ],
        'transfer_students': [
            'transfer', 'انتقال', 'تحويل', 'نقل', 'طالب محول', 'معادلة'
        ],
        'international_students': [
            'international', 'وافد', 'وافدين', 'طلاب دوليين', 'أجنبي', 'foreign'
        ],
        'campus_facilities': [
            'campus', 'facilities', 'مرافق', 'حرم جامعي', 'مباني', 'building'
        ]
    }
    
    def __init__(self):
        """Initialize alias service."""
        self.logger = get_logger()
    
    # ========================================
    # NORMALIZATION
    # ========================================
    
    def normalize_input(self, query: str) -> Tuple[str, str]:
        """
        Normalize user input.
        
        Args:
            query: Raw user query
            
        Returns:
            Tuple of (normalized_query, detected_language)
        """
        # Remove extra whitespace
        normalized = ' '.join(query.split())
        
        # Normalize Arabic diacritics and accents
        normalized = unicodedata.normalize('NFKD', normalized)
        
        # Detect language
        language = self._detect_language(normalized)
        
        # Lowercase English parts while preserving Arabic
        if language in ('english', 'mixed'):
            words = normalized.split()
            normalized_words = []
            for word in words:
                if self._is_english(word):
                    normalized_words.append(word.lower())
                else:
                    normalized_words.append(word)
            normalized = ' '.join(normalized_words)
        
        return normalized, language
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is Arabic, English, or mixed."""
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        total_chars = len([c for c in text if c.isalpha()])
        
        if total_chars == 0:
            return 'unknown'
        
        arabic_ratio = arabic_chars / total_chars
        
        if arabic_ratio > 0.5:
            return 'arabic'
        elif arabic_ratio > 0:
            return 'mixed'
        else:
            return 'english'
    
    def _is_english(self, word: str) -> bool:
        """Check if word is primarily English."""
        english_chars = sum(1 for char in word if char.isalpha() and ord(char) < 128)
        return english_chars > len(word) * 0.5
    
    # ========================================
    # CANONICAL KEY MAPPING
    # ========================================
    
    def build_canonical_key(self, query: str) -> str:
        """
        Build canonical key from query.
        
        Args:
            query: User query
            
        Returns:
            Canonical key string
        """
        normalized, language = self.normalize_input(query)
        return self.map_to_canonical_key(normalized, language)
    
    def map_to_canonical_key(self, normalized_query: str, language: str) -> str:
        """
        Map normalized input to canonical Redis key.
        NEVER returns 'general' - always generates a specific key.
        
        Args:
            normalized_query: Normalized query
            language: Detected language
            
        Returns:
            Canonical key (never 'general')
        """
        query_lower = normalized_query.lower()
        
        # Check each canonical key's keywords
        for canonical_key, keywords in self.KEYWORD_MAPPINGS.items():
            if any(keyword in query_lower for keyword in keywords):
                self.logger.debug(f"Mapped '{normalized_query}' to {canonical_key}")
                return canonical_key
        
        # Generate a key from the query instead of using 'general'
        generated_key = self._generate_key_from_query(normalized_query, language)
        self.logger.debug(f"Generated key '{generated_key}' for '{normalized_query}'")
        return generated_key
    
    def _generate_key_from_query(self, query: str, language: str) -> str:
        """
        Generate a canonical key from the query when no keyword matches.
        
        Args:
            query: The normalized query
            language: Detected language
            
        Returns:
            A snake_case canonical key
        """
        # Remove common Arabic stop words
        arabic_stop_words = {'في', 'من', 'على', 'إلى', 'عن', 'مع', 'هل', 'ما', 'كيف', 'متى', 'أين', 'لماذا', 'هذا', 'هذه', 'التي', 'الذي', 'أن', 'ان', 'كان', 'يكون', 'هي', 'هو', 'انا', 'انت', 'نحن', 'شو', 'وين', 'كيف', 'ليش'}
        english_stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves'}
        
        stop_words = arabic_stop_words | english_stop_words
        
        # Split query and filter
        words = query.lower().split()
        meaningful_words = []
        
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word not in stop_words and len(clean_word) > 1:
                meaningful_words.append(clean_word)
        
        # Take first 3 meaningful words
        key_words = meaningful_words[:3]
        
        if not key_words:
            # Fallback: use first significant word
            for word in words:
                clean = re.sub(r'[^\w]', '', word)
                if clean and len(clean) > 2:
                    return clean.lower()[:20]
            return 'university_query'
        
        # Convert Arabic to transliteration for key
        key = '_'.join(key_words)
        
        # Ensure valid key format
        key = re.sub(r'[^a-z0-9_\u0600-\u06FF]', '', key.lower())
        key = re.sub(r'_+', '_', key).strip('_')
        
        # If key has Arabic, transliterate to English-like
        if any('\u0600' <= c <= '\u06FF' for c in key):
            key = self._transliterate_arabic(key)
        
        return key[:30] if key else 'university_query'
    
    def _transliterate_arabic(self, text: str) -> str:
        """Simple Arabic to Latin transliteration for keys."""
        trans_map = {
            'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th',
            'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'th', 'ر': 'r', 'ز': 'z',
            'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a',
            'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
            'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'a', 'ء': '', 'ئ': 'y',
            'ؤ': 'w', 'ـ': ''
        }
        result = ''
        for char in text:
            if char in trans_map:
                result += trans_map[char]
            elif char.isalnum() or char == '_':
                result += char
        return result
    
    # ========================================
    # ALIAS GENERATION
    # ========================================
    
    def generate_aliases(self, canonical_key: str, original_query: str, language: str = None) -> List[str]:
        """
        Generate array of plausible aliases for canonical key.
        
        Args:
            canonical_key: The canonical Redis key
            original_query: Original user query
            language: Detected language (optional, will detect if not provided)
            
        Returns:
            List of aliases
        """
        if not language:
            _, language = self.normalize_input(original_query)
        
        aliases = []
        
        # Add original query as first alias
        aliases.append(original_query)
        
        # Add predefined aliases based on canonical key
        predefined = self._get_predefined_aliases(canonical_key)
        aliases.extend(predefined)
        
        # Add common typos and variations
        aliases.extend(self._generate_typos(original_query))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_aliases = []
        for alias in aliases:
            alias_lower = alias.lower().strip()
            if alias_lower and alias_lower not in seen:
                seen.add(alias_lower)
                unique_aliases.append(alias)
        
        return unique_aliases
    
    def _get_predefined_aliases(self, canonical_key: str) -> List[str]:
        """Get predefined aliases for a canonical key."""
        predefined_aliases = {
            'plan_software_engineering': [
                'خطة هندسة البرمجيات',
                'software engineering plan',
                'خطة برمجة',
                'خطة SE',
                'خطة هندسة سوفت وير',
                'plan SE',
                'se curriculum',
                'software engineer plan',
                'هندسة البرمجيات',
                'se plan',
                'khtah handsat albrmjyat'
            ],
            'plan_computer_science': [
                'خطة علوم الحاسوب',
                'computer science plan',
                'خطة CS',
                'plan CS',
                'cs curriculum',
                'computer science curriculum',
                'علوم الحاسوب',
                'khtah olom alhasob'
            ],
            'plan_data_science': [
                'خطة علوم البيانات',
                'data science plan',
                'خطة DS',
                'plan DS',
                'ds curriculum',
                'علوم البيانات'
            ],
            'fees': [
                'الرسوم الجامعية',
                'الـ fees',
                'مصاريف',
                'university fees',
                'تكلفة الدراسة',
                'رسوم',
                'payment',
                'cost',
                'tuition',
                'مصاريف الجامعة',
                'kam elrsom',
                'كم الرسوم'
            ],
            'registration': [
                'تسجيل',
                'registration',
                'enroll',
                'enrollment',
                'تسجيل المواد',
                'register',
                'تسجيل الطلاب',
                'kif asjel',
                'كيف اسجل'
            ],
            'admissions': [
                'قبول',
                'قبولات',
                'admission',
                'admissions',
                'apply',
                'application',
                'طلب قبول',
                'قبول الطلاب'
            ],
            'academic_calendar': [
                'تقويم أكاديمي',
                'academic calendar',
                'semester dates',
                'مواعيد الفصل',
                'calendar',
                'تقويم',
                'mata yabda alfasl',
                'متى يبدأ الفصل'
            ],
            'schedules': [
                'جدول',
                'schedule',
                'schedules',
                'timetable',
                'class schedule',
                'مواعيد',
                'جدول الحصص',
                'jadwal'
            ],
            'student_services': [
                'خدمات الطالب',
                'student services',
                'خدمات',
                'support services'
            ],
            'scholarships': [
                'منح',
                'منحة',
                'scholarship',
                'scholarships',
                'financial aid',
                'منح دراسية'
            ],
            'housing': [
                'سكن',
                'سكن طلابي',
                'housing',
                'dorm',
                'dormitory',
                'accommodation'
            ],
            'departments': [
                'أقسام',
                'قسم',
                'departments',
                'department',
                'faculty'
            ],
            'library': [
                'مكتبة',
                'library',
                'libraries',
                'مكتبة الجامعة'
            ]
        }
        
        return predefined_aliases.get(canonical_key, [])
    
    def _generate_typos(self, text: str) -> List[str]:
        """Generate common typos and variations."""
        typos = []
        text_lower = text.lower()
        
        # Common character substitutions
        typo_mappings = {
            'engineering': ['enginering', 'engeneering', 'engineerng'],
            'software': ['softwear', 'sowftware', 'sofware'],
            'registration': ['registeration', 'registraion', 'regestration'],
            'admission': ['addmission', 'admision', 'admisssion'],
            'schedule': ['schedul', 'scedule', 'shedule'],
            'computer': ['compter', 'computr', 'compoter'],
            'science': ['scince', 'sceince', 'sciense']
        }
        
        for word, variations in typo_mappings.items():
            if word in text_lower:
                for variation in variations:
                    typos.append(text_lower.replace(word, variation))
        
        return typos
    
    # ========================================
    # ALIAS VALIDATION
    # ========================================
    
    def validate_aliases(self, canonical_key: str, aliases: List[str]) -> List[str]:
        """
        Validate that aliases are semantically relevant to canonical key.
        
        Args:
            canonical_key: Canonical key
            aliases: List of aliases to validate
            
        Returns:
            Validated list of aliases
        """
        if not aliases:
            return []
        
        # Keywords that should be present for each canonical key
        key_keywords = {
            'plan_software_engineering': ['software', 'engineering', 'se', 'برمجيات', 'هندسة', 'خطة'],
            'plan_computer_science': ['computer', 'science', 'cs', 'حاسوب', 'علوم', 'خطة'],
            'plan_data_science': ['data', 'science', 'ds', 'بيانات', 'خطة'],
            'fees': ['fee', 'cost', 'payment', 'مصاريف', 'رسوم', 'تكلفة'],
            'registration': ['register', 'enroll', 'تسجيل', 'اسجل'],
            'admissions': ['admission', 'apply', 'قبول', 'application'],
            'academic_calendar': ['calendar', 'semester', 'تقويم', 'فصل', 'dates'],
            'schedules': ['schedule', 'timetable', 'جدول', 'مواعيد'],
            'scholarships': ['scholarship', 'منح', 'financial', 'منحة'],
            'housing': ['housing', 'dorm', 'سكن', 'accommodation'],
            'departments': ['department', 'faculty', 'أقسام', 'قسم'],
            'library': ['library', 'مكتبة']
        }
        
        required_keywords = key_keywords.get(canonical_key, [])
        
        # If no specific keywords, accept all (for general keys)
        if not required_keywords:
            return aliases
        
        validated = []
        for i, alias in enumerate(aliases):
            alias_lower = alias.lower()
            
            # Always keep the first alias (original query)
            if i == 0:
                validated.append(alias)
            # Check if alias contains at least one relevant keyword
            elif any(keyword in alias_lower for keyword in required_keywords):
                validated.append(alias)
        
        return validated
    
    # ========================================
    # COMPLETE WORKFLOW
    # ========================================
    
    def process_query(self, query: str) -> Dict[str, any]:
        """
        Complete workflow: Normalize, map, generate aliases, validate.
        NEVER returns 'general' as canonical key.
        
        Args:
            query: Student query
            
        Returns:
            {
                "canonical_key": "...",  # Always specific, never 'general'
                "aliases": [...],
                "language": "..."
            }
        """
        # Step 1: Normalization & Pre-processing
        normalized, language = self.normalize_input(query)
        self.logger.debug(f"Normalized query: '{normalized}', Language: {language}")
        
        # Step 2: Canonical Key Mapping (never returns 'general')
        canonical_key = self.map_to_canonical_key(normalized, language)
        
        # Add to known keys if new
        if canonical_key not in self.CANONICAL_KEYS:
            self.CANONICAL_KEYS.add(canonical_key)
        
        self.logger.debug(f"Mapped to canonical key: {canonical_key}")
        
        # Step 3: Alias Generation
        aliases = self.generate_aliases(canonical_key, query, language)
        
        # Step 4: Validation (relaxed for dynamic keys)
        validated_aliases = self.validate_aliases(canonical_key, aliases)
        
        self.logger.info(f"Generated {len(validated_aliases)} validated aliases for key: {canonical_key}")
        
        return {
            "canonical_key": canonical_key,
            "aliases": validated_aliases,
            "language": language
        }

