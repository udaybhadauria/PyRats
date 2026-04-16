#!/bin/bash

test_case="$1"
cm_mac="$2"
cmac=$(echo "$cm_mac" | tr '[:upper:]' '[:lower:]')

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_GWSpeedTest_"$cm_mac".json"

# Install speed test utility if not available
if ! command -v java >/dev/null 2>&1; then
  echo "speedtest is not installed. Installing..."
  # Replace 'your_package_manager' with the appropriate package manager for your Raspberry Pi OS (e.g., sudo apt install)
  sudo apt-get install -y default-jdk
fi

response=$(java -jar $jar_path "gateway_speedtest" "$cmac" |grep -i "Response_Body" |awk -F "=" '{print $NF}')
echo "$response"

output=$(echo $response | jq -r '.output')

# Split the output string into result and description
result=$(echo "$output" | cut -d';' -f1 | xargs)
description=$(echo "$output" | cut -d';' -f2- | xargs)

# Check if result or description is null
if [ -z "$result" ] || [ -z "$description" ]; then
  result="Failed"
  description="No output received from Gateway Speed Test Utility."
fi

sleep 2

# Construct the JSON output
echo "{
  \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": $test_case,
      \"Result\": \"$result\",
      \"Description\": \"$description\"
    }
  ]
}" > "$filename"