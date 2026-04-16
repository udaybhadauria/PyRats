#!/bin/bash

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_SpeedTest_${cm_mac}.json"

# Install speed test utility if not available
if ! command -v speedtest-cli >/dev/null 2>&1; then
  echo "speedtest-cli is not installed. Installing..."
  sudo apt-get install -y speedtest-cli
fi

total_download_speed=0
total_upload_speed=0
iterations=1
valid_results=1

# Run the speed test multiple times
for i in $(seq 1 $iterations); do
  echo "Running iteration $i..."

  # Create a temp file in the current directory
  tmp_file="$(pwd)/speedtest_output_$$.txt"

  # Run speedtest-cli, store in variable and file
  speedtest_output=$(speedtest-cli --secure --simple 2>/dev/null | xargs | tee "$tmp_file")

  #speedtest_output=$(speedtest-cli --secure --simple 2>/dev/null | xargs)

  download_speed=$(echo "$speedtest_output" | grep -Eo 'Download: [0-9.]+' | cut -d' ' -f2)
  upload_speed=$(echo "$speedtest_output" | grep -Eo 'Upload: [0-9.]+' | cut -d' ' -f2)

  total_download_speed=$(echo "$total_download_speed + $download_speed" | bc)
  total_upload_speed=$(echo "$total_upload_speed + $upload_speed" | bc)

done

if [ -z "$total_download_speed" ] || [ -z "$total_upload_speed" ] || [ "$(echo "$total_download_speed == 0" | bc)" -eq 1 ] || [ "$(echo "$total_upload_speed == 0" | bc)" -eq 1 ]; then
    echo "Download/Upload speed is missing or shows 0 mbps speed"
    result="Failed"
    response="$tmp_file"
    valid_results=0
fi

# Remove Temporary FIle
rm -f "$tmp_file"

if [ "$valid_results" -eq 0 ]; then
  # No valid results → publish failure
  result="Failed"
  description="Speed test did not execute successfully. No valid results captured. $response"
  average_download_speed="N/A"
  average_upload_speed="N/A"
  ds_boot_sup="N/A"
  us_boot_sup="N/A"
  dsm="N/A"
  dst="N/A"
  ust="N/A"
else
  # Calculate averages
  average_download_speed=$(echo "scale=2; $total_download_speed / $valid_results" | bc)
  average_upload_speed=$(echo "scale=2; $total_upload_speed / $valid_results" | bc)

  echo "Average Download Speed: $average_download_speed Mbps"
  echo "Average Upload Speed: $average_upload_speed Mbps"

  dsm=$(cat /sys/class/net/eth0/speed 2>/dev/null || echo 1000)   # fallback if file missing
  echo "max supported ds: $dsm"
  ds=$(echo "$dsm * 0.5" | bc)

  us=43

  obj="Device.X_RDKCENTRAL-COM_EthernetWAN.CurrentOperationalMode"
  gw_mode=$(java -jar "$jar_path" "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "Gateway WAN: $gw_mode"

  if [ "$gw_mode" == "DOCSIS" ]; then
      # DOCSIS mode
      obj="Device.X_CISCO_COM_CableModem.DOCSISDownstreamDataRate"
      ds_boot=$(java -jar "$jar_path" "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
      # Convert bps to Mbps
      ds_boot=$(echo "scale=2; $ds_boot / 1000000" | bc)

      obj="Device.X_CISCO_COM_CableModem.DOCSISUpstreamDataRate"
      us_boot=$(java -jar "$jar_path" "webpa_get" "$cmac" "$obj" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
      # Convert bps to Mbps
      us_boot=$(echo "scale=2; $us_boot / 1000000" | bc)
  else
      # Ethernet Mode - convert from bytes to Mbps
      ds_boot=$(echo "scale=2; (1625000000) / 1000000" | bc)  # Convert bytes to Mbps
      us_boot=$(echo "scale=2; (43750000) / 1000000" | bc)    # Convert bytes to Mbps
  fi

  ds_boot_sup=$ds_boot
  dst=$(echo "$ds_boot * 0.5" | bc)

  echo "Download Threshold Speed: $dst mbps"

  # us_boot is already in Mbps from earlier conversion
  us_boot_sup=$us_boot
  ust=$(echo "$us_boot * 0.5" | bc)

  echo "Upload Threshold Speed: $ust mbps"

  if [ "$(echo "$average_download_speed >= $dst" | bc)" -eq 1 ] && \
     [ "$(echo "$average_upload_speed >= $ust" | bc)" -eq 1 ]; then
    result="Passed"
  else
    result="Failed"
  fi
  # Build description
  # Convert download speed to Gbps if > 1000 Mbps
  if [ "$(echo "$average_download_speed > 1000" | bc)" -eq 1 ]; then
    download_display=$(echo "scale=2; $average_download_speed / 1000" | bc)
    download_unit="gbps"
  else
    download_display=$average_download_speed
    download_unit="mbps"
  fi
  description="[DS: $download_display/$ds_boot_sup $download_unit | US: $average_upload_speed/$us_boot_sup mbps]"
fi

echo "Filename: $filename"

cat <<EOF > "$filename"
{
  "test_results": [
    {
      "Device_Mac": "$cm_mac",
      "Test_ID": $test_case,
      "Result": "$result",
      "Description": "$description"
    }
  ]
}
EOF
