#!/bin/bash

# File path
FILE="/var/tmp/sw_version.txt"
main_dir="/home/rats"

# Check if the file exists
if [ ! -f "$FILE" ]; then
    echo "File not found!"
    exit 1
fi

# Check which service is currently running
if systemctl is-active --quiet RATSserver.service; then
    SERVICE_NAME="RATSserver.service"
elif systemctl is-active --quiet RATSclient.service; then
    SERVICE_NAME="RATSclient.service"
else
    echo "No target service is currently active."
    exit 1
fi

# Read the file line by line
while IFS= read -r line
do
    echo "$line" | grep -o '<[^/][^>]*>' | sed 's/[<>]//g'
    echo $line
    cd $main_dir
    cd $line
    sudo sh Backend/Utility/sw_dl/openssl_setup.sh
    make
    sudo systemctl stop $SERVICE_NAME
    sudo cp Backend/RATS_Server/RATS_Server /usr/bin/
    sudo cp Backend/RATS_Client/RATS_Client /usr/bin/
    cd ..
    sudo ln -sfn $line RATS
    sudo find ~/RATS/ -type f -name "*.sh" -exec chmod u+x {} \;
    sudo touch /var/tmp/sw_migration.txt
    if [ -f /var/tmp/device_info.json ]; then
        sudo dos2unix /var/tmp/device_info.json
    fi
    sleep 1
    sudo systemctl start $SERVICE_NAME
    echo "Upgrade Completed.."
    (crontab -l | grep -v "/home/rats/RATS/Backend/Utility/sw_dl/software_migration.sh") | crontab -

done < "$FILE"
