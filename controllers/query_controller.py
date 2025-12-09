"""
Query Controller - Main business logic for handling student queries.
Implements the STRICT 7-step workflow with embeddings + cosine similarity.

WORKFLOW (MUST FOLLOW EXACTLY):
================================
STEP 1: Embeddings + Cosine Similarity (alias matching)
STEP 2: Redis Cache Check (if canonical key found)
STEP 3: Resource Selection (semantic reasoning)
STEP 4: ChatGPT Web Search & Extraction
STEP 5: Auto-Generate Aliases
STEP 6: Store in Redis (with embeddings)
STEP 7: Return Final Result
"""
import copy
from typing import Dict, Any, Optional, List, Tuple
from services.redis_service import RedisService
from services.openai_service import OpenAIService
from services.alias_service import AliasService
from services.extractor_service import ExtractorService
from services.embeddings_service import EmbeddingsService
from config import SIMILARITY_THRESHOLD
from logger import (
    log_query_received, log_redis_check, log_redis_data_used,
    log_resource_selection, log_web_search, log_web_extraction_start,
    log_web_extraction_complete, log_json_building_start, log_json_building_complete,
    log_redis_cache_store, log_answer_generation, log_response_ready, log_error,
    log_alias_generation_start, log_alias_generation_complete, get_logger
)


class QueryController:
    """
    Main controller for processing student queries.
    Implements the strict 7-step workflow with embeddings.
    """
    
    def __init__(self):
        """Initialize all services."""
        self.redis_service = RedisService()
        self.openai_service = OpenAIService()
        self.alias_service = AliasService()
        self.extractor_service = ExtractorService(self.openai_service)
        self.embeddings_service = EmbeddingsService()
        self.logger = get_logger()
    
    def process_query(self, query: str, redis_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a student query following the STRICT 7-step workflow.
        
        WORKFLOW:
        =========
        STEP 1: Embeddings + Cosine Similarity
        STEP 2: Redis Cache Check
        STEP 3: Resource Selection
        STEP 4: ChatGPT Web Search
        STEP 5: Auto-Generate Aliases
        STEP 6: Store in Redis
        STEP 7: Return Result
        
        Args:
            query: Student's question
            redis_json: Optional cached JSON (if provided, skip to answer generation)
            
        Returns:
            {
                "source": "redis" | "live_web",
                "json": {...},
                "aliases": [...],
                "answer": "..."
            }
        """
        has_provided_json = redis_json is not None and redis_json != {}
        log_query_received(query, has_provided_json)
        
        # If JSON provided directly, use it
        if has_provided_json:
            self.logger.info("Using provided Redis JSON (skip workflow)")
            return self._handle_redis_data(redis_json, query)
        
        # ========================================
        # STEP 1: EMBEDDINGS + COSINE SIMILARITY
        # ========================================
        self.logger.info("STEP 1: Embeddings + Cosine Similarity matching")
        
        canonical_key, confidence = self._match_with_embeddings(query)
        
        if canonical_key:
            # ========================================
            # STEP 2: REDIS CACHE CHECK
            # ========================================
            self.logger.info(f"STEP 2: Redis cache check for key: {canonical_key}")
            log_redis_check(True)
            
            cached_data = self.redis_service.fetch_from_redis(canonical_key)
            
            if cached_data:
                log_redis_data_used(canonical_key)
                self.logger.info(f"Cache HIT: Using cached data for {canonical_key}")
                return self._handle_redis_data(cached_data, query)
            else:
                self.logger.info(f"Cache MISS: Key {canonical_key} found but no data")
        else:
            log_redis_check(False)
            self.logger.info("No matching alias found - proceeding to live extraction")
        
        # ========================================
        # STEPS 3-7: LIVE WEB EXTRACTION
        # ========================================
        return self._handle_live_web(query, canonical_key)
    
    def _match_with_embeddings(self, query: str) -> Tuple[Optional[str], float]:
        """
        STEP 1: Match query to aliases using embeddings + cosine similarity.
        
        1. Generate embedding for query
        2. Compare with all stored alias embeddings
        3. If similarity >= threshold: use match directly
        4. If similarity < threshold: ask ChatGPT to validate
        
        Args:
            query: User query
            
        Returns:
            Tuple of (canonical_key, confidence) or (None, 0)
        """
        if not self.embeddings_service.is_configured():
            self.logger.warning("Embeddings service not configured - using fallback")
            return self._fallback_alias_matching(query)
        
        # Get all stored alias embeddings
        alias_embeddings = self.redis_service.get_all_alias_embeddings()
        
        if not alias_embeddings:
            self.logger.info("No alias embeddings stored yet")
            return self._fallback_alias_matching(query)
        
        # Match query to aliases
        best_alias, canonical_key, score, is_confident = \
            self.embeddings_service.match_query_to_aliases(query, alias_embeddings)
        
        self.logger.info(
            f"Embedding match: alias='{best_alias}', key={canonical_key}, "
            f"score={score:.4f}, confident={is_confident}"
        )
        
        if is_confident:
            # Score >= threshold, use match directly
            return canonical_key, score
        
        elif best_alias and score > 0.5:
            # Score below threshold but has some match - ask ChatGPT to validate
            self.logger.info("Uncertain match - asking ChatGPT to validate")
            
            # Prepare top candidates for ChatGPT
            candidates = self._get_top_candidates(query, alias_embeddings, top_k=5)
            
            if candidates:
                validated_alias, validated_key, confidence = \
                    self.openai_service.validate_alias_match(
                        query,
                        candidates['aliases'],
                        candidates['scores']
                    )
                
                if validated_key:
                    return validated_key, confidence
        
        # No match found
        return self._fallback_alias_matching(query)
    
    def _get_top_candidates(
        self, 
        query: str, 
        alias_embeddings: Dict[str, Dict], 
        top_k: int = 5
    ) -> Optional[Dict]:
        """Get top K candidate matches for ChatGPT validation."""
        query_embedding = self.embeddings_service.generate_embedding(query)
        if not query_embedding:
            return None
        
        scores = []
        for alias, data in alias_embeddings.items():
            embedding = data.get('embedding')
            if embedding:
                score = self.embeddings_service.cosine_similarity(query_embedding, embedding)
                scores.append({
                    'alias': alias,
                    'canonical_key': data.get('canonical_key'),
                    'score': score
                })
        
        # Sort by score and take top K
        scores.sort(key=lambda x: x['score'], reverse=True)
        top = scores[:top_k]
        
        if not top:
            return None
        
        return {
            'aliases': [{'alias': s['alias'], 'canonical_key': s['canonical_key']} for s in top],
            'scores': [s['score'] for s in top]
        }
    
    def _fallback_alias_matching(self, query: str) -> Tuple[Optional[str], float]:
        """
        Fallback alias matching using alias_service when embeddings unavailable.
        """
        # Try to get canonical key from alias service
        result = self.alias_service.process_query(query)
        canonical_key = result.get('canonical_key')
        
        if canonical_key and canonical_key != 'general':
            # Check if this key exists in Redis
            if self.redis_service.resolve_alias(query):
                return canonical_key, 0.7
        
        return None, 0.0
    
    def _handle_redis_data(self, redis_json: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Handle query when Redis data is available.
        
        STRICT RULES:
        - Use Redis JSON exactly as-is
        - Do NOT modify the JSON
        - Do NOT fetch new data
        - Do NOT regenerate aliases
        - Pass JSON to ChatGPT for refined answer
        """
        original_json = copy.deepcopy(redis_json)
        
        topic_key = original_json.get('topic', 'unknown')
        log_redis_data_used(topic_key)
        
        # Extract aliases
        aliases = original_json.get('aliases', [])
        
        # Create clean JSON for answer generation
        clean_json = {k: v for k, v in original_json.items() if k != 'aliases'}
        
        # Generate refined answer using ChatGPT
        log_answer_generation("redis")
        answer = self.openai_service.generate_answer(clean_json, query, "redis")
        
        result = {
            "source": "redis",
            "json": original_json,
            "aliases": aliases,
            "answer": answer
        }
        
        log_response_ready("redis", len(answer), len(aliases))
        return result
    
    def _handle_live_web(self, query: str, canonical_key: Optional[str]) -> Dict[str, Any]:
        """
        Handle query with live web extraction.
        
        STEPS 3-7:
        ==========
        STEP 3: Resource Selection
        STEP 4: ChatGPT Web Search & Extraction
        STEP 5: Auto-Generate Aliases
        STEP 6: Store in Redis (with embeddings)
        STEP 7: Return Result
        """
        # ========================================
        # STEP 3: RESOURCE SELECTION
        # ========================================
        self.logger.info("STEP 3: Resource Selection")
        log_resource_selection(query)
        
        # Use alias service to determine canonical key if not already set
        if not canonical_key:
            result = self.alias_service.process_query(query)
            canonical_key = result.get('canonical_key', 'general')
        
        # ========================================
        # STEP 4: CHATGPT WEB SEARCH & EXTRACTION
        # ========================================
        self.logger.info("STEP 4: ChatGPT Web Search & Extraction")
        log_web_extraction_start(canonical_key)
        
        json_data = self.extractor_service.extract_data(canonical_key, query)
        
        if json_data:
            log_web_extraction_complete(canonical_key, True, len(str(json_data)))
        else:
            log_web_extraction_complete(canonical_key, False)
            json_data = {
                "topic": canonical_key,
                "query": query,
                "message": "Unable to retrieve information at this time."
            }
        
        # Build structured JSON
        log_json_building_start()
        json_keys = list(json_data.keys())
        log_json_building_complete(json_keys)
        
        # ========================================
        # STEP 5: AUTO-GENERATE ALIASES
        # ========================================
        self.logger.info("STEP 5: Auto-Generate Aliases")
        log_alias_generation_start()
        
        # Generate aliases using alias service
        alias_result = self.alias_service.process_query(query)
        aliases = alias_result.get('aliases', [])
        
        # Enhance with AI-generated aliases
        if self.openai_service.is_configured():
            ai_aliases = self.openai_service.generate_aliases_with_ai(canonical_key, query)
            if ai_aliases:
                existing = set(a.lower() for a in aliases)
                for alias in ai_aliases:
                    if alias.lower() not in existing:
                        aliases.append(alias)
                        existing.add(alias.lower())
        
        # Validate aliases
        aliases = self.alias_service.validate_aliases(canonical_key, aliases)
        
        # Update topic
        json_data['topic'] = canonical_key
        
        log_alias_generation_complete(canonical_key, len(aliases))
        
        # ========================================
        # STEP 6: STORE IN REDIS (with embeddings)
        # ========================================
        self.logger.info("STEP 6: Store in Redis")
        
        if self.redis_service.is_connected():
            # Generate embeddings for aliases
            alias_embeddings = {}
            if self.embeddings_service.is_configured():
                self.logger.info(f"Generating embeddings for {len(aliases)} aliases")
                embeddings_batch = self.embeddings_service.generate_embeddings_batch(aliases)
                for alias, embedding in embeddings_batch.items():
                    alias_embeddings[alias] = embedding
            
            # Store data with aliases and embeddings
            success = self.redis_service.save_to_redis(
                canonical_key, 
                json_data, 
                aliases,
                alias_embeddings
            )
            log_redis_cache_store(canonical_key, success)
        
        # ========================================
        # STEP 7: RETURN FINAL RESULT
        # ========================================
        self.logger.info("STEP 7: Generate Answer & Return")
        log_answer_generation("live_web")
        
        answer = self.openai_service.generate_answer(json_data, query, "live_web")
        
        result = {
            "source": "live_web",
            "json": json_data,
            "aliases": aliases,
            "answer": answer
        }
        
        log_response_ready("live_web", len(answer), len(aliases))
        return result
    
    # ========================================
    # API HELPER METHODS
    # ========================================
    
    def get_cached_data(self, topic_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data for a topic."""
        return self.redis_service.fetch_from_redis(topic_key)
    
    def generate_aliases(self, query: str) -> Dict[str, Any]:
        """Generate aliases for a query without full processing."""
        result = self.alias_service.process_query(query)
        
        # Store aliases in Redis
        if self.redis_service.is_connected():
            canonical_key = result['canonical_key']
            aliases = result['aliases']
            
            # Generate and store embeddings
            if self.embeddings_service.is_configured():
                embeddings = self.embeddings_service.generate_embeddings_batch(aliases)
                for alias, embedding in embeddings.items():
                    self.redis_service.store_alias_embedding(alias, embedding, canonical_key)
        
        return {
            "canonical_key": result['canonical_key'],
            "aliases": result['aliases']
        }
    
    def get_aliases(self, canonical_key: str) -> Dict[str, Any]:
        """Get aliases for a canonical key."""
        aliases = self.redis_service.get_aliases_for_key(canonical_key)
        return {
            "canonical_key": canonical_key,
            "aliases": aliases
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        redis_stats = self.redis_service.get_stats()
        return {
            "redis_connected": self.redis_service.is_connected(),
            "openai_configured": self.openai_service.is_configured(),
            "embeddings_configured": self.embeddings_service.is_configured(),
            "similarity_threshold": SIMILARITY_THRESHOLD,
            **redis_stats
        }


class OutputValidator:
    """Validates that output follows the strict format requirements."""
    
    @staticmethod
    def validate_output(output: Dict[str, Any]) -> tuple:
        """
        Validate output format.
        
        Required format:
        {
            "source": "redis" | "live_web",
            "json": {...},
            "aliases": [...],
            "answer": "..."
        }
        """
        required_keys = ["source", "json", "answer"]
        for key in required_keys:
            if key not in output:
                return False, f"Missing required key: {key}"
        
        if output["source"] not in ["redis", "live_web"]:
            return False, f"Invalid source: {output['source']}"
        
        if not isinstance(output["json"], dict):
            return False, "Field 'json' must be a dictionary"
        
        if not isinstance(output["answer"], str):
            return False, "Field 'answer' must be a string"
        
        if "aliases" in output and not isinstance(output["aliases"], list):
            return False, "Field 'aliases' must be a list"
        
        if output["source"] == "live_web" and "aliases" not in output:
            return False, "Missing 'aliases' for live_web source"
        
        return True, ""
