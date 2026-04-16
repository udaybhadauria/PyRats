#!/bin/bash

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

get_ip() {
    local ip_version=$1
    local ip_var

    for url in "https://ipinfo.io/ip" "https://icanhazip.com" "https://ifconfig.co"; do
        ip_var=$(curl -s -${ip_version} --connect-timeout 5 --max-time 10 "$url")
        if [ -n "$ip_var" ]; then
            echo "$ip_var"
            return
        fi
    done

    echo ""
}

# Get IP addresses
PI_IP=$(get_ip 4)
PI_IP6=$(get_ip 6)

# Get active interface MAC
ACTIVE_INTERFACE=$(ip route get 8.8.8.8 | awk '{print $5; exit}')
PI_MAC=$(ip link show "$ACTIVE_INTERFACE" | awk '/ether/ {print $2}')

# Reading user name from file
if [[ -s /var/tmp/user_name.txt ]]; then
    PI_USER=$(< /var/tmp/user_name.txt)
else
    echo "Error: /var/tmp/user_name.txt is empty/missing."
    PI_USER="PI_USER_${PI_MAC}"
fi

Result=$(java -jar $jar_path "server_info" "$PI_USER" "$PI_IP" "$PI_IP6" | awk '/Response_Body/ {print $2}')
if [[ -n "$Result" ]]; then
    echo "$Result"
fi
