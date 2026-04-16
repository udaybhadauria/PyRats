import sys
import json
import shutil
import subprocess
import os
import importlib
import time
import pwd
import threading

test_name = "SSHPortForward"
subdoc = "portforwarding"

packetCapture = False
first_packet_time = None
packet_count = 0
wait_after_first_packet = 15  # seconds to wait after first packet before stopping
sniffer = None

new_port = 25634
# Define the username and password for the new user
new_username = 'testuser'
new_password = 'testuser@123'

source_sshd_config_file = '/etc/ssh/sshd_config'
custom_sshd_config_file = '/etc/ssh/sshd_custom_config'

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
    global packetCapture, first_packet_time, packet_count
    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if tcp_dport == new_port:
            if ip_src == target_ip:
                packet_count += 1
                print(f"Source IP matches the target IP address")
                packetCapture = True
                if first_packet_time is None:
                    first_packet_time = time.time()
                    print(f"First packet captured, will stop in {wait_after_first_packet} seconds")
                    # Schedule the stop after wait_after_first_packet seconds
                    stop_timer = threading.Timer(wait_after_first_packet, schedule_stop)
                    stop_timer.start()

def stop_UserProcess():
    # Kill the process running on testuser
    kill_userProcess_command = ['sudo', 'pkill', '-9', '-U', new_username]
    subprocess.run(kill_userProcess_command)

def delete_newUser():
    # Delete the new user
    delete_user_command = ['sudo', 'userdel', new_username]
    subprocess.run(delete_user_command)

    # Remove the user's home directory
    remove_home_command = ['sudo', 'rm', '-r', '/home/testuser']
    subprocess.run(remove_home_command)
    print(f"user: {new_username} deleted successfully")

def remove_custom_config_file():
    os.remove(custom_sshd_config_file)
    print(f"File {custom_sshd_config_file} has been successfully removed")

def stop_sshd_service():
    process_pattern = "/usr/sbin/sshd -f /etc/ssh/sshd_custom_config"
    # Execute the pkill command to stop the process by matching the command line pattern
    subprocess.run(["sudo", "pkill", "-f", process_pattern])
    print("SSH process with pattern '{}' has been stopped.".format(process_pattern))

def user_exists(username):
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 ssh_traffic.py <test_ID> <mac_address> <webserver_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ip = sys.argv[3]

    packages_to_install = ['python3-pip', 'libpcap-dev', 'openssh-server']
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

    from scapy.all import *

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
        description = f"Failed to create user: {new_username}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Set the password for the new user
    set_password_command = ['sudo', 'passwd', new_username]
    set_password_process = subprocess.Popen(set_password_command, stdin=subprocess.PIPE)
    set_password_process.communicate(input=f'{new_password}\n{new_password}\n'.encode())
    if set_password_process.returncode != 0:
        result = "Failed"
        description = f"Failed to set password for user: {new_username}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Copy the sshd_config file to ssh_custom_config
    shutil.copyfile(source_sshd_config_file, custom_sshd_config_file)
    if not os.path.exists(custom_sshd_config_file):
        result = "Failed"
        description = "Failed to copy sshd_config file to sshd_custom_config file"
        write_test_result_to_json(mac_address, test_ID, result, description)
        delete_newUser()
        sys.exit(1)

    # Modify the Port line in ssh_custom_config to use port 4444
    with open(custom_sshd_config_file, 'r') as file:
        lines = file.readlines()

    with open(custom_sshd_config_file, 'w') as file:
        for line in lines:
            if line.startswith("Port") or line.startswith("#Port"):
                file.write("Port {}\n".format(new_port))
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
        sys.exit(1)

    print(f"SSH service started on port {new_port}, waiting to capture packet")
    print(f"Start packet capture on port {new_port}")
    sniffer = AsyncSniffer(filter="tcp dst port {}".format(new_port), prn=lambda x: packet_handler(x, target_ip), store=0)
    sniffer.start()
    # Wait for the sniffer to complete (will be stopped by timer or timeout)
    sniffer.join(timeout=450)

    # Stop if still running
    if sniffer.running:
        sniffer.stop()

    if packetCapture:
        result = "Passed"
        description = "Received SSH request on client"
    else:
        result = "Passed"
        description = "No SSH request received on client"

    print(f"[INFO] Test Result: {result} - {description}")
    write_test_result_to_json(mac_address, test_ID, result, description)

    stop_sshd_service()
    remove_custom_config_file()
    stop_UserProcess()
    delete_newUser()
