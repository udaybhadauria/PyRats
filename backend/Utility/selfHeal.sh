#!/bin/bash

RESOLV_FILE="/etc/resolv.conf"
DEFAULT_DNS="nameserver 8.8.8.8"

echo "$(date): Checking for IPv4 DNS in $RESOLV_FILE..."

# Check for any IPv4 DNS entry every 5 minutes through crontab
if ! grep -E "^nameserver[[:space:]]+[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" "$RESOLV_FILE" > /dev/null; then
    echo "$(date): No IPv4 DNS found. Adding $DEFAULT_DNS..."
    echo "$DEFAULT_DNS" | sudo tee -a "$RESOLV_FILE" > /dev/null
else
    echo "$(date): IPv4 DNS entry already present."
fi

