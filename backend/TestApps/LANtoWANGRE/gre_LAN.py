import subprocess
import ipaddress
import sys
import socket
from urllib.parse import urlencode
import importlib
import json
import time

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
packages_to_install = ['python3-pip']

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

test_name = "LANtoWANGRE"

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

def fetch_client_mac():
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        addrs = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
        if addrs:
            for addr_info in addrs:
                ip_address = addr_info['addr']
                if ip_address.startswith('10.') or ip_address.startswith('172.') or ip_address.startswith('192.168'):
                    client_mac = netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
                    print("Network interface: {}, Private ip address: {}, Client MAC Address: {}".format(interface, ip_address, client_mac))
                    return client_mac
    return None

def assign_gre_ip(eth0_ip):
    """Determine the IP range to assign based on eth0 IP."""
    if eth0_ip.startswith("10.") or eth0_ip.startswith("172."):
        return "192.168.100.1/30"
    elif eth0_ip.startswith("192."):
        return "10.0.0.1/30"
    else:
        print("Error: LAN IP does not match any expected range")
        result = "Failed"
        description = "Error: LAN IP does not match any expected range"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

def configure_gre_tunnel(local_ip, remote_ip):
    """Configure the GRE tunnel."""
    gre_ip = assign_gre_ip(local_ip)
    if not gre_ip:
        return

    try:
        # Add GRE tunnel
        subprocess.run(["sudo", "ip", "tunnel", "add", gre_name, "mode", "gre", "local", local_ip, "remote", remote_ip, "ttl", "255"], check=True)
        print("GRE tunnel added successfully.")

        # Assign IP to GRE tunnel
        subprocess.run(["sudo", "ip", "addr", "add", gre_ip, "dev", gre_name], check=True)
        print(f"Assigned IP {gre_ip} to GRE tunnel.")

        # Bring GRE tunnel up
        subprocess.run(["sudo", "ip", "link", "set", gre_name, "up"], check=True)
        print("GRE tunnel is up.")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        result = "Failed"
        description = "GRE tunnel setup failed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

def remove_gre_tunnel():
    try:
        # Run the command to delete the GRE tunnel
        subprocess.run(["sudo", "ip", "tunnel", "del", gre_name], check=True)
        print(f"Tunnel removed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to remove tunnel {gre_name}: {e}")

def find_remote_gre_ip(ip):
    if ip.startswith("10.") or ip.startswith("172."):
        return "192.168.100.2"
    elif ip.startswith("192."):
        return "10.0.0.2"
    else:
        print("Error: LAN IP does not match any expected range")
        result = "Failed"
        description = "Error: LAN IP does not match any expected range"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_gre_tunnel()
        sys.exit(1)

def prioritize_device(mac, DSCP_Value):
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

    client_mac = mac.lower().replace(":", "")
    while attempt < max_retries:
        # payload
        data = {
            "action": "MARK_UPSTREAM",
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
            print("Successfully added the Device Prioritization Configuration")
            return
        else:
            attempt += 1
            if attempt < max_retries:
                print(f"prioritize_device failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                result = "Failed"
                description = f"Device prioritization blob set with DSCPMarking Value {DSCP_Value} Failed after {max_retries} attempts"
                write_test_result_to_json(mac_address, test_ID, result, description)
                remove_gre_tunnel()
                sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python3 gre_LAN.py <test_ID> <mac_address> <webserver_ip> <client_lan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    remote_ip = sys.argv[3]
    local_ip = sys.argv[4]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    last_four = mac_address[-5:]
    res = last_four.replace(':', '')
    global gre_name
    gre_name = f"gre_{res}"
    # Configure GRE tunnel
    configure_gre_tunnel(local_ip, remote_ip)

    client_mac = fetch_client_mac()

    remote_gre_ip = find_remote_gre_ip(local_ip)

    # --------------------------------------------------------------------------------
    # ---------------------------------------- case 1 --------------------------------
    SRC_PORT = 21212
    DST_PORT = 31313
    PACKET_COUNT = 100

    # DSCP value set
    dscp = 26
    prioritize_device(client_mac, dscp)

    time.sleep(5)

    print("Validating GRE")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", SRC_PORT))  # Bind source port
    try:
        dscp_value = 34 << 2  # DSCP occupies the upper 6 bits of TOS
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, dscp_value)

        sock.connect((remote_gre_ip, DST_PORT))  # Connect to server
        print(f"Connected to {remote_gre_ip}:{DST_PORT}")

        # Send request
        message = "RATS Test"
        for _ in range(PACKET_COUNT):
            sock.send(message.encode())
            data = sock.recv(1024)
            print("Received from server:", data.decode())
    except Exception as e:
        print("Connection error:", e)
        result = "Failed"
        description = f"Connection error: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_gre_tunnel()
        sys.exit(1)

    sock.close()
    print("Socket closed")

    time.sleep(60)

    # --------------------------------------------------------------------------------------
    # ---------------------------------------- case 2 --------------------------------
    SRC_PORT = 32323
    DST_PORT = 42424
    PACKET_COUNT = 100

    # DSCP value set
    dscp = 40
    prioritize_device(client_mac, dscp)

    time.sleep(5)

    print("Validating GRE")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", SRC_PORT))  # Bind source port
    try:
        dscp_value = 56 << 2  # DSCP occupies the upper 6 bits of TOS
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, dscp_value)

        sock.connect((remote_gre_ip, DST_PORT))  # Connect to server
        print(f"Connected to {remote_gre_ip}:{DST_PORT}")

        # Send request
        message = "RATS Test"
        for _ in range(PACKET_COUNT):
            sock.send(message.encode())
            data = sock.recv(1024)
            print("Received from server:", data.decode())
    except Exception as e:
        print("Connection error:", e)
        result = "Failed"
        description = f"Connection error: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_gre_tunnel()
        sys.exit(1)

    sock.close()
    print("Socket closed")


    # -------------------------------------------------------------------------------------------------

    result = "Passed"
    description = "GRE tunnel setup and traffic send to remote GRE interface success"
    write_test_result_to_json(mac_address, test_ID, result, description)

    remove_gre_tunnel()

