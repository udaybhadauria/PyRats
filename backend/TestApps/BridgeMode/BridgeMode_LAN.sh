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

# Get gateway IP address
gw_ip=$(ip route | grep -i eth0 | awk '/default/ {print $3}')

get_UIaccess() {
  local response
  response=$(curl --connect-timeout 10 -Is http://$gw_ip/ | awk '/200 OK/ {print $2}')

  if [ "$response" -eq 200 ]; then
    echo "GUI is accessible"
  else
    echo "GUI is NOT accessible"
  fi
}

get_clientIpCheck() {
  # Get the LAN IP address of the RPI
  #ip=$(hostname -I | awk '{print $1}')
  ip=$(ifconfig eth0 | awk '/inet /{print $2}')

  # Define private IP ranges
  if [[ $ip =~ ^10\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$ ]] ||
   [[ $ip =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$ ]] ||
   [[ $ip =~ ^192\.168\.(0[0-9][0-9]?|1[0-4][0-9]?|14[0-8]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$ ]] ||
   [[ $ip =~ ^192\.168\.(14[9-9]|1[5-9][0-9]?|2[0-5][0-5]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$ ]]; then
    echo "$ip is a private IP"
  else
    echo "$ip is a public IP"
  fi
}

get_lanspeed() {
  # Install speed test utility if not available
  if ! command -v speedtest &>/dev/null; then
    sudo apt-get install -y speedtest-cli
  fi

  #local dsm ds us speedtest_output download_speed upload_speed result desc
  dsm=$(cat /sys/class/net/eth0/speed)
  ds=$(echo "$dsm * 0.8" | bc)

  us=39

  obj="Device.X_CISCO_COM_CableModem.DOCSISDownstreamDataRate"
  ds_boot=$(java -jar $jar_path "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  ds_boot=$((ds_boot / 1000 / 1000))
  ds_boot=$(echo "$ds_boot * 0.8" | bc)
  #echo "$ds_boot"

  # Condition check for downstream threshold, To select between bootfile value or linux system capability
  if [ "$ds" -gt "$ds_boot" ]; then
    dst="$ds_boot"
  else
    dst="$ds"
  fi

  speedtest_output=$(speedtest-cli --secure --simple)
  download_speed=$(echo "$speedtest_output" | awk '/Download:/ {print $2}')
  upload_speed=$(echo "$speedtest_output" | awk '/Upload:/ {print $2}')

  if (( $(echo "$download_speed >= $dst" | bc) )) && (( $(echo "$upload_speed >= $us" | bc) )); then
    result="Passed"
    desc="ds= $download_speed/$ds mbps & us= $upload_speed/$us mbps"
  else
    result="Failed"
    desc="ds= $download_speed/$ds mbps & us= $upload_speed/$us mbps"
  fi

  echo "$result:$desc"
}

get_data() {
  local lan_ip4 val_ipv4 lan_ip6 val_ipv6 res1 desc1 res2 desc2 res desc
  lan_ip4=$(hostname -I | awk '{print $1}')
  val_ipv4=$(ping -c 4 google.com | awk -F', ' '/packet loss/ {print $3}' | awk '{print $1}')

  if [ -z "$lan_ip4" ] || [ "$val_ipv4" != "0%" ]; then
    res1="0"
    desc1="No LAN IPv4 available or Packet Loss on IPv4 is observed"
  else
    res1="1"
    desc1="LAN IPv4 is available & No Packet Loss is observed"
  fi

  lan_ip6=$(hostname -I | awk '{print $2}')
  val_ipv6=$(ping6 -c 4 google.com | awk -F', ' '/packet loss/ {print $3}' | awk '{print $1}')

  if [ -z "$lan_ip6" ] || [ "$val_ipv6" != "0%" ]; then
    res2="0"
    desc2="No LAN IPv6 available or Packet Loss on IPv6 is observed"
  else
    res2="1"
    desc2="LAN IPv6 is available & No Packet Loss is observed"
  fi

  if [ "$res1" -eq 1 ] && [ "$res2" -eq 1 ]; then
    res="Passed"
    desc="LAN IPs available and ping is successful"
  else
    res="Failed"
    desc="$desc1 and $desc2"
  fi

  echo "$res:$desc"
}

execute_tests() {
  local mode lan_test test_result test_desc speed_test speed_result speed_desc UI_test
  mode="$1"

  client_ip=$(get_clientIpCheck)

  lan_test=$(get_data)
  test_result=$(echo "$lan_test" | awk -F ':' '{print $1}')
  test_desc=$(echo "$lan_test" | awk -F ':' '{print $2}')

  speed_test=$(get_lanspeed)
  speed_result=$(echo "$speed_test" | awk -F ':' '{print $1}')
  speed_desc=$(echo "$speed_test" | awk -F ':' '{print $2}')

  UI_test=$(get_UIaccess)

  echo "LAN Test: $client_ip, $test_result, Speed Test: $speed_result, UI Test: $UI_test"
}

#Check if device LAN mode is router or not
param="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"
gw_mode1=$(get_result_weg "$cmac" "$param")
echo "Device Lan Mode: $gw_mode1"

if [ "$gw_mode1" = "router" ]; then
  # Test in Router Mode
  result1=$(execute_tests "Router")
else
  # Test in Bridge Mode
  result1=$(execute_tests "bridge-static")
fi

test_result1=$(echo "$result1" | grep -oP 'LAN Test: .*?, \K[^,]*')
speed_result1=$(echo "$result1" | grep -oP 'Speed Test: \K[^,]*')
UI_test1=$(echo "$result1" | grep -oP 'UI Test: \K.*')

# Sleep while switching gateway to router/bridge mode
sleep 190

# Check if device LAN mode is router or bridge static
param="Device.X_CISCO_COM_DeviceControl.LanManagementEntry.1.LanMode"
gw_mode2=$(get_result_weg "$cmac" "$param")
echo "Device Lan Mode: $gw_mode2"

# Test in Bridge Mode
result2=$(execute_tests "$gw_mode2")

test_result2=$(echo "$result2" | grep -oP 'LAN Test: .*?, \K[^,]*')
speed_result2=$(echo "$result2" | grep -oP 'Speed Test: \K[^,]*')
UI_test2=$(echo "$result2" | grep -oP 'UI Test: \K.*')

# Final result compilation
#if [ "$test_result1" = "Passed" ] && [ "$speed_result1" = "Passed" ] && [ "$UI_test1" = "GUI is accessible" ] && [ "$test_result2" = "Passed" ] && [ "$speed_result2" = "Passed" ] && [ "$UI_test2" = "GUI is accessible" ]; then
# Final result compilation
if [[ "$test_result1" = "Passed" && "$speed_result1" = "Passed" && "$UI_test1" = "GUI is accessible" &&
      "$test_result2" = "Passed" && "$speed_result2" = "Passed" && "$UI_test2" = "GUI is accessible" ]]; then
  final_result="Passed"
  final_desc="[$gw_mode1]: $result1; [$gw_mode2]: $result2"
else
  final_result="Failed"
  final_desc="[$gw_mode1]: $result1; [$gw_mode2]: $result2"
fi

echo "{
  \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": \"$test_case\",
      \"Result\": \"$final_result\",
      \"Description\": \"$final_desc\"
    }
  ]
}" > "$filename"

sleep 200

echo "Test is completed."