from flask import Flask
from config.settings import settings
from core.tracing import tracing_manager
from routes.web import web_bp
from routes.api import api_bp
from routes.site24x7_api import site24x7_bp
from services.site24x7_service import site24x7_service
import structlog
import os
import asyncio
import threading

# Configure logging
logger = structlog.get_logger()

def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = settings.DEBUG
    
    # Register blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(site24x7_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return "Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error", error=str(error))
        return "Internal server error", 500
    
    # Health check
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'docker-agent'}
    
    logger.info("Flask application created successfully")
    return app

def start_site24x7_service():
    """Start Site24x7 service in background thread"""
    def run_async_service():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(site24x7_service.start())
    
    thread = threading.Thread(target=run_async_service, daemon=True)
    thread.start()
    logger.info("Site24x7 service started in background thread")

if __name__ == '__main__':
    app = create_app()
    
    # Start Site24x7 service
    start_site24x7_service()
    
    logger.info(
        "Starting Docker Agent application with Site24x7 integration",
        host=settings.HOST,
        port=settings.PORT,
        debug=settings.DEBUG
    )
    
    app.run(
        host=settings.HOST,
        port=settings.PORT,
        debug=settings.DEBUG
    )