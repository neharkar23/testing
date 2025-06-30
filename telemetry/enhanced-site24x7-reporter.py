#!/usr/bin/env python3
"""
Enhanced Site24x7 Reporter with Input/Output Logging and CPU Monitoring
This script collects comprehensive application logs and system metrics for Site24x7
"""

import asyncio
import time
import logging
import statistics
import psutil
import sqlite3
from typing import Dict, List, Optional
import aiohttp
from dataclasses import dataclass
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Logger config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AppLogData:
    timestamp: str
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
class SystemMetric:
    timestamp: int
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int

class EnhancedSite24x7Reporter:
    def __init__(self):
        self.api_key = os.getenv('SITE24X7_API_KEY', 'in_24be7e829d6ca9b6dd72ca278c32e2bf')
        self.app_key = os.getenv('SITE24X7_APP_KEY', 'e5b0f39bd1c6a990b6ca6ef78104bff7')
        self.license_key = os.getenv('SITE24X7_LICENSE_KEY', self.api_key)

        # Site24x7 endpoints
        self.metrics_endpoint = f"https://plusinsight.site24x7.in/metrics/v2/data?app.key={self.app_key}&license.key={self.license_key}"
        self.logs_endpoint = f"https://logs.site24x7.com/v1/logs"
        
        # Local database for reading application logs
        self.db_path = "/app/metrics.db"  # Docker volume mount
        self.prometheus_url = "http://host.docker.internal:8001/metrics"
        
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'Content-Type': 'application/json'}
        )
        logger.info("Enhanced Site24x7 Reporter started")
        await self._reporting_loop()

    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Enhanced Site24x7 Reporter stopped")

    async def _reporting_loop(self):
        while self.running:
            try:
                # Collect and send different types of data
                await asyncio.gather(
                    self._collect_and_send_app_logs(),
                    self._collect_and_send_system_metrics(),
                    self._collect_and_send_prometheus_metrics()
                )
                await asyncio.sleep(30)  # Report every 30 seconds
            except Exception as e:
                logger.error(f"Reporting loop error: {e}")
                await asyncio.sleep(60)

    async def _collect_and_send_app_logs(self):
        """Collect application logs from SQLite database and send to Site24x7"""
        try:
            if not os.path.exists(self.db_path):
                logger.warning(f"Database not found: {self.db_path}")
                return

            # Get recent logs from database
            logs = self._get_recent_logs_from_db()
            
            if logs:
                await self._send_app_logs_to_site24x7(logs)
                logger.info(f"Sent {len(logs)} application logs to Site24x7")
            
        except Exception as e:
            logger.error(f"Failed to collect app logs: {e}")

    def _get_recent_logs_from_db(self, minutes: int = 5) -> List[AppLogData]:
        """Get recent logs from SQLite database"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM metrics 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (cutoff_time.isoformat(),))
                
                rows = cursor.fetchall()
                
                logs = []
                for row in rows:
                    log = AppLogData(
                        timestamp=row['timestamp'],
                        trace_id=row['trace_id'],
                        framework=row['framework'],
                        model=row['model'],
                        input_query="",  # Would need to be added to DB schema
                        output_response="",  # Would need to be added to DB schema
                        input_tokens=row['input_tokens'],
                        output_tokens=row['output_tokens'],
                        total_tokens=row['total_tokens'],
                        latency_ms=row['latency_ms'],
                        cost_usd=row['total_cost'],
                        cpu_percent=0,  # Would need to be added to DB schema
                        memory_percent=0,  # Would need to be added to DB schema
                        status=row['status'],
                        error_message=row.get('error_message')
                    )
                    logs.append(log)
                
                return logs
                
        except Exception as e:
            logger.error(f"Failed to read from database: {e}")
            return []

    async def _send_app_logs_to_site24x7(self, logs: List[AppLogData]):
        """Send application logs to Site24x7 AppLogs"""
        try:
            log_entries = []
            
            for log in logs:
                log_entry = {
                    "timestamp": log.timestamp,
                    "level": "INFO" if log.status == "completed" else "ERROR",
                    "message": f"Docker Agent Interaction - {log.framework} - {log.model}",
                    "service": "docker-agent",
                    "trace_id": log.trace_id,
                    "attributes": {
                        "framework": log.framework,
                        "model": log.model,
                        "input_query": log.input_query,
                        "output_response": log.output_response,
                        "input_tokens": log.input_tokens,
                        "output_tokens": log.output_tokens,
                        "total_tokens": log.total_tokens,
                        "latency_ms": log.latency_ms,
                        "cost_usd": log.cost_usd,
                        "cpu_percent": log.cpu_percent,
                        "memory_percent": log.memory_percent,
                        "status": log.status,
                        "error_message": log.error_message
                    }
                }
                log_entries.append(log_entry)
            
            if log_entries:
                headers = {
                    'Content-Type': 'application/json',
                    'X-API-Key': self.api_key,
                    'X-License-Key': self.license_key
                }
                
                async with self.session.post(
                    self.logs_endpoint,
                    json=log_entries,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.debug("App logs sent to Site24x7 successfully")
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send app logs: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"Error sending app logs to Site24x7: {e}")

    async def _collect_and_send_system_metrics(self):
        """Collect and send system metrics"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            system_metric = SystemMetric(
                timestamp=int(time.time() * 1000),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                memory_total_mb=memory.total / (1024 * 1024),
                disk_usage_percent=disk.percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv
            )
            
            await self._send_system_metrics_to_site24x7(system_metric)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    async def _send_system_metrics_to_site24x7(self, metric: SystemMetric):
        """Send system metrics to Site24x7"""
        try:
            metrics = [
                {
                    "metric_name": "docker_agent_system_cpu_percent",
                    "value": metric.cpu_percent,
                    "count": 1,
                    "time_stamp": metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system", "component": "cpu"}
                },
                {
                    "metric_name": "docker_agent_system_memory_percent",
                    "value": metric.memory_percent,
                    "count": 1,
                    "time_stamp": metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system", "component": "memory"}
                },
                {
                    "metric_name": "docker_agent_system_memory_used_mb",
                    "value": metric.memory_used_mb,
                    "count": 1,
                    "time_stamp": metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system", "component": "memory"}
                },
                {
                    "metric_name": "docker_agent_system_disk_usage_percent",
                    "value": metric.disk_usage_percent,
                    "count": 1,
                    "time_stamp": metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system", "component": "disk"}
                },
                {
                    "metric_name": "docker_agent_system_network_bytes_sent",
                    "value": metric.network_bytes_sent,
                    "count": 1,
                    "time_stamp": metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system", "component": "network"}
                },
                {
                    "metric_name": "docker_agent_system_network_bytes_recv",
                    "value": metric.network_bytes_recv,
                    "count": 1,
                    "time_stamp": metric.timestamp,
                    "tags": {"service": "docker-agent", "type": "system", "component": "network"}
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

    async def _collect_and_send_prometheus_metrics(self):
        """Collect metrics from Prometheus and send to Site24x7"""
        try:
            async with self.session.get(self.prometheus_url) as response:
                if response.status != 200:
                    logger.error(f"Prometheus returned status {response.status}")
                    return

                raw_metrics = await response.text()
                parsed_metrics = self._parse_prometheus_metrics(raw_metrics)
                
                if parsed_metrics:
                    await self._send_prometheus_metrics_to_site24x7(parsed_metrics)

        except Exception as e:
            logger.error(f"Failed to collect Prometheus metrics: {e}")

    def _parse_prometheus_metrics(self, raw: str) -> List[Dict]:
        """Parse Prometheus metrics"""
        result = []
        current_timestamp = int(time.time() * 1000)

        for line in raw.splitlines():
            if line.startswith("#") or line.strip() == "":
                continue
            if "docker_agent_" not in line:
                continue

            try:
                if "{" in line:
                    metric_part, value_str = line.split("} ")
                    tags_str = metric_part.split("{")[1]
                    metric_name = metric_part.split("{")[0]
                    value = float(value_str.strip())
                    tags = dict(tag.split("=") for tag in tags_str.split(","))
                    tags = {k: v.strip('"') for k, v in tags.items()}
                else:
                    metric_name, value = line.strip().split()
                    tags = {}

                result.append({
                    "metric_name": metric_name,
                    "value": float(value),
                    "count": 1,
                    "time_stamp": current_timestamp,
                    "tags": {**tags, "source": "prometheus"}
                })
            except Exception as e:
                logger.warning(f"Skipping malformed line: {line} ({e})")
        return result

    async def _send_prometheus_metrics_to_site24x7(self, metrics: List[Dict]):
        """Send Prometheus metrics to Site24x7"""
        try:
            async with self.session.post(
                self.metrics_endpoint,
                json=metrics
            ) as response:
                if response.status == 200:
                    logger.debug(f"Sent {len(metrics)} Prometheus metrics to Site24x7")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send Prometheus metrics: {response.status} - {error_text}")
        except Exception as e:
            logger.error(f"HTTP error sending Prometheus metrics: {e}")

async def main():
    reporter = EnhancedSite24x7Reporter()
    try:
        await reporter.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await reporter.stop()

if __name__ == "__main__":
    asyncio.run(main())