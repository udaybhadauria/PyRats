import sys
import subprocess
import json
import importlib
import time
from urllib.parse import quote, urlencode

def check_package(package_name):
    try:
        result = subprocess.run(['dpkg', '-l', package_name], capture_output=True, text=True)
        if 'ii  ' + package_name in result.stdout:
            print("{} is already installed.".format(package_name))
        else:
            print("{} is not installed. Installing...".format(package_name))
            subprocess.run(['sudo', 'apt', 'update'])
            subprocess.run(['sudo', 'apt', 'install', '-y', package_name])
    except subprocess.CalledProcessError as e:
        print("Error checking status of {}: {}".format(package_name, e))

check_package('python3-pip')

def check_python_package(package):
    try:
        importlib.import_module(package)
        print(f"{package} is already installed.")
    except ImportError:
        print(f"{package} is not installed. Installing...")
        try:
            # First try to install without breaking system packages
            subprocess.run(['sudo', 'pip', 'install', package], check=True)
        except subprocess.CalledProcessError:
            print(f"Failed to install {package} using pip. Trying with --break-system-packages.")
            try:
                # Try again with --break-system-packages option
                subprocess.run(['sudo', 'pip', 'install', package, '--break-system-packages'], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package} with --break-system-packages: {e}")

check_python_package('paramiko')

import paramiko

test_name = "XMBoostDMZ"
timeout = 15

def write_test_result_to_json(mac_address, test_ID, result, description):
    test_result = {
        "Device_Mac": mac_address,
        "Test_ID": test_ID,
        "Result": result,
        "Description": description
    }

    file_name = "test_results_{}_{}.json".format(test_name, mac_address)

    try:
        with open(file_name, 'r') as json_file:
            existing_data = json.load(json_file)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        existing_data = {"test_results": []}

    existing_data["test_results"].append(test_result)

    with open(file_name, 'w') as json_file:
        json.dump(existing_data, json_file, indent=4)

    print("Test result data has been written to", file_name)

def ssh_connect(ip_address, port, timeout):
    try:
        # Create an SSH client instance
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"port = {port}")
        # Connect to the device using SSH with password authentication
        client.connect(ip_address, port, 'testuser', 'testuser@123', look_for_keys=False, allow_agent=False, timeout=timeout)

        # Close the SSH connection
        client.close()

        return "Success"
    except Exception as e:
        return "Failure"

def webpa_get(mac_address, parameter):
    getValue = None
    get_command = f"java -jar {utility_path} webpa_get {mac_address} {parameter}"
    get_response = subprocess.run(get_command, shell=True, capture_output=True, text=True).stdout
    response_lines = get_response.splitlines()
    response_code = None
    response_body = None
    for line in response_lines:
        if line.startswith("Response_Code"):
            response_code = int(line.split('=')[1].strip())
        elif line.startswith("Response_Body"):
            start_index = line.find("Response_Body=")
            response_body = line[start_index + len("Response_Body="):]
    if response_code == 200:
        response_json = json.loads(response_body)
        data = json.loads(response_json['output'])
        for item in data:
            for key, value in item.items():
                if key == parameter:
                    getValue = value
        return True, getValue
    else:
        print(f"Failed to get the value of {parameter}")
        return False, getValue

def webpa_set(mac_address, parameter, value, type):
    set_command = f"java -jar {utility_path} webpa_set {mac_address} {parameter} {value} {type}"
    set_response = subprocess.run(set_command, shell=True, capture_output=True, text=True).stdout
    response_lines = set_response.splitlines()
    response_code = None
    response_body = None
    for line in response_lines:
        if line.startswith("Response_Code"):
            response_code = int(line.split('=')[1].strip())
        elif line.startswith("Response_Body"):
            start_index = line.find("Response_Body=")
            response_body = line[start_index + len("Response_Body="):]
    if response_code == 200 and 'Success' in response_body:
       print("Webpa set Success")
       return True
    else:
       print(f"Failed to set the value of {parameter}")
       return False

def set_blob(mac_address, subdoc, json):
    post_command = f"java -jar {utility_path} blob_enable {mac_address} {subdoc} {json}"
    post_response = subprocess.run(post_command, shell=True, capture_output=True, text=True).stdout
    response_lines = post_response.splitlines()
    response_code = None
    response_body = None
    for line in response_lines:
        if line.startswith("Response_Code"):
            response_code = int(line.split('=')[1].strip())
        elif line.startswith("Response_Body"):
            response_body = line

    if response_code == 200 and "POST Request Successful" in response_body:
        print("Successfully added the DMZ Rule")
        return True
    else:
        print("DMZ Blob set failed")
        return False

def enable_dmz():
    # payload
    data = {
        "dmz_enabled": True,
        "dmz_host": client_ip,
    }

    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Enable the wan blob
    subdoc = "wan"
    blobEnable = set_blob(mac_address, subdoc, encoded_json)
    if blobEnable:
        print("DMZ enable Successful")
        return True
    else:
        print("Failed to enable DMZ")
        return False

def disable_dmz():
    # payload
    data = {
        "dmz_enabled": False,
    }

    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Disable wan blob
    subdoc = "wan"
    blobDisable = set_blob(mac_address, subdoc, encoded_json)
    if blobDisable:
        print("DMZ disable Success")
    else:
       print("DMZ disable Failed")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 xmDMZ_WAN.py <test_ID> <mac_address> <lanclient_ip> <gateway_wan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    client_ip = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    response, pvdEnable = webpa_get(mac_address, pvdParameter)
    if not response:
        result = "Failed"
        description = "Failed to get the value of {pvdParameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    print(f"speedboost feature - {pvdEnable}")
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if len(sys.argv) == 5:
        gateway_ip = sys.argv[4]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        response, gateway_ip = webpa_get(mac_address, parameter)
        if not response:
            result = "Failed"
            description = "Failed to get the WAN IP"
            write_test_result_to_json(mac_address, test_ID, result, description)
            sys.exit(1)

    xmPortParameter = "Device.X_RDK_Speedboost.PortRanges"
    response, xmPort = webpa_get(mac_address, xmPortParameter)
    if not response:
        result = "Failed"
        description = "Failed to get the value of {xmPortParameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    defaultXmport = quote(xmPort)

    normalPortParameter = "Device.X_RDK_Speedboost.NormalPortRange"
    response, normalPort =  webpa_get(mac_address, normalPortParameter)
    if not response:
        result = "Failed"
        description = "Failed to get the value of {normalPortParameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    defaultNormalPort = quote(normalPort)

    # Enable DMZ
    enabledmz = enable_dmz()
    if not enabledmz:
        result = "Failed"
        description = "Failed to enable DMZ"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    #---------------------------- Case 1: Validate DMZ with speedboost port range 40001 - 41000 -----------------

    print("------Validate DMZ with speedboost port range 40001 - 41000----")
    # Disable speedboost feature
    print("Disable speedboost feature")
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Failed to disable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        disable_dmz()
        sys.exit(1)

    # Set speedboost port range to 40001 - 41000
    print("Setting speedboost port range to 40001 - 41000")
    xmPortRange = "IPv4 BOTH 40001 41000,IPv6 BOTH 40001 41000"
    xmport_range = quote(xmPortRange)
    response = webpa_set(mac_address, xmPortParameter, xmport_range, 0)
    if not response:
        result = "Failed"
        description = "Failed to set speedboost port range to 40001 - 41000"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        disable_dmz()
        sys.exit(1)

    # Set Normal port range to 50000 - 65000
    print("Setting Normal PortRange to 50000 - 65000")
    normalPortRange = "IPv4 BOTH 50000 65000,IPv6 BOTH 50000 65000"
    normalPort_range = quote(normalPortRange)
    response = webpa_set(mac_address, normalPortParameter, normalPort_range, 0)
    if not response:
        result = "Failed"
        description = "Failed to set Normal PortRange to 50000 - 65000"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Select one port within speedboost port range
    port = 40500

    # Run the SSH connection test when speedboost feature disabled
    print("Run the SSH connection test when speedboost feature disabled")
    disableResult =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm disabled: result = {disableResult}")
    if disableResult == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    response = webpa_set(mac_address, pvdParameter, True, 3)
    if not response:
        result = "Failed"
        description = "Failed to enable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Run the SSH connection test when speedboost feature enabled
    print("Run the SSH connection test when speedboost feature enabled")
    enableResult =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm enabled: result = {enableResult}")
    if enableResult == "Success":
        time.sleep(timeout)
    print("ssh test completed for speedboost port range 40001 - 41000")

    if disableResult == "Success" and enableResult == "Failure":
        result1 = "Passed"
    else:
        result1 = "Failed"
    description1 = f"PortRange 40001-41000[Disable-{disableResult},Enable-{enableResult}]"
    #-------------------------------------------------------------------------------------------------------------------------


    #---------------------------- Case 2: Validate DMZ with speedboost port range 45001 - 46000 -----------------

    print("------Validate DMZ with speedboost port range 45001 - 46000----")
    # Disable speedboost feature
    print("Disable speedboost feature")
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Failed to disable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)

    # Set speedboost port range to 45001 - 46000
    print("Setting speedboost port range to 45001 - 46000")
    xmPortRange = "IPv4 BOTH 45001 46000,IPv6 BOTH 45001 46000"
    xmport_range = quote(xmPortRange)
    response = webpa_set(mac_address, xmPortParameter, xmport_range, 0)
    if not response:
        result = "Failed"
        description = "Failed to set speedboost port range to 45001 - 46000"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Select one port within speedboost port range
    port = 45500

    # Run the SSH connection test when speedboost feature disabled
    print("Run the SSH connection test when speedboost feature disabled")
    disableResult =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm disabled: result = {disableResult}")
    if disableResult == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    response = webpa_set(mac_address, pvdParameter, True, 3)
    if not response:
        result = "Failed"
        description = "Failed to enable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        sys.exit(1)
    time.sleep(timeout)

    # Run the SSH connection test when speedboost feature enabled
    print("Run the SSH connection test when speedboost feature enabled")
    enableResult =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm enabled: result = {enableResult}")
    if enableResult == "Success":
        time.sleep(timeout)
    print("ssh test completed for speedboost port range 45001 - 46000")

    if disableResult == "Success" and enableResult == "Failure":
        result2 = "Passed"
    else:
        result2 = "Failed"
    description2 = f"PortRange 45001-46000[Disable-{disableResult},Enable-{enableResult}]"
    #-------------------------------------------------------------------------------------------------------------------------

    #------------------------ Case 3: Validate DMZ for port 47100 without and within speedboost range-----------------

    print("----------- Validate DMZ for port 47100 without and within speedboost range --------")
    # Select one port which is not in speedboost port range
    port = 47100

    # Disable speedboost feature
    print("Disable speedboost feature")
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Failed to disable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Run the SSH connection test when speedboost feature disabled
    print("Run the SSH connection test when speedboost feature disabled")
    disableResult1 =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm disabled: result = {disableResult1}")
    if disableResult1 == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    response = webpa_set(mac_address, pvdParameter, True, 3)
    if not response:
        result = "Failed"
        description = "Failed to enable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Run the SSH connection test when speedboost feature enabled
    print("Run the SSH connection test when speedboost feature enabled")
    enableResult1 =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm enabled: result = {enableResult1}")
    if enableResult1 == "Success":
        time.sleep(timeout)

    # Enable speedboost port range with 47100 port, Set speedboost port range to 47001 - 48000
    print("Setting speedboost port range to 47001 - 48000")
    xmPortRange = "IPv4 BOTH 47001 48000,IPv6 BOTH 47001 48000"
    xmport_range = quote(xmPortRange)
    response = webpa_set(mac_address, xmPortParameter, xmport_range, 0)
    if not response:
        result = "Failed"
        description = "Failed to set speedboost port range to 47001 - 48000"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)

    # Disable speedboost feature
    print("Disable speedboost feature")
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Failed to disable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Run the SSH connection test when speedboost feature disabled
    print("Run the SSH connection test when speedboost feature disabled")
    disableResult2 =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm disabled: result = {disableResult2}")
    if disableResult2 == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    response = webpa_set(mac_address, pvdParameter, True, 3)
    if not response:
        result = "Failed"
        description = "Failed to enable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        disable_dmz()
        sys.exit(1)
    time.sleep(timeout)

    # Run the SSH connection test when speedboost feature enabled
    print("Run the SSH connection test when speedboost feature enabled")
    enableResult2 =  ssh_connect(gateway_ip, port, timeout)
    print(f"xm enabled: result = {enableResult2}")
    if enableResult2 == "Success":
        time.sleep(15)
    print("ssh test completed for speedboost port range 47001 - 48000")

    if disableResult1 == "Success" and enableResult1 == "Success" and disableResult2 == "Success" and enableResult2 == "Failure":
        result3 = "Passed"
    else:
        result3 = "Failed"
    description3 = f"Port 47100 PortRange 45001-46000[Disable-{disableResult1},Enable-{enableResult1}], PortRange 47100-48000[Disable-{disableResult2},Enable-{enableResult2}]"

    #----------------------------------------------------------------------------------------------------------------------------
    if result1 == "Passed" and result2 == "Passed" and result3 == "Passed":
        result = "Passed"
    else:
        result = "Failed"
    description = f"SSH Connection status:({description1} {description2} {description3})"
    print(f"result = {result}, description = {description}")
    write_test_result_to_json(mac_address, test_ID, result, description)

    webpa_set(mac_address, pvdParameter, pvdEnable, 3)
    webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
    webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
    disable_dmz()

