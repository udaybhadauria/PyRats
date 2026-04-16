#!/bin/bash

test_case="$1"
cm_mac="$2"

filename="test_results_BridgeMode_${cm_mac}.json"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

# Function for get queries
get_result_weg() {
  local cmac="$1"
  local obj="$2"

  Result=$(java -jar $jar_path "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "$Result"
}

# Function for set queries
get_result_wes() {
  local cmac="$1"
  local name="$2"
  local value="$3"
  local type="$4"

  Result=$(java -jar $jar_path "webpa_set" "$cmac" "$name" "$value" "$type" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "$Result"
}

#Check if device LAN mode is router or not
param="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"
gw_mode1=$(get_result_weg "$cmac" "$param")
echo "Device Lan Mode: $gw_mode1"

if [ "$gw_mode1" = "router" ]; then
  # Test in Router Mode
  #result1=$(execute_tests "Router")
  sleep 55
  #Switch Gateway to Bridge mode
  name="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"; value="bridge-static"; type="0";
  res=$(get_result_wes "$cmac" "$name" "$value" "$type")
  echo "Device Mode: $res"
else
  # Test in Bridge Mode
  #result1=$(execute_tests "bridge-static")
  sleep 55
  #Switch Gateway to Router mode
  name="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"; value="router"; type="0";
  res=$(get_result_wes "$cmac" "$name" "$value" "$type")
  res=$(get_result_weg "$cmac" "$param")
  echo "Device Mode: $res"
fi

# Sleep while switching gateway to router/bridge mode
sleep 235

# Check if device LAN mode is router or bridge static
param="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"
gw_mode2=$(get_result_weg "$cmac" "$param")
echo "Device Lan Mode: $gw_mode2"

echo "{
  \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": \"$test_case\",
      \"Result\": \"NA\",
      \"Description\": \"NA\"
    }
  ]
}" > "$filename"

#Switch back device to previous state.

if [ "$gw_mode2" = "router" ]; then
  #Switch Gateway to Bridge mode
  name="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"; value="bridge-static"; type="0";
  res=$(get_result_wes "$cmac" "$name" "$value" "$type")
else
  #Switch Gateway to Router mode
  name="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"; value="router"; type="0";
  res=$(get_result_wes "$cmac" "$name" "$value" "$type")
fi

sleep 200

echo "Test is completed."