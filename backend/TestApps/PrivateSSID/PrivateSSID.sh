#!/bin/bash

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

ssid_name=$(echo "$cm_mac" | tr 'a-z' 'A-Z' | tr -d ':' | xargs | tail -c 5)
echo "ssid_name: $ssid_name"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_PrivateSSID_${cm_mac}.json"

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

  Result=$(java -jar $jar_path "blob_enable" "$cmac" "$sub" "$json" | grep -i "Response_Body")
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

  if [ "$class" = "XB8" ] || [ "$class" = "XB9" ] || [ "$class" = "XB10" ] || [ "$class" = "XF10" ] || [ "$class" = "XER10" ]; then
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

if [ "$class" = "XB8" ] || [ "$class" = "XB9" ] || [ "$class" = "XB10" ] || [ "$class" = "XF10" ] || [ "$class" = "XER10" ]; then
    echo "Default Private WiFi Configuration - ssid_2g: $ssid_2g pass2g: $pass_2g ssid_5g: $ssid_5g pass_5g: $pass_5g ssid_6g: $ssid_6g pass6g: $pass_6g"
else
    echo "Default Private WiFi Configuration - ssid_2g: $ssid_2g pass2g: $pass_2g ssid_5g: $ssid_5g pass_5g: $pass_5g"
fi
#====================================================================
# Call Funtion to Generate JSON code to Enable Webconfig
param="true"
SSID="RATS_${ssid_name}"
PASSPHRASE="Rats98765"

# Function to generate encoded json
generate_json "$model" "$param" "$SSID" "$SSID" "$SSID" "$PASSPHRASE" "$PASSPHRASE" "$PASSPHRASE"

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
    if [ "$SSID1" = "$SSID" ] && [ "$PASSPHRASE1" = "$PASSPHRASE" ] && \
       [ "$SSID2" = "$SSID" ] && [ "$PASSPHRASE2" = "$PASSPHRASE" ] && \
       [ "$SSID3" = "$SSID" ] && [ "$PASSPHRASE3" = "$PASSPHRASE" ]; then
          echo "Successfully configured PrivateSSID"
    fi
elif [ "$SSID1" = "$SSID" ] && [ "$PASSPHRASE1" = "$PASSPHRASE" ] && \
     [ "$SSID2" = "$SSID" ] && [ "$PASSPHRASE2" = "$PASSPHRASE" ]; then
        echo "Successfully configured PrivateSSID"
else
     echo "Failed to configure PrivateSSID"
     res="Failed"
     desc="Failed to configure PrivateSSID"
     generate_json_output "$res" "$desc"
     generate_json "$model" "$param" "$ssid_2g" "$ssid_5g" "$ssid_6g" "$pass_2g" "$pass_5g" "$pass_6g"
     exit 1
fi

sudo nmcli radio wifi on
sudo nmcli device wifi rescan
sleep 5

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
    desc="$Cur_SSID: WiFi not connected or missing IP address, test aborted"
    generate_json_output "$res" "$desc"
    generate_json "$model" "$param" "$ssid_2g" "$ssid_5g" "$ssid_6g" "$pass_2g" "$pass_5g" "$pass_6g"
    exit 1
  fi
}

get_speed_wifi() {
  total_download_speed=0
  total_upload_speed=0
  iterations=1

  # Run the speed test for 2 iterations
  for i in $(seq 1 $iterations); do
    #echo "Running iteration $i..."
    curl --interface wlan0 -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python - | grep -E 'Download:|Upload:' | awk '{print $2}' > speed_output.txt

    download_speed=$(cat speed_output.txt | head -n1 | xargs)
    upload_speed=$(cat speed_output.txt | tail -n1 | xargs)

    total_download_speed=$(echo "$total_download_speed + $download_speed" | bc)
    total_upload_speed=$(echo "$total_upload_speed + $upload_speed" | bc)
  done

  # Calculate average speeds
  average_download_speed=$(echo "scale=2; $total_download_speed / $iterations" | bc)
  average_upload_speed=$(echo "scale=2; $total_upload_speed / $iterations" | bc)

  echo "[DS/US]: $average_download_speed/$average_upload_speed Mbps"

  #output=$(fast -I wlan0 | sed -n 's/^\s*\([0-9]*\s*Mbps\).*/\1/p')
}

iwlist wlan0 scan

# Function to connect to WiFi
connect_to_wifi() {
  sudo nmcli device wifi connect "$1" password "$2"
}

# Function to disconnect from Wi-Fi
disconnect_from_wifi() {
    sudo nmcli device disconnect wlan0
}

#==================================================================
gather_wifi_info() {
    Freq=$(iwlist wlan0 freq | grep -i Current | awk -F ':' '{print $2}' | awk -F ' ' '{print $1}')
    Chan=$(nmcli dev wifi | grep -i $(iwgetid -r) | awk '{print $5}' | xargs)
    Bar=$(nmcli dev wifi | grep -i $(iwgetid -r) | awk '{print $9}' | xargs)
    Signal=$(iwconfig wlan0 | grep -i --color 'signal level' | awk -F '=' '{print $3}' | awk '{print $1}')

    # Determine signal strength category
    SignalStrength="Unknown"
    if (( $(echo "$Signal > -30" | bc -l) )); then
        SignalStrength="Extremely Good"
    elif (( $(echo "$Signal > -55" | bc -l) )); then
        SignalStrength="Very Strong"
    elif (( $(echo "$Signal > -65" | bc -l) )); then
        SignalStrength="Excellent"
    elif (( $(echo "$Signal <= -65 && $Signal > -75" | bc -l) )); then
        SignalStrength="Good"
    elif (( $(echo "$Signal <= -75 && $Signal > -85" | bc -l) )); then
        SignalStrength="Fair"
    elif (( $(echo "$Signal <= -85 && $Signal > -95" | bc -l) )); then
        SignalStrength="Poor"
    fi

    echo "[Freq: $Freq GHz, Ch: $Chan, RSSI: $Signal dBm, Signal Level: $SignalStrength] $Bar"
}

#==================================================================

# Single SSID connection with retry logic (no need for separate arrays)

# Function to connect to WiFi for each SSID and passphrase pair
connect_and_test_wifi() {
  local all_desc=""
  local overall_result="Failed"
  local success=false
  local max_attempts=5

  # Retry loop: Attempt to connect up to 5 times
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    echo "Connection Attempt $attempt of $max_attempts"

    # Attempt to connect to the WiFi
    connect_to_wifi "$SSID" "$PASSPHRASE"
    sleep 5
    Conn_SSID=$(iwgetid | awk -F ":" '{print $NF}' | xargs)

    if [ "$Conn_SSID" == "$SSID" ]; then
      echo "Successfully connected to $SSID on attempt $attempt"
      sleep 10
      echo "Sleep... 10 seconds."
      check_wifi_connection
      sleep 5
      echo "Fetching WiFi info from connected client."
      desc=$(gather_wifi_info)
      echo "Speed Test is in progress"
      speed=$(get_speed_wifi)

      signal_level=$(iwconfig wlan0 | grep -i --color 'signal level' | awk -F '=' '{print $3}' | awk '{print $1}')
      signal_strength_category=$(echo "$desc" | grep -oP '(?<=Signal Strength: ).*')

      if [[ "$signal_strength_category" == "Poor" || "$signal_strength_category" == "Fair" ]]; then
        overall_result="Failed"
        echo "Signal strength is $signal_strength_category, retrying..."
        disconnect_from_wifi
        sleep 5
      else
        overall_result="Passed"
        all_desc="$desc, $speed"
        success=true
        break  # Connection successful, exit retry loop
      fi
    else
      echo "Failed to connect to $SSID on attempt $attempt"
      if [ $attempt -lt $max_attempts ]; then
        echo "Retrying connection..."
        sleep 5
      fi
    fi
  done

  if [ "$success" = false ]; then
    overall_result="Failed"
    all_desc="Failed to connect to $SSID after $max_attempts attempts"
  fi

  generate_json_output "$overall_result" "$all_desc"
}

#Clean WiFi profiles before starting connection and test
sudo nmcli -t -f NAME connection show | grep -E '^(RATS_|iOT_)' | xargs -r -I {} sudo nmcli connection delete "{}"

connect_and_test_wifi

disconnect_from_wifi

# Call Funtion to Generate JSON code to query Private SSID
param="true"
# Function to generate encoded json
generate_json "$model" "$param" "$SSID" "$SSID" "$SSID" "$PASSPHRASE" "$PASSPHRASE" "$PASSPHRASE"

rm speed_output.txt
echo "Test is completed."

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Elapsed Time: $elapsed_time seconds"