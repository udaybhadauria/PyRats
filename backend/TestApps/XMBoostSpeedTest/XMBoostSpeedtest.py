import sys
import json
import time
import subprocess
import importlib
from urllib.parse import urlencode

def check_package(package_name):
    try:
        result = subprocess.run(['dpkg', '-l', package_name], capture_output=True, text=True)
        if 'ii  ' + package_name in result.stdout:
            print(f"{package_name} is already installed.")
        else:
            print(f"{package_name} is not installed. Installing....")
            subprocess.run(['sudo', 'apt', 'update'])
            subprocess.run(['sudo', 'apt', 'install', '-y', package_name])
    except subprocess.CalledProcessError as e:
        print(f"Error checking status of {package_name}: {e}.")

# List of packages to check and install
packages_to_install = ['python3-pip', 'speedtest-cli']
for package in packages_to_install:
    check_package(package)

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

# List of required python packages
required_python_packages = ['netifaces']
for package in required_python_packages:
    check_python_package(package)

import netifaces
import speedtest

test_name = "XMBoostSpeedTest"

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

def fetchClientMac():
    client_mac = None
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
        if addrs:
            for addr_info in addrs:
                ip_address = addr_info['addr']
                if ip_address.startswith('10.') or ip_address.startswith('172.') or ip_address.startswith('192.168'):
                    client_mac = netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
    return client_mac

def webpa_set(mac_address, parameter, value, type):
    set_command = f"java -jar {utility_path} webpa_set {mac_address} {parameter} {value} {type}"
    set_response = subprocess.run(set_command, shell=True, capture_output=True, text=True).stdout

def test_speed():
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        iterations = 2
        total_download_speed = 0
        total_upload_speed = 0
        for i in range(iterations):
            download_speed = st.download() / 1024 / 1024  # Convert to Mbps
            upload_speed = st.upload() / 1024 / 1024  # Convert to Mbps
            total_download_speed = total_download_speed + download_speed
            total_upload_speed = total_upload_speed + upload_speed
        avg_download_speed = total_download_speed / iterations
        avg_upload_speed = total_upload_speed / iterations
        return avg_download_speed, avg_upload_speed
    except speedtest.ConfigRetrievalError as e:
        print(f"Error retrieving speedtest server configuration: {e}")
        result = "Failed"
        description = f"Error retrieving speedtest server configuration: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred in speedtest server: {e}")
        result = "Failed"
        description = f"An unexpected error occurred in speedtest server: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)

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
    else:
        print(f"Failed to get the value of {parameter}")
        result = "Failed"
        Description = "Failed to get the value of {pvdParameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    return getValue

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
        print("Successfully added the XMBoost Client")
        return True
    else:
        print("Failed to add XMBoost Client")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 XMBoostSpeedtest.py <test_ID> <mac_address>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    global pvdEnable
    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    pvdEnable = webpa_get(mac_address, pvdParameter)

    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    configSubStrings = ["xm2dsclassifiers75", "xm2dsclassifiers", "xmsingleclassifier1g", "xmsingleclassifier2g", "xmsingleclassifier75", "xmsingleclassifier"]

    configParameter = "Device.X_CISCO_COM_CableModem.DOCSISConfigFileName"
    configFileName = webpa_get(mac_address, configParameter)

    found = any(substring in configFileName for substring in configSubStrings)
    if found:
        print("Device has speedboost boot file")
    elif "xm" in configFileName:
        print("Device has speedboost boot file")
    else:
        result = "Failed"
        description = f"Speedboost boot file is not present in the device. Current boot file: {configFileName}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Enable speedboost if it is disabled
    if pvdEnable == "false":
        webpa_set(mac_address, pvdParameter, True, 3)
        Enabled = webpa_get(mac_address, pvdParameter)
        if Enabled != "true":
            result = "Failed"
            description = "Failed to enable SpeedBoost feature"
            write_test_result_to_json(mac_address, test_ID, result, description)
            sys.exit(1)

    download_speed, upload_speed = test_speed()
    print(f"Download Speed: {download_speed:.2f} Mbps")
    print(f"Upload Speed: {upload_speed:.2f} Mbps")

    client_mac = fetchClientMac().replace(":","")
    data = {
        "device_mac_list": [client_mac],
        "duration": 3
    }

    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Add Speedboost client
    subdoc = "xmspeedboost"
    response = set_blob(mac_address, subdoc, encoded_json)
    if not response:
        result = "Failed"
        description = "Failed to add the XMBoost Client"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)

    currentDevices = webpa_get(mac_address, "Device.X_RDK_Speedboost.CurrentDeviceList")
    if currentDevices:
        device_list = currentDevices.split(',')
        if client_mac in device_list:
            print("Speedboost client added")
        else:
            result = "Failed"
            description = "Failed to add the XMBoost Client"
            write_test_result_to_json(mac_address, test_ID, result, description)
            webpa_set(mac_address, pvdParameter, pvdEnable, 3)
            sys.exit(1)
    else:
        result = "Failed"
        description = "Failed to add the XMBoost Client"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)

    time.sleep(20)

    XM_download_speed, XM_upload_speed = test_speed()
    print(f"SpeedBoost Download Speed: {XM_download_speed:.2f} Mbps")
    print(f"SpeedBoost Upload Speed: {XM_upload_speed:.2f} Mbps")

    description = f"NonXMBoost Client(DownloadSpeed: {download_speed:.2f}Mbps, UploadSpeed: {upload_speed:.2f}Mbps) XMBoost Client(DownloadSpeed: {XM_download_speed:.2f}Mbps, UploadSpeed: {XM_upload_speed:.2f}Mbps)."
    if (XM_download_speed < download_speed):
        result = "Failed"
        description = f"{description} Download Speed is not Boosted"
    else:
        boosted_speed = XM_download_speed-download_speed
        result = "Passed"
        description = f"{description} DownloadSpeed Boosted: {boosted_speed:.2f} Mbps"
        print(f"Download speed boosted: {boosted_speed:.2f} Mbps")
    write_test_result_to_json(mac_address, test_ID, result, description)
    webpa_set(mac_address, pvdParameter, pvdEnable, 3)
