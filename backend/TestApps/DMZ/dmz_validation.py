import subprocess
import sys
import json
import time
from urllib.parse import urlencode
import importlib

test_name = "DMZ"

http_port = 25469
ssh_port = 26834
time_out = 15
subdoc = "wan"

def check_package(package_name):
    try:
        result = subprocess.run(['dpkg', '-l', package_name], capture_output=True, text=True)
        if 'ii  ' + package_name in result.stdout:
            print(f"{package_name} is already installed.")
            return True, f"{package_name} is already installed."
        else:
            print(f"{package_name} is not installed. Installing....")
            update_result = subprocess.run(['sudo', 'apt', 'update'])
            if update_result.returncode != 0:
                return False, f"Failed to run apt update for {package_name}"
            install_result = subprocess.run(['sudo', 'apt', 'install', '-y', package_name])
            if install_result.returncode != 0:
                return False, f"Failed to install system package: {package_name}"
            return True, f"{package_name} installed successfully."
    except subprocess.CalledProcessError as e:
        print(f"Error checking status of {package_name}: {e}.")
        return False, f"Error checking status of {package_name}: {e}."

def check_python_package(package):
    try:
        importlib.import_module(package)
        print(f"{package} is already installed.")
        return True, f"{package} is already installed."
    except ImportError:
        print(f"{package} is not installed. Installing...")
        try:
            # First try to install without breaking system packages
            subprocess.run(['sudo', 'pip', 'install', package], check=True)
            return True, f"{package} installed successfully."
        except subprocess.CalledProcessError:
            print(f"Failed to install {package} using pip. Trying with --break-system-packages.")
            try:
                # Try again with --break-system-packages option
                subprocess.run(['sudo', 'pip', 'install', package, '--break-system-packages'], check=True)
                return True, f"{package} installed successfully."
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package} with --break-system-packages: {e}")
                return False, f"Failed to install Python package: {package}. {e}"
    return False, f"Failed to install Python package: {package}"

def http_access(website):
    try:
        # Run the curl command to access the website and capture the output
        curl_process = subprocess.run(['curl', '--connect-timeout', str(time_out), '-I', website], capture_output=True, text=True)
        # Check the return code of the subprocess
        if curl_process.returncode == 0:
            # Check if the HTTP response code is 200 (OK)
            if 'HTTP/1.1 200 OK' in curl_process.stdout:
                result = "Passed"
                description = "HTTP service access Success"
            else:
                result = "Failed"
                description = "Failed to access HTTP service"
        else:
            result = "Failed"
            description = "Failed to access HTTP service"
    except Exception as e:
        result = "Failed"
        description = f"HTTP service access Failed: {str(e)}"

    return result, description

def ssh_connect(ip_address):
    try:
        # Create an SSH client instance
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the device using SSH with password authentication
        client.connect(ip_address, ssh_port, 'newtestuser', 'newtestuser@123', timeout=time_out, look_for_keys=False, allow_agent=False)

        # Close the SSH connection
        client.close()

        description = "SSH connection Success"
        return "Passed", description

    except Exception as e:
        description = f"SSH connection Failed: {str(e)}"
        return "Failed", description

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

def set_blob(json):
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

    while attempt < max_retries:
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
        if response_code == 200 and response_body and "POST Request Successful" in response_body:
            return True
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Blob enable failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("[ERROR] Failed to enable blob")
                return False

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
            return True, getValue
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Webpa get of {parameter} failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"[ERROR] WebPA get for {parameter} failed")
                result = "Failed"
                description = f"WebPA get for {parameter} failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                return False, getValue

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
        if response_code == 200 and response_body and "Success" in response_body:
            print("Webpa set Success")
            return True
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Webpa set of {parameter} failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"[ERROR] WebPA set for {parameter} failed")
                return False

def CheckDMZ():
    global host
    dmzEnabled = False
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

    while attempt < max_retries:
        get_command = f"java -jar {utility_path} blob_get {mac_address} {subdoc}"
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
            print("Successfully get the DMZ status")
            response_json = json.loads(response_body)
            response_data = response_json['output'].split('Response = ')
            json_data = json.loads(response_data[1])
            data = json_data['data']
            if data['dmz_enabled']:
                dmzEnabled = True
                host = data['dmz_host']
            return dmzEnabled
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"CheckDMZ failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("[ERROR] Webcfg fetch for DMZ status failed")
                result = "Failed"
                description = "Webcfg fetch for DMZ status failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)

def enable_dmz(dmzhost):
    data = {
        "dmz_enabled": True,
        "dmz_host": dmzhost,
    }

    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Enable the wan blob
    blobEnable = set_blob(encoded_json)
    return blobEnable

def disable_dmz():
    data = {
        "dmz_enabled": False,
    }

    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Disable wan blob
    blobDisable = set_blob(encoded_json)
    return blobDisable

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 dmz_validation.py <test_ID> <mac_address> <lanClient_IP> <gateway_wan_IP>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    client_ip = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    if len(sys.argv) == 5:
        gateway_ip = sys.argv[4]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        response, gateway_ip = webpa_get(parameter)
        if not response:
            sys.exit(1)
            
    packages_to_install = ['python3-pip']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    ok, message = check_python_package('paramiko')
    if not ok:
        write_test_result_to_json(mac_address, test_ID, "Failed", message)
        sys.exit(1)

    import paramiko

    # Check DMZ enabled
    dmzStatus = CheckDMZ()
    if dmzStatus:
        print("DMZ enabled already")

    # Enable DMZ
    blobEnable = enable_dmz(client_ip)
    time.sleep(15)
    if blobEnable:
        res1, dmzenable = webpa_get("Device.NAT.X_CISCO_COM_DMZ.Enable")
        if not res1:
            if dmzStatus:
                enable_dmz(host)
            sys.exit(1)

        res2, hostname = webpa_get("Device.NAT.X_CISCO_COM_DMZ.InternalIP")
        if not res2:
            if dmzStatus:
                enable_dmz(host)
            sys.exit(1)

        if dmzenable == "true" and hostname == client_ip:
            print("DMZ enable Successful")
        else:
            print("[ERROR] Failed to enable DMZ in device")
            result = "Failed"
            description = f"Failed to enable DMZ in device"
            write_test_result_to_json(mac_address, test_ID, result, description)
            if dmzStatus:
                enable_dmz(host)
            else:
                disable_dmz()
            sys.exit(1)
    else:
        print("[ERROR] Webcfg request to enable DMZ failed")
        result = "Failed"
        description = "Webcfg request to enable DMZ failed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        if dmzStatus:
            enable_dmz(host)
        sys.exit(1)

    # Check PF is enabled, if enabled disable it
    parameter = "Device.NAT.X_Comcast_com_EnablePortMapping"
    response, PFEnable = webpa_get(parameter)
    if not response:
        if dmzStatus:
            enable_dmz(host)
        else:
            disable_dmz()
        sys.exit(1)
    if PFEnable == "true":
        set_status = webpa_set(parameter, False, 3)
        if not set_status:
            print(f"[ERROR] WebPA set to disable Port Forwarding failed")
            result = "Failed"
            description = f"WebPA set to disable Port Forwarding failed"
            write_test_result_to_json(mac_address, test_ID, result, description)

            if dmzStatus:
                enable_dmz(host)
            else:
                disable_dmz()
            sys.exit(1)

    time.sleep(15)

    # Do HTTP & SSH request
    print("Try Http & SSH access")
    website = "http://"+gateway_ip+":"+str(http_port)+"/"
    print("Website URL:", website)
    httpResult, httpDescription = http_access(website)
    sshResult, sshDescription = ssh_connect(gateway_ip)
    if httpResult == "Passed" and sshResult == "Passed":
        result = "Passed"
    else:
        result = "Failed"
    description =f"{httpDescription}, {sshDescription}"
    
    print(f"[INFO] Test Result: {result}, Description: {description}")
    write_test_result_to_json(mac_address, test_ID, result, description)

     # Enable the PF rule
    if PFEnable == "true":
        webpa_set(parameter, True, 3)

    if dmzStatus:
        enable_dmz(host)
    else:
        disable_dmz()
