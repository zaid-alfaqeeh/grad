"""
Comprehensive logging system for University Assistant.
Tracks all operations, queries, and system flow.
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class UniversityAssistantLogger:
    """Centralized logging system for University Assistant."""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        """Singleton pattern to ensure one logger instance."""
        if cls._instance is None:
            cls._instance = super(UniversityAssistantLogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """Initialize the logger with file and console handlers."""
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self._logger = logging.getLogger('UniversityAssistant')
        self._logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers
        if self._logger.handlers:
            return
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler - All logs (rotating, max 10MB, keep 5 backups)
        file_handler = RotatingFileHandler(
            log_dir / 'assistant.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # Error file handler - Errors only
        error_handler = RotatingFileHandler(
            log_dir / 'errors.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # Console handler - Info and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # Add handlers
        self._logger.addHandler(file_handler)
        self._logger.addHandler(error_handler)
        self._logger.addHandler(console_handler)
    
    def get_logger(self):
        """Get the logger instance."""
        return self._logger


# Convenience functions for easy logging
def get_logger():
    """Get the logger instance."""
    return UniversityAssistantLogger().get_logger()


# Flow tracking functions
def log_query_received(query: str, redis_json_provided: bool = False):
    """Log when a query is received."""
    logger = get_logger()
    logger.info("=" * 80)
    logger.info(f"QUERY RECEIVED")
    logger.info(f"Query: {query}")
    logger.info(f"Redis JSON Provided: {redis_json_provided}")
    logger.info("=" * 80)


def log_redis_check(has_redis_data: bool):
    """Log Redis cache check result."""
    logger = get_logger()
    if has_redis_data:
        logger.info("✓ Redis cache HIT - Using cached data")
    else:
        logger.info("✗ Redis cache MISS - Proceeding with live extraction")


def log_redis_data_used(topic_key: str):
    """Log when Redis data is used."""
    logger = get_logger()
    logger.info(f"Using Redis data for topic: {topic_key}")
    logger.debug("Redis JSON used exactly as-is (no modifications)")


def log_resource_selection(query: str, selected_url: str = None):
    """Log resource selection process."""
    logger = get_logger()
    logger.info(f"Resource Selection - Query: {query}")
    if selected_url:
        logger.info(f"✓ Selected resource URL: {selected_url}")
    else:
        logger.info("✗ No matching resource found - Will perform web search")


def log_web_search(query: str):
    """Log web search operation."""
    logger = get_logger()
    logger.info(f"Performing web search for: {query}")


def log_web_extraction_start(url: str):
    """Log start of web extraction."""
    logger = get_logger()
    logger.info(f"Starting web extraction from: {url}")


def log_web_extraction_complete(url: str, success: bool, data_size: int = 0):
    """Log completion of web extraction."""
    logger = get_logger()
    if success:
        logger.info(f"✓ Web extraction complete - URL: {url}, Data size: {data_size} bytes")
    else:
        logger.warning(f"✗ Web extraction failed - URL: {url}")


def log_json_building_start():
    """Log start of JSON building."""
    logger = get_logger()
    logger.info("Building structured JSON dataset...")


def log_json_building_complete(json_keys: list):
    """Log completion of JSON building."""
    logger = get_logger()
    logger.info(f"✓ JSON dataset built - Keys: {', '.join(json_keys)}")
    logger.debug(f"JSON structure: {json_keys}")


def log_redis_cache_store(topic_key: str, success: bool):
    """Log Redis cache storage attempt."""
    logger = get_logger()
    if success:
        logger.info(f"✓ Data cached in Redis - Topic: {topic_key}")
    else:
        logger.warning(f"✗ Failed to cache in Redis - Topic: {topic_key}")


def log_answer_generation(source: str):
    """Log answer generation."""
    logger = get_logger()
    logger.info(f"Generating natural-language answer (source: {source})...")


def log_response_ready(source: str, answer_length: int, aliases_count: int = 0):
    """Log when response is ready."""
    logger = get_logger()
    if aliases_count > 0:
        logger.info(f"✓ Response ready - Source: {source}, Answer length: {answer_length} chars, Aliases: {aliases_count}")
    else:
        logger.info(f"✓ Response ready - Source: {source}, Answer length: {answer_length} chars")
    logger.info("=" * 80)


def log_alias_generation_start():
    """Log start of alias generation."""
    logger = get_logger()
    logger.info("Auto-generating aliases for query and extracted data...")


def log_alias_generation_complete(canonical_key: str, aliases_count: int):
    """Log completion of alias generation."""
    logger = get_logger()
    logger.info(f"✓ Generated {aliases_count} aliases for canonical key: {canonical_key}")


def log_error(operation: str, error: Exception):
    """Log errors."""
    logger = get_logger()
    logger.error(f"ERROR in {operation}: {str(error)}", exc_info=True)


def log_api_request(method: str, endpoint: str, status_code: int = None):
    """Log API requests."""
    logger = get_logger()
    if status_code:
        logger.info(f"API {method} {endpoint} - Status: {status_code}")
    else:
        logger.info(f"API {method} {endpoint}")


def log_redis_connection(status: bool):
    """Log Redis connection status."""
    logger = get_logger()
    if status:
        logger.info("✓ Redis connection established")
    else:
        logger.warning("✗ Redis connection failed - System will work without caching")


def log_validation_result(is_valid: bool, error_msg: str = ""):
    """Log output validation result."""
    logger = get_logger()
    if is_valid:
        logger.debug("✓ Output validation passed")
    else:
        logger.error(f"✗ Output validation failed: {error_msg}")


def log_system_start():
    """Log system startup."""
    logger = get_logger()
    logger.info("=" * 80)
    logger.info("UNIVERSITY ASSISTANT SYSTEM STARTING")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


def log_system_config(redis_connected: bool, openai_configured: bool):
    """Log system configuration."""
    logger = get_logger()
    logger.info("System Configuration:")
    logger.info(f"  Redis: {'Connected' if redis_connected else 'Not Connected'}")
    logger.info(f"  OpenAI: {'Configured' if openai_configured else 'Not Configured'}")
    logger.info("=" * 80)

