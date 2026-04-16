import subprocess
import sys
import json
import importlib
import shutil
import os
import time
from urllib.parse import quote

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

test_name = "XMBoostDynamicPM"
httpPacketCapture = False
nginx_config_file = '/etc/nginx/sites-available/default'
nginx_config_file_backup = '/etc/nginx/sites-available/default_backup'
timeout = 15

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

def packet_handler(pkt, target_ip, port):
    global httpPacketCapture
    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if ip_src == target_ip:
            print("Source IP matches the target IP address")
            if tcp_dport == port:
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

def webpa_get(mac_address, parameter):
    attempt = 0
    max_retries = 3
    retry_delay = 10  # seconds

    while attempt < max_retries:
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
                print(f"Aborted, Webpa request to get {parameter} failed after multiple attempts")
                result = "Failed"
                description = f"Aborted, Webpa request to get {parameter} failed after multiple attempts"
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)

def webpa_set(mac_address, parameter, value, type):
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
                print(f"Failed to set the value of {parameter}")
                return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 xmDynamicPM_LAN.py <test_ID> <mac_address> <Webserver_IP>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ip = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    pvdEnable = webpa_get(mac_address, pvdParameter)
    print(f"speedboost feature - {pvdEnable}")
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        time.sleep(5)
        sys.exit(1)

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

    xmPortParameter = "Device.X_RDK_Speedboost.PortRanges"
    xmPort = webpa_get(mac_address, xmPortParameter)
    defaultXmport = quote(xmPort)

    normalPortParameter = "Device.X_RDK_Speedboost.NormalPortRange"
    normalPort =  webpa_get(mac_address, normalPortParameter)
    defaultNormalPort = quote(normalPort)

    # Discover device
    try:
        u = miniupnpc.UPnP()
        u.discoverdelay = 200
        devices = u.discover()
    except Exception as e:
        result = "Failed"
        description = f"UPnP discovery failed : {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if devices == 0:
        result = "Failed"
        description = "No UPnP devices found"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    try:
        u.selectigd()
    except Exception as e:
        result = "Failed"
        description = f"UPnP selectigd failed : {e}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)


    #---------------------------- Case 1: Run the service on port 40500 which is within speedboost port range 40001 - 41000 -----------------

    print("------ Run the service on port 40500 which is within speedboost port range 40001 - 41000 --------")
    # Disable speedboost feature
    print("Disable speedboost feature")
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Aborted, Webpa set request to disable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Set speedboost port range to 40001 - 41000
    print("Setting speedboost port range to 40001 - 41000")
    xmPortRange = "IPv4 BOTH 40001 41000,IPv6 BOTH 40001 41000"
    xmport_range = quote(xmPortRange)
    response = webpa_set(mac_address, xmPortParameter, xmport_range, 0)
    if not response:
        result = "Failed"
        description = "Aborted, Webpa set request to set speedboost port range to 40001 - 41000 failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)

    # Set Normal port range to 50000 - 65000
    print("Setting Normal PortRange to 50000 - 65000")
    normalPortRange = "IPv4 BOTH 50000 65000,IPv6 BOTH 50000 65000"
    normalPort_range = quote(normalPortRange)
    response = webpa_set(mac_address, normalPortParameter, normalPort_range, 0)
    if not response:
        result = "Failed"
        description = "Aborted, Webpa set request to set Normal PortRange to 50000 - 65000 failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        sys.exit(1)
    time.sleep(timeout)

    port = 40500

    # Take backup of default nginx configuration
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
        listen {port} default_server;
        listen [::]:{port} default_server;

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
        os.remove(nginx_config_file_backup)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
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
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        sys.exit(1)

    add_success = add_port_mapping(u, port, port)
    if add_success:
       print("Dynamic PortMapping Rule is added successfully for port 40500")
       sniff(filter=f"tcp and ip src host {target_ip} and dst port {port}", prn=lambda x: packet_handler(x, target_ip, port), store=0, timeout=80)
    else:
        result = "Failed"
        description = "Failed to add Dynamic PortMapping Rule for port 40500"
        stop_nginx_service()
        set_nginx_default()
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if add_success:
        delete_success = delete_port_mapping(u, port)

    stop_nginx_service()
    # -----------------------------------------------------------------------------------------------------------------------------------------------

    #---------------------------- Case 2: Run the service on port 40500 which is within speedboost port range 45001 - 46000 -----------------

    print("------ Run the service on port 40500 which is within speedboost port range 45001 - 46000 ----")
    # Disable speedboost feature
    print("Disable speedboost feature")
    response = webpa_set(mac_address, pvdParameter, False, 3)
    if not response:
        result = "Failed"
        description = "Aborted, Webpa set request to disable speedboost feature failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        set_nginx_default()
        sys.exit(1)

    # Set speedboost port range to 45001 - 46000
    print("Setting speedboost port range to 45001 - 46000")
    xmPortRange = "IPv4 BOTH 45001 46000,IPv6 BOTH 45001 46000"
    xmport_range = quote(xmPortRange)
    response = webpa_set(mac_address, xmPortParameter, xmport_range, 0)
    if not response:
        result = "Failed"
        description = "Aborted, Webpa set request to set speedboost port range to 45001 - 46000 failed after multiple attempts"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        set_nginx_default()
        sys.exit(1)
    time.sleep(timeout)

    # Select one port within speedboost port range
    port = 45500

    nginx_config = f"""
    server {{
        listen {port} default_server;
        listen [::]:{port} default_server;

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
        os.remove(nginx_config_file_backup)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
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
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        sys.exit(1)

    add_success = add_port_mapping(u, port, port)
    if add_success:
       print(f"Dynamic PortMapping Rule is added successfully for port {port}")
       sniff(filter=f"tcp and ip src host {target_ip} and dst port {port}", prn=lambda x: packet_handler(x, target_ip, port), store=0, timeout=80)
    else:
        result = "Failed"
        description = f"Failed to add Dynamic PortMapping Rule for port {port}"
        stop_nginx_service()
        set_nginx_default()
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if add_success:
        delete_success = delete_port_mapping(u, port)

    stop_nginx_service()
    # -----------------------------------------------------------------------------------------------------------------------------------------------

    #---------------------------- Case 3: Run the server on port 47100 ---------------------------------------------------------

    print("------Run the service on port 47100 and then enable the speedboost port range with in that port 45001 - 46000----")

    port = 47100

    nginx_config = f"""
    server {{
        listen {port} default_server;
        listen [::]:{port} default_server;

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
        os.remove(nginx_config_file_backup)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
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
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        sys.exit(1)

    add_success = add_port_mapping(u, port, port)
    if add_success:
       print(f"Dynamic PortMapping Rule is added successfully for port {port}")
       sniff(filter=f"tcp and ip src host {target_ip} and dst port {port}", prn=lambda x: packet_handler(x, target_ip, port), store=0, timeout=170)
    else:
        result = "Failed"
        description = f"Failed to add Dynamic PortMapping Rule for port {port}"
        stop_nginx_service()
        set_nginx_default()
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
        webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if add_success:
        delete_success = delete_port_mapping(u, port)

    stop_nginx_service()
    set_nginx_default()
    webpa_set(mac_address, pvdParameter, pvdEnable, 3)
    webpa_set(mac_address, xmPortParameter, defaultXmport, 0)
    webpa_set(mac_address, normalPortParameter, defaultNormalPort, 0)
    # -----------------------------------------------------------------------------------------------------------------------------------------------

    result = "Passed"
    description = "Service ran on 40500,45500,47100"
    write_test_result_to_json(mac_address, test_ID, result, description)
