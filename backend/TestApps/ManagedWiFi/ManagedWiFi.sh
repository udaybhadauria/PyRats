#!/bin/bash

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

ssid_name=$(echo "$cm_mac" | tr 'a-z' 'A-Z' | tr -d ':' | xargs | tail -c 5)
echo "ssid_name: $ssid_name"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_ManagedWiFi_${cm_mac}.json"

start_time=$(date +%s)

#Check if client is raspberry
client_model=$(uname -n)
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

  Result=$(java -jar $jar_path "blob_enable" "$cmac" "$sub" "$json" |grep -i "Response_Body" |awk -F "=" '{print $NF}')
  echo "$Result"
}
#=====================================================================
#Run WEBPA Get Query and Fetch Device Model

param="Device.DeviceInfo.ModelName"
model=$(get_result_weg "$cmac" "$param")
echo "Gateway Model: $model"

#====================================================================
#Function to Generate Json Data for Connecting Building Blob Enable/Disable

generate_json() {
  local model=$1
  local param=$2
  local ssid_name=$3

  local SSID_2G="iOT_${ssid_name}_2G"
  local PASSPHRASE_2G="iotssid2345"
  local SSID_5G="iOT_${ssid_name}_5G"
  local PASSPHRASE_5G="iotssid2345"
  local SSID_6G="iOT_${ssid_name}_6G"
  local PASSPHRASE_6G="iotssid2345"

  if [ "$model" = "CGM4981COM" ]; then
    JSON=$(jq -n \
      --arg ssid_2g "$SSID_2G" \
      --arg passphrase_2g "$PASSPHRASE_2G" \
      --arg ssid_5g "$SSID_5G" \
      --arg passphrase_5g "$PASSPHRASE_5G" \
      --arg ssid_6g "$SSID_6G" \
      --arg passphrase_6g "$PASSPHRASE_6G" \
      '{
        "managed_wifi_enabled": '$param',
        "ssid_enabled_2g": true,
        "ssid_name_2g": $ssid_2g,
        "broadcast_ssid_2g": true,
        "wifi_security_2g": 2,
        "wifi_passphrase_2g": $passphrase_2g,
        "ssid_enabled_5g": true,
        "ssid_name_5g": $ssid_5g,
        "broadcast_ssid_5g": true,
        "wifi_security_5g": 2,
        "wifi_passphrase_5g": $passphrase_5g,
        "ssid_enabled_6g": true,
        "ssid_name_6g": $ssid_6g,
        "broadcast_ssid_6g": true,
        "wifi_security_6g": 11,
        "wifi_passphrase_6g": $passphrase_6g,
        "wifihotspot_guest_mode": true
      }')
  else
    JSON=$(jq -n \
      --arg ssid_2g "$SSID_2G" \
      --arg passphrase_2g "$PASSPHRASE_2G" \
      --arg ssid_5g "$SSID_5G" \
      --arg passphrase_5g "$PASSPHRASE_5G" \
      '{
        "managed_wifi_enabled": '$param',
        "ssid_enabled_2g": true,
        "ssid_name_2g": $ssid_2g,
        "broadcast_ssid_2g": true,
        "wifi_security_2g": 2,
        "wifi_passphrase_2g": $passphrase_2g,
        "ssid_enabled_5g": true,
        "ssid_name_5g": $ssid_5g,
        "broadcast_ssid_5g": true,
        "wifi_security_5g": 2,
        "wifi_passphrase_5g": $passphrase_5g,
        "wifihotspot_guest_mode": true
      }')
  fi
  json=$(jq -rn --argjson data "$JSON" '$data | @uri')
  echo "$json"

  sub="connectedbuilding"
  response=$(get_result_ben "$cmac" "$sub" "$json")
  result=$(echo $response | grep -o 'POST Request Successful.')

  # Check if the result is equal to "POST Request successful."
  if [ "$result" = "POST Request Successful." ]; then
    echo "ManagedWiFi Blob query is Passed"
  else
    echo "ManagedWiFi Blob query is Failed"
  fi
}
#====================================================================

# Call Funtion to Generate JSON code to Enable Webconfig
param="true"
# Function to generate encoded json
generate_json "$model" "$param" "$ssid_name"
#encoded_json=$(generate_json "$model" "$param" "$ssid_name")

# Define the SSID and passphrase
SSID1="iOT_${ssid_name}_2G"
PASSPHRASE1="iotssid2345"
SSID2="iOT_${ssid_name}_5G"
PASSPHRASE2="iotssid2345"

sleep 10 # Add sleep for SSID to start broadcasting before start of the test

#sudo iwlist wlan0 scan | grep ESSID
sudo nmcli dev wifi list | grep -i "iot"

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
    exit 1
  fi
}

get_speed_wifi() {
  total_download_speed=0
  total_upload_speed=0
  iterations=1

  # Run the speed test for 5 iterations
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

  echo "[DS/US]: $average_download_speed Mbps/$average_upload_speed Mbps"

  #output=$(fast -I wlan0 | sed -n 's/^\s*\([0-9]*\s*Mbps\).*/\1/p')
}

iwlist wlan0 scan

#Clean WiFi profiles before starting connection and test
sudo nmcli -t -f NAME connection show | grep -E '^(RATS_|iOT_)' | xargs -r -I {} sudo nmcli connection delete "{}"

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

# Define arrays for SSIDs and passphrases
SSIDS=("$SSID1" "$SSID2")
PASSPHRASES=("$PASSPHRASE1" "$PASSPHRASE2")

# Global variables to store results
overall_result=""
all_desc=""

# Function to connect to WiFi for each SSID and passphrase pair
# Function to connect to WiFi for each SSID and passphrase pair
connect_and_test_wifi() {
  #local all_desc=""
  #local overall_result="Passed"

  for ((i=0; i<${#SSIDS[@]}; i++)); do
    connect_to_wifi "${SSIDS[$i]}" "${PASSPHRASES[$i]}"
    Conn_SSID=$(iwgetid | awk -F ":" '{print $NF}' | xargs)

    if [ "$Conn_SSID" == "${SSIDS[$i]}" ]; then
      echo "Successfully connected to ${SSIDS[$i]}"
      sleep 10
      check_wifi_connection
      #iwlist wlan0 scan > output.txt
      sleep 5
      echo "Fetching WiFi info from connected client."
      desc=$(gather_wifi_info)
      echo "Speed Test is in progress"
      speed=$(get_speed_wifi)

      signal_level=$(iwconfig wlan0 | grep -i --color 'signal level' | awk -F '=' '{print $3}' | awk '{print $1}')
      signal_strength_category=$(echo "$desc" | grep -oP '(?<=Signal Strength: ).*')

      if [[ "$signal_strength_category" == "Poor" || "$signal_strength_category" == "Fair" ]]; then
        result="Failed"
        overall_result="Failed"
      else
        result="Passed"
        # Do NOT override overall_result if already Failed
        if [[ "$overall_result" != "Failed" ]]; then
          overall_result="Passed"
        fi
      fi
    else
      echo "Failed to connect to ${SSIDS[$i]}"
      desc="Failed to connect to ${SSIDS[$i]}"
      result="Failed"
      overall_result="Failed"
    fi

    var=$(echo "${SSIDS[$i]}" | awk -F '_' '{print $NF}')
    all_desc+="$var: $desc, $speed; "  # Aggregate descriptions
  done

  generate_json_output "$overall_result" "$all_desc"
}

connect_and_test_wifi

sleep 2

disconnect_from_wifi

sleep 2
#==================================================================
# Call Funtion to Generate JSON code to Enable Webconfig
param="false"
# Function to generate encoded json
generate_json "$model" "$param" "$ssid_name"
#encoded_json=$(generate_json "$model" "$param" "$ssid_name")

sleep 10
#=================================================================
SSID_2G="iOT_${ssid_name}_2G"
PASSPHRASE_2G="iotssid2345"
SSID_5G="iOT_${ssid_name}_5G"
PASSPHRASE_5G="iotssid2345"

ssid_1="Device.WiFi.SSID.10004.X_COMCAST-COM_DefaultSSID"
ssid_2="Device.WiFi.SSID.10104.X_COMCAST-COM_DefaultSSID"
pass_1="Device.WiFi.AccessPoint.10004.Security.X_COMCAST-COM_DefaultKeyPassphrase"
pass_2="Device.WiFi.AccessPoint.10104.Security.X_COMCAST-COM_DefaultKeyPassphrase"

SSID1=$(get_result_weg "$cmac" "$ssid_1")
echo "Default SSID 2G: $SSID1"

PASSPHRASE1=$(get_result_weg "$cmac" "$pass_1")
echo "Default Passphrase 2G: $PASSPHRASE1"

SSID2=$(get_result_weg "$cmac" "$ssid_2")
echo "Default SSID 5G: $SSID2"

PASSPHRASE2=$(get_result_weg "$cmac" "$pass_2")
echo "Default Passphrase 5G: $PASSPHRASE2"

# Calculate lengths
val1=$(echo -n "$PASSPHRASE1" | wc -c)
val2=$(echo -n "$PASSPHRASE2" | wc -c)
val3=63  # Hardcoded length for PASSPHRASE comparison

val4=$(echo -n "$SSID1" | wc -c)
val5=$(echo -n "$SSID2" | wc -c)
val6=32  # Hardcoded length for SSID comparison

# Output lengths
echo "$val1, $val2, $val3, $val4, $val5, $val6"

# Function to check if values match expected lengths
check_length() {
  local val1=$1
  local val2=$2
  local expected=$3
  local msg=$4

  if [ "$val1" -ne "$expected" ] || [ "$val2" -ne "$expected" ]; then
    echo "[Issue] $msg is not reverted to default settings."
    des="[Issue] $msg is not reverted to default settings."
    all_desc+=" $des;"
  else
    echo "[Info] $msg is reverted to default settings."
  fi
}

# Check Lengths if SSID1 and PASSPHRASE1 match SSID_2G and PASSPHRASE_2G
check_length "$val1" "$val2" "$val3" "Passphrase"

# Check Lengths if SSID1 and PASSPHRASE1 match SSID_5G and PASSPHRASE_5G
check_length "$val4" "$val5" "$val6" "SSID"

# Function to check if values match expected strings
check_string() {
  local val1=$1
  local val2=$2
  local expected1=$3
  local expected2=$4
  local msg=$5

  if [ "$val1" == "$expected1" ] && [ "$val2" == "$expected2" ]; then
    echo "[Issue] $msg did not revert to previous Settings."
    des="[Issue] $msg did not revert to previous Settings."
    all_desc+=" $des;"
  else
    echo "[Info] $msg also reverted to previous Settings."
  fi
}

# Check if SSID1 and PASSPHRASE1 match SSID_2G and PASSPHRASE_2G
check_string "$SSID1" "$PASSPHRASE1" "$SSID_2G" "$PASSPHRASE_2G" "2G SSID & Passphrase"

# Check if SSID2 and PASSPHRASE2 match SSID_5G and PASSPHRASE_5G
check_string "$SSID2" "$PASSPHRASE2" "$SSID_5G" "$PASSPHRASE_5G" "5G SSID & Passphrase"

# Genearet Final Result
generate_json_output "$overall_result" "$all_desc"

rm speed_output.txt
rm output.txt
rm response.json
echo "Test is completed."

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Elapsed Time: $elapsed_time seconds"