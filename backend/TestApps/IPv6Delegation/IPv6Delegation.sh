#!binbash
#set -e

test_case=$1
cm_mac=$2

##########################################
# Build filename
##########################################

cmac=$(echo $cm_mac  tr 'A-Z' 'a-z'  tr -d '')
filename=test_results_IPv6Delegation_${cm_mac}.json

echo Filename $filename

##########################################
# Paths
##########################################

CONF_FILE=etcdibblerclient.conf
XML_FILE=varlibdibblerclient-AddrMgr.xml
LOG_FILE=varlogdibblerdibbler-client.log

echo ===== Dibbler Setup + PD Validation =====

##########################################
# Install dibbler-client if missing
##########################################

if ! dpkg -s dibbler-client devnull 2&1; then
    echo [INFO] Installing dibbler-client...
    sudo apt update
    sudo apt install -y dibbler-client
else
    echo [INFO] dibbler-client already installed
fi

##########################################
# Function WEBPA Query
##########################################

get_result() {
    local cmac=$1
    local obj=$2

    local Result
    Result=$(java -jar $jar_path webpa_get $cmac $obj 
         grep 'output' 
         sed -E 's.output [{. ([^]).1')

    echo $Result
}

##########################################
# Fetch Device Info
##########################################

jar_path=$(cat homeratsRATSBackendUtilityjar_path.txt)

param1=Device.DeviceInfo.ProductClass
param2=Device.X_CISCO_COM_CableModem.DOCSISConfigFileName
param3=Device.DeviceInfo.ModelName

res1=$(get_result $cmac $param1)
res2=$(get_result $cmac $param2)
res3=$(get_result $cmac $param3)

# Normalize case
res1=$(echo $res1  tr '[lower]' '[upper]')
res2=$(echo $res2  tr '[upper]' '[lower]')

##########################################
# Device Validation
##########################################

if [[ $res1 =~ ^(CBRXB10)$ && $res2 == bci  && $res2 == bi ]]; then
    echo Condition PASSED
else
    echo Condition FAILED

    result=Failed
    description=Abort Test — IPv6 delegation feature is NOT supported.

    cat EOF  $filename
{
  test_results [
    {
      Device_Mac $cm_mac,
      Test_ID $test_case,,
      Result $result,
      Description $description
    }
  ]
}
EOF
    exit 1
fi

##########################################
# Write client.conf
##########################################

echo [INFO] Writing client.conf

sudo tee $CONF_FILE  devnull 'EOF'
log-level 7

iface eth0 {
    ia
    pd { prefix 59 }

    option dns-server
    option domain
}
EOF

##########################################
# Restart dibbler
##########################################

echo [INFO] Restarting dibbler-client

sudo systemctl daemon-reload
sudo systemctl enable dibbler-client
sudo systemctl restart dibbler-client

echo [INFO] Waiting for lease...
sleep 10

##########################################
# Extract Prefix
##########################################

XML_PREFIX=$(sudo awk -F'[]' 'AddrPrefix{gsub([[space]]+, , $3); print $3}' $XML_FILE  head -n1)
XML_LEN=$(sudo awk -F'length=' 'AddrPrefix{split($2,a,); print a[1]}' $XML_FILE  head -n1)

LOG_PREFIX=$(sudo grep -oP 'PD Adding prefix K[0-9a-f]+[0-9]+' $LOG_FILE  tail -n1)

##########################################
# Results
##########################################

echo
echo ========= RESULTS =========
echo XML Prefix  $XML_PREFIX$XML_LEN
echo Log Prefix  $LOG_PREFIX

if [[ $XML_LEN == 59 ]]  [[ $LOG_PREFIX == 59 ]]; then
    echo SUCCESS — Prefix Delegated (59 received)
    result=Passed
    description=SUCCESS — Prefix Delegated received $XML_PREFIX$XML_LEN
else
    echo FAILURE — Prefix delegation not confirmed
    result=Failed
    description=FAILURE — Prefix delegation not received
fi

##########################################
# JSON Output
##########################################

cat EOF  $filename
{
  test_results [
    {
      Device_Mac $cm_mac,
      Test_ID $test_case,
      Result $result,
      Description $description
    }
  ]
}
EOF

cat $filename
