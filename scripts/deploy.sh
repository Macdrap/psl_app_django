#!/bin/bash

# PSL Workflow System - Deployment Script
# This script deploys the application to AWS EC2

set -e  # Exit on error

echo "========================================="
echo "PSL Workflow System - Deployment"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Get project root (parent of scripts folder)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found at $PROJECT_ROOT/.env"
    exit 1
fi

print_success ".env file found"

# Stop existing containers
echo ""
echo "Stopping existing containers..."
docker-compose --env-file .env -f docker/docker-compose.prod.yml down
print_success "Containers stopped"

# Remove old images to force clean rebuild
echo ""
echo "Cleaning up old images..."
docker-compose --env-file .env -f docker/docker-compose.prod.yml down --rmi local 2>/dev/null || true
print_success "Cleanup completed"

# Build new images (no cache to ensure fresh build)
echo ""
echo "Building Docker images (this may take a few minutes)..."
docker-compose --env-file .env -f docker/docker-compose.prod.yml build --no-cache
print_success "Images built"

# Start containers
echo ""
echo "Starting containers..."
docker-compose --env-file .env -f docker/docker-compose.prod.yml up -d
print_success "Containers started"

# Wait for services to be ready
echo ""
echo "Waiting for services to initialize..."
sleep 15
print_success "Services initialized"

# Run migrations
echo ""
echo "Running database migrations..."
docker-compose --env-file .env -f docker/docker-compose.prod.yml exec -T web python manage.py migrate --noinput
print_success "Migrations completed"

# Collect static files
echo ""
echo "Collecting static files..."
docker-compose --env-file .env -f docker/docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput --clear
print_success "Static files collected"

# Show running containers
echo ""
echo "Running containers:"
docker-compose --env-file .env -f docker/docker-compose.prod.yml ps

# Show logs
echo ""
echo "Recent logs:"
docker-compose --env-file .env -f docker/docker-compose.prod.yml logs --tail=50

echo ""
echo "========================================="
print_success "Deployment completed successfully!"
echo "========================================="
echo ""
echo "Application is running"
echo ""
echo "Useful commands:"
echo "  View logs:    cd $PROJECT_ROOT && docker-compose --env-file .env -f docker/docker-compose.prod.yml logs -f"
echo "  Restart:      cd $PROJECT_ROOT && docker-compose --env-file .env -f docker/docker-compose.prod.yml restart"
echo "  Stop all:     cd $PROJECT_ROOT && docker-compose --env-file .env -f docker/docker-compose.prod.yml down"
echo ""