#!/bin/bash
echo "Please provide the following inputs to establish GitHub connectivity"

read -p "GitHub username: "  username
read -p "GitHub passkey: "  passkey
read -p "GitHub mail id: "  email

# Collecting user inputs
read -p "RATS Server Management URL: <RATS Server IP e.g. 73.24.91.18> " MGMT_IP

echo "[user]" > ~/.gitconfig
echo "        name = $username" >> ~/.gitconfig
echo "        email = $email" >> ~/.gitconfig
echo "[section]" >> ~/.gitconfig
echo "        key = $passkey" >> ~/.gitconfig

git config --list

#=================================================

# Update package lists
sudo apt-get update

# Upgrade package lists
# sudo apt-get upgrade

# Install tools
success=true

sudo apt-get update

for tool in sshpass default-jdk python3-pip shc traceroute dnsutils nmap jq mosquitto mosquitto-clients speedtest-cli wget libjsoncpp-dev libmicrohttpd-dev libpaho-mqtt-dev libjson-c-dev libcurl4-openssl-dev libcurl-dev libpcap-dev software-properties-common git apache2 openssh-server libssl-dev; do
  if sudo apt-get install -y "$tool"; then
      echo "$tool installed successfully"
  else
      echo "Error installing $tool"
      success=false
  fi
done

if [ "$success" = false ]; then
  echo "Some installations failed. Please check the messages above."
fi

echo "Installation completed."

# Install requests library using pip
#python3 -m pip install --upgrade pip
pip3 install requests scapy netifaces requests_oauthlib paramiko
pip install requests scapy netifaces requests_oauthlib paramiko --break-system-packages
pip install requests scapy netifaces requests_oauthlib paramiko

echo "Installation complete!"

#===========================================================
# Goto home directory

dir=$(pwd)
cd $dir"/"

#`git clone -b release https://$username:$passkey@github.com/sshriv323/RATS.git RATS-release`
`git clone -b release https://$username:$passkey@github.com/rdkcentral/RATS.git RATS-release`
`sudo ln -sfn RATS-release RATS`

#Go to RATS directory
cd RATS/

#Compile the Server & Client code
make

#===========================================================
#Go back to /home/rats directory & create config files for token
cd

#=====================================================
#Configure Mosquitto config file

echo "" > /etc/mosquitto/mosquitto.conf

# Define the path to the config file
CONFIG_FILE="/etc/mosquitto/mosquitto.conf"

# Define the content to be written to the config file
CONFIG_CONTENT="# Place your local configuration in /etc/mosquitto/conf.d/
#
# A full description of the configuration file is at
# /usr/share/doc/mosquitto/examples/mosquitto.conf.example

pid_file /run/mosquitto/mosquitto.pid

persistence true
persistence_location /var/lib/mosquitto/

log_dest file /var/log/mosquitto/mosquitto.log

listener 1883
allow_anonymous true

include_dir /etc/mosquitto/conf.d"

# Write the content to the config file
echo "$CONFIG_CONTENT" | sudo tee "$CONFIG_FILE" > /dev/null

sudo systemctl restart mosquitto
sleep 1
sudo systemctl status mosquitto

#==================================================================
# Run the RATS Server service on pi

# Set the path to the RATS_Client directory
rats_client_dir="$dir/RATS/Backend/RATS_Client"
echo "$rats_client_dir"

# Copy RATS_Client to /usr/bin
sudo cp "$rats_client_dir/RATS_Client" /usr/bin/

# Set the path to the RATSclient.service directory
rats_service_dir="$dir/RATS/Backend/Utility/service"
echo "$rats_service_dir"

`sudo sed -i 's/WorkingDirectory=~\(.*\)/WorkingDirectory=\/home\/rats\1/' $rats_service_dir/RATSclient.service`

# Copy RATSserver.service to /etc/systemd/system
sudo cp "$rats_service_dir/RATSclient.service" /etc/systemd/system/
#===================================================================

#=================================================
#Generating /var/tmp/device_info.json file

JSON_FILE="/var/tmp/device_info.json"

# Fetch MAC for eth0
MAC=$(arp -a | grep "ether" | awk -F'[()]' '$2 ~ /\.1$/ {print $0}' | awk '{print $4}')

INTERFACE=$(arp -a | grep "ether" | awk -F'[()]' '$2 ~ /\.1$/ {print $0}' | awk '{print $NF}')

# Extract first 5 bytes and last byte separately
MAC_PREFIX=$(echo "$MAC" | cut -d: -f1-5)
LAST_BYTE=$(echo "$MAC" | cut -d: -f6)

# Convert last byte to decimal, subtract 3, convert back to uppercase hex
LAST_DEC=$((16#$LAST_BYTE - 3))
LAST_HEX=$(printf '%02X' "$LAST_DEC")

# Combine and convert entire MAC to uppercase
DEVICE_MAC=$(echo "$MAC_PREFIX:$LAST_HEX" | awk '{print toupper($0)}')

if [ -z "$DEVICE_MAC" ]; then
    echo "Failed to fetch Device MAC!"
    exit 1
fi

if [ -z "$INTERFACE" ]; then
  echo "Error: could not determine Interface" >&2
  exit 1
fi

sudo chmod +x /home/rats/RATS/Backend/Utility/getGwInfo.sh
GW_INFO=$(/home/rats/RATS/Backend/Utility/getGwInfo.sh "$DEVICE_MAC")

# Derive Device_Name from last 4 digits of MAC (remove colon)
LAST_4=$(echo "$DEVICE_MAC" | awk -F: '{print $(NF-1) $NF}')
DEVICE_NAME="${GW_INFO}_${LAST_4}"

# Fetch WAN IP with fallback
WAN_IP=$(curl -s https://api.ipify.org)
if [ -z "$WAN_IP" ]; then
    WAN_IP=$(curl -4 -s https://icanhazip.com)
fi
if [ -z "$WAN_IP" ]; then
    echo "Failed to fetch WAN IP!"
    exit 1
fi

# Generate random Device ID (1 to 15)
DEVICE_ID=$(( RANDOM % 15 + 1 ))

# Create JSON safely using jq or printf fallback
if command -v jq &> /dev/null; then
    TMP_FILE="/tmp/device_info.json.tmp"
    jq -n --arg mgmt "tcp://$MGMT_IP:1883" \
          --arg id "$DEVICE_ID" \
          --arg name "$DEVICE_NAME" \
          --arg mac "$DEVICE_MAC" \
          --arg ver "1.1" \
          --arg wan "$WAN_IP" \
          --arg iface "$INTERFACE" \
          '{
              Mgmnt_URL: $mgmt,
              Device_ID: ($id|tonumber),
              Device_Name: $name,
              Device_MAC: $mac,
              Software_Version: $ver,
              WAN_IP: $wan,
              TEST_Interface: $iface
          }' > "$TMP_FILE"
    sudo cp "$TMP_FILE" "$JSON_FILE"
    rm -f "$TMP_FILE"
else
    # Fallback using printf (less pretty formatting)
    sudo printf '{
  "Mgmnt_URL": "tcp://%s:1883",
  "Device_ID": %d,
  "Device_Name": "%s",
  "Device_MAC": "%s",
  "Software_Version": "1.1",
  "WAN_IP": "%s",
  "TEST_Interface": "eth0"
}\n' "$MGMT_IP" "$DEVICE_NAME" "$DEVICE_MAC" "$WAN_IP" | sudo tee "$JSON_FILE" > /dev/null
fi

echo "Created $JSON_FILE with details available."

#===================================================================
# Reload systemd and enable/start RATSclient.service
sudo systemctl daemon-reload
sudo systemctl enable RATSclient.service
sudo systemctl start RATSclient.service
