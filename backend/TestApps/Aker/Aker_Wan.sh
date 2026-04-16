#!/bin/bash

test_case="$1"
cm_mac="$2"
cmac=$(echo "$2" | tr 'A-Z' 'a-z' | tr -d ':')

# Convert Client MAC address to uppercase and remove colons
client_mac=$(echo "$3" | tr 'a-z' 'A-Z' | tr -d ':')

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

filename="test_results_Aker_${cm_mac}.json"

start_time=$(date +%s)

#=======================================================================
#Delete Previous Aker Rule

#response=$(blob_disable?mac=$curl_mac&subdoc=aker&group=device_management")

sub="aker"; group="device_management";

response=$(java -jar $jar_path "blob_disable" "$cmac" "$sub" "$group" |grep -i "Response_Body" |awk -F "=" '{print $NF}')
result=$(echo $response | grep -o 'DELETE Request Successful.')

# Check if the result is equal to "DELETE Request Successful."
if [ "$result" = "DELETE Request Successful." ]; then
    echo "Disable Blob query is Passed"
else
    echo "Disable Blob query is Failed"
fi
#=======================================================================

# Create the JSON object
JSON=$(jq -n \
  --arg mac "$client_mac" \
  '{
    action: "create_schedule",
    device_mac_list: [$mac],
    schedule_name: "day",
    schedule_icon: "day.gif",
    group_id: "RATS_DowntimeSchedule",
    timezone: "PT",
    schedule: [
      { day_of_week: "Mon", start_time: "00:05", end_time: "23:55" },
      { day_of_week: "Tue", start_time: "00:05", end_time: "23:55" },
      { day_of_week: "Wed", start_time: "00:05", end_time: "23:55" },
      { day_of_week: "Thu", start_time: "00:05", end_time: "23:55" },
      { day_of_week: "Fri", start_time: "00:05", end_time: "23:55" },
      { day_of_week: "Sat", start_time: "00:05", end_time: "23:55" },
      { day_of_week: "Sun", start_time: "00:05", end_time: "23:55" }
    ]
  }')

encoded_json=$(jq -rn --argjson data "$JSON" '$data | @uri')

sleep 1

sub="aker";
response=$(java -jar $jar_path "blob_enable" "$cmac" "$sub" "$encoded_json" |grep -i "Response_Body" |awk -F "=" '{print $NF}')
result=$(echo $response | grep -o 'POST Request Successful.')

# Check if the result is equal to "POST Request successful."
if [ "$result" = "POST Request Successful." ]; then
    echo "Enable Blob query is Passed"
else
    echo "Enable Blob query is Failed"
fi

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Elapsed Time: $elapsed_time seconds"

sleep 60

#============================================================================
#Delete Aker rule using blob query.

# Create the JSON object
JSON=$(jq -n \
  '{
    action: "delete_schedule",
    group_id: "RATS_DowntimeSchedule"
  }')

encoded_json=$(jq -rn --argjson data "$JSON" '$data | @uri')

sleep 3

sub="aker";
response=$(java -jar $jar_path "blob_enable" "$cmac" "$sub" "$encoded_json" |grep -i "Response_Body" |awk -F "=" '{print $NF}')
result=$(echo $response | grep -o 'POST Request Successful.')

# Check if the result is equal to "POST Request successful."
if [ "$result" = "POST Request Successful." ]; then
    echo "Enable Blob query is Passed"
else
    echo "Enable Blob query is Failed"
fi

#============================================================================

#filename="test_results_Aker_"$cm_mac".json"
echo "{
 \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": $test_case,
      \"Result\": \"NA\",
      \"Description\": \"NA\"
    }
  ]
}" > "$filename"

sleep 10