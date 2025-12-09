"""
Flask server for the University Assistant API.

SYSTEM ARCHITECTURE:
- Embeddings + Cosine Similarity for alias matching
- ChatGPT Web Search for data extraction (NO manual scraping)
- Redis for caching JSON datasets and alias embeddings
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
    
    WORKFLOW:
    1. Embeddings + Cosine Similarity (alias matching)
    2. Redis Cache Check (if canonical key found)
    3. Resource Selection (semantic reasoning)
    4. ChatGPT Web Search & Extraction
    5. Auto-Generate Aliases
    6. Store in Redis (with embeddings)
    7. Return {source, json, aliases, answer}
    
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
            return jsonify({
                'error': 'Missing required field: query'
            }), 400
        
        query = data['query']
        redis_json = data.get('redis_json', None)
        
        # Process query through controller (7-step workflow)
        result = query_controller.process_query(query, redis_json)
        
        # Validate output format
        is_valid, error_msg = OutputValidator.validate_output(result)
        log_validation_result(is_valid, error_msg)
        
        if not is_valid:
            log_api_request('POST', '/query', 500)
            return jsonify({
                'error': f'Output validation failed: {error_msg}',
                'result': result
            }), 500
        
        log_api_request('POST', '/query', 200)
        return jsonify(result), 200
        
    except Exception as e:
        log_error('handle_query', e)
        log_api_request('POST', '/query', 500)
        return jsonify({
            'error': f'Internal server error: {str(e)}'
        }), 500


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
    logger.info("Using ChatGPT web_search for data extraction (NO manual scraping)")
    
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
