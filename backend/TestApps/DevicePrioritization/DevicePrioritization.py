import importlib
import subprocess
import sys
import json
import time
import re
from urllib.parse import urlencode

test_name = "DevicePrioritization"

DSCPPacketReceived = False
UnexpectedDSCP = False
PacketReceived = False
DSCPMarked = False

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

def process_DSCP_packet(packet, expected_DSCP):
    global DSCPPacketReceived
    global UnexpectedDSCP
    DSCPPacketReceived = True
    ip_header = packet[IP]
    if ip_header.version == 4:
        dscp = (ip_header.tos & 0xfc) >> 2
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

def fetch_client_interface():
    # Run arp -a and parse output
    arp_output = subprocess.check_output(['arp', '-a'], text=True)
    for line in arp_output.splitlines():
        match = re.search(r'\(([\d\.]+)\).*ether.* ([\w:]+) +(\w+)$', line)
        if match and match.group(1).endswith('.1'):
            interface = match.group(3)
            # Get MAC for this interface
            addrs = netifaces.ifaddresses(interface)
            ip_info = addrs.get(netifaces.AF_INET, [{}])[0]
            mac_info = addrs.get(netifaces.AF_LINK, [{}])[0]
            mac_address = mac_info.get('addr')
            print(f"Interface: {interface}, MAC: {mac_address}")
            return interface, mac_address
    return None, None

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

def test_devicePrioritization(mac_address, client_mac, interface, DSCP_Value):
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

    # Add Device Prioritization Rule (retry up to 3 attempts)
    subdoc = "prioritizedmacs"
    post_command = f"java -jar {utility_path} blob_enable {mac_address} {subdoc} {encoded_json}"
    max_attempts = 3
    response_code = None
    response_body = None
    for attempt in range(1, max_attempts + 1):
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
            print("Successfully added the Device Prioritization Configuration")
            break

        if attempt < max_attempts:
            print(f"Blob apply failed. Retrying in 10 seconds... (Attempt {attempt}/{max_attempts})")
            time.sleep(10)
        else:
            result = "Failed"
            print(f"[ERROR] Webconfig request to apply device prioritization failed")
            description = f"Webconfig request to apply device prioritization failed"
            write_test_result_to_json(mac_address, test_ID, result, description)
            testFlag = True
            return testFlag

    time.sleep(5)
    sniff(filter="icmp and ether dst {}".format(client_mac), prn=lambda x: process_DSCP_packet(x, DSCP_Value), iface=interface, store=0, timeout=50)

    if DSCPPacketReceived:
        if UnexpectedDSCP:
            result = "Failed"
            description = f"Received DSCP value does not match expected value"
            write_test_result_to_json(mac_address, test_ID, result, description)
            testFlag = True
        else:
            time.sleep(10)
            print("After removing device prioritization configuration with DSCPMarking Value: ", DSCP_Value)
            sniff(filter="icmp and ether dst {}".format(client_mac), prn=process_packet, iface=interface, store=0, timeout=30)
            if PacketReceived:
                if DSCPMarked:
                    print("[ERROR] Packets still marked after device prioritization removal")
                    result = "Failed"
                    description = "Packets still marked after device prioritization removal"
                    write_test_result_to_json(mac_address, test_ID, result, description)
                    testFlag = True
            else:
                print("[ERROR] No packets received after removing device prioritization")
                result = "Failed"
                description = f"No packets received after removing device prioritization"
                write_test_result_to_json(mac_address, test_ID, result, description)
                testFlag = True
    else:
        print("[ERROR] No packets received after applying DSCP marking")
        result = "Failed"
        description = f"No packets received after applying DSCP marking"
        write_test_result_to_json(mac_address, test_ID, result, description)
        testFlag = True

    return testFlag

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 DevicePrioritization.py <test_ID> <mac_address>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    # Install required system packages
    packages_to_install = ['python3-pip', 'libpcap-dev']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    # Install required python packages
    required_python_packages = ['scapy', 'netifaces']
    for package in required_python_packages:
        ok, message = check_python_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    from scapy.all import *
    import netifaces

    interface, mac = fetch_client_interface()
    if mac:
        client_mac = mac.lower().replace(":", "")
    else:
        result = "Failed"
        description = "Failed to fetch the client details"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Start the ping to 8.8.8.8
    ping_process = subprocess.Popen(["ping", "8.8.8.8"])

    dscpvalues = [8, 40, 45, 46, 56]
    for value in dscpvalues:
        testFlag = test_devicePrioritization(mac_address, client_mac, interface, value)
        if testFlag:
            ping_process.kill()
            sys.exit(1)

    ping_process.kill()
    result = "Passed"
    description = "Received expected DSCP values for all packets"
    write_test_result_to_json(mac_address, test_ID, result, description)
