import json
import sys
import time
import subprocess

test_name = "GWDHCPClientv6"

def write_test_result_to_json(mac_address, test_ID, result, description):
    test_result = {
        "Device_Mac": mac_address,
        "Test_ID": test_ID,
        "Result": result,
        "Description": description
    }

    file_name = f"test_results_{test_name}_{mac_address}.json"

    try:
        with open(file_name, 'r') as json_file:
            existing_data = json.load(json_file)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        existing_data = {"test_results": []}

    existing_data["test_results"].append(test_result)

    with open(file_name, 'w') as json_file:
        json.dump(existing_data, json_file, indent=4)

    print("Test result data has been written to", file_name)

def webpa_get(parameter):
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

    while attempt < max_retries:
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
            return getValue
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Webpa get of {parameter} failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                result = "Failed"
                description = f"Failed to get the value of {parameter}"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)

def webpa_set(parameter, value, type):
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

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
            break
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Webpa set of {parameter} failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to set the value of {parameter}")
                result = "Failed"
                description = f"Failed to set the value of {parameter}"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python3 DHCPClientv6Test.py <test_ID> <mac_address>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    runParameter = "Device.X_RDK_AutomationTest.Run"
    testSupport = webpa_get(runParameter)

    if testSupport is None or testSupport.lower() == "null":
        result = "NoConf"
        description = "RATS Automation test is not configured in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    elif testSupport == "Test not enabled":
        result = "Failed"
        description = f"{testSupport}, Create the file /nvram/rats_enabled on the gateway to enable testing"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    elif testSupport == "Library for Automation test is unavailable":
        result = "Failed"
        description = f"{testSupport}, so validation cannot be performed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    test = "DHCPClientv6"
    webpa_set(runParameter, test, 0)

    # Wait for the test to complete
    time.sleep(150)

    statusParameter = "Device.X_RDK_AutomationTest.Status"
    result = webpa_get(statusParameter)

    resultParameter = "Device.X_RDK_AutomationTest.Result"
    description = webpa_get(resultParameter)

   # Check if result is valid
    if result not in ["Passed", "Failed"]:
        result = "Failed"
        description = "No result available in the device"

    print(f"{description}")
    write_test_result_to_json(mac_address, test_ID, result, description)
