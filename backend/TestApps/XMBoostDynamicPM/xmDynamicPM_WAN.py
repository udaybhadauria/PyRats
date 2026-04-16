import subprocess
import sys
import json
import time
from urllib.parse import quote

test_name = "XMBoostDynamicPM"
timeout = 15
Success = '\u2714'  # ?
Failure = '\u274C' # ?

def test_website_access(website):
    try:
        # Run the curl command to access the website and capture the output
        curl_process = subprocess.run(['curl', '-I', website], capture_output=True, text=True, timeout=timeout)

        # Check the return code of the subprocess
        if curl_process.returncode == 0:
            # Check if the HTTP response code is 200 (OK)
            if 'HTTP/1.1 200 OK' in curl_process.stdout:
                result = "Success"
            else:
                result = "Failure"
        else:
            result = "Failure"
    except Exception as e:
        result = "Failure"
    return result

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

def webpa_get(mac_address, parameter):
    getValue = None
    max_retries = 3
    retry_delay = 10 # seconds
    attempt = 0

    while attempt < max_retries:
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
            return getValue
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Attempt {attempt}: Failed to get the value of {parameter}, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Attempt {attempt}: Failed to get the value of {parameter} after {max_retries} attempts.")
                print(f"Aborted, Webpa request to get {parameter} failed after multiple attempts")
                write_test_result_to_json(mac_address, test_ID, "Failed", f"Aborted, Webpa request to get {parameter} failed after multiple attempts")
                sys.exit(1)

def webpa_set(mac_address, parameter, value, type):
    max_retries = 3
    retry_delay = 10 # seconds
    attempt = 0

    while attempt < max_retries:
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
            attempt += 1
            if attempt < max_retries:
                print(f"Attempt {attempt}: Failed to set the value of {parameter}, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Aborted, Webpa request to set {parameter} failed after multiple attempts")
                return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 xmDynamicPM_WAN.py <test_ID> <mac_address> <gateway_wan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    pvdEnable = webpa_get(mac_address, pvdParameter)
    print(f"speedboost feature - {pvdEnable}")
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if len(sys.argv) == 4:
        gateway_ip = sys.argv[3]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        gateway_ip = webpa_get(mac_address, parameter)

    time.sleep(50)

    # ----------- Case 1: Validate Dynamic PortMapping for a port within speedboost port range 40001 - 41000 -------
    print("-------- Validate Dynamic PortMapping for a port within speedboost port range 40001 - 41000 --------")
    port = 40500
    website = "http://"+gateway_ip+":"+str(port)+"/"

    # Disable speedboost feature
    print("Disable speedboost feature")
    res = webpa_set(mac_address, pvdParameter, False, 3)
    if not res:
        description = "Aborted, Webpa request to disable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature disabled")
    disableResult = test_website_access(website)
    print(f"xmboost disable - {disableResult}")
    if disableResult == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    print("Enable speedboost feature")
    res =  webpa_set(mac_address, pvdParameter, True, 3)
    if not res:
        description = "Aborted, Webpa request to enable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature enabled")
    enableResult = test_website_access(website)
    print(f"xmboost enable - {enableResult}")
    if enableResult == "Success":
        time.sleep(timeout)
    print("Testing with speedboost port range 40001 - 41000 completed")

    if disableResult == "Success" and enableResult == "Failure":
        result1 = "Passed"
    else:
        result1 = "Failed"

    disableStatus = Success if disableResult == "Success" else Failure
    enableStatus = Success if enableResult == "Failure" else Failure
    description1 = f"40001-41000port{port}[XM Disable:{disableStatus},Enable:{enableStatus}]"
    # ----------------------------------------------------------------------------------------------------------------------

    # ----------- Case 2: Validate Dynamic PortMapping for a port within speedboost port range 45001 - 46000 -------
    time.sleep(35)
    print("--------- Validate Dynamic PortMapping for a port within speedboost port range 45001 - 46000 --------")
    port = 45500
    website = "http://"+gateway_ip+":"+str(port)+"/"

    # Disable speedboost feature
    print("Disable speedboost feature")
    res = webpa_set(mac_address, pvdParameter, False, 3)
    if not res:
        description = "Aborted, Webpa request to disable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature disabled")
    disableResult = test_website_access(website)
    print(f"xmboost disable - {disableResult}")
    if disableResult == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    print("Enable speedboost feature")
    res =  webpa_set(mac_address, pvdParameter, True, 3)
    if not res:
        description = "Aborted, Webpa request to enable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature enabled")
    enableResult = test_website_access(website)
    print(f"xmboost enable - {enableResult}")
    if enableResult == "Success":
        time.sleep(timeout)
    print("Testing with speedboost port range 45001 - 46000 completed")

    if disableResult == "Success" and enableResult == "Failure":
        result2 = "Passed"
    else:
        result2 = "Failed"
    disableStatus = Success if disableResult == "Success" else Failure
    enableStatus = Success if enableResult == "Failure" else Failure
    description2 = f"45001-46000port{port}[XM Disable:{disableStatus},Enable:{enableStatus}]"
    # ----------------------------------------------------------------------------------------------------------------------

    # ----------- Case 3: Validate Dynamic PortMapping for a port 47100 without & within speedboost port range 47001 - 48000 -------
    time.sleep(35)
    print("--------- Validate Dynamic PortMapping for a port without & within speedboost port range 47001 - 48000 --------")
    port = 47100
    website = "http://"+gateway_ip+":"+str(port)+"/"

    # Disable speedboost feature
    print("Disable speedboost feature")
    res = webpa_set(mac_address, pvdParameter, False, 3)
    if not res:
        description = "Aborted, Webpa request to disable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature disabled")
    disableResult1 = test_website_access(website)
    print(f"xmboost disable - {disableResult1}")
    if disableResult1 == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    print("Enable speedboost feature")
    res = webpa_set(mac_address, pvdParameter, True, 3)
    if not res:
        description = "Aborted, Webpa request to enable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature enabled")
    enableResult1 = test_website_access(website)
    print(f"xmboost enable - {enableResult1}")
    if enableResult1 == "Success":
        time.sleep(timeout)

    # Enable speedboost port range with 47100 port, Set speedboost port range to 47001 - 48000
    print("Setting speedboost port range to 47001 - 48000")
    xmPortParameter = "Device.X_RDK_Speedboost.PortRanges"
    xmPortRange = "IPv4 BOTH 47001 48000,IPv6 BOTH 47001 48000"
    xmport_range = quote(xmPortRange)
    res = webpa_set(mac_address, xmPortParameter, xmport_range, 0)
    if not res:
        description = f"Aborted, Webpa request to set speedboost port range {xmPortRange} failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)

    # Disable speedboost feature
    print("Disable speedboost feature")
    res = webpa_set(mac_address, pvdParameter, False, 3)
    if not res:
        description = "Aborted, Webpa request to disable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature disabled")
    disableResult2 = test_website_access(website)
    print(f"xmboost disable - {disableResult2}")
    if disableResult2 == "Success":
        time.sleep(timeout)

    # Enable speedboost feature
    print("Enable speedboost feature")
    res = webpa_set(mac_address, pvdParameter, True, 3)
    if not res:
        description = "Aborted, Webpa request to enable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, "Failed", description)
        sys.exit(1)
    time.sleep(timeout)

    print("Test the website when speedboost feature enabled")
    enableResult2 = test_website_access(website)
    print(f"xmboost enable - {enableResult2}")
    if enableResult2 == "Success":
        time.sleep(timeout)
    print("Testing with speedboost port range 47001 - 48000 completed")

    if disableResult1 == "Success" and enableResult1 == "Success" and disableResult2 == "Success" and enableResult2 == "Failure":
        result3 = "Passed"
    else:
        result3 = "Failed"

    disableStatus1 = Success if disableResult1 == "Success" else Failure
    enableStatus1 = Success if enableResult1 == "Success" else Failure
    disableStatus2 = Success if disableResult2 == "Success" else Failure
    enableStatus2 = Success if enableResult2 == "Failure" else Failure
    description3 = f"45001-46000port{port}[XM Disable:{disableStatus1},Enable:{enableStatus1}] 47100-48000port{port}[Disable:{disableStatus2},Enable:{enableStatus2}]"
    #----------------------------------------------------------------------------------------------------------------------------
    if result1 == "Passed" and result2 == "Passed" and result3 == "Passed":
        result = "Passed"
    else:
        result = "Failed"
    description = f"ConnectionStatus:{description1} {description2} {description3}"
    print(f"result = {result}, description = {description}")
    write_test_result_to_json(mac_address, test_ID, result, description)
