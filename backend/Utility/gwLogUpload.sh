#!/bin/bash

cm_mac="$1"
cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

#=====================================================================
# Function to execute WEBPA Get Query and Fetch output
gw_log_upload() {
  local cmac="$1"
  local Result=""

  Result=$(java -jar $jar_path "log_upload" "$cmac")

  if [[ -n "$Result" ]]; then
    echo "$Result"
    return 0
  fi

  #echo "Failed to get response after 2 attempts."
  return 1
}
#=====================================================================
# Run WEBPA Query to trigger GW Logs Upload
res=$(gw_log_upload "$cmac")
res=$(echo "$res" | awk -F'"output"[[:space:]]*:[[:space:]]*"' '{print $2}' | awk -F'"' '{print $1}' | awk 'NF')
if [[ -n "$res" ]]; then
  printf "%s\0" "$res"
else
  printf "%s\0" "Unable to trigger log upload."
fi
