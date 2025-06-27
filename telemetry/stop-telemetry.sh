#!/bin/bash

# Site24x7 Telemetry Services Shutdown Script

set -e

echo "🛑 Stopping Site24x7 Telemetry Services..."

# Stop telemetry services
docker-compose -f docker-compose.telemetry.yml down

echo "✅ Telemetry services stopped successfully!"