#!/bin/bash

cm_mac="$1"
cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "cmac: $cmac"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

#=====================================================================
# Function to execute WEBPA Get Query and Fetch output
get_result_weg() {
  local cmac="$1"
  local obj="$2"
  local Result=""
  local attempt=0

  while [[ $attempt -lt 20 ]]; do
    sleep 30
    Result=$(java -jar $jar_path "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')

    if [[ -n "$Result" ]]; then
      echo "$Result"
      return 0
    fi

    attempt=$((attempt + 1))
    #echo "Attempt $attempt failed. Retrying in 30 seconds..."
  done

  #echo "Failed to get response after 5 attempts."
  return 1
}
#=====================================================================
# Run WEBPA Get Query and Fetch Device Software Version
param="Device.DeviceInfo.SoftwareVersion"
res=$(get_result_weg "$cmac" "$param")
if [[ -n "$res" ]]; then
  echo "Software Version: $res"
else
  echo "Unable to retrieve Software Version."
fi
