from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.enhanced_agent_service import enhanced_agent_service
from services.enhanced_metrics_service import enhanced_metrics_service
from services.site24x7_service import site24x7_service
from core.tracing import tracing_manager
from config.settings import settings
import structlog

logger = structlog.get_logger()

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def index():
    """Main playground page"""
    configs = enhanced_agent_service.get_available_configurations()
    
    return render_template(
        'playground.html',
        frameworks=configs['frameworks'],
        models=configs['models'],
        vectorstores=configs['vector_stores'],
        selected_fw=configs['frameworks'][0] if configs['frameworks'] else '',
        selected_m=configs['models'][0] if configs['models'] else '',
        selected_vs=configs['vector_stores'][0] if configs['vector_stores'] else '',
        prompt_text='',
        response=None
    )

@web_bp.route('/generate', methods=['POST'])
def generate():
    """Handle form submission with enhanced logging"""
    try:
        # Get form data
        framework = request.form.get('framework')
        model = request.form.get('model')
        vector_store = request.form.get('vector_store')
        query = request.form.get('prompt_text', '').strip()
        
        if not query:
            flash('Please enter a query', 'error')
            return redirect(url_for('web.index'))
        
        # Prepare request data
        request_data = {
            'framework': framework,
            'model': model,
            'vector_store': vector_store,
            'query': query
        }
        
        # Execute query with enhanced logging
        result = enhanced_agent_service.execute_query(request_data)
        
        # Get configurations for form
        configs = enhanced_agent_service.get_available_configurations()
        
        return render_template(
            'playground.html',
            frameworks=configs['frameworks'],
            models=configs['models'],
            vectorstores=configs['vector_stores'],
            selected_fw=framework,
            selected_m=model,
            selected_vs=vector_store,
            prompt_text=query,
            response=result['answer'],
            trace_id=result.get('trace_id'),
            duration=result.get('duration', 0),
            tokens_used=result.get('tokens_used', 0),
            input_tokens=result.get('input_tokens', 0),
            output_tokens=result.get('output_tokens', 0),
            cost_usd=result.get('cost_usd', 0.0),
            cpu_usage_change=result.get('cpu_usage_change', 0),
            memory_usage_change=result.get('memory_usage_change', 0),
            status=result.get('status', 'unknown')
        )
        
    except Exception as e:
        logger.error("Web generate error", error=str(e))
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.route('/traces')
def traces():
    """Traces page"""
    traces = tracing_manager.get_all_traces()
    return render_template('traces.html', traces=traces)

@web_bp.route('/traces/<trace_id>')
def trace_detail(trace_id):
    """Trace detail page"""
    trace = tracing_manager.get_trace(trace_id)
    if not trace:
        flash('Trace not found', 'error')
        return redirect(url_for('web.traces'))
    
    return render_template('trace_detail.html', trace=trace)

@web_bp.route('/metrics')
def metrics():
    """Enhanced metrics page with real-time data"""
    try:
        # Get real-time metrics
        real_time_metrics = enhanced_metrics_service.get_real_time_metrics(24)
        
        # Get enhanced metrics for backward compatibility
        enhanced_metrics = enhanced_metrics_service.get_enhanced_metrics(7)
        
        configs = enhanced_agent_service.get_available_configurations()
        
        return render_template(
            'enhanced_metrics.html',
            real_time_metrics=real_time_metrics,
            enhanced_metrics=enhanced_metrics,
            frameworks=configs['frameworks'],
            models=configs['models'],
            vectorstores=configs['vector_stores']
        )
    except Exception as e:
        logger.error("Web metrics error", error=str(e))
        flash(f'Error loading metrics: {str(e)}', 'error')
        
        # Fallback to basic metrics page
        configs = enhanced_agent_service.get_available_configurations()
        fallback_metrics = {
            'total_requests': 0,
            'success_rate': 0,
            'average_duration': 0,
            'total_tokens_used': 0,
            'active_requests': 0
        }
        
        return render_template(
            'metrics.html',
            metrics=fallback_metrics,
            frameworks=configs['frameworks'],
            models=configs['models'],
            vectorstores=configs['vector_stores']
        )

@web_bp.route('/logs')
def logs():
    """System logs and application logs page"""
    return render_template('app_logs.html')

@web_bp.route('/real-time-dashboard')
def real_time_dashboard():
    """Real-time dashboard page"""
    try:
        # Get current real-time metrics
        metrics = enhanced_metrics_service.get_real_time_metrics(24)
        configs = enhanced_agent_service.get_available_configurations()
        
        return render_template(
            'real_time_dashboard.html',
            metrics=metrics,
            frameworks=configs['frameworks'],
            models=configs['models'],
            vectorstores=configs['vector_stores']
        )
    except Exception as e:
        logger.error("Real-time dashboard error", error=str(e))
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('web.metrics'))