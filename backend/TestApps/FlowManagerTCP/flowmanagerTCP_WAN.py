import json
import sys
import time
import subprocess
import socket
import ipaddress
from urllib.parse import urlencode
import importlib
import threading

test_name = "FlowManagerTCP"

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
    max_retries = 3
    retry_delay = 10  # seconds
    attempt = 0

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
                print(f"Webpa get {parameter} failed (attempt {attempt}/{max_retries}), retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"[ERROR] WebPA get for {parameter} failed")
                result = "Failed"
                description = f"WebPA get for {parameter} failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)

def process_packet(packet, expected_dscp):
    global packet_received
    global invalid_dscp
    if IP in packet and TCP in packet:
        packet_received = True
        dscp = packet[IP].tos >> 2  # DSCP is the upper 6 bits of the TOS field
        print(f"Packet from {packet[IP].src} DSCP: {dscp}")
        if dscp != 0 and dscp != expected_dscp:
            invalid_dscp = True
    if IPv6 in packet and TCP in packet:
        packet_received = True
        dscp = packet[IPv6].tc >> 2
        print(f"Packet from {packet[IPv6].src} DSCP: {dscp}")
        if dscp != 0 and dscp != expected_dscp:
            invalid_dscp = True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 flowManagerTCP_WAN.py <test_ID> <mac_address> <gateway_wan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    # Install required system packages
    packages_to_install = ['python3-pip', 'libpcap-dev']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    # Install required python packages
    required_python_packages = ['scapy']
    for package in required_python_packages:
        ok, message = check_python_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    from scapy.all import *

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    runParam = "Device.X_RDK_AutomationTest.Run"

    testSupport = webpa_get(runParam)
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

    if len(sys.argv) == 4:
        gateway_wan_ip = sys.argv[3]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        gateway_wan_ip = webpa_get(parameter)

    # -----------------------------------------------------------------------

    # ----------------------- Validating TCP IPv4 packet --------------------
    global invalid_dscp
    global packet_received

    PORT = 33331
    ipv4_socket_created = True
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("0.0.0.0", PORT))
        server_sock.listen(1)
        server_sock.settimeout(180)
    except Exception as e:
        print(f"[ERROR] Failed to create or bind IPv4 TCP server socket: {e}")
        result1 = "Failed"
        description1 = "Failed to create or bind IPv4 TCP server"
        ipv4_socket_created = False

    if ipv4_socket_created:
        print(f"Listening on {PORT}...")

        packet_received = False
        invalid_dscp = False

        try:
            conn, addr = server_sock.accept()
            print(f"Connection from {addr}")

            print(f"Starting packet capture...")
            filter_exp = f"ip src {gateway_wan_ip} and tcp src port 22221 and tcp dst port {PORT}"
            sniff_thread = threading.Thread(
                target=sniff,
                kwargs={
                    "filter": filter_exp,
                    "prn": lambda x: process_packet(x, expected_dscp=26),
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
                print("Received:", data.decode("utf-8", errors="ignore"))
                conn.send(b"ACK")

            sniff_thread.join()
            conn.close()
            print("Packet sniffing completed.")

        except socket.timeout:
            print("No connection received within 3 minutes. Closing server.")

        print("Closing connection")
        server_sock.close()

        if packet_received:
            if invalid_dscp:
                result1 = "Failed"
                description1 = "Packets received with invalid DSCP"
            else:
                result1 = "Passed"
                description1 = "Success"
        else:
            result1 = "Failed"
            description1 = "Didn't receive any packets"

        time.sleep(30)
    else:
        time.sleep(90)
    print(f"TCP IPv4 validation - {description1}")
    # ----------------------------------------------------------------------------------------

    # ----------------- Validating TCP IPv6 packet ------------------------------
    PORT = 33332
    ipv6_socket_created = True

    try:
        server_sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        server_sock.bind(("::", PORT))
        server_sock.listen(1)
        server_sock.settimeout(180)
    except Exception as e:
        print(f"[ERROR] Failed to create or bind IPv6 TCP server socket: {e}")
        result2 = "Failed"
        description2 = "Failed to create or bind IPv6 TCP server"
        ipv6_socket_created = False
    
    if ipv6_socket_created:
        print(f"Listening on [::]:{PORT}...")

        packet_received = False
        invalid_dscp = False

        try:
            conn, addr = server_sock.accept()
            print(f"Connection from {addr}")

            print(f"Starting packet capture...")
            filter_exp = f"ip6 and tcp src port 22222 and tcp dst port {PORT}"
            sniff_thread = threading.Thread(
                target=sniff,
                kwargs={
                    "filter": filter_exp,
                    "prn": lambda x: process_packet(x, expected_dscp=40),
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
                print("Received:", data.decode("utf-8", errors="ignore"))
                conn.send(b"ACK")

            sniff_thread.join()
            conn.close()
            print("Packet sniffing completed.")

        except socket.timeout:
            print("No connection received within 3 minutes. Closing server.")

        print("Closing connection")
        server_sock.close()

        if packet_received:
            if invalid_dscp:
                result2 = "Failed"
                description2 = "Packets received with invalid DSCP"
            else:
                result2 = "Passed"
                description2 = "Success"
        else:
            result2 = "Failed"
            description2 = "Didn't receive any packets"

    print(f"TCP IPv6 validation - {description2}")

    # --------------------------------------------------------------------------------------------------------

    if result1 == "Passed" and result2 == "Passed":
        result = "Passed"
    else:
        result = "Failed"

    description = f"IPv4-{description1}, IPv6-{description2}"

    write_test_result_to_json(mac_address, test_ID, result, description)
    sys.exit(1)
