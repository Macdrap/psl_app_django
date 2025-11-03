#!/bin/bash

# Database Backup Script to AWS S3
# Backs up PostgreSQL database and uploads to S3
# Keeps backups for 30 days locally and in S3

set -e

# Configuration
BACKUP_DIR="/opt/psl-app/backups"
S3_BUCKET="s3://psl-app-db-backups"
BACKUP_FILE="psl-app-db-backup-$(date '+%Y-%m-%d_%H-%M-%S').sql.gz"
RETENTION_DAYS=30  # keep backups for 30 days

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "========================================="
echo "Database Backup"
echo "========================================="

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Load environment variables
if [ -f /opt/psl-app/.env ]; then
    set -a
    source /opt/psl-app/.env
    set +a
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

echo "Creating database backup..."

# Create backup using docker-compose
cd /opt/psl-app
docker-compose --env-file .env -f docker/docker-compose.prod.yml exec -T db \
    pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/$BACKUP_FILE

# Check if backup was created successfully
if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Backup created: $BACKUP_FILE ($BACKUP_SIZE)${NC}"
else
    echo -e "${RED}✗ Backup failed${NC}"
    exit 1
fi

# Upload to S3
echo "Uploading to S3..."
aws s3 cp $BACKUP_DIR/$BACKUP_FILE $S3_BUCKET/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Uploaded to S3: $S3_BUCKET/$BACKUP_FILE${NC}"
else
    echo -e "${RED}✗ S3 upload failed${NC}"
    exit 1
fi

# ------------------------
# Cleanup old backups
# ------------------------

echo "Cleaning up old backups older than $RETENTION_DAYS days..."

# Delete local backups older than RETENTION_DAYS
find $BACKUP_DIR -name "psl-app-db-backup-*.sql.gz" -type f -mtime +$RETENTION_DAYS -exec rm -v {} \;

# Delete old backups in S3 (older than RETENTION_DAYS)
# Requires AWS CLI >=2 for --query with timestamps
aws s3 ls $S3_BUCKET/ | while read -r line; do
    file_date=$(echo $line | awk '{print $1}')
    file_name=$(echo $line | awk '{print $4}')
    if [[ -n "$file_name" ]]; then
        file_ts=$(date -d "$file_date" +%s)
        expire_ts=$(date -d "-$RETENTION_DAYS days" +%s)
        if [ "$file_ts" -lt "$expire_ts" ]; then
            echo "Deleting old S3 backup: $file_name"
            aws s3 rm $S3_BUCKET/$file_name
        fi
    fi
done

echo ""
echo "========================================="
echo -e "${GREEN}Backup completed successfully!${NC}"
echo "========================================="
echo "Backup file: $BACKUP_FILE"
echo "S3 location: $S3_BUCKET/$BACKUP_FILE"
echo "Local backups: $(ls -1 $BACKUP_DIR/*.sql.gz 2>/dev/null | wc -l)"
echo ""

# List recent backups in S3
echo "Recent S3 backups:"
aws s3 ls $S3_BUCKET/ | tail -5
