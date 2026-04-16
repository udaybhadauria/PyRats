#!/bin/bash

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

ssid_name=$(echo "$cm_mac" | tr 'a-z' 'A-Z' | tr -d ':' | xargs | tail -c 5)
echo "ssid_name: $ssid_name"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_PrivateWiFiConn_${cm_mac}.json"

start_time=$(date +%s)

#Check if client is raspberry
client_model=$(uname -n)

# Check if NetworkManager is installed
if ! command -v nmcli &> /dev/null
then
    echo "NetworkManager is not installed. Installing..."
    sudo apt update
    sudo apt install -y network-manager
else
    echo "NetworkManager is already installed."
fi

# Check if NetworkManager service is running
if ! systemctl is-active --quiet NetworkManager
then
    echo "NetworkManager is not running. Starting service..."
    sudo systemctl enable NetworkManager
    sudo systemctl start NetworkManager
else
    echo "NetworkManager is already running."
fi

# Function to generate JSON output
generate_json_output() {
  local final_result=$1
  local descriptions=$2
  echo "{
    \"test_results\": [
      {
        \"Device_Mac\": \"$cm_mac\",
        \"Test_ID\": $test_case,
        \"Result\": \"$final_result\",
        \"Description\": \"$descriptions\"
      }
    ]
  }" > "$filename"
}

#=====================================================================
get_result_weg() {
  local cmac="$1"
  local obj_tr181="$2"

  Result=$(java -jar $jar_path "webpa_get" "$cmac" "$obj_tr181" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "$Result"
}
#=====================================================================
get_result_ben() {
  local cmac="$1"
  local sub="$2"
  local json="$3"

  Result=$(java -jar $jar_path "blob_enable" "$cmac" "$sub" "$json" |grep -i "Response_Body")
  echo "$Result"
}
#=====================================================================
#Run WEBPA Get Query and Fetch Device Model

param="Device.DeviceInfo.ModelName"
model=$(get_result_weg "$cmac" "$param")
echo "Gateway Model: $model"

#====================================================================
#Run WEBPA Get Query and Fetch Device Product Class
param="Device.DeviceInfo.ProductClass"
class=$(get_result_weg "$cmac" "$param")
echo "Gateway Product Class: $class"

#====================================================================
#Function to Generate Json Data for Private SSID Blob Enable/Disable

generate_json() {
  local model=$1
  local param=$2
  local SSID_2G=$3
  local SSID_5G=$4
  local SSID_6G=$5
  local PASSPHRASE_2G=$6
  local PASSPHRASE_5G=$7
  local PASSPHRASE_6G=$8

  if [ "$class" = "XB8" ] || [ "$class" = "XB9" ] || [ "$class" = "XB10" ] || [ "$class" = "XER10" ] || [ "$class" = "XF10" ]; then
    JSON=$(jq -n \
      --arg ssid_2g "$SSID_2G" \
      --arg passphrase_2g "$PASSPHRASE_2G" \
      --arg ssid_5g "$SSID_5G" \
      --arg passphrase_5g "$PASSPHRASE_5G" \
      --arg ssid_6g "$SSID_6G" \
      --arg passphrase_6g "$PASSPHRASE_6G" \
      '{
        "ssid_name_2g": $ssid_2g,
        "wifi_passphrase_2g": $passphrase_2g,
        "ssid_enabled_2g": true,
        "broadcast_ssid_2g": true,
        "wifi_security_2g": 12,
        "ssid_name_5g": $ssid_5g,
        "wifi_passphrase_5g": $passphrase_5g,
        "ssid_enabled_5g": true,
        "broadcast_ssid_5g": true,
        "wifi_security_5g": 12,
        "ssid_name_6g": $ssid_6g,
        "wifi_passphrase_6g": $passphrase_6g,
        "ssid_enabled_6g": true,
        "broadcast_ssid_6g": true,
        "wifi_security_6g": 11
      }')
  else
    JSON=$(jq -n \
      --arg ssid_2g "$SSID_2G" \
      --arg passphrase_2g "$PASSPHRASE_2G" \
      --arg ssid_5g "$SSID_5G" \
      --arg passphrase_5g "$PASSPHRASE_5G" \
      '{
        "ssid_name_2g": $ssid_2g,
        "wifi_passphrase_2g": $passphrase_2g,
        "ssid_enabled_2g": true,
        "broadcast_ssid_2g": true,
        "wifi_security_2g": 2,
        "ssid_name_5g": $ssid_5g,
        "wifi_passphrase_5g": $passphrase_5g,
        "ssid_enabled_5g": true,
        "broadcast_ssid_5g": true,
        "wifi_security_5g": 2
      }')
  fi
  json=$(jq -rn --argjson data "$JSON" '$data | @uri')
  echo "$json"

  sub="privatessid"
  response=$(get_result_ben "$cmac" "$sub" "$json")

  # Check if the result is equal to "POST Request successful."
  if [[ "$response" == *"POST Request Successful."* ]]; then
    echo "PrivateSSID Blob query is Passed"
  else
    echo "PrivateSSID Blob query is Failed"
  fi
}
#====================================================================

#Fetch latest SSID and Passphrase of the Gateway
ssid_2g=$(get_result_weg "$cmac" "Device.WiFi.SSID.10001.SSID")
ssid_5g=$(get_result_weg "$cmac" "Device.WiFi.SSID.10101.SSID")
ssid_6g=$(get_result_weg "$cmac" "Device.WiFi.SSID.10201.SSID")
pass_2g=$(get_result_weg "$cmac" "Device.WiFi.AccessPoint.10001.Security.KeyPassphrase")
pass_5g=$(get_result_weg "$cmac" "Device.WiFi.AccessPoint.10101.Security.KeyPassphrase")
pass_6g=$(get_result_weg "$cmac" "Device.WiFi.AccessPoint.10201.Security.KeyPassphrase")

if [ "$class" = "XB3" ] || [ "$class" = "XB6" ] || [ "$class" = "XB7" ] || [ "$class" = "CBR" ] || [ "$class" = "XD4" ]; then
    echo "Default Private WiFi Configuration - ssid_2g: $ssid_2g pass2g: $pass_2g ssid_5g: $ssid_5g pass_5g: $pass_5g"
else
    echo "Default Private WiFi Configuration - ssid_2g: $ssid_2g pass2g: $pass_2g ssid_5g: $ssid_5g pass_5g: $pass_5g ssid_6g: $ssid_6g pass6g: $pass_6g"
fi

#====================================================================

# Call Funtion to Generate JSON code to Enable Webconfig
param="true"
SSID_2G="RATS_${ssid_name}_2G"
SSID_5G="RATS_${ssid_name}_5G"
SSID_6G="RATS_${ssid_name}_6G"
PASS_2G="Rats2G98765"
PASS_5G="Rats5G98765"
PASS_6G="Rats6G98765"

# Function to generate encoded json
generate_json "$model" "$param" "$SSID_2G" "$SSID_5G" "$SSID_6G" "$PASS_2G" "$PASS_5G" "$PASS_6G"
#encoded_json=$(generate_json "$model" "$param" "$ssid_name")

#Adding Sleep to let the ssids broadcast
sleep 60

#encoded_json=$(jq -rn --argjson data "$JSON" '$data | @uri')

#=====================================================================
#Fetch SSID and Passwords details

ssid_1="Device.WiFi.SSID.10001.SSID"
ssid_2="Device.WiFi.SSID.10101.SSID"
ssid_3="Device.WiFi.SSID.10201.SSID"
pass_1="Device.WiFi.AccessPoint.10001.Security.KeyPassphrase"
pass_2="Device.WiFi.AccessPoint.10101.Security.KeyPassphrase"
pass_3="Device.WiFi.AccessPoint.10201.Security.KeyPassphrase"

SSID1=$(get_result_weg "$cmac" "$ssid_1")
echo "SSID 2G: $SSID1"

PASSPHRASE1=$(get_result_weg "$cmac" "$pass_1")
echo "Passphrase 2G: $PASSPHRASE1"

SSID2=$(get_result_weg "$cmac" "$ssid_2")
echo "SSID 5G: $SSID2"

PASSPHRASE2=$(get_result_weg "$cmac" "$pass_2")
echo "Passphrase 5G: $PASSPHRASE2"

SSID3=$(get_result_weg "$cmac" "$ssid_3")
echo "SSID 6G: $SSID3"

PASSPHRASE3=$(get_result_weg "$cmac" "$pass_3")
echo "Passphrase 6G: $PASSPHRASE3"

if [ "$class" = "XB8" ] || [ "$class" = "XB9" ] || [ "$class" = "XB10" ] || [ "$class" = "XF10" ] || [ "$class" = "XER10" ]; then
    if [ "$SSID1" = "$SSID_2G" ] && [ "$PASSPHRASE1" = "$PASS_2G" ] && \
       [ "$SSID2" = "$SSID_5G" ] && [ "$PASSPHRASE2" = "$PASS_5G" ] && \
       [ "$SSID3" = "$SSID_6G" ] && [ "$PASSPHRASE3" = "$PASS_6G" ]; then
          echo "Successfully configured PrivateSSID"
    fi
elif [ "$SSID1" == "$SSID_2G" ] && [ "$PASSPHRASE1" == "$PASS_2G" ] && [ "$SSID2" == "$SSID_5G" ] && [ "$PASSPHRASE2" == "$PASS_5G" ]; then
  echo "Successfully configured PrivateSSID"
else
  echo "Failed to configure PrivateSSID"
  res="Failed"
  desc="Failed to configure PrivateSSID"
  generate_json_output "$res" "$desc"
  generate_json "$model" "$param" "$ssid_2g" "$ssid_5g" "$ssid_6g" "$pass_2g" "$pass_5g" "$pass_6g"
  exit 1
fi

#sudo iwlist wlan0 scan | grep ESSID
sudo nmcli dev wifi list | grep -i "rats"

#=====================================================================
check_wifi_connection() {
  #Connected SSID details
  Cur_SSID=$(iwgetid | awk -F ":" '{print $NF}' | xargs)
  echo "Client is connected to $Cur_SSID"

  # Check wifi connection status with iwconfig
  iwconfig wlan0 | grep ESSID >/dev/null 2>&1
  connected=$?  # 0 indicates connected, 1 indicates not connected

  # Check for IP address with ip addr show
  ip addr show wlan0 | grep inet >/dev/null 2>&1
  has_ip=$?  # 0 indicates IP found, 1 indicates no IP

  # Test internet connectivity with ping
  ping -q -c 1 8.8.8.8 >/dev/null 2>&1
  ping_ok=$?  # 0 indicates ping successful, 1 indicates ping failed

  # Output results

  if [[ $connected -eq 0 && $has_ip -eq 0 && $ping_ok -eq 0 ]]; then
    echo "WiFi connected and internet reachable!"
  elif [[ $connected -eq 0 && $has_ip -eq 0 ]]; then
    echo "WiFi connected but no internet access."
  else
    echo "WiFi not connected or missing IP address, test aborted"
    res="Failed"
    desc="$Cur_SSID: WiFi not connected or missing IP address"
    generate_json_output "$res" "$desc"
    generate_json "$model" "$param" "$ssid_2g" "$ssid_5g" "$ssid_6g" "$pass_2g" "$pass_5g" "$pass_6g"
    exit 1
  fi
}

#Clean WiFi profiles before starting connection and test
sudo nmcli -t -f NAME connection show | grep -E '^(RATS_|iOT_)' | xargs -r -I {} sudo nmcli connection delete "{}"

iwlist wlan0 scan

# Function to connect to WiFi
connect_to_wifi() {
  sudo nmcli device wifi connect "$1" password "$2"
}

# Function to disconnect from WiFi
disconnect_from_wifi() {
  sudo nmcli device disconnect wlan0
}

# Define arrays for SSIDs and passphrases
if [ "$class" = "XB8" ] || [ "$class" = "XB9" ] || [ "$class" = "XB10" ] || [ "$class" = "XF10" ] || [ "$class" = "XER10" ]; then
    if [[ "$client_model" == *"raspberrypi"* ]]; then
        # RPI → Skip 6GHz
        SSIDS=("$SSID1" "$SSID2")
        PASSPHRASES=("$PASSPHRASE1" "$PASSPHRASE2")
        echo "RPI detected — Skipping 6GHz SSID"
    else
        SSIDS=("$SSID1" "$SSID2" "$SSID3")
        PASSPHRASES=("$PASSPHRASE1" "$PASSPHRASE2" "$PASSPHRASE3")
    fi
else
    SSIDS=("$SSID1" "$SSID2")
    PASSPHRASES=("$PASSPHRASE1" "$PASSPHRASE2")
fi

# Function to connect to WiFi for each SSID and passphrase pair
connect_and_test_wifi() {
  local all_desc=""
  local overall_result="Passed"
  local total_ssids=${#SSIDS[@]}
  val=0

  # Arrays to hold success and failure counts for each SSID
  declare -a success_counts
  declare -a fail_counts

  # Initialize success and failure counts to 0
  for ((i=0; i<total_ssids; i++)); do
    success_counts[i]=0
    fail_counts[i]=0
  done

  for ((i=0; i<total_ssids; i++)); do
    for attempt in {1..5}; do
      val=$((val + 1))
      connect_to_wifi "${SSIDS[$i]}" "${PASSPHRASES[$i]}"
      Conn_SSID=$(iwgetid -r)
      if [ "$Conn_SSID" == "${SSIDS[$i]}" ]; then
        echo "Successfully connected to ${SSIDS[$i]} on attempt $attempt"
        sleep 25
        check_wifi_connection
        iwlist wlan0 scan > output.txt
        sleep 10
        success_counts[i]=$((success_counts[i] + 1))
      else
        echo "Failed to connect to ${SSIDS[$i]} on attempt $attempt"
        fail_counts[i]=$((fail_counts[i] + 1))
      fi
      disconnect_from_wifi
      sleep 3
      #Clean WiFi profiles before starting connection and test
      sudo nmcli -t -f NAME connection show | grep -E '^(RATS_|iOT_)' | xargs -r -I {} sudo nmcli connection delete "{}"
      sleep 3
    done
  done

  # Prepare overall result and description
  overall_result="Passed"
  all_desc=""
  for ((i=0; i<total_ssids; i++)); do
    if [ ${fail_counts[i]} -gt 0 ]; then
      overall_result="Failed"
    fi
    all_desc+="[Connection ${SSIDS[$i]}] success count: ${success_counts[i]}, failure count: ${fail_counts[i]}; "
  done

  generate_json_output "$overall_result" "$all_desc"
}

connect_and_test_wifi

sleep 2

# Call Funtion to Generate JSON code to query Private SSID
param="true"
# Function to generate encoded json
generate_json "$model" "$param" "$ssid_2g" "$ssid_5g" "$ssid_6g" "$pass_2g" "$pass_5g" "$pass_6g"

rm output.txt
echo "Test is completed."