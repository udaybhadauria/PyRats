#!/bin/bash

# Install jq utility if not available
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is not installed. Installing..."
  # Replace 'your_package_manager' with the appropriate package manager for your Raspberry Pi OS (e.g., sudo apt install)
  sudo apt-get install -y jq
fi

cm_mac="$1"
cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

#=====================================================================
get_result_wes() {
  local cmac="$1"
  local name="$2"
  local value="$3"
  local type="$4"

  Result=$(java -jar $jar_path "webpa_set" "$cmac" "$name" "$value" "$type" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "$Result"
}
#=====================================================================
get_result_weg() {
  local cmac="$1"
  local obj="$2"

  Result=$(java -jar $jar_path "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "$Result"
}
#====================================================================

#Fetch Log filename before triggering log upload

#param="Device.DeviceInfo.X_RDKCENTRAL-COM.Ops.LogFileName"
#file1=$(get_result_weg "$cmac" "$param")
#echo "Filename before Log Upload: $file1"

#=============================================================================

#Trigger Log Upload

name="Device.DeviceInfo.X_RDKCENTRAL-COM.Ops.UploadLogsNow"; value="true"; type="3";
res=$(get_result_wes "$cmac" "$name" "$value" "$type")

sleep 5

#=============================================================================

#Fetch rdk tarball filename after log upload

param="Device.DeviceInfo.X_RDKCENTRAL-COM.Ops.LogFileName"
file2=$(get_result_weg "$cmac" "$param")
echo "Tarball: $file2"

#=============================================================================