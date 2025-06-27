#!/usr/bin/env python3
"""
Site24x7 Telemetry Verification Script
This script verifies that telemetry data is being sent to Site24x7
"""

import asyncio
import aiohttp
import json
import time
import os
from datetime import datetime

async def verify_otel_collector():
    """Verify OpenTelemetry Collector is running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8888/metrics') as response:
                if response.status == 200:
                    print("✅ OpenTelemetry Collector is running and exposing metrics")
                    return True
                else:
                    print(f"❌ OpenTelemetry Collector metrics endpoint returned {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Failed to connect to OpenTelemetry Collector: {e}")
        return False

async def verify_otlp_endpoints():
    """Verify OTLP endpoints are accessible"""
    endpoints = [
        ("OTLP gRPC", "localhost:4317"),
        ("OTLP HTTP", "localhost:4318")
    ]
    
    results = []
    for name, endpoint in endpoints:
        try:
            # For HTTP endpoint, try a simple connection
            if "4318" in endpoint:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f'http://{endpoint}/v1/traces', 
                                          json={"test": "connection"}) as response:
                        print(f"✅ {name} endpoint is accessible")
                        results.append(True)
            else:
                # For gRPC, just check if port is open
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', 4317))
                sock.close()
                if result == 0:
                    print(f"✅ {name} endpoint is accessible")
                    results.append(True)
                else:
                    print(f"❌ {name} endpoint is not accessible")
                    results.append(False)
        except Exception as e:
            print(f"❌ Failed to verify {name} endpoint: {e}")
            results.append(False)
    
    return all(results)

async def send_test_metric_to_site24x7():
    """Send a test metric to Site24x7 to verify the pipeline"""
    endpoint = "https://plusinsight.site24x7.in/metrics/v2/data?app.key=e5b0f39bd1c6a990b6ca6ef78104bff7&license.key=in_24be7e829d6ca9b6dd72ca278c32e2bf"
    
    test_metric = {
        "metric_name": "telemetry_verification_test",
        "value": 1.0,
        "count": 1,
        "time_stamp": int(time.time() * 1000),
        "tags": {
            "service": "docker-agent",
            "test": "verification",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=[test_metric]) as response:
                if response.status == 200:
                    print("✅ Successfully sent test metric to Site24x7")
                    return True
                else:
                    response_text = await response.text()
                    print(f"❌ Failed to send test metric to Site24x7. Status: {response.status}")
                    print(f"Response: {response_text}")
                    return False
    except Exception as e:
        print(f"❌ Error sending test metric to Site24x7: {e}")
        return False

async def verify_site24x7_reporter():
    """Check if Site24x7 reporter container is running"""
    try:
        import subprocess
        result = subprocess.run(['docker', 'ps', '--filter', 'name=site24x7-reporter', '--format', 'table {{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True)
        
        if 'site24x7-reporter' in result.stdout and 'Up' in result.stdout:
            print("✅ Site24x7 Reporter container is running")
            return True
        else:
            print("❌ Site24x7 Reporter container is not running")
            return False
    except Exception as e:
        print(f"❌ Error checking Site24x7 Reporter: {e}")
        return False

async def main():
    """Main verification function"""
    print("🔍 Verifying Site24x7 Telemetry Integration...")
    print("=" * 50)
    
    # Check all components
    checks = [
        ("OpenTelemetry Collector", verify_otel_collector()),
        ("OTLP Endpoints", verify_otlp_endpoints()),
        ("Site24x7 Reporter", verify_site24x7_reporter()),
        ("Site24x7 API Connection", send_test_metric_to_site24x7())
    ]
    
    results = []
    for name, check in checks:
        print(f"\n📋 Checking {name}...")
        result = await check
        results.append(result)
    
    print("\n" + "=" * 50)
    print("📊 Verification Summary:")
    
    all_passed = all(results)
    if all_passed:
        print("🎉 All telemetry components are working correctly!")
        print("\n📈 Next steps:")
        print("1. Check Site24x7 dashboard for incoming data")
        print("2. Generate some application traffic to see metrics")
        print("3. Monitor the telemetry logs for any issues")
    else:
        print("⚠️  Some components need attention. Please check the logs above.")
        print("\n🔧 Troubleshooting:")
        print("1. Ensure Docker services are running: docker-compose -f telemetry/docker-compose.telemetry.yml ps")
        print("2. Check logs: docker-compose -f telemetry/docker-compose.telemetry.yml logs")
        print("3. Verify environment variables are set correctly")
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)