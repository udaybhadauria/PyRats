import sys
import json
import shutil
import subprocess
import os
import importlib

def check_package(package_name):
    try:
        result = subprocess.run(['dpkg', '-l', package_name], capture_output=True, text=True)
        if 'ii  ' + package_name in result.stdout:
            print("{} is already installed.".format(package_name))
        else:
            print("{} is not installed. Installing...".format(package_name))
            subprocess.run(['sudo', 'apt', 'update'])
            subprocess.run(['sudo', 'apt', 'install', '-y', package_name])
    except subprocess.CalledProcessError as e:
        print("Error checking status of {}: {}".format(package_name, e))

# List of packages to check and install
packages_to_install = ['python3-pip', 'libpcap-dev', 'openssh-server']

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

from scapy.all import *
import netifaces

test_name = "XMBoostPortForward"
packetCapture = False

# Define the username and password for the new user
new_username = 'testuser'
new_password = 'testuser@123'

source_sshd_config_file = '/etc/ssh/sshd_config'
custom_sshd_config_file = '/etc/ssh/sshd_custom_config'

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

def packet_handler(pkt, target_ip, port):
    global packetCapture
    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if tcp_dport == port:
            if ip_src == target_ip:
                print("Source IP matches the target IP address")
                packetCapture = True

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
    print(f"File {custom_sshd_config_file} has been successfully removed.")

def stop_sshd_service():
    process_pattern = "/usr/sbin/sshd -f /etc/ssh/sshd_custom_config"
    # Execute the pkill command to stop the process by matching the command line pattern
    subprocess.run(["sudo", "pkill", "-f", process_pattern])
    print("SSH process with pattern '{}' has been stopped.".format(process_pattern))

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
        return True, getValue
    else:
        print(f"Failed to get the value of {parameter}")
        return False, getValue

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 xmPortForward_LAN.py <test_ID> <mac_address> <webserver_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ip = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    response, pvdEnable = webpa_get(mac_address, pvdParameter)
    if not response:
        result = "Failed"
        description = "Failed to get the value of {pvdParameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    print(f"speedboost feature - {pvdEnable}")
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        time.sleep(5)
        sys.exit(1)

    # Create a new user
    create_user_command = ['sudo', 'useradd', new_username, '-m']
    create_user_process = subprocess.run(create_user_command)
    if create_user_process.returncode != 0:
        result = "Failed"
        description = f"Failed to create new user: {new_username}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Set the password for the new user
    set_password_command = ['sudo', 'passwd', new_username]
    set_password_process = subprocess.Popen(set_password_command, stdin=subprocess.PIPE)
    set_password_process.communicate(input=f'{new_password}\n{new_password}\n'.encode())
    if set_password_process.returncode != 0:
        result = "Failed"
        description = f"Failed to set password for new user: {new_username}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Copy the sshd_config file to ssh_custom_config
    shutil.copyfile(source_sshd_config_file, custom_sshd_config_file)
    if not os.path.exists(custom_sshd_config_file):
        result = "Failed"
        description = "Failed to copy sshd_config file to shhd_custom_config file"
        write_test_result_to_json(mac_address, test_ID, result, description)
        delete_newUser()
        sys.exit(1)

    time.sleep(15)

    # ------------------------------- Case 1: Run ssh service on port 40500 ----------------------------
    # Modify the Port line in ssh_custom_config to use port 40500
    with open(custom_sshd_config_file, 'r') as file:
        lines = file.readlines()

    ssh_port = 40500
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
        description = f"Failed to start sshd service on port 40500"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_custom_config_file()
        delete_newUser()
        sys.exit(1)
    else:
        print("SSH process started on port 40500")

    print("capture packet on port 40500")
    sniff(filter="tcp dst port {}".format(ssh_port), prn=lambda x: packet_handler(x, target_ip, ssh_port), store=0, timeout=80)
    print("packet capture completed")

    stop_sshd_service()
    print("SSH process running on port 40500 stopped")
    stop_UserProcess()
    # --------------------------------------------------------------------------------------------------

    # ------------------------------- Case 2: Run ssh service on port 45500 ----------------------------
    # Modify the Port line in ssh_custom_config to use port 45500
    with open(custom_sshd_config_file, 'r') as file:
        lines = file.readlines()

    ssh_port = 45500
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
        description = f"Failed to start sshd service on port 45500"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_custom_config_file()
        delete_newUser()
        sys.exit(1)
    else:
        print("SSH process started on port 45500")

    print("capture packet on port 45500")
    sniff(filter="tcp dst port {}".format(ssh_port), prn=lambda x: packet_handler(x, target_ip, ssh_port), store=0, timeout=80)
    print("packet capture completed")

    stop_sshd_service()
    print("SSH process running on port 45500 stopped")
    stop_UserProcess()

    # --------------------------------------------------------------------------------------------------

    # ------------------------------- Case 3: Run ssh service on port 47100 ----------------------------
    # Modify the Port line in ssh_custom_config to use port 47100
    with open(custom_sshd_config_file, 'r') as file:
        lines = file.readlines()

    ssh_port = 47100
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
        description = f"Failed to start sshd service on port 47100"
        write_test_result_to_json(mac_address, test_ID, result, description)
        remove_custom_config_file()
        delete_newUser()
        sys.exit(1)
    else:
        print("SSH process started on port 47100")

    print("capture packet on port 47100")
    sniff(filter="tcp dst port {}".format(ssh_port), prn=lambda x: packet_handler(x, target_ip, ssh_port), store=0, timeout=150)
    print("packet capture completed")

    stop_sshd_service()
    print("SSH process running on port 47100 stopped")
    remove_custom_config_file()
    stop_UserProcess()
    delete_newUser()
    # --------------------------------------------------------------------------------------------------

    result = "Passed"
    description = "Successfully ran the ssh service on 40500, 45500 & 47100 ports"
    write_test_result_to_json(mac_address, test_ID, result, description)
