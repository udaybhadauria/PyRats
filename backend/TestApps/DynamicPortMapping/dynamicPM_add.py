import subprocess
import sys
import json
import importlib
import shutil
import time
import os

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

test_name = "DynamicPortMapping"
httpPacketCapture = False
nginx_config_file = '/etc/nginx/sites-available/default'
nginx_config_file_backup = '/etc/nginx/sites-available/default_backup'
new_port = 16374

def add_port_mapping(u, start_port, end_port, retries=3, delay=10):
    for attempt in range(1, retries + 1):
        try:
            success = u.addportmapping(start_port, 'TCP', u.lanaddr, end_port, 'My Port Mapping', '')
            if success:
                print(f"Port mapping added successfully (attempt {attempt})")
                return True
            else:
                print(f"Failed to add port mapping (attempt {attempt})")
        except Exception as e:
            print(f"An error occurred while adding port mapping (attempt {attempt}): {e}")
        if attempt < retries:
            time.sleep(delay)
    return False

def delete_port_mapping(u, start_port, retries=3, delay=10):
    for attempt in range(1, retries + 1):
        try:
            success = u.deleteportmapping(start_port, 'TCP')
            if success:
                print(f"Port mapping deleted successfully (attempt {attempt})")
                return True
            else:
                print(f"Failed to delete port mapping (attempt {attempt})")
        except Exception as e:
            print(f"An error occurred while deleting port mapping (attempt {attempt}): {e}")
        if attempt < retries:
            time.sleep(delay)
    return False

def packet_handler(pkt, target_ip):
    global httpPacketCapture
    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if ip_src == target_ip:
            print("Source IP matches the target IP address")
            if tcp_dport == new_port:
                httpPacketCapture = True

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

def stop_nginx_service():
    stop_command = "sudo systemctl stop nginx"
    try:
        subprocess.run(stop_command, shell=True, check=True)
        print("Nginx service stopped successfully")
    except subprocess.CalledProcessError as e:
        print("Error stopping Nginx service:", e)

def set_nginx_default():
    if os.path.exists(nginx_config_file_backup):
        try:
            shutil.copyfile(nginx_config_file_backup, nginx_config_file)
            os.remove(nginx_config_file_backup)
        except Exception as e:
            print(f"Warning: Failed to restore or remove nginx config backup: {e}")
    else:
        print("Warning: nginx config backup does not exist, skipping restore.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 dynamicPM_add.py <test_ID> <mac_address> <webserver_IPv4>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ip = sys.argv[3]

    # List of packages to check and install
    packages_to_install = ['python3-pip', 'libpcap-dev', 'nginx', 'python3-miniupnpc']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    # Check/install scapy before import
    required_python_packages = ['scapy', 'miniupnpc']
    for package in required_python_packages:
        ok, message = check_python_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    import miniupnpc
    from scapy.all import *

    if not os.path.exists(nginx_config_file):
        result = "Failed"
        description = f"nginx config file does not exist: {nginx_config_file}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    try:
        shutil.copyfile(nginx_config_file, nginx_config_file_backup)
    except Exception as e:
        result = "Failed"
        description = f"Failed to backup nginx config: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    nginx_config = f"""
    server {{
        listen {new_port} default_server;
        listen [::]:{new_port} default_server;

        root /var/www/html;
        index index.html index.htm index.nginx-debian.html;

        server_name _;

        location / {{
                try_files $uri $uri/ =404;
        }}
    }}
    """

    try:
        # Write the new configuration to the nginx config file
        with open(nginx_config_file, 'w') as file:
            file.write(nginx_config)
        print("Nginx configuration updated successfully")
    except FileNotFoundError:
        print("Nginx configuration file does not exist")
        result = "Failed"
        description = "Nginx configuration file does not exist"
        write_test_result_to_json(mac_address, test_ID, result, description)
        set_nginx_default()
        sys.exit(1)

    # Command to restart Nginx using systemctl
    restart_command = "sudo systemctl restart nginx"
    try:
        subprocess.run(restart_command, shell=True, check=True)
        print("Nginx service restarted successfully")
    except subprocess.CalledProcessError as e:
        print("Error restarting Nginx service:", e)
        result = "Failed"
        description = "Error restarting Nginx service: {}".format(e)
        write_test_result_to_json(mac_address, test_ID, result, description)
        set_nginx_default()
        sys.exit(1)

    try:
        u = miniupnpc.UPnP()
        u.discoverdelay = 200
        devices = u.discover()
    except Exception as e:
        result = "Failed"
        description = f"UPnP discovery failed: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        stop_nginx_service()
        set_nginx_default()
        sys.exit(1)

    if devices == 0:
        result = "Failed"
        description = "No UPnP devices found"
        write_test_result_to_json(mac_address, test_ID, result, description)
        stop_nginx_service()
        set_nginx_default()
        sys.exit(1)

    try:
        u.selectigd()
    except Exception as e:
        result = "Failed"
        description = f"UPnP selectigd failed: {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        stop_nginx_service()
        set_nginx_default()
        sys.exit(1)

    add_success = add_port_mapping(u, new_port, new_port)
    if add_success:
        print("Start packet capture")
        sniff(filter=f"tcp and ip src host {target_ip} and dst port {new_port}", prn=lambda x: packet_handler(x, target_ip), store=0, timeout=60)
        if httpPacketCapture:
            result = "Passed"
            description = "Dynamic PortMapping Rule is added and got request on the service from Server"
        else:
            result = "Failed"
            description = "Dynamic PortMapping Rule is added but didn't got request on the service from Server"
    else:
        result = "Failed"
        description = "Failed to add Dynamic PortMapping Rule"

    if add_success:
        delete_success = delete_port_mapping(u, new_port)

    stop_nginx_service()
    set_nginx_default()
    write_test_result_to_json(mac_address, test_ID, result, description)
