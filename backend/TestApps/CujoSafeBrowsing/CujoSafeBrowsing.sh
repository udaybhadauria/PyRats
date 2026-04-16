#!/bin/bash

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_CujoSafeBrowsing_"$cm_mac".json"

# Install jq utility if not available
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is not installed. Installing..."
  # Replace 'your_package_manager' with the appropriate package manager for your Raspberry Pi OS (e.g., sudo apt install)
  sudo apt-get install -y jq
fi

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
# Fetch Safe Browsing Status

param="Device.DeviceInfo.X_RDKCENTRAL-COM_AdvancedSecurity.SafeBrowsing.Enable"
res=$(get_result_weg "$cmac" "$param")
echo "Safe Browsing: $res"

#===============================================================================
#Function to Generate Json Data for Connecting Building Blob Enable/Disable

generate_json() {
  local param=$1

  # Create the JSON object
  JSON=$(jq -n \
      '{
        "enabled": '$param'
      }')

  json=$(jq -rn --argjson data "$JSON" '$data | @uri')
  echo "$json"
}

if [[ "$res" == "false" ]]; then
  # Enable Safebrowsing if its disabled in Gateway
  param="true"
  encoded_json=$(generate_json "$param")

  sub="advsecurity"
  response=$(get_result_ben "$cmac" "$sub" "$encoded_json")

  # Check if the result is equal to "POST Request successful."
  if [[ "$response" == *"POST Request Successful."* ]]; then
    echo "Enable Blob query is Passed"
  else
    echo "Enable Blob query is Failed"
  fi

  sleep 5

  param="Device.DeviceInfo.X_RDKCENTRAL-COM_AdvancedSecurity.SafeBrowsing.Enable"
  res=$(get_result_weg "$cmac" "$param")
  echo "Safe Browsing: $res"
else
  # Statements to run if $res1 is equal to $res2 (test failed)
  echo "Safebrowsing is already enabled in Gateway"
fi

#sleep 2

#===============================================================================
#Safebrowsing Test on Connected LAN client

start_time=$(date +%s)

# Define the list of URLs as an array
urls=(http://js.users.51.la http://fadzulani.com http://wicar.org http://kcteam.jp/ http://afobal.cl trovi.com http://teamsofer.com http://lottonow88.com http://kntksales.tk http://www.mauritaniecoeur.org http://standefer.com http://thebert.com http://genxphones.com http://denisecameron.com http://ykmkq.com/ http://sleepybearcreations.com http://platinumcon.com/)
#urls=(http://js.users.51.la http://fadzulani.com http://wicar.org http://kcteam.jp/ http://afobal.cl trovi.com http://teamsofer.com http://www.mauritaniecoeur.org http://standefer.com)

#x=0
successful_urls=()
failure_urls=()
for url in "${urls[@]}" # Loop through each URL in the array
do
  # Run curl command and capture the output
  response=$(curl --connect-timeout 10 -Is "$url" | grep -i "http/" | awk -F ' ' '{print $2}' | xargs)
  msg=$(curl --connect-timeout 10 -Is "$url"  | grep -i "warn.html" | awk -F '/' '{print $4}' | awk -F '?' '{print $1}' | xargs)
  echo "Checking URL: $url"
  echo "Warning Messgae: $msg"

  # Check if the response contains 200 status code & warn html msg
  if [ -n "$response" ] && [ $response -eq 302 ] && [ "$msg" == "warn.html" ]; then
    successful_urls+=("$url")
    echo "Cujo Threat is succesfully notified for $url (status: $response, $msg)"
  else
    failure_urls+=("$url")
    echo "Cujo Threat is NOT generated for $url"
  fi

  echo "" # Add an empty line between checks
done

x=${x:-0}
count=${count:-0}

#echo "value: $x"
x=${#successful_urls[@]}
echo "value: $x"

iface=$(ip route get 8.8.8.8 2>/dev/null | awk '{print $5; exit}')
client_mac=$(cat /sys/class/net/$iface/address | tr -d ':' | tr 'a-z' 'A-Z')

count=$(java -jar $jar_path blob_get "$cmac" threats \
| grep Response_Body \
| sed 's/Response_Body= //' \
| jq -r '.output' \
| sed 's/^Response = //' \
| jq -r --arg mac "$client_mac" '
    .data
    | map(select(.threat_type=="SAFE_BROWSING" and .device_mac==$mac))
    | length
')

if [ "$count" -eq 0 ]; then
    echo "FAIL: No SAFE_BROWSING threats for this client MAC ($client_mac)"
else
    echo "PASS: $count SAFE_BROWSING threat(s) found for $client_mac"
fi

# Prepare the results as per above validations
if [ $x -ge 3 ] && [ "$count" -ge 1 ]; then
  result="Passed"
  desc="Cujo Threat is succesfully notified to client."
  URL=${successful_urls[@]}
  echo "Working URLs: $URL"
else
  result="Failed"
  desc="Cujo Threat is NOT succesfully notified to client."
  URL=${failure_urls[@]}
  echo "Not Working URLs: $URL"
fi

echo "{
 \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": $test_case,
      \"Result\": \"$result\",
      \"Description\": \"$desc\"
    }
  ]
}" > "$filename"

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Elapsed Time: $elapsed_time seconds"
