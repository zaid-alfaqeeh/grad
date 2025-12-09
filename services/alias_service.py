"""
Alias service for mapping student questions to canonical Redis keys.
Handles normalization, multilingual support, alias generation and validation.
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple
from logger import get_logger


class AliasService:
    """
    Maps student queries to canonical Redis keys and generates aliases.
    
    Workflow:
    1. Normalize & pre-process input
    2. Map to canonical key
    3. Generate aliases
    4. Validate aliases
    """
    
    # Canonical keys that exist in the system
    CANONICAL_KEYS = {
        'plan_software_engineering',
        'plan_computer_science',
        'plan_data_science',
        'registration',
        'fees',
        'admissions',
        'academic_calendar',
        'schedules',
        'courses_schedule',
        'student_services',
        'admission_rules',
        'scholarships',
        'housing',
        'departments',
        'library',
        'general'
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
    
    # Keyword mappings for canonical key detection
    KEYWORD_MAPPINGS = {
        'plan_software_engineering': [
            'software engineering', 'هندسة البرمجيات', 'se plan', 'se curriculum', 
            'خطة se', 'software engineer', 'هندسة سوفت وير'
        ],
        'plan_computer_science': [
            'computer science', 'علوم الحاسوب', 'cs plan', 'cs curriculum', 
            'خطة cs', 'علوم حاسوب'
        ],
        'plan_data_science': [
            'data science', 'علوم البيانات', 'ds plan', 'ds curriculum', 'خطة ds'
        ],
        'registration': [
            'register', 'registration', 'تسجيل', 'enroll', 'enrollment', 'تسجيل المواد'
        ],
        'fees': [
            'fee', 'fees', 'مصاريف', 'رسوم', 'payment', 'cost', 'tuition', 'price', 'تكلفة'
        ],
        'admissions': [
            'admission', 'admissions', 'قبول', 'قبولات', 'apply', 'application', 'طلب قبول'
        ],
        'academic_calendar': [
            'calendar', 'تقويم', 'academic calendar', 'semester dates', 'مواعيد الفصل', 
            'semester', 'تقويم أكاديمي'
        ],
        'schedules': [
            'schedule', 'جدول', 'schedules', 'timetable', 'class schedule', 'مواعيد', 
            'جدول الحصص', 'courses schedule'
        ],
        'student_services': [
            'student service', 'خدمات الطالب', 'student services', 'support', 'خدمات'
        ],
        'scholarships': [
            'scholarship', 'منح', 'scholarships', 'financial aid', 'منحة'
        ],
        'housing': [
            'housing', 'سكن', 'dorm', 'accommodation', 'residence', 'سكن طلابي'
        ],
        'departments': [
            'department', 'أقسام', 'departments', 'faculty', 'قسم'
        ],
        'library': [
            'library', 'مكتبة', 'libraries'
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
        
        Args:
            normalized_query: Normalized query
            language: Detected language
            
        Returns:
            Canonical key
        """
        query_lower = normalized_query.lower()
        
        # Check each canonical key's keywords
        for canonical_key, keywords in self.KEYWORD_MAPPINGS.items():
            if any(keyword in query_lower for keyword in keywords):
                self.logger.debug(f"Mapped '{normalized_query}' to {canonical_key}")
                return canonical_key
        
        # Default to 'general' if no match
        self.logger.debug(f"No specific mapping for '{normalized_query}', using 'general'")
        return 'general'
    
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
        
        Args:
            query: Student query
            
        Returns:
            {
                "canonical_key": "...",
                "aliases": [...],
                "language": "..."
            }
        """
        # Step 1: Normalization & Pre-processing
        normalized, language = self.normalize_input(query)
        self.logger.debug(f"Normalized query: '{normalized}', Language: {language}")
        
        # Step 2: Canonical Key Mapping
        canonical_key = self.map_to_canonical_key(normalized, language)
        
        if canonical_key not in self.CANONICAL_KEYS:
            self.logger.warning(f"Invalid canonical key: {canonical_key}, using 'general'")
            canonical_key = 'general'
        
        self.logger.debug(f"Mapped to canonical key: {canonical_key}")
        
        # Step 3: Alias Generation
        aliases = self.generate_aliases(canonical_key, query, language)
        
        # Step 4: Validation
        validated_aliases = self.validate_aliases(canonical_key, aliases)
        
        self.logger.info(f"Generated {len(validated_aliases)} validated aliases for key: {canonical_key}")
        
        return {
            "canonical_key": canonical_key,
            "aliases": validated_aliases,
            "language": language
        }

