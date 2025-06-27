#!/bin/bash

# Site24x7 Telemetry Services Startup Script
# This script starts both OpenTelemetry Collector and Site24x7 Reporter

set -e

echo "🚀 Starting Site24x7 Telemetry Services..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Set environment variables
export OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.site24x7rum.in
export OTEL_EXPORTER_OTLP_HEADERS="api-key=in_24be7e829d6ca9b6dd72ca278c32e2bf"
export OTEL_SERVICE_NAME=docker-agent
export OTEL_RESOURCE_ATTRIBUTES="service.name=docker-agent,service.version=1.0.0"

echo "📊 Environment variables set for OpenTelemetry"

# Start telemetry services
echo "🔄 Starting OpenTelemetry Collector and Site24x7 Reporter..."
docker-compose -f docker-compose.telemetry.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if docker-compose -f docker-compose.telemetry.yml ps | grep -q "Up"; then
    echo "✅ Telemetry services started successfully!"
    echo ""
    echo "📈 Services running:"
    echo "  - OpenTelemetry Collector: http://localhost:8888/metrics"
    echo "  - OTLP gRPC Receiver: localhost:4317"
    echo "  - OTLP HTTP Receiver: localhost:4318"
    echo "  - Site24x7 Reporter: Background service"
    echo ""
    echo "🔍 To check logs:"
    echo "  docker-compose -f docker-compose.telemetry.yml logs -f"
    echo ""
    echo "🛑 To stop services:"
    echo "  docker-compose -f docker-compose.telemetry.yml down"
else
    echo "❌ Failed to start telemetry services"
    docker-compose -f docker-compose.telemetry.yml logs
    exit 1
fi