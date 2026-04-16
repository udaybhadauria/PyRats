#!/bin/bash

LOG_FILE="/var/log/rats.log"
MAX_SIZE=$((5 * 1024 * 1024))   # 5 MB in bytes

# Exit if file does not exist
[ ! -f "$LOG_FILE" ] && exit 0

# Get file size
CURRENT_SIZE=$(stat -c%s "$LOG_FILE")

if [ "$CURRENT_SIZE" -gt "$MAX_SIZE" ]; then
    echo "Log file exceeded 5MB. Clearing file..."
    : > "$LOG_FILE"
fi
