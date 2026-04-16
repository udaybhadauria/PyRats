import json
import sys
import time
import subprocess
import socket
import ipaddress
import re
from urllib.parse import urlencode
import importlib

test_name = "FlowManagerUDP"

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

def fetch_client_details():
    arp_output = subprocess.check_output(['arp', '-a'], text=True)
    for line in arp_output.splitlines():
        match = re.search(r'\(([\d\.]+)\).*ether.* ([\w:]+) +(\w+)$', line)
        if match and match.group(1).endswith('.1'):
            interface = match.group(3)
            # Get MAC for this interface
            addrs = netifaces.ifaddresses(interface)
            ip_info = addrs.get(netifaces.AF_INET, [{}])[0]
            ip_address = ip_info.get('addr')
            ipv6_info = addrs.get(netifaces.AF_INET6, [{}])[0]
            ipv6_address = ipv6_info.get('addr')
            mac_info = addrs.get(netifaces.AF_LINK, [{}])[0]
            mac_address = mac_info.get('addr')
            print(f"Interface: {interface}, MAC: {mac_address}")
            return ip_address, ipv6_address, mac_address
    return None, None, None

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
                print(f"[ERROR] WebPA get for {parameter} failed")
                result = "Failed"
                description = f"WebPA get for {parameter} failed"
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
            return True
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Webpa set of {parameter} failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"[ERROR] WebPA set for {parameter} failed")
                result = "Failed"
                description = f"WebPA set for {parameter} failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                return False

def set_dscp(client_mac, DSCP_Value):
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

    while attempt < max_retries:
        # payload
        data = {
            "action": "MARK_BOTH",
            "device_mac_list": [
                client_mac
            ],
            "dscp": DSCP_Value,
            "duration": 2,
            "timezone": "PT"
        }

        # Encode the JSON object
        encoded_data = urlencode({"json": json.dumps(data)})
        encoded_json = encoded_data.split("=")[1]

        # Add Device Prioritization Rule
        subdoc = "prioritizedmacs"
        post_command = f"java -jar {utility_path} blob_enable {mac_address} {subdoc} {encoded_json}"
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
            print("Device Prioritization blob set Success")
            return
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"Device prioritization blob set failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("[ERROR] Webcfg add for Device prioritization rule failed")
                result = "Failed"
                description = f"Webcfg add for Device prioritization rule failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python3 flowmanagerUDP_LAN.py <test_ID> <mac_address> <webserver_ipv4> <webserver_ipv6>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    SERVER_IPv4 = sys.argv[3]
    SERVER_IPv6 = sys.argv[4]

    # Install required system packages
    packages_to_install = ['python3-pip']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    # Install required python packages
    required_python_packages = ['netifaces']
    for package in required_python_packages:
        ok, message = check_python_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    import netifaces

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    runParam = "Device.X_RDK_AutomationTest.Run"
    statusParam = "Device.X_RDK_AutomationTest.Status"
    resultParam = "Device.X_RDK_AutomationTest.Result"

    testSupport = webpa_get(runParam)
    if testSupport is None or testSupport.lower() == "null":
        result = "NoConf"
        description = "RATS Automation test is not configured in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        time.sleep(5)
        sys.exit(1)
    elif testSupport == "Test not enabled":
        result = "Failed"
        description = f"{testSupport}, Create the file /nvram/rats_enabled on the gateway to enable testing"
        write_test_result_to_json(mac_address, test_ID, result, description)
        time.sleep(5)
        sys.exit(1)
    elif testSupport == "Library for Automation test is unavailable":
        result = "Failed"
        description = f"{testSupport}, so validation cannot be performed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        time.sleep(5)
        sys.exit(1)

    # --------------------------------------------------------------------------------

    src_ip, src_ipv6, mac = fetch_client_details()
    if src_ip and src_ipv6 and mac:
        print(f"Client IP address: {src_ip}")
        print(f"Client IPv6 address: {src_ipv6}")
        client_mac = mac.lower().replace(":", "")
        print(f"Client mac: {client_mac}")
    else:
        print("[ERROR] Unable to retrieve client IP, IPv6 or MAC address")
        result = "Failed"
        description = "Unable to retrieve client IP, IPv6 or MAC address"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # -------------------- IPv4 UDP connection validation ----------------------------
    
    SRC_PORT = 22223
    DST_PORT = 33333
    PACKET_COUNT = 100

    # DSCP value set
    dscp = 26
    set_dscp(client_mac, dscp)

    time.sleep(10)
    print("Validating UDP IPv4")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", SRC_PORT))  # Bind source port
    sock.settimeout(2)  # Set timeout to 2 seconds per packet

    value = f"FlowManager%7Csrcip={src_ip}%7Cdstip={SERVER_IPv4}%7Cprotocol=udp%7Csrcport={SRC_PORT}%7Cdstport={DST_PORT}%7Ccount={PACKET_COUNT}%7Cdscp={dscp}"
    print(f"input - {value}")
    res = webpa_set(runParam, value, 0)
    if not res:
        sock.close()
        sys.exit(1)

    # Send request
    message = "RATS Test"
    print("Start sending v4 packet")
    for _ in range(PACKET_COUNT):
        sock.sendto(message.encode(), (SERVER_IPv4, DST_PORT))
        try:
            data, addr = sock.recvfrom(1024)
            print("Received from server:", data.decode("utf-8", errors="ignore"))
        except socket.timeout:
            print("No response received")

    sock.close()
    print("Socket closed")

    time.sleep(420)

    retry_count = 5
    attempt = 0

    while attempt < retry_count:
        FMresult = webpa_get(statusParam)
        FMdescription = webpa_get(resultParam)
        if FMresult not in ["Passed", "Failed"]:
            attempt += 1
            if attempt < retry_count:
                print(f"Attempt {attempt}: No Results available. Retrying in 15 seconds...")
                time.sleep(15)
            else:
                result1 = "Failed"
                description1 = "No result available in the device"
        else:
            result1 = FMresult
            description1 = FMdescription
            break
    print(f"UDP IPv4 description: {description1}")

    time.sleep(30)
    # -------------------------------------------------------------------------------------------------

    # -------------------- IPv6 UDP connection validation ---------------------------------------------

    SRC_PORT = 22224
    DST_PORT = 33334
    PACKET_COUNT = 100

    # DSCP value set
    dscp = 40
    set_dscp(client_mac, dscp)

    time.sleep(10)

    print(f"source ipv6: {src_ipv6}")
    src_ip6 = ipaddress.IPv6Address(src_ipv6).exploded
    dst_ip6 = ipaddress.IPv6Address(SERVER_IPv6).exploded

    print("Validating UDP IPv6")
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.bind(("::", SRC_PORT)) # Bind source port
    sock.settimeout(2)  # Set timeout to 2 seconds per packet

    value = f"FlowManager%7Csrcip={src_ip6}%7Cdstip={dst_ip6}%7Cprotocol=udp%7Csrcport={SRC_PORT}%7Cdstport={DST_PORT}%7Ccount={PACKET_COUNT}%7Cdscp={dscp}"
    print(f"input - {value}")
    res = webpa_set(runParam, value, 0)
    if not res:
        sock.close()
        sys.exit(1)

    # Send request
    message = "RATS Test"
    print("Start Sending v6 packet")
    for _ in range(PACKET_COUNT):
        sock.sendto(message.encode(), (SERVER_IPv6, DST_PORT))
        try:
            data, addr = sock.recvfrom(1024)
            print("Received from server:", data.decode("utf-8", errors="ignore"))
        except socket.timeout:
            print("No response received")

    sock.close()
    print("Socket closed")

    time.sleep(420)

    retry_count = 5
    attempt = 0

    while attempt < retry_count:
        FMresult = webpa_get(statusParam)
        FMdescription = webpa_get(resultParam)
        if FMresult not in ["Passed", "Failed"]:
            attempt += 1
            if attempt < retry_count:
                print(f"Attempt {attempt}: No Results available. Retrying in 15 seconds...")
                time.sleep(15)
            else:
                result2 = "Failed"
                description2 = "No result available in the device"
        else:
            result2 = FMresult
            description2 = FMdescription
            break
    print(f"UDP IPv6 description: {description2}")
    # --------------------------------------------------------------------------------------------------------

    if result1 == "Passed" and result2 == "Passed":
        result = "Passed"
    else:
        result = "Failed"

    description = f"IPv4 - {description1}, IPv6 - {description2}"

    write_test_result_to_json(mac_address, test_ID, result, description)
    sys.exit(1)
