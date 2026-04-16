#!/bin/bash

test_case="$1"
cm_mac="$2"
cmac=$(echo "$2" | tr 'A-Z' 'a-z' | tr -d ':')

filename="test_results_PortScan_"$cm_mac".json"

# Target IP address
target_ip="$3"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

if [ -z "$3" ]; then
  echo "Error: target_ip is required"
  tr181="Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
  target_ip=$(java -jar $jar_path "webpa_get" "$cmac" "$tr181" | awk '/Response_Body/ {print $4}' | tr -d '[\\\"]')
  echo "Gateway WAN IP: $target_ip"
fi

#==================================================================
# Fetch Ports which are opened in Port Forwarding
#==================================================================
# Run Java command and redirect output to response.txt
java -jar $jar_path blob_get $cmac portforwarding | grep -i "Response_Body" | sed 's/^Response_Body= {"output":"Response = //g' | sed 's/"}$//g' > response.json

# Define initial allowed ports
ALLOWED_PORTS=(80 443 5900 5901 8080 8181)

# Extract ports from JSON
ports=$(cat response.json | sed 's/\\//g' | jq -r '.data[] | .wan_port_start, .wan_port_end' | awk '{printf "%s ", $0}' | sed 's/ $//')

# Convert ports into an array
ports_array=($ports)

# Initialize variables
result=()
i=0
len=${#ports_array[@]}

while [ $i -lt $len ]; do
    start=${ports_array[$i]}
    end=${ports_array[$i+1]}

    if [ "$start" -eq "$end" ]; then
        result+=("$start")
    elif [ "$start" -lt "$end" ]; then
        for ((j=start; j<=end; j++)); do
            result+=("$j")
        done
    fi

    i=$((i + 2))
done

# Combine existing allowed ports with new results and remove duplicates
ALLOWED_PORTS=($(echo "${ALLOWED_PORTS[@]}" "${result[@]}" | tr ' ' '\n' | sort -n | uniq | tr '\n' ' '))

# Output final allowed ports
echo "ALLOWED_PORTS=(${ALLOWED_PORTS[@]})"

#==================================================================
open_port=()
open_port_a=()

val=$(ping -c 1 $target_ip | grep -i "0% packet loss" | awk -F "," '{print $3}' | xargs)
echo "$val"

if [ "$val" = "100% packet loss" ]; then
 result="$target_ip IP is not rechable"
 echo "{
\"test_results\": [
   {
     \"Device_Mac\": \"$cm_mac\",
     \"Test_ID\": $test_case,
     \"Result\": \"Failed\",
     \"Description\": \"$result\"
   }
 ]
}" > "$filename"
else
 # Run nmap scan and capture the output
 nmap_output=$(sudo timeout 20s nmap -sT $target_ip | grep -e "open" -e "filtered" | awk '{print $1,$3}' | tr '/' ' ' | awk -F ' ' '{print $1 ":" $3}' | xargs)
 echo "$nmap_output"
 # Print the result if nmap_output is not null
 if [ ! -z "$nmap_output" ]; then
   echo "$nmap_output"
 fi

 # Capture filtered ports
 #FILTERED_PORTS=$(sudo timeout 20s nmap -sT $target_ip | grep filtered | awk -F '/' '{print $1}')

 # Capture open ports
 OPEN_PORTS=($(sudo timeout 20s nmap -sT "$target_ip" | grep open | awk -F '/' '{print $1}'))
 echo "OPEN PORTS: ${OPEN_PORTS[@]}"

 #OPEN_PORTS=$(sudo timeout 20s nmap -sT "$target_ip" | grep open | awk -F '/' '{print $1}')

 # Define an array of allowed open ports
 #ALLOWED_PORTS=(80 443 5900 5901 8080 8181)

 # Loop through each open port found by nmap
 passed=true  # Flag to track if all ports are allowed
 for port in "${OPEN_PORTS[@]}"; do
    # Check if the port is allowed
    if [[ " ${ALLOWED_PORTS[@]} " =~ " $port " ]]; then
        echo "Port $port is allowed."
        open_port_a+=("$port")
    else
        echo "Port $port is not allowed."
        open_port+=("$port")
        passed=false  # Set flag to false if any port is not allowed
    fi
 done

 # Check if there are no open ports found or all open ports are allowed
 if [ ${#open_port[@]} -eq 0 ]; then
    if [ ${#open_port_a[@]} -gt 0 ]; then
        output="[Info] ${open_port_a[@]} port/s are allowed"
        result="Passed"
    else
        output="No open ports found."
        result="Passed"
    fi
 elif ! $passed; then
    output="${open_port[@]} port/s are NOT allowed"
    result="Failed"
 else
    output="[Info] ${open_port_a[@]} port/s are allowed"
    result="Passed"
 fi

 echo "Filename: $filename"

 echo "{
 \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": $test_case,
      \"Result\": \"$result\",
      \"Description\": \"$output\"
    }
  ]
}" > "$filename"
fi

rm response.txt
rm response.json