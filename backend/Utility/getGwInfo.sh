#!/bin/bash

cm_mac="$1"
param1="Device.DeviceInfo.ProductClass"
param2="Device.X_RDKCENTRAL-COM_EthernetWAN.CurrentOperationalMode"
param3="Device.DeviceInfo.X_RDKCENTRAL-COM_Syndication.PartnerId"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
#echo "cmac: $cmac"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

#====================================================
# Function to execute WEBPA Get Query and Fetch output

get_result() {

  local cmac="$1"
  local obj="$2"

  Result=$(java -jar $jar_path "webpa_get" "$cmac" "$obj" | grep '"output"' | sed -E 's/.*"output": *"\[\{.*: *\\?"([^"\\]*)\\?".*/\1/')
  echo "$Result"
}
#====================================================

# Run for all 3 params
res1=$(get_result "$cmac" "$param1")
res2=$(get_result "$cmac" "$param2")
res3=$(get_result "$cmac" "$param3")

# Concatenate results
final_result="${res1}_${res2}_${res3}"

echo "$final_result"