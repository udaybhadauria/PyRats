import sys
import subprocess
import time
import json
import importlib

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

import netifaces
from scapy.all import *

test_name = "XMBoostRA"

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

def get_private_interfaces():
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
        if addrs:
            for addr_info in addrs:
                ip_address = addr_info['addr']
                if ip_address.startswith('10.') or ip_address.startswith('172.') or ip_address.startswith('192.168'):
                    return interface
    return None

# Extract and log Option 21 info
def handle_option21_bytes(option_bytes, packet_num):
    if len(option_bytes) >= 6:
        flags = option_bytes[2]
        H_flag = (flags >> 7) & 1
        L_flag = (flags >> 6) & 1
        R_flag = (flags >> 5) & 1
        delay = flags & 0x0F
        sequence_number = int.from_bytes(option_bytes[3:5], 'big')

        print(f'Packet #{packet_num} - Option 21 found!')
        hexdump(option_bytes)
        print(f'H flag: {H_flag}')
        print(f'L flag: {L_flag}')
        print(f'R flag: {R_flag}')
        print(f'Delay: {delay}')
        print(f'Sequence Number: {sequence_number}')
    else:
        print(f'Packet #{packet_num} - Option 21 is too short to parse.')

def process_packet(packet):
    global icmpv6_ra_counter
    global XMRAPacket
    global NoXMRAPacket

    if IPv6 in packet and ICMPv6ND_RA in packet:
        icmpv6_ra_counter += 1
        print(f'Router Advertisement (RA) packet found. Packet number: {icmpv6_ra_counter}')

        found_option21 = False

        # Try Scapy-parsed layers first
        next_layer = packet[ICMPv6ND_RA].payload
        while next_layer:
            if isinstance(next_layer, ICMPv6NDOptUnknown) and next_layer.type == 21:
                print(f'Packet #{icmpv6_ra_counter} - Option 21 found via ICMPv6NDOptUnknown')
                handle_option21_bytes(bytes(next_layer), icmpv6_ra_counter)
                found_option21 = True
                XMRAPacket = True
                break
            next_layer = next_layer.payload

        # Fallback: Check raw bytes
        if not found_option21 and packet.haslayer('Raw'):
            raw = packet['Raw'].load
            try:
                offset = raw.index(b'\x15')
                option21_data = raw[offset:offset+6]  # minimum 6 bytes expected
                print(f'Packet #{icmpv6_ra_counter} - Option 21 found via Raw fallback')
                handle_option21_bytes(option21_data, icmpv6_ra_counter)
                found_option21 = True
                XMRAPacket = True
            except ValueError:
                pass  # \x15 not found

        if not found_option21:
            print(f'Packet #{icmpv6_ra_counter} - Option 21 not found in packet.')
            NoXMRAPacket = True
    else:
        print(f'Packet Does not contain IPv6 or ICMPv6ND_RA')

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
            response_body = line[start_index + len("Responxse_Body="):]
    if response_code == 200 and 'Success' in response_body:
       print("Webpa set Success")
       return True
    else:
        print("Webpa set Failed")
        return False

if __name__ == "__main__":
    global icmpv6_ra_counter
    global XMRAPacket
    global NoXMRAPacket

    if len(sys.argv) != 3:
        print("Usage: python3 XMBoostRA.py <test_ID> <mac_address>")
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

    # Find private network interfaces
    iface = get_private_interfaces()
    print(f"interface = {iface}")

    enableTest = False
    disableTest = False

    # Enable xmboost if it is disabled by default
    if pvdEnable == "false":
        response = webpa_set(mac_address, pvdParameter, True, 3)
        if not response:
            result = "Failed"
            description = "Failed to enable speedboost feature"
            write_test_result_to_json(mac_address, test_ID, result, description)
            sys.exit(1)
        time.sleep(15)

    icmpv6_ra_counter = 0
    XMRAPacket = False
    NoXMRAPacket = False

    sniff(prn=process_packet, filter='icmp6', iface=iface, timeout=60, store=0)
    if icmpv6_ra_counter > 0:
       if XMRAPacket and not NoXMRAPacket:
           enableTest = True
           description1 = "XMBoost enabled - Success"
       else:
           description1 = "XMBoost enabled - Didn't recived XMBoost Router Advertisement"
    else:
        description1 = "XMBoost enabled - Didn't received any Router Advertisement"

    # Disable xmboost
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Failed to disable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)
    time.sleep(15)

    icmpv6_ra_counter = 0
    XMRAPacket = False
    NoXMRAPacket = False

    sniff(prn=process_packet, filter='icmp6', iface=iface, timeout=60, store=0)
    if icmpv6_ra_counter > 0:
       if NoXMRAPacket and not XMRAPacket:
           disableTest = True
           description2 = "XMBoost disabled - Success"
       else:
           description2 = "XMBoost disabled - Recived XMBoost Router Advertisement"
    else:
        description2 = "XMBoost disabled - Didn't received any Router Advertisement"

    # set default value
    webpa_set(mac_address, pvdParameter, pvdEnable, 3)

    if enableTest and disableTest:
        result = "Passed"
    else:
        result = "Failed"
    description = f"{description1}, {description2}"
    write_test_result_to_json(mac_address, test_ID, result, description)
    print('Packet capture completed')

