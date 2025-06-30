from flask import Blueprint, request, jsonify
from services.site24x7_service import site24x7_service
import structlog
import asyncio

logger = structlog.get_logger()

site24x7_bp = Blueprint('site24x7', __name__, url_prefix='/api/site24x7')

@site24x7_bp.route('/logs', methods=['GET'])
def get_app_logs():
    """Get recent application logs"""
    try:
        limit = request.args.get('limit', 50, type=int)
        logs = site24x7_service.get_recent_logs(limit)
        
        return jsonify({
            'logs': logs,
            'total': len(logs)
        })
        
    except Exception as e:
        logger.error("API get_app_logs error", error=str(e))
        return jsonify({'error': str(e)}), 500

@site24x7_bp.route('/system', methods=['GET'])
def get_system_info():
    """Get current system information"""
    try:
        system_info = site24x7_service.get_system_info()
        return jsonify(system_info)
        
    except Exception as e:
        logger.error("API get_system_info error", error=str(e))
        return jsonify({'error': str(e)}), 500

@site24x7_bp.route('/test-log', methods=['POST'])
def test_log():
    """Test logging to Site24x7"""
    try:
        data = request.get_json()
        
        test_interaction = {
            'trace_id': 'test-' + str(int(time.time())),
            'framework': data.get('framework', 'test'),
            'model': data.get('model', 'test-model'),
            'vector_store': 'test-store',
            'input_query': data.get('input_query', 'Test query'),
            'output_response': data.get('output_response', 'Test response'),
            'input_tokens': 10,
            'output_tokens': 20,
            'total_tokens': 30,
            'latency_ms': 1000,
            'cost_usd': 0.001,
            'status': 'completed'
        }
        
        # Log asynchronously
        asyncio.create_task(site24x7_service.log_interaction(test_interaction))
        
        return jsonify({'message': 'Test log sent successfully'})
        
    except Exception as e:
        logger.error("API test_log error", error=str(e))
        return jsonify({'error': str(e)}), 500

@site24x7_bp.route('/status', methods=['GET'])
def get_service_status():
    """Get Site24x7 service status"""
    try:
        return jsonify({
            'running': site24x7_service.running,
            'session_active': site24x7_service.session is not None,
            'recent_logs_count': len(site24x7_service.recent_logs),
            'endpoints': {
                'metrics': site24x7_service.metrics_endpoint,
                'logs': site24x7_service.logs_endpoint
            }
        })
        
    except Exception as e:
        logger.error("API get_service_status error", error=str(e))
        return jsonify({'error': str(e)}), 500