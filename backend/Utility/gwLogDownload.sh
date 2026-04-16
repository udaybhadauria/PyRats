#!/bin/bash

log_file="$1"
#echo "log_file: $log_file"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

#=====================================================================
# Function to download logs
download_logs() {
  local log_file="$1"
  local Result=""

  #echo "java -jar $jar_path download $log_file"
  Result=$(java -jar $jar_path "download" "$log_file")
  Result=$(echo "$Result" | awk -F'Reports/' '{print $2}' | awk '{print $1}' | grep '\.tgz$')

  if [[ -n "$Result" ]]; then
    echo "$Result"
    return 0
  fi

  return 1
}
#=====================================================================
# Run WEBPA Query
res=$(download_logs "$log_file")
if [[ -n "$res" ]]; then
  printf "%s\0" "$res"
else
  printf "%s\0" "Unable to download logs."
fi
