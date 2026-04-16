#!/bin/bash
echo "Please provide the following inputs to establish GitHub connectivity, make WebConfig XPC/ODP calls, run SpeedTest, and execute WebPA queries."

read -p "GitHub username: "  username
read -p "GitHub passkey: "  passkey
read -p "GitHub mail id: "  email

echo "[user]" > ~/.gitconfig
echo "        name = $username" >> ~/.gitconfig
echo "        email = $email" >> ~/.gitconfig
echo "[section]" >> ~/.gitconfig
echo "        key = $passkey" >> ~/.gitconfig

git config --list

#zip_file="$1"
#=================================================

# Update package lists
 apt-get update

# Upgrade package lists
#  apt-get upgrade

# Install tools
success=true

 apt-get update

for tool in sshpass default-jdk python3-pip dnsutils nmap jq mosquitto mosquitto-clients speedtest-cli wget libjsoncpp-dev libmicrohttpd-dev libpaho-mqtt-dev libjson-c-dev libcurl4-openssl-dev libcurl-dev libpcap-dev software-properties-common git apache2 libssl-dev; do
  if  apt-get install -y "$tool"; then
      echo "$tool installed successfully"
  else
      echo "Error installing $tool"
      success=false
  fi
done

if [ "$success" = false ]; then
  echo "Some installations failed. Please check the messages above."
fi

wget https://github.com/eclipse/paho.mqtt.c/archive/refs/heads/master.zip -O paho-mqtt-c.zip
unzip paho-mqtt-c.zip
cd paho.mqtt.c-master
mkdir build
cd build
cmake ..
make
make install
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
echo "Installation completed."

# Install requests library using pip
pip3 install requests
pip3 install scapy
pip3 install netifaces
pip3 install requests_oauthlib

pip install requests scapy netifaces requests_oauthlib --break-system-packages

echo "Installation complete!"

#===========================================================
# Goto home directory

dir=$(pwd)
cd $dir"/"

`git clone -b release https://$username:$passkey@github.com/rdkcentral/RATS.git RATS-release`
` ln -sfn RATS-release RATS`

#Go to RATS directory
cd RATS/

#Compile the Server & Client code
make

#===========================================================
#Go back to /home/rats directory & create config files for token
#cd
#===========================================================
#UI page path changes for apache2 server

 sed -i 's|/var/www/html|/home/rats/RATS/Frontend|g' /etc/apache2/sites-available/000-default.conf
 sed -i 's|/var/www/|/home/rats/RATS/|g' /etc/apache2/apache2.conf

 chmod +x /home /home/rats
 service apache2 restart

 rm /tmp/my_socket
#rm $dir/RATS/Frontend/url.json
#===========================================================
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
echo "$CONFIG_CONTENT" |  tee "$CONFIG_FILE" > /dev/null

 systemctl restart mosquitto
sleep 1
 systemctl status mosquitto

#==================================================================
# Run the RATS Server service on pi

# Set the path to the RATS_Server directory
rats_server_dir="$dir/RATS/Backend/RATS_Server"
echo "$rats_server_dir"

# Copy RATS_Server to /usr/bin
 cp "$rats_server_dir/RATS_Server" /usr/bin/

# Set the path to the RATSserver.service directory
rats_service_dir="$dir/RATS/Backend/Utility/service"
echo "$rats_service_dir"

` sed -i 's/WorkingDirectory=~\(.*\)/WorkingDirectory=\/home\/rats\1/' $rats_service_dir/RATSserver.service`

# Copy RATSserver.service to /etc/systemd/system
 cp "$rats_service_dir/RATSserver.service" /etc/systemd/system/

# Reload systemd and enable/start RATSserver.service
 systemctl daemon-reload
 systemctl enable RATSserver.service
 systemctl start RATSserver.service
