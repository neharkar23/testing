import asyncio
import aiohttp
import psutil
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import structlog
from config.settings import settings

logger = structlog.get_logger()

@dataclass
class AppLogEntry:
    timestamp: str
    level: str
    service: str
    trace_id: str
    framework: str
    model: str
    input_query: str
    output_response: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    cpu_percent: float
    memory_percent: float
    status: str
    error_message: Optional[str] = None

@dataclass
class CPUMetric:
    timestamp: int
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int

class Site24x7Service:
    def __init__(self):
        self.api_key = "in_24be7e829d6ca9b6dd72ca278c32e2bf"
        self.app_key = "e5b0f39bd1c6a990b6ca6ef78104bff7"
        self.license_key = "in_24be7e829d6ca9b6dd72ca278c32e2bf"
        
        # Site24x7 endpoints
        self.metrics_endpoint = f"https://plusinsight.site24x7.in/metrics/v2/data?app.key={self.app_key}&license.key={self.license_key}"
        self.logs_endpoint = f"https://logs.site24x7.com/v1/logs"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        
        # Local storage for displaying in app
        self.recent_logs: List[AppLogEntry] = []
        self.max_logs = 1000
        
    async def start(self):
        """Start the Site24x7 service"""
        self.running = True
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
        )
        
        # Start background tasks
        asyncio.create_task(self._cpu_monitoring_loop())
        logger.info("Site24x7 service started")
    
    async def stop(self):
        """Stop the Site24x7 service"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Site24x7 service stopped")
    
    async def log_interaction(self, interaction_data: Dict[str, Any]):
        """Log a complete interaction with input/output details"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Create log entry
            log_entry = AppLogEntry(
                timestamp=datetime.utcnow().isoformat(),
                level="INFO",
                service="docker-agent",
                trace_id=interaction_data.get('trace_id', ''),
                framework=interaction_data.get('framework', ''),
                model=interaction_data.get('model', ''),
                input_query=interaction_data.get('input_query', ''),
                output_response=interaction_data.get('output_response', ''),
                input_tokens=interaction_data.get('input_tokens', 0),
                output_tokens=interaction_data.get('output_tokens', 0),
                total_tokens=interaction_data.get('total_tokens', 0),
                latency_ms=interaction_data.get('latency_ms', 0),
                cost_usd=interaction_data.get('cost_usd', 0.0),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                status=interaction_data.get('status', 'completed'),
                error_message=interaction_data.get('error_message')
            )
            
            # Store locally for app display
            self.recent_logs.append(log_entry)
            if len(self.recent_logs) > self.max_logs:
                self.recent_logs.pop(0)
            
            # Send to Site24x7 AppLogs
            await self._send_app_log(log_entry)
            
            # Send metrics to Site24x7
            await self._send_interaction_metrics(log_entry)
            
            logger.info("Interaction logged successfully", trace_id=log_entry.trace_id)
            
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")
    
    async def _send_app_log(self, log_entry: AppLogEntry):
        """Send application log to Site24x7 AppLogs"""
        try:
            log_payload = {
                "timestamp": log_entry.timestamp,
                "level": log_entry.level,
                "message": f"Docker Agent Interaction - {log_entry.framework} - {log_entry.model}",
                "service": log_entry.service,
                "trace_id": log_entry.trace_id,
                "attributes": {
                    "framework": log_entry.framework,
                    "model": log_entry.model,
                    "input_query": log_entry.input_query,
                    "output_response": log_entry.output_response,
                    "input_tokens": log_entry.input_tokens,
                    "output_tokens": log_entry.output_tokens,
                    "total_tokens": log_entry.total_tokens,
                    "latency_ms": log_entry.latency_ms,
                    "cost_usd": log_entry.cost_usd,
                    "cpu_percent": log_entry.cpu_percent,
                    "memory_percent": log_entry.memory_percent,
                    "status": log_entry.status,
                    "error_message": log_entry.error_message
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.api_key,
                'X-License-Key': self.license_key
            }
            
            async with self.session.post(
                self.logs_endpoint,
                json=[log_payload],
                headers=headers
            ) as response:
                if response.status == 200:
                    logger.debug("App log sent to Site24x7 successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send app log: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error sending app log to Site24x7: {e}")
    
    async def _send_interaction_metrics(self, log_entry: AppLogEntry):
        """Send interaction metrics to Site24x7"""
        try:
            timestamp = int(time.time() * 1000)
            
            metrics = [
                {
                    "metric_name": "docker_agent_interaction_latency",
                    "value": log_entry.latency_ms,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "framework": log_entry.framework,
                        "model": log_entry.model,
                        "status": log_entry.status
                    }
                },
                {
                    "metric_name": "docker_agent_token_usage",
                    "value": log_entry.total_tokens,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "framework": log_entry.framework,
                        "model": log_entry.model,
                        "token_type": "total"
                    }
                },
                {
                    "metric_name": "docker_agent_input_tokens",
                    "value": log_entry.input_tokens,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "framework": log_entry.framework,
                        "model": log_entry.model,
                        "token_type": "input"
                    }
                },
                {
                    "metric_name": "docker_agent_output_tokens",
                    "value": log_entry.output_tokens,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "framework": log_entry.framework,
                        "model": log_entry.model,
                        "token_type": "output"
                    }
                },
                {
                    "metric_name": "docker_agent_cost",
                    "value": log_entry.cost_usd,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "framework": log_entry.framework,
                        "model": log_entry.model
                    }
                },
                {
                    "metric_name": "docker_agent_cpu_usage",
                    "value": log_entry.cpu_percent,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "service": "docker-agent"
                    }
                },
                {
                    "metric_name": "docker_agent_memory_usage",
                    "value": log_entry.memory_percent,
                    "count": 1,
                    "time_stamp": timestamp,
                    "tags": {
                        "service": "docker-agent"
                    }
                }
            ]
            
            async with self.session.post(
                self.metrics_endpoint,
                json=metrics
            ) as response:
                if response.status == 200:
                    logger.debug("Interaction metrics sent to Site24x7 successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send metrics: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error sending metrics to Site24x7: {e}")
    
    async def _cpu_monitoring_loop(self):
        """Continuous CPU and system monitoring"""
        while self.running:
            try:
                await self._collect_and_send_system_metrics()
                await asyncio.sleep(30)  # Send system metrics every 30 seconds
            except Exception as e:
                logger.error(f"CPU monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _collect_and_send_system_metrics(self):
        """Collect and send system metrics"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            cpu_metric = CPUMetric(
                timestamp=int(time.time() * 1000),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_total_mb=memory.total / (1024 * 1024),
                disk_usage_percent=disk.percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv
            )
            
            # Send to Site24x7
            await self._send_system_metrics(cpu_metric)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    async def _send_system_metrics(self, cpu_metric: CPUMetric):
        """Send system metrics to Site24x7"""
        try:
            metrics = [
                {
                    "metric_name": "system_cpu_percent",
                    "value": cpu_metric.cpu_percent,
                    "count": 1,
                    "time_stamp": cpu_metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system"}
                },
                {
                    "metric_name": "system_memory_percent",
                    "value": cpu_metric.memory_percent,
                    "count": 1,
                    "time_stamp": cpu_metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system"}
                },
                {
                    "metric_name": "system_memory_used_mb",
                    "value": cpu_metric.memory_used_mb,
                    "count": 1,
                    "time_stamp": cpu_metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system"}
                },
                {
                    "metric_name": "system_disk_usage_percent",
                    "value": cpu_metric.disk_usage_percent,
                    "count": 1,
                    "time_stamp": cpu_metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system"}
                },
                {
                    "metric_name": "system_network_bytes_sent",
                    "value": cpu_metric.network_bytes_sent,
                    "count": 1,
                    "time_stamp": cpu_metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system"}
                },
                {
                    "metric_name": "system_network_bytes_recv",
                    "value": cpu_metric.network_bytes_recv,
                    "count": 1,
                    "time_stamp": cpu_metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system"}
                }
            ]
            
            async with self.session.post(
                self.metrics_endpoint,
                json=metrics
            ) as response:
                if response.status == 200:
                    logger.debug("System metrics sent to Site24x7 successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send system metrics: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error sending system metrics to Site24x7: {e}")
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent logs for display in the application"""
        return [asdict(log) for log in self.recent_logs[-limit:]]
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get current system information"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used / (1024**3),
                "disk_total_gb": disk.total / (1024**3),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}

# Global service instance
site24x7_service = Site24x7Service()