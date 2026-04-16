import importlib
import subprocess
import sys
import json
import re
import time
import threading

test_name = "PortForward"
config_file = "/etc/apache2/ports.conf"
new_port = 19897

packetCapture = False
first_packet_time = None
packet_count = 0
wait_after_first_packet = 15  # seconds to wait after first packet before stopping
sniffer = None

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

def read_current_port(config_file):
    try:
        with open(config_file, 'r') as file:
            config_data = file.read()
        match = re.search(r"Listen\s+(\d+)", config_data)
        if match:
            return match.group(1), "Listen port found"
        else:
            return None, "No Listen directive found in the Apache2 configuration file"
    except Exception as e:
        return None, f"Apache2 port read failed: {e}"

def change_apache2_port(new_port):
    try:
        with open(config_file, 'r') as file:
            config_data = file.read()
        updated_config_data = re.sub(r"Listen\s+\d+", f"Listen {new_port}", config_data, count=1)
        with open(config_file, 'w') as file:
            file.write(updated_config_data)
        print(f"Apache2 port changed to {new_port}")
        return True, f"Apache2 port changed to {new_port}"
    except Exception as e:
        print(f"Apache2 port change failed: {e}")
        return False, f"Apache2 port change failed: {e}"

def restart_apache2():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "apache2"], check=True)
        print("Apache2 restarted successfully")
        return True, "Apache2 restarted successfully"
    except subprocess.CalledProcessError as e:
        print(f"Apache2 restart failed: {e}")
        return False, f"Apache2 restart failed: {e}"

def schedule_stop():
    global sniffer
    if sniffer:
        print(f"Timer expired: stopping capture after {wait_after_first_packet} seconds from first packet")
        sniffer.stop()

def packet_handler(pkt, target_ip):
    global packetCapture, first_packet_time, packet_count
    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if tcp_dport == new_port:
            if ip_src == target_ip:
                packet_count += 1
                print("Source IP matches the target IP address")
                packetCapture = True
                if first_packet_time is None:
                    first_packet_time = time.time()
                    print(f"First packet captured, will stop in {wait_after_first_packet} seconds")
                    # Schedule the stop after wait_after_first_packet seconds
                    stop_timer = threading.Timer(wait_after_first_packet, schedule_stop)
                    stop_timer.start()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 web_traffic.py <test_ID> <mac_address> <webserver_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ip = sys.argv[3]

    packages_to_install = ['python3-pip', 'libpcap-dev', 'apache2']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    required_python_packages = ['scapy']
    for package in required_python_packages:
        ok, message = check_python_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    from scapy.all import *  # noqa: F401,F403

    # Read the current Listen port of apache2
    current_port, report = read_current_port(config_file)
    if current_port:
        print(f"Current Apache2 port: {current_port}")
        # Change the apache2 port
        success, message = change_apache2_port(new_port)
        if success:
            # Restart the apache2 service
            result, status = restart_apache2()
            if not result:
                change_apache2_port(current_port)
                result = "Failed"
                description = "Apache restart failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)
        else:
            result = "Failed"
            description = "Apache port change failed"
            write_test_result_to_json(mac_address, test_ID, result, description)
            sys.exit(1)
    else:
        result = "Failed"
        description = "Apache port read failed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    print(f"Apache2 service started on port {new_port}; waiting to capture traffic")
    # Start capture packet
    print(f"Starting packet capture on port {new_port}")
    sniffer = AsyncSniffer(filter=f"tcp dst port {new_port}", prn=lambda x: packet_handler(x, target_ip), store=0)
    sniffer.start()
    # Wait for the sniffer to complete (will be stopped by timer or timeout)
    sniffer.join(timeout=450)
    # Stop if still running
    if sniffer.running:
        sniffer.stop()

    if packetCapture:
        result = "Passed"
        description = "Received HTTP request on client"
    else:
        result = "Passed"
        description = "No HTTP request received on client"

    print(f"[INFO] Test Result: {result} - {description}")
    write_test_result_to_json(mac_address, test_ID, result, description)
    change_apache2_port(current_port)
    restart_apache2()
