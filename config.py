"""
Configuration file for the University Assistant system.

SYSTEM ARCHITECTURE:
- Embeddings + Cosine Similarity for alias matching
- ChatGPT Web Search for data extraction (NO manual scraping)
- Redis for caching JSON datasets and alias embeddings
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Chat model for web search and reasoning
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')

# Embeddings model for cosine similarity
EMBEDDINGS_MODEL = os.getenv('EMBEDDINGS_MODEL', 'text-embedding-3-small')

# Cosine similarity threshold for confident matches
# If score >= threshold, use the match directly
# If score < threshold, ask ChatGPT to validate
SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.70'))

# Minimum similarity to consider as a candidate
MIN_SIMILARITY = float(os.getenv('MIN_SIMILARITY', '0.50'))

# API retry settings
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = float(os.getenv('RETRY_DELAY', '1.0'))

# Server Configuration
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('SERVER_PORT', 5000))

# Resources file path
RESOURCES_FILE = os.getenv('RESOURCES_FILE', 'resources.json')

# Cache TTL (Time To Live) in seconds
CACHE_TTL = int(os.getenv('CACHE_TTL', 86400))  # 24 hours default
