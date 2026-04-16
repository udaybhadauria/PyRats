import importlib
import subprocess
import sys
import json
import shutil
import os
import time
import pwd
import re
import threading

test_name = "DMZ"

# Define the username and password for the new user
new_username = 'newtestuser'
new_password = 'newtestuser@123'

config_file = "/etc/apache2/ports.conf"

http_port = 25469
ssh_port = 26834

source_sshd_config_file = '/etc/ssh/sshd_config'
custom_sshd_config_file = '/etc/ssh/custom_sshd_config'

httpPacketCapture = False
sshPacketCapture = False

# For timed sniffer stop
first_packet_time = None
wait_after_first_packet = 25  # seconds to wait after first packet before stopping
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

def schedule_stop():
    global sniffer
    if sniffer:
        print(f"Timer expired: stopping capture after {wait_after_first_packet} seconds from first packet")
        sniffer.stop()

def packet_handler(pkt, target_ip):
    global httpPacketCapture, sshPacketCapture, first_packet_time, sniffer
    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if ip_src == target_ip:
            print("Source IP matches the target IP address")
            if tcp_dport == http_port:
                print(f"Destination Port: {tcp_dport}")
                httpPacketCapture = True
            elif tcp_dport == ssh_port:
                print(f"Destination Port: {tcp_dport}")
                sshPacketCapture = True
            # Start timer to stop sniffer after first relevant packet
            if (httpPacketCapture or sshPacketCapture) and first_packet_time is None:
                first_packet_time = time.time()
                print(f"First packet captured, will stop in {wait_after_first_packet} seconds")
                stop_timer = threading.Timer(wait_after_first_packet, schedule_stop)
                stop_timer.start()

def read_current_port(config_file):
    try:
        with open(config_file, 'r') as file:
            config_data = file.read()
        match = re.search(r"Listen\s+(\d+)", config_data)
        if match:
            return match.group(1), "Listen port found"
        else:
            return None, "No Listen directive found in the configuration file"
    except Exception as e:
        return None, f"Failed to read Apache2 port: {e}"

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
        print(f"Failed to change Apache2 port: {e}")
        return False, f"Failed to change Apache2 port: {e}"

def restart_apache2():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "apache2"], check=True)
        print("Apache2 restarted successfully")
        return True, "Apache2 restarted successfully"
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart Apache2: {e}")
        return False, f"Failed to restart Apache2: {e}"

def stop_UserProcess():
    # Kill the process running on testuser
    kill_userProcess_command = ['sudo', 'pkill', '-9', '-U', new_username]
    subprocess.run(kill_userProcess_command)

def delete_newUser():
    # Delete the new user
    delete_user_command = ['sudo', 'userdel', new_username]
    subprocess.run(delete_user_command)

    # Remove the user's home directory
    remove_home_command = ['sudo', 'rm', '-r', f'/home/{new_username}']
    subprocess.run(remove_home_command)
    print(f"user: {new_username} deleted successfully")

def user_exists(username):
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def remove_custom_config_file():
    os.remove(custom_sshd_config_file)
    print(f"File {custom_sshd_config_file} has been successfully removed")

def stop_sshd_service():
    process_pattern = f"/usr/sbin/sshd -f {custom_sshd_config_file}"
    # Execute the pkill command to stop the process by matching the command line pattern
    subprocess.run(["sudo", "pkill", "-f", process_pattern])
    print("SSH process with pattern '{}' has been stopped".format(process_pattern))

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 dmz_traffic.py <test_ID> <mac_address> <webserver_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ip = sys.argv[3]

    # List of packages to check and install
    packages_to_install = ['python3-pip', 'libpcap-dev', 'openssh-server', 'apache2']
    for package in packages_to_install:
        ok, message = check_package(package)
        if not ok:
            write_test_result_to_json(mac_address, test_ID, "Failed", message)
            sys.exit(1)

    ok, message = check_python_package('scapy')
    if not ok:
        write_test_result_to_json(mac_address, test_ID, "Failed", message)
        sys.exit(1)

    from scapy.all import *

    # Read the current Listen port of apache2
    current_port, report = read_current_port(config_file)
    if current_port:
        print(f"Current Apache2 port: {current_port}")
        # Change the apache2 port
        success, message = change_apache2_port(http_port)
        if success:
            # Restart the apache2 service
            result, status = restart_apache2()
            if not result:
                change_apache2_port(current_port)
                result = "Failed"
                description = status
                write_test_result_to_json(mac_address, test_ID, result, description)
                sys.exit(1)
        else:
            result = "Failed"
            description = message
            write_test_result_to_json(mac_address, test_ID, result, description)
            sys.exit(1)
    else:
        result = "Failed"
        description = report
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # If user already exists, remove it before creating a new one
    if user_exists(new_username):
        print(f"User {new_username} already exists. Removing it before creation.")
        stop_UserProcess()
        delete_newUser()

    # Create a new user
    create_user_command = ['sudo', 'useradd', new_username, '-m']
    create_user_process = subprocess.run(create_user_command)
    if create_user_process.returncode != 0:
        result = "Failed"
        description = f"Failed to create new user: {new_username}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        change_apache2_port(current_port)
        restart_apache2()
        sys.exit(1)

    # Set the password for the new user
    set_password_command = ['sudo', 'passwd', new_username]
    set_password_process = subprocess.Popen(set_password_command, stdin=subprocess.PIPE)
    set_password_process.communicate(input=f'{new_password}\n{new_password}\n'.encode())
    if set_password_process.returncode != 0:
        result = "Failed"
        description = f"Failed to set password for new user: {new_username}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        delete_newUser()
        change_apache2_port(current_port)
        restart_apache2()
        sys.exit(1)

    # Copy the sshd_config file to ssh_custom_config
    shutil.copyfile(source_sshd_config_file, custom_sshd_config_file)
    if not os.path.exists(custom_sshd_config_file):
        result = "Failed"
        description = "Failed to copy sshd_config file to sshd_custom_config file"
        write_test_result_to_json(mac_address, test_ID, result, description)
        delete_newUser()
        change_apache2_port(current_port)
        restart_apache2()
        sys.exit(1)

    # Modify the Port line in ssh_custom_config to use port 26834
    with open(custom_sshd_config_file, 'r') as file:
        lines = file.readlines()

    with open(custom_sshd_config_file, 'w') as file:
        for line in lines:
            if line.startswith("Port") or line.startswith("#Port"):
                file.write("Port {}\n".format(ssh_port))
            else:
                file.write(line)

    # Start the SSH service
    start_ssh_command = ['sudo', '/usr/sbin/sshd', '-f', custom_sshd_config_file]
    process = subprocess.Popen(start_ssh_command, stdout=subprocess.PIPE)
    output, _ = process.communicate()
    return_code = process.wait()
    if return_code != 0:
        result = "Failed"
        description = f"Failed to start sshd service from {custom_sshd_config_file}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_custom_config_file()
        delete_newUser()
        change_apache2_port(current_port)
        restart_apache2()
        sys.exit(1)


    print("Start packet capture")
    sniffer = AsyncSniffer(filter=f"tcp dst port {http_port} or tcp dst port {ssh_port}", prn=lambda x: packet_handler(x, target_ip), store=0)
    sniffer.start()
    # Wait for the sniffer to complete (will be stopped by timer or timeout)
    sniffer.join(timeout=300)
    # Stop if still running
    if sniffer.running:
        sniffer.stop()

    if httpPacketCapture:
        if sshPacketCapture:
            result = "Passed"
            description = "Received HTTP and SSH request"
        else:
            result = "Failed"
            description = "Received HTTP request but didn't receive SSH request"
    elif sshPacketCapture:
           result = "Failed"
           description = "Received SSH request but didn't receive HTTP request"
    else:
        result = "Failed"
        description = "Didn't receive HTTP or SSH request"
    write_test_result_to_json(mac_address, test_ID, result, description)

    stop_sshd_service()
    remove_custom_config_file()
    stop_UserProcess()
    delete_newUser()
    change_apache2_port(current_port)
    restart_apache2()

