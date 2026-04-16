#!/bin/bash
# Kill all child processes of the RATs client
pkill -P $$

touch /tmp/client_restart_requested
#killall -9 RATS_Client
sleep 1

./../RATS_Client/RATS_Client &
# Stop the RATs client
#sudo systemctl stop rats-client.service

# Start the RATs client
#sudo systemctl start rats-client.service
