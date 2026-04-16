import subprocess
import ipaddress
import sys
import json
import socket
from urllib.parse import urlencode
import importlib

test_name = "LANtoWANGRE"

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
required_python_packages = ['scapy','netifaces']
for package in required_python_packages:
    check_python_package(package)

from scapy.all import *
import netifaces

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

def webpa_get(parameter):
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
        result = "Failed"
        description = f"Failed to get the value of {parameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    return getValue

def assign_gre_ip(lan_ip):
    """Determine the IP range to assign based on lan IP."""
    if lan_ip.startswith("10.") or lan_ip.startswith("172."):
        return "192.168.100.2/30"
    elif lan_ip.startswith("192."):
        return "10.0.0.2/30"
    else:
        print("Error: LAN IP does not match any expected range")
        result = "Failed"
        description = "Error: LAN IP does not match any expected range"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

def fetch_local_ip():
    interface = 'eth0'
    try:
        addrs = netifaces.ifaddresses(interface)
        ip_info = addrs.get(netifaces.AF_INET)
        if ip_info:
            ip_address = ip_info[0]['addr']
            print(f"Interface: {interface}, IP: {ip_address}")
            return ip_address
    except Exception:
        print("Failed to fetch local ip")
    return None


def configure_gre_tunnel(remote_ip, lan_ip):
    """Configure the GRE tunnel."""
    local_ip = fetch_local_ip()
    if not local_ip:
        result = "Failed"
        description = "Error: Failed to fetch local IP"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    gre_ip = assign_gre_ip(lan_ip)
    if not gre_ip:
        return

    try:
        # Add GRE tunnel
        subprocess.run(["sudo", "ip", "tunnel", "add", gre_name, "mode", "gre", "local", local_ip, "remote", remote_ip, "ttl", "255"], check=True)
        print("GRE tunnel added successfully")

        # Assign IP to GRE tunnel
        subprocess.run(["sudo", "ip", "addr", "add", gre_ip, "dev", gre_name], check=True)
        print(f"Assigned IP {gre_ip} to GRE tunnel")

        # Bring GRE tunnel up
        subprocess.run(["sudo", "ip", "link", "set", gre_name, "up"], check=True)
        print("GRE tunnel is up")
        return gre_ip
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        result = "Failed"
        description = f"GRE tunnel setup failed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)


def remove_gre_tunnel():
    try:
        # Run the command to delete the GRE tunnel
        subprocess.run(["sudo", "ip", "tunnel", "del", gre_name], check=True)
        print(f"Tunnel removed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to remove tunnel {gre_name}: {e}")

def packet_handler(packet, expected_outer_dscp, expected_inner_dscp):
    global GRE_packet
    global invalid_inner_dscp
    global invalid_outer_dscp
    # Check if the packet has an IP layer and a GRE layer
    if IP in packet and GRE in packet:
        GRE_packet = True
        # Extract the TOS (Type of Service) value from the outer IP header
        outer_tos = packet[IP].tos  # TOS is an 8-bit field in the IP header

        # Extract the DSCP value (first 6 bits of the TOS field) from the outer packet
        outer_dscp = (outer_tos & 0b11111100) >> 2  # Mask the first 6 bits and shift right by 2

        # Print the extracted values for the outer packet
        print(f"GRE Packet Detected:")
        print(f"  Outer TOS: {outer_tos} (0x{outer_tos:02x})")
        print(f"  Outer DSCP: {outer_dscp} (0x{outer_dscp:02x})")
        print(f"  Outer Source IP: {packet[IP].src}, Outer Destination IP: {packet[IP].dst}")
        if outer_dscp != expected_outer_dscp:
            invalid_outer_dscp = True

        # Check if the GRE packet contains an inner IP packet
        if IP in packet[GRE]:
            inner_packet = packet[GRE][IP]  # Extract the inner IP packet

            # Extract the TOS (Type of Service) value from the inner IP header
            inner_tos = inner_packet.tos

            # Extract the DSCP value (first 6 bits of the TOS field) from the inner packet
            inner_dscp = (inner_tos & 0b11111100) >> 2  # Mask the first 6 bits and shift right by 2

            # Print the extracted values for the inner packet
            print(f"  Inner TOS: {inner_tos} (0x{inner_tos:02x})")
            print(f"  Inner DSCP: {inner_dscp} (0x{inner_dscp:02x})")
            print(f"  Inner Source IP: {inner_packet.src}, Inner Destination IP: {inner_packet.dst}")
            if inner_packet.src == remote_gre_ip:
                if inner_dscp != expected_inner_dscp:
                    invalid_inner_dscp = True
        else:
            print("No inner IP packet found in the GRE payload.")

def find_remote_gre_ip(ip):
    if ip.startswith("10.") or ip.startswith("172."):
        return "192.168.100.1"
    elif ip.startswith("192."):
        return "10.0.0.1"
    else:
        print("Error: eth0 IP does not match any expected range")
        result = "Failed"
        description = "Error: LAN IP does not match any expected range"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_gre_tunnel()
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 gre_WAN.py <test_ID> <mac_address> <lan_client_ip> <gateway_wan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    lan_ip = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    if len(sys.argv) == 5:
        remote_ip = sys.argv[4]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        remote_ip = webpa_get(parameter)

    last_four = mac_address[-5:]
    res = last_four.replace(':', '')
    global gre_name
    gre_name = f"gre_{res}"

    # Configure GRE tunnel
    gre_ip_with_subnet = configure_gre_tunnel(remote_ip, lan_ip)
    GRE_IP = gre_ip_with_subnet.split('/')[0]
    print(f"GRE IP of server - {GRE_IP}")
    remote_gre_ip = find_remote_gre_ip(lan_ip)

    global GRE_packet; GRE_packet = False
    global invalid_inner_dscp; invalid_inner_dscp = False
    global invalid_outer_dscp; invalid_outer_dscp = False

    # ------------------------ case 1 -----------------------------------
    PORT = 31313

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((GRE_IP, PORT))
    server_sock.listen(1)
    server_sock.settimeout(60)

    print(f"Listening on {GRE_IP}:{PORT}...")

    try:
        conn, addr = server_sock.accept()
        print(f"Connection from {addr}")

        print(f"Starting packet capture...")
        filter_exp = f"ip proto gre and src {remote_ip}"
        sniff_thread = threading.Thread(
            target=sniff,
            kwargs={
                "filter": filter_exp,
                "prn": lambda x: packet_handler(x, expected_outer_dscp=26, expected_inner_dscp=34),
                "timeout": 60
            }
        )
        sniff_thread.start()

        # Receive and respond to data
        while True:
            data = conn.recv(1024)
            if not data:
                print("Connection closed by client.")
                break
            print("Received:", data.decode())
            conn.send(b"ACK")

        sniff_thread.join()
        conn.close()
        print("Packet sniffing completed.")

    except socket.timeout:
        print("No connection received within 3 minutes. Closing server.")

    print("Closing connection")
    server_sock.close()

    if GRE_packet:
        print("Received GRE Packet")
        if invalid_inner_dscp and invalid_outer_dscp:
            result = "Failed"
            description = "Error: At least one packet had an invalid DSCP value in inner and outer packet"
        elif invalid_inner_dscp:
            result = "Failed"
            description = "Error: At least one packet had an invalid inner DSCP value"
        elif invalid_outer_dscp:
            result = "Failed"
            description = "Error: At least one packet had an invalid outer DSCP value"
        else:
            description = "All packets had a valid DSCP value"
            result = "Success"
    else:
        print("GRE packets not received")
        result = "Failed"
        description = "GRE packets not received"

    print(description)
    if result == "Failed":
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_gre_tunnel()
        sys.exit(1)

    # ------------------------------------------------------------------------
    # ---------------------------------------case 2 -------------------------------
    GRE_packet = False
    invalid_inner_dscp = False
    inalid_outer_dscp = False

    PORT = 42424

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((GRE_IP, PORT))
    server_sock.listen(1)
    server_sock.settimeout(180)

    print(f"Listening on {GRE_IP}:{PORT}...")

    try:
        conn, addr = server_sock.accept()
        print(f"Connection from {addr}")

        print(f"Starting packet capture...")
        filter_exp = f"ip proto gre and src {remote_ip}"
        sniff_thread = threading.Thread(
            target=sniff,
            kwargs={
                "filter": filter_exp,
                "prn": lambda x: packet_handler(x, expected_outer_dscp=40, expected_inner_dscp=56),
                "timeout": 60
            }
        )
        sniff_thread.start()

        # Receive and respond to data
        while True:
            data = conn.recv(1024)
            if not data:
                print("Connection closed by client.")
                break
            print("Received:", data.decode())
            conn.send(b"ACK")

        sniff_thread.join()
        conn.close()
        print("Packet sniffing completed.")

    except socket.timeout:
        print("No connection received within 3 minutes. Closing server.")

    print("Closing connection")
    server_sock.close()

    if GRE_packet:
        print("Received GRE Packet")
        if invalid_inner_dscp and invalid_outer_dscp:
            result = "Failed"
            description = "Error: At least one packet had an invalid DSCP value in inner and outer packet"
        elif invalid_inner_dscp:
            result = "Failed"
            description = "Error: At least one packet had an invalid inner DSCP value"
        elif invalid_outer_dscp:
            result = "Failed"
            description = "Error: At least one packet had an invalid outer DSCP value"
        else:
            description = "All packets had a valid DSCP value"
            result = "Success"
    else:
        print("GRE packets not received")
        result = "Failed"
        description = "GRE packets not received"

    print(description)
    if result == "Failed":
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_gre_tunnel()
        sys.exit(1)

    result = "success"
    description = "GRE packet validation scuccess"
    write_test_result_to_json(mac_address, test_ID, result, description)

    remove_gre_tunnel()
