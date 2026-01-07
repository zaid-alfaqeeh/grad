"""
Flask server for the JUST University Assistant API.
شات بوت متخصص لجامعة العلوم والتكنولوجيا الأردنية

SYSTEM ARCHITECTURE:
- Primary: ChatGPT Web Search (auto-search for any university question)
- Secondary: Redis Cache with Embeddings (for faster repeated queries)
- Aliases: 10 Arabic + 10 English per topic
- Resources: Helper URLs passed to GPT for context
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from controllers.query_controller import QueryController, OutputValidator
from services.redis_service import RedisService
from logger import (
    log_api_request, log_system_start, log_system_config,
    log_validation_result, log_error, get_logger
)
from config import OPENAI_API_KEY, SIMILARITY_THRESHOLD
import os
import json

app = Flask(__name__)
CORS(app)

# Initialize controller and services
query_controller = QueryController()
redis_service = RedisService()


@app.route('/', methods=['GET'])
@app.route('/test', methods=['GET'])
@app.route('/test.html', methods=['GET'])
def serve_test():
    """Serve the test.html interface."""
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test.html')
    if os.path.exists(file_path):
        return send_file(file_path, mimetype='text/html')
    else:
        return jsonify({'error': 'test.html file not found'}), 404


# ========================================
# REDIS DATA VIEWER API ENDPOINTS
# ========================================

@app.route('/api/redis/keys', methods=['GET'])
def get_redis_keys():
    """Get all Redis keys categorized by type."""
    try:
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        client = redis_service.client
        data_keys = []
        alias_keys = []
        embedding_keys = []
        canonical_keys = []
        
        # Scan all keys
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match="*", count=100)
            for key in keys:
                if key.startswith("data:"):
                    data_keys.append(key)
                elif key.startswith("alias:"):
                    alias_keys.append(key)
                elif key.startswith("emb:"):
                    embedding_keys.append(key)
                elif key.startswith("canonical:"):
                    canonical_keys.append(key)
            if cursor == 0:
                break
        
        return jsonify({
            'data_keys': sorted(data_keys),
            'alias_keys': sorted(alias_keys),
            'embedding_keys': sorted(embedding_keys),
            'canonical_keys': sorted(canonical_keys)
        })
    except Exception as e:
        log_error('get_redis_keys', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/redis/all-data', methods=['GET'])
def get_all_redis_data():
    """Get all cached data from Redis."""
    try:
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        client = redis_service.client
        all_data = []
        
        # Get all data keys
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match="data:*", count=100)
            for key in keys:
                try:
                    data = client.get(key)
                    if data:
                        canonical_key = key.replace("data:", "")
                        parsed_data = json.loads(data)
                        all_data.append({
                            'canonical_key': canonical_key,
                            'data': parsed_data
                        })
                except:
                    continue
            if cursor == 0:
                break
        
        return jsonify(all_data)
    except Exception as e:
        log_error('get_all_redis_data', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/redis/data/<canonical_key>', methods=['GET'])
def get_redis_data_by_key(canonical_key):
    """Get cached data for a specific canonical key."""
    try:
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        data = redis_service.fetch_from_redis(canonical_key)
        if data:
            return jsonify(data)
        else:
            return jsonify({'error': 'Key not found'}), 404
    except Exception as e:
        log_error('get_redis_data_by_key', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/redis/aliases', methods=['GET'])
def get_all_aliases():
    """Get all aliases grouped by canonical key."""
    try:
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        client = redis_service.client
        aliases_by_key = {}
        
        # Get all canonical keys with their aliases
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match="canonical:*:aliases", count=100)
            for key in keys:
                try:
                    aliases_json = client.get(key)
                    if aliases_json:
                        # Extract canonical key from "canonical:KEY:aliases"
                        canonical_key = key.replace("canonical:", "").replace(":aliases", "")
                        aliases = json.loads(aliases_json)
                        aliases_by_key[canonical_key] = aliases
                except:
                    continue
            if cursor == 0:
                break
        
        return jsonify(aliases_by_key)
    except Exception as e:
        log_error('get_all_aliases', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/redis/embeddings', methods=['GET'])
def get_embeddings_stats():
    """Get embeddings statistics."""
    try:
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        client = redis_service.client
        total = 0
        sample_dim = None
        
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match="emb:*", count=100)
            total += len(keys)
            
            # Get dimension from first embedding
            if sample_dim is None and keys:
                try:
                    data = client.get(keys[0])
                    if data:
                        parsed = json.loads(data)
                        if 'embedding' in parsed:
                            sample_dim = len(parsed['embedding'])
                except:
                    pass
            
            if cursor == 0:
                break
        
        return jsonify({
            'total_embeddings': total,
            'embedding_dimension': sample_dim
        })
    except Exception as e:
        log_error('get_embeddings_stats', e)
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    log_api_request('GET', '/health', 200)
    return jsonify({
        'status': 'healthy',
        'redis_connected': redis_service.is_connected(),
        'openai_configured': bool(OPENAI_API_KEY),
        'similarity_threshold': SIMILARITY_THRESHOLD
    })


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get system statistics."""
    log_api_request('GET', '/stats', 200)
    return jsonify(query_controller.get_stats())


@app.route('/query', methods=['POST'])
def handle_query():
    """
    Main query endpoint.
    
    OPTIMIZED WORKFLOW:
    1. Embeddings + Cosine Similarity (alias matching)
    2. Redis Cache Check (if canonical key found)
    3. Extract Data (quick)
    4. Generate VERY DETAILED Answer → Return IMMEDIATELY (Priority #1)
    5. Background: Generate aliases, embeddings, cache (non-blocking)
    
    Expected request body:
    {
        "query": "student question",
        "redis_json": {...}  // optional
    }
    """
    try:
        log_api_request('POST', '/query')
        data = request.get_json()
        if not data or 'query' not in data:
            log_api_request('POST', '/query', 400)
            return jsonify({'error': 'Missing required field: query'}), 400
        query = data['query']
        redis_json = data.get('redis_json', None)
        # Process query through controller (7-step workflow)
        result = query_controller.process_query(query, redis_json)
        # Validate output format
        is_valid, error_msg = OutputValidator.validate_output(result)
        log_validation_result(is_valid, error_msg)
        if not is_valid:
            log_api_request('POST', '/query', 500)
            return jsonify({'error': f'Output validation failed: {error_msg}','result': result}), 500
        log_api_request('POST', '/query', 200)
        return jsonify(result), 200
    except Exception as e:
        log_error('handle_query', e)
        log_api_request('POST', '/query', 500)
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/cache/<topic_key>', methods=['GET'])
def get_cache(topic_key):
    """Get cached data for a topic."""
    log_api_request('GET', f'/cache/{topic_key}')
    cached = query_controller.get_cached_data(topic_key)
    if cached:
        return jsonify(cached), 200
    else:
        return jsonify({'message': 'No cached data found'}), 404


@app.route('/cache/<topic_key>', methods=['DELETE'])
def delete_cache(topic_key):
    """Delete cached data for a topic."""
    log_api_request('DELETE', f'/cache/{topic_key}')
    success = redis_service.delete_key(topic_key)
    if success:
        return jsonify({'message': f'Cache deleted for {topic_key}'}), 200
    else:
        return jsonify({'message': 'Cache deletion failed'}), 500


@app.route('/api/redis/clear', methods=['DELETE'])
def clear_all_redis():
    """Clear all Redis data (for testing)."""
    try:
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        client = redis_service.client
        client.flushdb()
        return jsonify({'message': 'All Redis data cleared'}), 200
    except Exception as e:
        log_error('clear_all_redis', e)
        return jsonify({'error': str(e)}), 500


@app.route('/aliases/generate', methods=['POST'])
def generate_aliases():
    """
    Generate aliases for a query and store with embeddings.
    
    Expected request body:
    {
        "query": "student question"
    }
    """
    try:
        log_api_request('POST', '/aliases/generate')
        data = request.get_json()
        
        if not data or 'query' not in data:
            log_api_request('POST', '/aliases/generate', 400)
            return jsonify({
                'error': 'Missing required field: query'
            }), 400
        
        query = data['query']
        result = query_controller.generate_aliases(query)
        
        log_api_request('POST', '/aliases/generate', 200)
        return jsonify(result), 200
        
    except Exception as e:
        log_error('generate_aliases', e)
        log_api_request('POST', '/aliases/generate', 500)
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500


@app.route('/aliases/<canonical_key>', methods=['GET'])
def get_aliases(canonical_key):
    """Get all aliases for a canonical key."""
    try:
        log_api_request('GET', f'/aliases/{canonical_key}')
        
        if not redis_service.is_connected():
            return jsonify({'error': 'Redis not connected'}), 503
        
        result = query_controller.get_aliases(canonical_key)
        
        if result['aliases']:
            return jsonify(result), 200
        else:
            return jsonify({
                'canonical_key': canonical_key,
                'aliases': [],
                'message': 'No aliases found for this key'
            }), 404
            
    except Exception as e:
        log_error('get_aliases', e)
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500


if __name__ == '__main__':
    from config import SERVER_HOST, SERVER_PORT
    
    # Initialize logging
    log_system_start()
    log_system_config(redis_service.is_connected(), bool(OPENAI_API_KEY))
    
    logger = get_logger()
    logger.info(f"Starting University Assistant server on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Redis connected: {redis_service.is_connected()}")
    logger.info(f"Similarity threshold: {SIMILARITY_THRESHOLD}")
    logger.info("Using Embeddings + Cosine Similarity for alias matching")
    logger.info("Using ChatGPT knowledge for information generation")
    
    print(f"\n{'='*60}")
    print("UNIVERSITY ASSISTANT SERVER")
    print(f"{'='*60}")
    print(f"Server: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"Redis: {'Connected' if redis_service.is_connected() else 'Not Connected'}")
    print(f"OpenAI: {'Configured' if OPENAI_API_KEY else 'Not Configured'}")
    print(f"Similarity Threshold: {SIMILARITY_THRESHOLD}")
    print(f"{'='*60}")
    print("WORKFLOW: Embeddings → Cosine Similarity → Redis → ChatGPT Web Search")
    print(f"{'='*60}\n")
    
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=True)
