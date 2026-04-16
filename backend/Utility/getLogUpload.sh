#!/usr/bin/env bash
# What it does:
# 1) Calls: java -jar RATS-2.0.1.jar "log_upload" <cm_mac>
# 2) Parses the output to find the uploaded file name
# 3) Calls: java -jar RATS-2.0.1.jar "download" <file_name>
# Developed by RDKB Dev Team

set -u

cm_mac="$1"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
#echo "Gateway CM MAC: $cmac"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

FILE_NAME="$(java -jar "$jar_path" "log_upload" "$cmac" | grep -o '"output": *"[^"]*"' | awk -F'"' '{print $4}' | tr -d '}' | xargs)"

if [[ -z "$FILE_NAME" ]]; then
  echo "[ERROR] Could not determine uploaded RDK log tarball."
  exit 2
fi

RESPONSE="$(java -jar "$jar_path" "download" "$FILE_NAME")"

# Look for "File downloaded successfully" and extract path
DOWNLOADED_PATH="$(echo "$RESPONSE" | grep -oP 'File downloaded successfully:\s*\K.*')"

#FILE="/home/rats/RATS/Frontend/Reports/5896303FD0FD_Logs_10-31-25-03-14PM.tgz"

if [[ -f "$DOWNLOADED_PATH" ]]; then
    echo "RDK log tarball downloaded successfully!!! $FILE_NAME"
else
    echo "[ERROR] $FILE_NAME could not be download successfully. Check Result: $RESPONSE"
fi