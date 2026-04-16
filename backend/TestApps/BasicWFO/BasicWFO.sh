#!/bin/bash

# ==========================================================
# WAN Failover Test Script
# ==========================================================

test_case="$1"
cm_mac="$2"

cmac=$(echo "$cm_mac" | tr 'A-Z' 'a-z' | tr -d ':')
echo "Gateway CM MAC: $cmac"

filename="test_results_BasicWFO_${cm_mac}.json"

jar_path=$(cat /home/rats/RATS/Backend/Utility/jar_path.txt)

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="/var/tmp/WFO_${cmac}_${TIMESTAMP}.log"

##########################################
# Result tracking
##########################################
result="Passed"
description="WAN Failover test completed successfully."

PHASE1_OK=true
PRE_OK=true
WFO_OK=true
RESTORE_OK=true

# ==========================================================
# Helper functions
# ==========================================================

log_msg() {
    local msg="$1"
    echo "$(date '+%F %T') $msg" | tee -a "$LOG_FILE"
}

is_empty() { [[ -z "$1" || "$1" == "null" ]]; }

echo "WFO_RESULT: $LOG_FILE"
echo "" > $LOG_FILE

log_msg "========== WFO VALIDATION $LOG_FILE =========="
#=====================================================================
get_webpa() {
    local cmac="$1"
    local obj_tr181="$2"
    java -jar "$jar_path" "webpa_get" "$cmac" "$obj_tr181" \
        | awk '/Response_Body/ {print $4}' \
        | tr -d '[\\\"]'
}

#=====================================================================
set_webpa() {
    local cmac="$1"
    local name="$2"
    local value="$3"
    local type="$4"
    java -jar "$jar_path" "webpa_set" "$cmac" "$name" "$value" "$type" \
        | awk '/Response_Body/ {print $4}' \
        | tr -d '[\\\"]'
}

#=====================================================================
check_association() {
    local mac="$1"
    local json_path="$2"

    [[ -z "$json_path" ]] && {
        echo "Usage: check_association <mac> <json.path>"
        return 1
    }

    java -jar "$jar_path" blob_get "$mac" association \
        | awk -F 'Response_Body= ' 'NF>1 {print $2}' \
        | jq -r '.output' \
        | sed 's/^Response = //' \
        | jq -r ".$json_path" \
        | xargs
}

#=====================================================================
backup_mac=$(check_association "$cmac" "data.backup_cpe_mac")
log_msg "Backup CPE MAC: $backup_mac"

if is_empty "$backup_mac"; then
    log_msg "[FAIL] Backup CPE is NOT Found. Abort WFO Test immediately"
    result="Failed"
    description="Backup CPE [XLE] is NOT Found. Abort WFO Test."

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

XB_FW=$(get_webpa "$cmac" "Device.DeviceInfo.X_CISCO_COM_FirmwareName")
log_msg "Gateway Firmware: $XB_FW."

XLE_FW=$(get_webpa "$backup_mac" "Device.DeviceInfo.X_CISCO_COM_FirmwareName")
log_msg "XLE Firmware: $XLE_FW."

#=====================================================================
get_gateway_status() {
    local G1A G1O G2A G2O
    G1A=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.1.ActiveStatus")
    G1O=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.1.OperationStatus")
    G2A=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.2.ActiveStatus")
    G2O=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Gateway.2.OperationStatus")
    echo "$G1A $G1O $G2A $G2O"
}

#=====================================================================
# Adjust default settings
#=====================================================================
name="Device.X_RDK_WanManager.RestorationDelay"; value="5"; type="2"
set_webpa "$cmac" "$name" "$value" "$type"

Restore_Delay=$(get_webpa "$cmac" "Device.X_RDK_WanManager.RestorationDelay")
log_msg "Restore Delay Time has been changed to $Restore_Delay seconds for Wan Failover Test."

gw_mode=$(get_webpa "$cmac" "Device.X_RDKCENTRAL-COM_EthernetWAN.CurrentOperationalMode")
log_msg "Gateway Mode: $gw_mode"

if [[ "$gw_mode" == "DOCSIS" ]]; then
    name="Device.X_RDK_DOCSIS.LinkDownTimeout"; value="0"; type="2"
else
    name="Device.X_RDKCENTRAL-COM_EthernetWAN.LinkDownTimeout"; value="0"; type="2"
fi
set_webpa "$cmac" "$name" "$value" "$type"

#=====================================================================
# Fetch Initial Gateway Status
#=====================================================================
read G1A G1O G2A G2O <<< "$(get_gateway_status)"

if [[ "$G1A" != "true" || "$G1O" != "true" || "$G2A" != "false" || "$G2O" != "true" ]]; then
    log_msg "[ERROR] Gateway initial state invalid: G1A=$G1A G1O=$G1O G2A=$G2A G2O=$G2O"
    exit 1
fi

#=====================================================================
# Pre WAN Failover validations
#=====================================================================
phase1_validate() {

    local proceed=true
    log_msg "========== PHASE 1 VALIDATION =========="

    # -------- Fetch Static ----------
    XB_ACC=$(get_webpa "$cmac" "Device.DeviceInfo.X_RDKCENTRAL-COM_RFC.Feature.AccountInfo.AccountID")
    XLE_ACC=$(get_webpa "$backup_mac" "Device.DeviceInfo.X_RDKCENTRAL-COM_RFC.Feature.AccountInfo.AccountID")

    WAN_IPV4=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IP")
    WAN_IPV6=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IPv6")

    brRWAN_IPV4=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.4.VirtualInterface.1.IP.IPv4Address")
    brRWAN_IPV6=$(get_webpa "$cmac" "Device.X_RDK_WanManager.Interface.4.VirtualInterface.1.IP.IPv6Address")

    XLE_MAC=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.MAC")
    XLE_MODEL=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.ModelNumber")
    XLE_IPV4=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.IPv4")
    XLE_IPV6=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.IPv6")

    XB_GFO_EN=$(get_webpa "$cmac" "Device.X_RDK_GatewayManagement.Failover.Enable")
    #XB_WFO_EN=$(get_webpa "$cmac" "Device.X_RDK_WanManager.AllowRemoteInterfaces")
    XLE_GFO_EN=$(get_webpa "$backup_mac" "Device.X_RDK_GatewayManagement.Failover.Enable")
    #XLE_WFO_EN=$(get_webpa "$backup_mac" "Device.X_RDK_WanManager.AllowRemoteInterfaces")

    log_msg "XB Account: $XB_ACC; XLE Account: $XLE_ACC"
    log_msg "WAN IPv4: $WAN_IPV4; WAN IPv6: $WAN_IPV6"
    log_msg "brRWAN IPv4: $brRWAN_IPV4; brRWAN IPv6: $brRWAN_IPV4"
    log_msg "XLE MAC: $XLE_MAC; XLE Model: $XLE_MODEL; XLE IPv4: $XLE_IPV4; XLE IPv6: XLE_IPV6"
    log_msg "XB GFO Status: $XB_GFO_EN; XLE GFO Status: $XLE_GFO_EN"

    # -------- Validate GFO/WFO flags ----------
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

    check_flag "XB_GFO_EN"  "$XB_GFO_EN"
    #check_flag "XB_WFO_EN"  "$XB_WFO_EN"
    check_flag "XLE_GFO_EN" "$XLE_GFO_EN"

    # -------- Validate Accounts ----------
    [[ "$XB_ACC" != "$XLE_ACC" ]] && {
        log_msg "[FAIL] Account mismatch | XB=$XB_ACC XLE=$XLE_ACC"
        proceed=false
    }

    # -------- Validate XLE identity ----------
    for v in "$XLE_MAC" "$XLE_MODEL" "$XLE_IPV4" "$XLE_IPV6"; do
        is_empty "$v" && {
            log_msg "[ERROR] XLE field missing"
            proceed=false
        }
    done

    # -------- Heartbeat ----------
    XB_HB_STATUS=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.Status")
    XLE_HB_STATUS=$(get_webpa "$backup_mac" "Device.X_RDK_Remote.Device.2.Status")

    [[ "$XB_HB_STATUS" -lt 3 || "$XLE_HB_STATUS" -lt 3 ]] && {
        log_msg "[ERROR] Heartbeat low XB=$XB_HB_STATUS XLE=$XLE_HB_STATUS"
        proceed=false
    }

    # -------- Gateway state ----------
    [[ "$G1A" != "true" || "$G1O" != "true" || "$G2A" != "false" || "$G2O" != "true" ]] && {
        log_msg "[ERROR] Gateway state invalid"
        proceed=false
    }

    # -------- Phase1 dynamic (Pre-Failover) ----------
    CurActive_Intf=$(get_webpa "$cmac" "Device.X_RDK_WanManager.CurrentActiveInterface")
    CurStandBy_Intf=$(get_webpa "$cmac" "Device.X_RDK_WanManager.CurrentStandbyInterface")

    [[ "$CurActive_Intf" != "erouter0" || "$CurStandBy_Intf" != "brRWAN" ]] && {
        log_msg "[ERROR] Active/Standby interface mismatch in XB Gateway Active case"
        proceed=false
    }

    [[ -z "$WAN_IPV4" || -z "$WAN_IPV6" || -z "$brRWAN_IPV4" || -z "$brRWAN_IPV6" ]] && {
        log_msg "[ERROR] WAN IPs missing erouter IPs ["$WAN_IPV4","$WAN_IPV6"] & brRWAN IPs ["$brRWAN_IPV4","$brRWAN_IPV6"]"
        proceed=false
    }

    log_msg "XB Heartbeat: $XB_HB_STATUS; XLE Heartbeat: $XLE_HB_STATUS"
    log_msg "XB Active Status: $G1A; XB Operation Status: $G1O; XLE Active Status: $G2A; XLE Operation Status: $G2O;"
    log_msg "Current Active Interface: $CurActive_Intf; Current Standby Interface: $CurStandBy_Intf"

    # -------- Decision ----------
    if $proceed; then
        log_msg "[INFO] Gateway is ready for WAN Failover."
        return 0
    else
        log_msg "[ERROR] Gateway is not ready for WAN Failover."
        #Description="Abort the Test, Gateway is not ready for WAN Failover."
        return 1
    fi
}

#=====================================================================
# WAN Failover WAN Restore Validation
#=====================================================================
phase2_validate() {
    local state="$1"
    local ok=true

    log_msg "==========  VALIDATION ($state) =========="

    # -------- Heartbeat ----------
    XB_HB_STATUS=$(get_webpa "$cmac" "Device.X_RDK_Remote.Device.2.Status")
    XLE_HB_STATUS=$(get_webpa "$backup_mac" "Device.X_RDK_Remote.Device.2.Status")

    [[ "$XB_HB_STATUS" -lt 3 || "$XLE_HB_STATUS" -lt 3 ]] && {
        log_msg "[ERROR] Heartbeat is missing; XB Status: $XB_HB_STATUS XLE & XLE Status: $XLE_HB_STATUS"
        proceed=false
    }

    # -------- Fetch dynamic values ----------
    CurActive_Intf=$(get_webpa "$cmac" "Device.X_RDK_WanManager.CurrentActiveInterface")
    CurStandBy_Intf=$(get_webpa "$cmac" "Device.X_RDK_WanManager.CurrentStandbyInterface")

    raw_avail=$(get_webpa "$cmac" "Device.X_RDK_WanManager.InterfaceAvailableStatus")
    log_msg "Available Interfaces Output: $raw_avail"

    Available_List=$(echo "$raw_avail" | tr '|' '\n' | awk -F',' '$2==1 {print $1}' | xargs)
    log_msg "Available Interfaces: $Available_List"

    raw_active=$(get_webpa "$cmac" "Device.X_RDK_WanManager.InterfaceActiveStatus")
    log_msg "Active Interface Output    : $raw_active"

    Active_List=$(echo "$raw_active" | tr '|' '\n' | awk -F',' '$2==1 {print $1}' | xargs)
    log_msg "Active Interfaces   : $Active_List"

    WAN_IPV4=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IP")
    WAN_IPV6=$(get_webpa "$cmac" "Device.DeviceInfo.X_COMCAST-COM_WAN_IPv6")

    # -------- Logging ----------
    log_msg "Active WAN Interface  = ${CurActive_Intf:-NULL}"
    log_msg "Standby WAN Interface = ${CurStandBy_Intf:-NULL}"
    log_msg "Available Mode        = ${Available_List:-NONE}"
    log_msg "Active Modes          = ${Active_List:-NONE}"
    log_msg "WAN IPv4              = ${WAN_IPV4:-NULL}, WAN IPv6 = ${WAN_IPV6:-NULL}"

    # -------- State validation ----------
    case "$state" in
        Pre-Failover|WanRestore)

            [[ "$CurActive_Intf" != "erouter0" ]] && { log_msg "[FAIL] Active interface should be erouter0"; ok=false; }
            [[ "$CurStandBy_Intf" != "brRWAN" ]] && { log_msg "[FAIL] Standby interface should be brRWAN"; ok=false; }

            [[ -z "$WAN_IPV4" || -z "$WAN_IPV6" ]] && { log_msg "[FAIL] WAN IPs must NOT be NULL"; ok=false; }

            # Validate Active / Available by gw_mode
            if [[ "$gw_mode" == "DOCSIS" ]]; then
                [[ "$Active_List" != "DOCSIS" ]] && { log_msg "[FAIL] Active Interfaces should be DOCSIS"; ok=false; }
                [[ ! "$Available_List" =~ DOCSIS || ! "$Available_List" =~ REMOTE_LTE ]] && { log_msg "[FAIL] Available Interfaces should include DOCSIS & REMOTE_LTE"; ok=false; }
            elif [[ "$gw_mode" == "Ethernet" ]]; then
                [[ "$Active_List" != "WANOE" ]] && { log_msg "[FAIL] Active Interfaces should be WANOE"; ok=false; }
                [[ ! "$Available_List" =~ WANOE || ! "$Available_List" =~ REMOTE_LTE ]] && { log_msg "[FAIL] Available Interfaces should include WANOE & REMOTE_LTE"; ok=false; }
            fi
            ;;

        WFO)
            [[ "$CurActive_Intf" != "brRWAN" ]] && { log_msg "[FAIL] Active interface should be brRWAN"; ok=false; }
            [[ "$CurStandBy_Intf" != "erouter0" ]] && { log_msg "[FAIL] Standby interface should be erouter0"; ok=false; }

            [[ -z "$WAN_IPV4" || -n "$WAN_IPV6" ]] && { log_msg "[FAIL] WAN IPs should be NULL during WFO"; ok=false; }

            [[ "$Active_List" != "REMOTE_LTE" ]] && { log_msg "[FAIL] Active Interfaces should be REMOTE_LTE; current value is $Active_List"; ok=false; }

            # Validate Active / Available by gw_mode
            #if [[ "$gw_mode" == "DOCSIS" ]]; then
            #    [[ "$Active_List" != "REMOTE_LTE" ]] && { log_msg "[FAIL] Active Interfaces should be REMOTE_LTE; current value is $Active_List"; ok=false; }
            #elif [[ "$gw_mode" == "Ethernet" ]]; then
            #    [[ "$Active_List" != "REMOTE_LTE" ]] && { log_msg "[FAIL] Active Interfaces should be REMOTE_LTE; current value is $Active_List"; ok=false; }
            #fi
            ;;

        *)
            log_msg "[ERROR] Unknown STATE=$state"
            ok=false
            ;;
    esac

    # -------- Result ----------
    if $ok; then
        log_msg "[INFO] $state validation looks good"
        return 0
    else
        log_msg "[ERROR] ($state) validation FAILED. Please refer logs $LOG_FILE"
        return 1
    fi
}


#=====================================================================
# MAIN SCRIPT EXECUTION
#=====================================================================

#phase1_validate || exit 1
if ! phase1_validate; then
    PHASE1_OK=false
fi

#phase2_validate "Pre-Failover" || log_msg "Pre-Failover state invalid"
if ! phase2_validate "Pre-Failover"; then
    PRE_OK=false
fi

log_msg "Sleeping 10s before WAN Failover..."
sleep 10

###############################################################
# Trigger WAN Failover
log_msg "Triggering WAN Failover..."
if [[ "$gw_mode" == "DOCSIS" ]]; then
    name="Device.X_RDK_DOCSIS.LinkDown"; value="true"; type="3"
else
    name="Device.X_RDKCENTRAL-COM_EthernetWAN.LinkDown"; value="true"; type="3"
fi
set_webpa "$cmac" "$name" "$value" "$type"


log_msg "Waiting 90s after Wan Failover Trigerred..."
sleep 90

if ! phase2_validate "WFO"; then
    WFO_OK=false
fi
#phase2_validate "WFO" || log_msg "WFO state invalid"

sleep 30
##############################################################

log_msg "Triggering WAN Restore..."

# Trigger WAN Restore
if [[ "$gw_mode" == "DOCSIS" ]]; then
    name="Device.X_RDK_DOCSIS.LinkDown"; value="false"; type="3"
else
    name="Device.X_RDKCENTRAL-COM_EthernetWAN.LinkDown"; value="false"; type="3"
fi
set_webpa "$cmac" "$name" "$value" "$type"

log_msg "Waiting 90s after Wan Restore Triggered..."
sleep 90

if ! phase2_validate "WanRestore"; then
    RESTORE_OK=false
fi
#phase2_validate "WanRestore" || log_msg "Restore state invalid"

sleep 2

##############################################################
#Re-Check the detail after WAN Restore

#phase1_validate || exit 1

##############################################################

name="Device.X_RDK_WanManager.RestorationDelay"; value="300"; type="2"
set_webpa "$cmac" "$name" "$value" "$type"

Restore_Delay=$(get_webpa "$cmac" "Device.X_RDK_WanManager.RestorationDelay")
log_msg "Restore Delay is reverted to $Restore_Delay seconds."

##########################################
# Final Result Evaluation
##########################################
LOG_URL="https://50.189.74.50/webdav/$(basename "$LOG_FILE")"

if ! $PHASE1_OK; then
    result="Failed"
    description="Failed — Gateway not ready for failover. Log: $LOG_URL"

elif ! $PRE_OK; then
    result="Failed"
    description="Pre-Failover validation failed. Log: $LOG_URL"

elif ! $WFO_OK; then
    result="Failed"
    description="WAN Failover state validation failed. Log: $LOG_URL"

elif ! $RESTORE_OK; then
    result="Failed"
    description="WAN Restore validation failed. Log: $LOG_URL"

else
    result="Passed"
    description="All validations passed: Pre-Failover, WFO, and Restore successful. Log: $LOG_URL"
fi

log_msg "FINAL RESULT: $result"
log_msg "FINAL DESCRIPTION: $description"

log_msg "Test script execution completed."

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

##########################################
# JSON Output
##########################################

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
