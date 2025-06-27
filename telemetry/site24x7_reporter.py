import asyncio
import time
import logging
import statistics
from typing import Dict, List, Optional
import aiohttp
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

# Logger config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROMETHEUS_METRICS_URL = "http://host.docker.internal:8001/metrics"  # For Docker access to host

@dataclass
class MetricData:
    metric_name: str
    value: float
    count: int
    time_stamp: int
    tags: Dict[str, str]
    p0: Optional[float] = None
    p50: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None
    p100: Optional[float] = None

class Site24x7Reporter:
    def __init__(self):
        self.api_key = os.getenv('SITE24X7_API_KEY', 'in_24be7e829d6ca9b6dd72ca278c32e2bf')
        self.app_key = os.getenv('SITE24X7_APP_KEY', 'e5b0f39bd1c6a990b6ca6ef78104bff7')
        self.license_key = os.getenv('SITE24X7_LICENSE_KEY', self.api_key)

        self.endpoint = f"https://plusinsight.site24x7.in/metrics/v2/data?app.key={self.app_key}&license.key={self.license_key}"
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'Content-Type': 'application/json'}
        )
        logger.info("Site24x7 Reporter started")
        await self._reporting_loop()

    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("Site24x7 Reporter stopped")

    async def _reporting_loop(self):
        while self.running:
            try:
                await self._collect_and_send_metrics()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Reporting loop error: {e}")
                await asyncio.sleep(30)

    async def _collect_and_send_metrics(self):
        try:
            metrics = await self._collect_metrics_from_prometheus()
            if metrics:
                await self._send_metrics_to_site24x7(metrics)
        except Exception as e:
            logger.error(f"Collection/Sending error: {e}")

    async def _collect_metrics_from_prometheus(self) -> List[MetricData]:
        try:
            async with self.session.get(PROMETHEUS_METRICS_URL) as response:
                if response.status != 200:
                    logger.error(f"Prometheus returned status {response.status}")
                    return []

                raw_metrics = await response.text()
                return self._parse_prometheus_metrics(raw_metrics)

        except Exception as e:
            logger.error(f"Failed to fetch Prometheus metrics: {e}")
            return []

    def _parse_prometheus_metrics(self, raw: str) -> List[MetricData]:
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

                result.append(MetricData(
                    metric_name=metric_name,
                    value=float(value),
                    count=1,
                    time_stamp=current_timestamp,
                    tags=tags
                ))
            except Exception as e:
                logger.warning(f"Skipping malformed line: {line} ({e})")
        return result

    async def _send_metrics_to_site24x7(self, metrics: List[MetricData]):
        if not self.session:
            logger.error("Session not initialized")
            return

        payload = []
        for metric in metrics:
            data = {
                "metric_name": metric.metric_name,
                "value": metric.value,
                "count": metric.count,
                "time_stamp": metric.time_stamp,
                "tags": metric.tags
            }
            if metric.p0 is not None:
                data.update({
                    "p0": metric.p0, "p50": metric.p50,
                    "p95": metric.p95, "p99": metric.p99, "p100": metric.p100
                })
            payload.append(data)

        try:
            async with self.session.post(self.endpoint, json=payload) as resp:
                if resp.status == 200:
                    logger.info(f"Sent {len(metrics)} metrics to Site24x7")
                else:
                    err_text = await resp.text()
                    logger.error(f"Failed to send: {resp.status}, {err_text}")
        except Exception as e:
            logger.error(f"HTTP error: {e}")

async def main():
    reporter = Site24x7Reporter()
    try:
        await reporter.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await reporter.stop()

if __name__ == "__main__":
    asyncio.run(main())