import importlib
import subprocess
import sys
import json
from urllib.parse import urlencode

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

# List of packages to check and install
packages_to_install = ['python3-pip', 'libpcap-dev']

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
required_python_packages = ['scapy', 'netifaces']
for package in required_python_packages:
    check_python_package(package)

from scapy.all import *
import netifaces

test_name = "XMBoostDevicePrioritization"
DSCPPacketReceived = False
UnexpectedDSCP = False
PacketReceived = False
DSCPMarked = False

def process_DSCP_packet(packet, expected_DSCP):
    global DSCPPacketReceived
    global UnexpectedDSCP
    DSCPPacketReceived = True
    ip_header = packet[IP]
    if ip_header.version == 4:
        dscp = (ip_header.tos & 0xfc) >> 2
        if dscp != 0:
            print("DSCP field: {} (0x{:x})".format(dscp, dscp))
            if dscp != expected_DSCP:
                UnexpectedDSCP = True

def process_packet(packet):
    global PacketReceived
    global DSCPMarked
    PacketReceived = True
    ip_header = packet[IP]
    if ip_header.version == 4:
        dscp = (ip_header.tos & 0xfc) >> 2
        if dscp != 0:
            print("DSCP field: {} (0x{:x})".format(dscp, dscp))
            DSCPMarked = True

def check_private_interfaces():
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
        if addrs:
            for addr_info in addrs:
                ip_address = addr_info['addr']
                if ip_address.startswith('10.') or ip_address.startswith('172.') or ip_address.startswith('192.168'):
                    client_mac = netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
                    print("Network interface: {}, Private ip address: {}, Client MAC Address: {}".format(interface, ip_address, client_mac))
                    return interface, ip_address, client_mac
    return None, None, None

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
        description = f"Failed to get the value of {parameter}"
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
        print(f"Successfully added the {subdoc} Rule")
        return True
    else:
        print("Failed to add the Rule")
        return False

def test_devicePrioritization(mac_address, client_mac, DSCP_Value):
    print("Testing Device Prioritization with DSCPValue: ", DSCP_Value)
    global DSCPPacketReceived; DSCPPacketReceived = False
    global UnexpectedDSCP; UnexpectedDSCP = False
    global PacketReceived; PacketReceived = False
    global DSCPMarked; DSCPMarked = False
    testFlag = False

    # payload
    data = {
        "action": "MARK_DOWNSTREAM",
        "device_mac_list": [
            client_mac
        ],
        "dscp": DSCP_Value,
        "duration": 1,
        "timezone": "PT"
    }

    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Add Device Prioritization Rule
    subdoc = "prioritizedmacs"
    response = set_blob(mac_address, subdoc, encoded_json)
    if not response:
        result = "Failed"
        description = f"Device prioritization Blob set with DSCPMarking Value {DSCP_Value} Failed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        testFlag = True
        return testFlag

    sniff(filter="ip dst {} and (ip[1] & 0xfc) >> 2 != 0".format(ip_address), prn=lambda x: process_DSCP_packet(x, DSCP_Value), iface=interface, store=0, timeout=60)

    if DSCPPacketReceived:
        if UnexpectedDSCP:
            result = "Failed"
            description = f"DSCPMarking value received does not match with the expected DSCPMarking Value {DSCP_Value}"
            write_test_result_to_json(mac_address, test_ID, result, description)
            testFlag = True
        else:
            print("After removing device prioritization configuration with DSCPMarking Value: ", DSCP_Value)
            sniff(filter="ip dst {}".format(ip_address), prn=process_packet, iface=interface, store=0, timeout=30)
            if PacketReceived:
                if DSCPMarked:
                    result = "Failed"
                    description = f"Packets received with non zero DSCPMarking value, after removing the device prioritization configuration with DSCPMarking Value {DSCP_Value}"
                    write_test_result_to_json(mac_address, test_ID, result, description)
                    testFlag = True
            else:
                result = "Failed"
                description = f"No packets received within the 30-second timeout period, after removing the device prioritization configuration with DSCPMarking Value {DSCP_Value}"
                write_test_result_to_json(mac_address, test_ID, result, description)
                testFlag = True
    else:
        result = "Failed"
        description = f"No packets received within the 60-second timeout period, after set the device prioritization configuration with DSCPMarking Value {DSCP_Value}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        testFlag = True

    return testFlag

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 xmDevicePrioritization.py <test_ID> <mac_address>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    pvdEnable = webpa_get(mac_address, pvdParameter)
    print(f"Speedboost feature - {pvdEnable}")
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    interface, ip_address, mac = check_private_interfaces()
    if mac:
        client_mac = mac.lower().replace(":", "")
    else:
        result = "Failed"
        description = "Failed to fetch the client details"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    data = {
        "device_mac_list": [client_mac],
        "duration": 9
    }

    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Add speedboost client
    subdoc = "xmspeedboost"
    response = set_blob(mac_address, subdoc, encoded_json)
    if not response:
        result = "Failed"
        description = "Failed to add the XMBoost Client"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    time.sleep(15)
    # Start the ping to 8.8.8.8
    ping_process = subprocess.Popen(["ping", "8.8.8.8"])

    dscpvalues = [8, 40, 45, 46, 56]
    for value in dscpvalues:
        testFlag = test_devicePrioritization(mac_address, client_mac, value)
        if testFlag:
            ping_process.kill()
            sys.exit(1)

    ping_process.kill()
    result = "Passed"
    description = "All DSCPMarking values received matched with expected DSCPMarking Values, Device Prioritization Validation Success!"
    write_test_result_to_json(mac_address, test_ID, result, description)

