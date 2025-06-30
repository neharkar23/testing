from typing import Dict, Any, Optional
from core.registry import registry
from core.tracing import tracing_manager
from config.settings import settings
from .enhanced_metrics_service import enhanced_metrics_service
from .site24x7_service import site24x7_service
import structlog
import time
import asyncio
import psutil

logger = structlog.get_logger()

class EnhancedAgentService:
    """Enhanced Agent Service with Site24x7 integration"""
    
    def __init__(self):
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize and register all components"""
        from adapters import (
            LangGraphAdapter, LlamaIndexAdapter, 
            DSPyAdapter, AutoGenAdapter
        )
        
        registry.register_framework(LangGraphAdapter)
        registry.register_framework(LlamaIndexAdapter)
        registry.register_framework(DSPyAdapter)
        registry.register_framework(AutoGenAdapter)
    
    def execute_query(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a query with comprehensive logging and monitoring"""
        trace_id = tracing_manager.start_trace(request_data)
        start_time = time.time()
        
        # Capture initial system state
        initial_cpu = psutil.cpu_percent()
        initial_memory = psutil.virtual_memory().percent
        
        try:
            # Get framework adapter
            framework_name = request_data.get('framework', '').lower()
            adapter = registry.get_framework(framework_name)
            
            tracing_manager.add_step(trace_id, 'framework_initialization', {
                'framework': framework_name,
                'adapter_class': adapter.__class__.__name__
            })
            
            # Create agent
            agent_config = {
                'model': request_data.get('model'),
                'vector_store': request_data.get('vector_store'),
                'query': request_data.get('query')
            }
            
            agent = adapter.create_agent(agent_config)
            
            tracing_manager.add_step(trace_id, 'agent_creation', {
                'config': agent_config,
                'agent_type': type(agent).__name__
            })
            
            # Execute query
            query = request_data.get('query', '')
            result = adapter.execute_query(agent, query)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Capture final system state
            final_cpu = psutil.cpu_percent()
            final_memory = psutil.virtual_memory().percent
            
            tracing_manager.add_step(trace_id, 'query_execution', {
                'query_length': len(query),
                'response_length': len(result.get('answer', '')),
                'duration': result.get('duration', duration),
                'tokens': result.get('tokens_used', 0),
                'status': result.get('status', 'unknown'),
                'cpu_usage_change': final_cpu - initial_cpu,
                'memory_usage_change': final_memory - initial_memory
            })
            
            # Clean response
            cleaned_response = self._clean_response(result.get('answer', ''))
            
            # Calculate token costs
            model = request_data.get('model', 'gpt-4o-mini')
            input_tokens = self._estimate_input_tokens(query)
            output_tokens = self._estimate_output_tokens(cleaned_response)
            total_tokens = input_tokens + output_tokens
            cost_usd = self._calculate_cost(model, input_tokens, output_tokens)
            
            # Prepare comprehensive interaction data
            interaction_data = {
                'trace_id': trace_id,
                'framework': framework_name,
                'model': model,
                'vector_store': request_data.get('vector_store'),
                'input_query': query,
                'output_response': cleaned_response,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'latency_ms': duration * 1000,
                'cost_usd': cost_usd,
                'status': 'completed',
                'cpu_usage_change': final_cpu - initial_cpu,
                'memory_usage_change': final_memory - initial_memory
            }
            
            # Record metrics
            try:
                metrics_data = {
                    'trace_id': trace_id,
                    'framework': framework_name,
                    'model': model,
                    'vector_store': request_data.get('vector_store'),
                    'query': query,
                    'response': cleaned_response,
                    'duration': duration,
                    'tokens_used': total_tokens,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'status': 'completed'
                }
                
                enhanced_metrics_service.record_trace_metrics(metrics_data)
                
                # Log to Site24x7 asynchronously
                asyncio.create_task(site24x7_service.log_interaction(interaction_data))
                
                logger.info(
                    "Interaction logged successfully",
                    trace_id=trace_id,
                    tokens=total_tokens,
                    cost=cost_usd,
                    cpu_change=final_cpu - initial_cpu
                )
            except Exception as e:
                logger.error(f"Failed to record metrics: {e}", trace_id=trace_id)
            
            final_result = {
                'answer': cleaned_response,
                'trace_id': trace_id,
                'framework': framework_name,
                'model': model,
                'vector_store': request_data.get('vector_store'),
                'duration': duration,
                'tokens_used': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': cost_usd,
                'cpu_usage_change': final_cpu - initial_cpu,
                'memory_usage_change': final_memory - initial_memory,
                'status': 'success'
            }
            
            tracing_manager.end_trace(trace_id, 'completed')
            
            logger.info(
                "Query executed successfully",
                trace_id=trace_id,
                framework=framework_name,
                duration=duration,
                cost=cost_usd
            )
            
            return final_result
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            # Record failed interaction
            interaction_data = {
                'trace_id': trace_id,
                'framework': request_data.get('framework', 'unknown'),
                'model': request_data.get('model', 'unknown'),
                'vector_store': request_data.get('vector_store', 'unknown'),
                'input_query': request_data.get('query', ''),
                'output_response': '',
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'latency_ms': duration * 1000,
                'cost_usd': 0.0,
                'status': 'failed',
                'error_message': str(e)
            }
            
            try:
                # Record failed metrics
                metrics_data = {
                    'trace_id': trace_id,
                    'framework': request_data.get('framework', 'unknown'),
                    'model': request_data.get('model', 'unknown'),
                    'vector_store': request_data.get('vector_store', 'unknown'),
                    'query': request_data.get('query', ''),
                    'response': '',
                    'duration': duration,
                    'tokens_used': 0,
                    'status': 'failed',
                    'error': str(e)
                }
                
                enhanced_metrics_service.record_trace_metrics(metrics_data)
                
                # Log failed interaction to Site24x7
                asyncio.create_task(site24x7_service.log_interaction(interaction_data))
                
            except Exception as metrics_error:
                logger.error(f"Failed to record error metrics: {metrics_error}")
            
            tracing_manager.end_trace(trace_id, 'failed', str(e))
            
            logger.error(
                "Query execution failed",
                trace_id=trace_id,
                error=str(e),
                framework=request_data.get('framework')
            )
            
            return {
                'answer': f"❌ Error: {str(e)}",
                'trace_id': trace_id,
                'framework': request_data.get('framework'),
                'model': request_data.get('model'),
                'vector_store': request_data.get('vector_store'),
                'duration': duration,
                'tokens_used': 0,
                'cost_usd': 0.0,
                'status': 'error',
                'error': str(e)
            }
    
    def _clean_response(self, text: str) -> str:
        """Clean and format the response"""
        if not text:
            return "No response generated."
        
        # Remove query repetition
        if text.startswith("Here"):
            start_index = text.find("Here")
            if start_index != -1:
                text = text[start_index:].strip()
        
        return text.strip()
    
    def _estimate_input_tokens(self, text: str) -> int:
        """Estimate input tokens (rough approximation)"""
        return max(1, len(text.split()) * 1.3)
    
    def _estimate_output_tokens(self, text: str) -> int:
        """Estimate output tokens (rough approximation)"""
        return max(1, len(text.split()) * 1.3)
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model and token usage"""
        # Token costs per 1K tokens
        token_costs = {
            'gpt-4o': {'input': 0.005, 'output': 0.015},
            'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
            'gpt-3.5-turbo': {'input': 0.0015, 'output': 0.002},
            'llama3-8b-8192': {'input': 0.0005, 'output': 0.0008},
            'gemma2-9b-it': {'input': 0.0002, 'output': 0.0002},
            'llama-3.3-70b-versatile': {'input': 0.0009, 'output': 0.0009},
            'gemini-2.0-flash': {'input': 0.00075, 'output': 0.003}
        }
        
        pricing = token_costs.get(model, token_costs['gpt-4o-mini'])
        input_cost = (input_tokens / 1000) * pricing['input']
        output_cost = (output_tokens / 1000) * pricing['output']
        
        return round(input_cost + output_cost, 6)
    
    def get_available_configurations(self) -> Dict[str, Any]:
        """Get all available configurations"""
        return {
            'frameworks': registry.get_available_frameworks(),
            'models': settings.MODELS,
            'vector_stores': settings.VECTORSTORES
        }

# Global enhanced service instance
enhanced_agent_service = EnhancedAgentService()