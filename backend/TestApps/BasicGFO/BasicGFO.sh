#!/bin/bash
# ==========================================================
# Gateway Failover Test Script
# ==========================================================

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

filename="test_results_BasicGFO_${cm_mac}.json"
jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="/var/tmp/GFO_${cmac}_${TIMESTAMP}.log"

# ==========================================================
# Result Tracking
# ==========================================================
PRE_OK=true
GFO_OK=true
RESTORE_OK=true

result="Passed"
description="Gateway Failover test completed successfully."

# ==========================================================
# Helper Functions
# ==========================================================
log_msg() {
    local msg="$1"
    echo "$(date '+%F %T') $msg" | tee -a "$LOG_FILE"
}

is_empty() { [[ -z "$1" || "$1" == "null" ]]; }

echo "GFO_RESULT: $LOG_FILE"
echo "" > "$LOG_FILE"
log_msg "========== GFO VALIDATION $LOG_FILE =========="

# ----------------------------------------------------------------
# WebPA GET/SET helpers
# ----------------------------------------------------------------
#get_webpa() {
#    java -jar "$jar_path" "webpa_get" "$1" "$2" \
#        | awk '/Response_Body/ {print $4}' \
#        | tr -d '[\\\"]'
#}

get_webpa() {
    java -jar "$jar_path" webpa_get "$1" "$2" \
        | awk -F'Response_Body= ' '/Response_Body/ {print $2}' \
        | jq -r '.output | fromjson[0][]'
}

set_webpa() {
    java -jar "$jar_path" "webpa_set" "$1" "$2" "$3" "$4" \
        | awk '/Response_Body/ {print $4}' \
        | tr -d '[\\\"]'
}

check_association() {
    [[ -z "$2" ]] && { echo "Usage: check_association <mac> <json.path>"; return 1; }
    java -jar "$jar_path" blob_get "$1" association \
        | awk -F 'Response_Body= ' 'NF>1 {print $2}' \
        | jq -r '.output' \
        | sed 's/^Response = //' \
        | jq -r ".$2" \
        | xargs
}

# ----------------------------------------------------------------
# Backup CPE detection
# ----------------------------------------------------------------
backup_mac=$(check_association "$cmac" "data.backup_cpe_mac")
log_msg "Backup CPE MAC: $backup_mac"

if is_empty "$backup_mac"; then
    log_msg "[FAIL] Backup CPE not found. Aborting test."
    result="Failed"
    description="Backup CPE [XLE] not found. Abort GFO Test."
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
    exit 1
fi

# ----------------------------------------------------------------
# Firmware Info
# ----------------------------------------------------------------
XB_FW=$(get_webpa "$cmac" "Device.DeviceInfo.X_CISCO_COM_FirmwareName")
XLE_FW=$(get_webpa "$backup_mac" "Device.DeviceInfo.X_CISCO_COM_FirmwareName")
log_msg "Gateway Firmware: $XB_FW | XLE Firmware: $XLE_FW"

# ----------------------------------------------------------------
# Gateway Status Helper
# ----------------------------------------------------------------
get_gateway_status() {
    G1A=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.1.ActiveStatus")
    G1O=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.1.OperationStatus")
    G2A=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.2.ActiveStatus")
    G2O=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.2.OperationStatus")
    echo "$G1A $G1O $G2A $G2O"
}

# ----------------------------------------------------------------
# Change XLE value for Test
# ----------------------------------------------------------------

#Reset XLE Param for testing
name="Device.X_RDK_GatewayManagement.CheckPrimaryWan"; value="false"; type="3"
set_webpa "$backup_mac" "$name" "$value" "$type"

# ----------------------------------------------------------------
# Gateway Environment Validation
# ----------------------------------------------------------------
validate_gateway_setup() {
    local proceed=true
    log_msg "========== GATEWAY VALIDATION START =========="

    # -------- Fetch Static Values ----------
    XB_ACC=$(get_webpa "$cmac" "Device.DeviceInfo.X_RDKCENTRAL-COM_RFC.Feature.AccountInfo.AccountID")
    XLE_ACC=$(get_webpa "$backup_mac" "Device.DeviceInfo.X_RDKCENTRAL-COM_RFC.Feature.AccountInfo.AccountID")

    WAN_IPV4=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IP")
    WAN_IPV6=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IPv6")

    # -------- Get REMOTE_LTE index directly ----------
    REMOTE_INDEX=""
    total=$(get_webpa "$cmac" "Device.X_RDK_WanManager.InterfaceNumberOfEntries")
    for ((idx=1; idx<=total; idx++)); do
        alias=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.${idx}.Alias" | tr -d '"' | xargs)
        log_msg "Checking Interface.$idx Alias = $alias"
        if [[ "$alias" == "REMOTE_LTE" ]]; then
            log_msg "[INFO] REMOTE_LTE found at Interface.$idx"
            REMOTE_INDEX=$idx
            break
        fi
    done
    if [[ -z "$REMOTE_INDEX" ]]; then
        log_msg "[FAIL] REMOTE_LTE interface not found"
    fi

    if [[ -n "$REMOTE_INDEX" ]]; then
        brRWAN_IPV4=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.${REMOTE_INDEX}.VirtualInterface.1.IP.IPv4Address")
        brRWAN_IPV6=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.${REMOTE_INDEX}.VirtualInterface.1.IP.IPv6Address")
        log_msg "REMOTE_LTE IPv4: $brRWAN_IPV4"
        log_msg "REMOTE_LTE IPv6: $brRWAN_IPV6"
    else
        log_msg "[FAIL] Cannot fetch brRWAN IPs because REMOTE_LTE index not found"
    fi
    #brRWAN_IPV4=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.4.VirtualInterface.1.IP.IPv4Address")
    #brRWAN_IPV6=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.4.VirtualInterface.1.IP.IPv6Address")

    XLE_MAC=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.MAC")
    XLE_MODEL=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.ModelNumber")
    XLE_IPV4=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.IPv4")
    XLE_IPV6=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.IPv6")

    XB_GFO_EN=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Failover.Enable")
    XLE_GFO_EN=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.Failover.Enable")

    log_msg "XB Account: $XB_ACC; XLE Account: $XLE_ACC"
    log_msg "WAN IPv4: $WAN_IPV4; WAN IPv6: $WAN_IPV6"
    log_msg "brRWAN IPv4: $brRWAN_IPV4; brRWAN IPv6: $brRWAN_IPV6"
    log_msg "XLE MAC: $XLE_MAC; XLE Model: $XLE_MODEL; XLE IPv4: $XLE_IPV4; XLE IPv6: $XLE_IPV6"
    log_msg "XB GFO Status: $XB_GFO_EN; XLE GFO Status: $XLE_GFO_EN"

    # -------- Helper: Validate Flag ----------
    check_flag() {
        local name="$1"
        local val="$2"
        if [[ "$val" == "0" ]]; then
            log_msg "$name : Disabled"
        elif [[ "$val" == "1" ]]; then
            log_msg "$name : Enabled"
        else
            log_msg "[FAIL] $name has invalid value -> $val"
            proceed=false
        fi
    }

    check_flag "XB_GFO_EN" "$XB_GFO_EN"
    check_flag "XLE_GFO_EN" "$XLE_GFO_EN"

    # -------- Validate Account Match ----------
    [[ "$XB_ACC" != "$XLE_ACC" ]] && {
        log_msg "[WARN] Account mismatch | XB=$XB_ACC XLE=$XLE_ACC"
        proceed=false
    }

    # -------- Validate XLE Identity ----------
    for v in "$XLE_MAC" "$XLE_MODEL" "$XLE_IPV4" "$XLE_IPV6"; do
        is_empty "$v" && {
            log_msg "[FAIL] XLE field missing"
            proceed=false
        }
    done

    # -------- Heartbeat ----------
    XB_HB_STATUS=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.Status")
    XLE_HB_STATUS=$(get_webpa "$backup_mac" "Device.X_RDK_Remote.Device.2.Status")

    [[ "$XB_HB_STATUS" -lt 3 || "$XLE_HB_STATUS" -lt 3 ]] && {
        log_msg "[FAIL] Heartbeat low | XB=$XB_HB_STATUS XLE=$XLE_HB_STATUS"
        proceed=false
    }

    # -------- Gateway Status ----------
    read G1A G1O G2A G2O <<< "$(get_gateway_status)"
    [[ "$G1A" != "true" || "$G1O" != "true" || "$G2A" != "false" || "$G2O" != "true" ]] && {
        log_msg "[FAIL] Gateway flags invalid | G1A=$G1A G1O=$G1O G2A=$G2A G2O=$G2O"
        proceed=false
    }

    # -------- Fetch Dynamic Interface Values ----------
    CurActive_Intf=$(get_webpa "$cmac" "Device.X_RDK_WanManager.CurrentActiveInterface")
    CurStandBy_Intf=$(get_webpa "$cmac" "Device.X_RDK_WanManager.CurrentStandbyInterface")

    raw_avail=$(get_webpa "$cmac" "Device.X_RDK_WanManager.InterfaceAvailableStatus")
    Available_List=$(echo "$raw_avail" | tr '|' '\n' | awk -F',' '$2==1 {print $1}' | xargs)

    raw_active=$(get_webpa "$cmac" "Device.X_RDK_WanManager.InterfaceActiveStatus")
    Active_List=$(echo "$raw_active" | tr '|' '\n' | awk -F',' '$2==1 {print $1}' | xargs)
    WAN_IPV4=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IP")
    WAN_IPV6=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IPv6")

    log_msg "Current Active Interface  = ${CurActive_Intf:-NULL}"
    log_msg "Current Standby Interface = ${CurStandBy_Intf:-NULL}"
    log_msg "Available Interfaces      = ${raw_avail}"
    log_msg "Active Interfaces         = ${raw_active}"
    log_msg "Available Interfaces List = ${Available_List:-NONE}"
    log_msg "Active Interfaces List    = ${Active_List:-NONE}"
    log_msg "WAN IPv4                  = ${WAN_IPV4:-NULL}"
    log_msg "WAN IPv6                  = ${WAN_IPV6:-NULL}"

    # -------- Validate Interfaces & IPs ----------
    [[ -z "$WAN_IPV4" || -z "$WAN_IPV6" || -z "$brRWAN_IPV4" || -z "$brRWAN_IPV6" ]] && {
        log_msg "[FAIL] WAN/Bridge IPs missing"
        proceed=false
    }

    # -------- Validate Interfaces According to Gateway Mode ----------
    gw_mode=$(get_webpa "$cmac" "Device.X_RDKCENTRAL-COM_EthernetWAN.CurrentOperationalMode")
    log_msg "Gateway Mode: $gw_mode"

    if [[ "$gw_mode" == "DOCSIS" ]]; then
        [[ "$Active_List" != "DOCSIS" ]] && { log_msg "[FAIL] Active interface should be DOCSIS"; proceed=false; }
        [[ ! "$Available_List" =~ DOCSIS || ! "$Available_List" =~ REMOTE_LTE ]] && { log_msg "[FAIL] Available interfaces should include DOCSIS & REMOTE_LTE"; proceed=false; }
    elif [[ "$gw_mode" == "Ethernet" ]]; then
        [[ "$Active_List" != "WANOE" ]] && { log_msg "[FAIL] Active interface should be WANOE"; proceed=false; }
        [[ ! "$Available_List" =~ WANOE || ! "$Available_List" =~ REMOTE_LTE ]] && { log_msg "[FAIL] Available interfaces should include WANOE & REMOTE_LTE"; proceed=false; }
    else
        log_msg "[FAIL] Unknown gateway mode: $gw_mode"
        proceed=false
    fi

    log_msg "XB Heartbeat: $XB_HB_STATUS; XLE Heartbeat: $XLE_HB_STATUS"
    log_msg "XB Active/Operation: $G1A/$G1O; XLE Active/Operation: $G2A/$G2O"
    log_msg "Current Active Interface: $CurActive_Intf; Standby Interface: $CurStandBy_Intf"

    # -------- Final Decision ----------
    if $proceed; then
        log_msg "[PASS] Gateway validation successful. Ready for Gateway Failover."
        return 0
    else
        log_msg "[FAIL] Gateway validation failed. Check logs $LOG_FILE"
        return 1
    fi
}

# ----------------------------------------------------------------
# Validations before Failover
# ----------------------------------------------------------------
if ! validate_gateway_setup; then
    PRE_OK=false
    log_msg "[FAIL] Gateway precheck failed for validation. Exiting test."
    result="Failed"
    description="Gateway setup is not ready for validation. Abort GFO Test. Refer Log: $LOG_URL"
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
    exit 1
fi

sleep 5

# ----------------------------------------------------------------
# Trigger Gateway Failover
# ----------------------------------------------------------------
log_msg "Triggering Gateway Failover..."
#sleep 5

#Disable Gateway WiFi
name="Device.WiFi.Radio.1.Enable"; value="false"; type="3"
set_webpa "$cmac" "$name" "$value" "$type"
name="Device.WiFi.Radio.2.Enable"; value="false"; type="3"
set_webpa "$cmac" "$name" "$value" "$type"
name="Device.WiFi.ApplyRadioSettings"; value="true"; type="3"
set_webpa "$cmac" "$name" "$value" "$type"

sleep 60

#Enable Gateway WiFi
name="Device.WiFi.Radio.1.Enable"; value="true"; type="3"
set_webpa "$cmac" "$name" "$value" "$type"
name="Device.WiFi.Radio.2.Enable"; value="true"; type="3"
set_webpa "$cmac" "$name" "$value" "$type"
name="Device.WiFi.ApplyRadioSettings"; value="true"; type="3"
set_webpa "$cmac" "$name" "$value" "$type"

sleep 10

#Reboot Gateway to trigger Failover
name="Device.X_CISCO_COM_DeviceControl.RebootDevice"; value="Device"; type="0"
set_webpa "$cmac" "$name" "$value" "$type"

sleep 30

#Validate if XLE has become Gateway 
while :; do
    # Fetch XLE mode status
    CHECK_PARAM="Device.X_RDKCENTRAL-COM_DeviceControl.DeviceNetworkingMode"
    XLE_MODE="$(get_webpa "$backup_mac" "$CHECK_PARAM" 2>/dev/null)"
    
    # Clean up the response
    XLE_MODE="$(echo "$XLE_MODE" | tr -d '\"' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    
    XLE_Act=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.Gateway.2.ActiveStatus")
    XLE_Op=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.Gateway.2.OperationStatus")

    if [[ "$XLE_Act" == "true" && "$XLE_Op" == "true" ]]; then
        log_msg "[PASS] XLE is active and operational afetr GFO."
        # Check if XLE has become Gateway
        if [ "$XLE_MODE" = "0" ]; then
            log_msg "[PASS] XLE has become Gateway after GFO."
            GFO_OK=true
            break
        fi
    else
        log_msg "[FAIL] XLE failed to become active/operational after failover."
        GFO_OK=false
    fi

    log_msg "[INFO] Not Gateway yet ($XLE_MODE). Rechecking in 10s..."
    sleep 10
done

# ----------------------------------------------------------------
# Gateway ping function (continuous until success)
# ----------------------------------------------------------------
gateway_ping() {
    local target="$1"
    [[ -z "$target" ]] && { log_msg "[FAIL] No target IP provided"; return 1; }
    log_msg "Waiting for Gateway ($target) to come online..."
    while true; do
        ping -c1 -W2 "$target" &>/dev/null && { log_msg "[Info] Gateway is online"; return 0; }
        sleep 2
    done
}

WAN_IPV4=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IP")
gateway_ping "$WAN_IPV4"

# ----------------------------------------------------------------
# Gateway Restore Validation
# ----------------------------------------------------------------

#Validate if XLE has become Extender after Restore
while :; do
    # Fetch XLE mode status
    XLE_MODE="$(get_webpa "$backup_mac" "Device.X_RDKCENTRAL-COM_DeviceControl.DeviceNetworkingMode" 2>/dev/null)"
    
    # Clean up the response
    XLE_MODE="$(echo "$XLE_MODE" | tr -d '\"' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    
    XLE_Act=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.Gateway.2.ActiveStatus")
    XLE_Op=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.Gateway.2.OperationStatus")

    if [[ "$XLE_Act" == "false" && "$XLE_Op" == "true" ]]; then
        log_msg "[PASS] XLE is active and operational after gateway restore."
        # Check if XLE has become Extender
        if [ "$XLE_MODE" = "1" ]; then
            log_msg "[PASS] XLE has become Extender now"
            RESTORE_OK=true
            break
        fi
    else
        log_msg "[FAIL] XLE yet to become extender, will check in sometime."
        RESTORE_OK=false
    fi

    log_msg "[INFO] Not Extender yet ($XLE_MODE). Rechecking in 30s..."
    sleep 30
done

validate_gateway_setup || RESTORE_OK=false
sleep 5

RESTORE_METHOD=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.GW_Restore_Method")
RESTORE_TIME=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.DurationOfXLEinGWModeInGFO")

log_msg "[INFO] Gateway Restore Method [$RESTORE_METHOD]"
log_msg "[INFO] Time take to Gateway Restore [$RESTORE_TIME]"

#Revert XLE Param as testing has been completed now
name="Device.X_RDK_GatewayManagement.CheckPrimaryWan"; value="true"; type="3"
set_webpa "$backup_mac" "$name" "$value" "$type"

# ----------------------------------------------------------------
# Final Result Evaluation
# ----------------------------------------------------------------
LOG_URL="https://50.189.74.50/webdav/$(basename "$LOG_FILE")"

declare -A PHASES=(
    [Pre-Failover]=$PRE_OK
    [Failover]=$GFO_OK
    [Restore]=$RESTORE_OK
)

result="Passed"
description="All validations passed: Pre-Failover, WFO, and Restore successful. $LOG_URL"

for phase in "${!PHASES[@]}"; do
    if ! ${PHASES[$phase]}; then
        result="Failed"
        description="$phase validation failed. Log: $LOG_URL"
        break
    fi
done

log_msg "FINAL RESULT: $result"
log_msg "FINAL DESCRIPTION: $description"

##########################################
# Upload Log File
##########################################

UPLOAD_URL="https://50.189.74.50/webdav/"
UPLOAD_FILE="$LOG_FILE"

echo "Uploading logfile to WebDAV..."

curl -k --fail --silent --show-error \
     -T "$UPLOAD_FILE" \
     "$UPLOAD_URL"

if [[ $? -eq 0 ]]; then
    echo "[PASS] Log upload successful"
else
    echo "[WARN] Log upload FAILED"
fi

# ----------------------------------------------------------------
# JSON Output
# ----------------------------------------------------------------
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