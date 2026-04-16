#!/bin/bash

# Delete 300MB of oldest logs if total RDKB Logs size crosses 1GB
# Configuration
PATTERN="*Logs*.tgz"
TOTAL_LIMIT_MB=1024       # 1GB threshold
DELETE_TARGET_MB=300     # Amount to delete
BYTES_IN_MB=1048576      # 1024 * 1024

# 1. Check total size of matching files
cd ../../Frontend/Reports/
total_bytes=$(du -cb $PATTERN 2>/dev/null | tail -n 1 | cut -f1)

# Convert to MB for comparison
total_mb=$((total_bytes / BYTES_IN_MB))

if [ "$total_mb" -gt "$TOTAL_LIMIT_MB" ]; then
    echo "Total size ($total_mb MB) exceeds $TOTAL_LIMIT_MB MB. Deleting $DELETE_TARGET_MB MB of oldest files..."
    
    deleted_bytes=0
    target_bytes=$((DELETE_TARGET_MB * BYTES_IN_MB))

    # 2. List files by modification time (oldest first) and delete until target is met
    # ls -tr sorts by time (reverse, so oldest is first)
    ls -tr $PATTERN 2>/dev/null | while read -r file; do
        if [ $deleted_bytes -lt $target_bytes ]; then
            file_size=$(stat -c%s "$file")
            rm "$file"
            deleted_bytes=$((deleted_bytes + file_size))
            echo "Deleted: $file ($((file_size / 1024)) KB)"
        else
            break
        fi
    done
    echo "Cleanup complete."
else
    echo "Limit $TOTAL_LIMIT_MB MB & total size ($total_mb MB) is within limits. No action taken."
fi

