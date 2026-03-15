#!/bin/sh
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
  RETRY_COUNT=$((RETRY_COUNT+1))
done
if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "PostgreSQL did not become ready within timeout"
    exit 1
fi

echo "PostgreSQL is up - executing command"

# Run database migration
echo "Running database migration..."
python -m app.db.migration

# Check if migration was successful
if [ $? -ne 0 ]; then
    echo "Migration failed!"
    exit 1
fi

echo "Migration completed successfully"

# Execute the main command (e.g., uvicorn)
exec "$@"
