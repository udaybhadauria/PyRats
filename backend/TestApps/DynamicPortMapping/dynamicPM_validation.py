import subprocess
import sys
import json
import time

test_name = "DynamicPortMapping"

def test_website_access(website):
    try:
        # Run the curl command to access the website and capture the output
        curl_process = subprocess.run(['curl', '--connect-timeout', str(15), '-I', website], capture_output=True, text=True)

        # Check the return code of the subprocess
        if curl_process.returncode == 0:
            # Check if the HTTP response code is 200 (OK)
            if 'HTTP/1.1 200 OK' in curl_process.stdout:
                result = "Passed"
                description = "Successfully accessed the service running on LanClient, Dynamic PortMapping Validation Success!"
            else:
                result = "Failed"
                description = "Failed to access the service running on LanClient"
        else:
            result = "Failed"
            description = "Error occurred while accessing the service running on LanClient"
    except Exception as e:
        result = "Failed"
        description = "Error occurred: {}, while accessing the service running on LanClient".format(str(e))
    return result, description

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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 dynamicPF_validation.py <test_ID> <mac_address> <gateway_wan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    if len(sys.argv) == 4:
        gateway_ip = sys.argv[3]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        gateway_ip = webpa_get(mac_address, parameter)

    website = "http://"+gateway_ip+":16374/"

    time.sleep(15)
    print("Try to access LAN Client")
    result, description = test_website_access(website)

    write_test_result_to_json(mac_address, test_ID, result, description)
