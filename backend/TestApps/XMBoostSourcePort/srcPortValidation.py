import sys
import json
import subprocess
import importlib
import ipaddress
from urllib.parse import urlencode
import shutil

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
required_python_packages = ['scapy']
for package in required_python_packages:
    check_python_package(package)

from scapy.all import *

test_name = "XMBoostSourcePort"

ipv4HttpPacket = False
ipv4HttpsPacket = False
ipv4UnexpectedhttpSrcport = False
ipv4UnexpectedhttpsSrcport = False
ipv6HttpPacket = False
ipv6HttpsPacket = False
ipv6UnexpectedhttpSrcport = False
ipv6UnexpectedhttpsSrcport = False

def nonXMBoost_packet_handler(pkt):
    global ipv4HttpPacket
    global ipv4HttpsPacket
    global ipv4UnexpectedhttpSrcport
    global ipv4UnexpectedhttpsSrcport
    global ipv6HttpPacket
    global ipv6HttpsPacket
    global ipv6UnexpectedhttpSrcport
    global ipv6UnexpectedhttpsSrcport

    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if ip_src == target_ipv4:
            print(f"Source IP {ip_src} matches the target IP {target_ipv4} address")
            print(f"Source port: {tcp_sport} destination port: {tcp_dport}")
            if tcp_dport == 80:
                ipv4HttpPacket = True
                if (XM_ipv4_start_port <= tcp_sport <= XM_ipv4_end_port):
                    ipv4UnexpectedhttpSrcport = True
            elif tcp_dport == 443:
                ipv4HttpsPacket = True
                if (XM_ipv4_start_port <= tcp_sport <= XM_ipv4_end_port):
                    ipv4UnexpectedhttpsSrcport = True
    if IPv6 in pkt and TCP in pkt:
        ip_src = pkt[IPv6].src
        ip_dst = pkt[IPv6].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        ipv6_src = ipaddress.IPv6Address(ip_src)
        if ipv6_src in target_ipv6:
            print(f"Source IP {ip_src} matches the target IP {target_ipv6} address")
            print(f"Source port: {tcp_sport} destination port: {tcp_dport}")
            if tcp_dport == 80:
                ipv6HttpPacket = True
                if (XM_ipv6_start_port <= tcp_sport <= XM_ipv6_end_port):
                    ipv6UnexpectedhttpSrcport = True
            elif tcp_dport == 443:
                ipv6HttpsPacket = True
                if (XM_ipv6_start_port <= tcp_sport <= XM_ipv6_end_port):
                    ipv6UnexpectedhttpsSrcport = True

def XMBoost_packet_handler(pkt):
    global ipv4HttpPacket
    global ipv4HttpsPacket
    global ipv4UnexpectedhttpSrcport
    global ipv4UnexpectedhttpsSrcport
    global ipv6HttpPacket
    global ipv6HttpsPacket
    global ipv6UnexpectedhttpSrcport
    global ipv6UnexpectedhttpsSrcport

    if IP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if ip_src == target_ipv4:
            print(f"Source IP {ip_src} matches the target IP {target_ipv4} address")
            print(f"Source port: {tcp_sport} destination port: {tcp_dport}")
            if tcp_dport == 80:
                ipv4HttpPacket = True
                if not (XM_ipv4_start_port <= tcp_sport <= XM_ipv4_end_port):
                    ipv4UnexpectedhttpSrcport = True
            elif tcp_dport == 443:
                ipv4HttpsPacket = True
                if not (XM_ipv4_start_port <= tcp_sport <= XM_ipv4_end_port):
                    ipv4UnexpectedhttpsSrcport = True
    elif IPv6 in pkt and TCP in pkt:
        ip_src = pkt[IPv6].src
        ip_dst = pkt[IPv6].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        ipv6_src = ipaddress.IPv6Address(ip_src)
        if ipv6_src in target_ipv6:
            print(f"Source IP {ip_src} matches the target IP {target_ipv6} address")
            print(f"Source port: {tcp_sport} destination port: {tcp_dport}")
            if tcp_dport == 80:
                ipv6HttpPacket = True
                if not (XM_ipv6_start_port <= tcp_sport <= XM_ipv6_end_port):
                    ipv6UnexpectedhttpSrcport = True
            elif tcp_dport == 443:
                ipv6HttpsPacket = True
                if not (XM_ipv6_start_port <= tcp_sport <= XM_ipv6_end_port):
                    ipv6UnexpectedhttpsSrcport = True

def packet_capture(pkt):
    global ipv4HttpsPacket
    global ipv4UnexpectedhttpsSrcport
    global ipv6HttpsPacket
    global ipv6UnexpectedhttpsSrcport

    if IP in pkt and TCP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        if ip_src == target_ipv4:
            print(f"Source IP {ip_src} matches the target IP {target_ipv4} address")
            print(f"Source port: {tcp_sport} destination port: {tcp_dport}")
            if tcp_dport == 443:
                ipv4HttpsPacket = True
                if not (nonXM_ipv4_start_port <= tcp_sport <= nonXM_ipv4_end_port):
                    ipv4UnexpectedhttpSrcport = True
    elif IPv6 in pkt and TCP in pkt:
        ip_src = pkt[IPv6].src
        ip_dst = pkt[IPv6].dst
        tcp_sport = pkt[TCP].sport
        tcp_dport = pkt[TCP].dport
        ipv6_src = ipaddress.IPv6Address(ip_src)
        if ipv6_src in target_ipv6:
            print(f"Source IP {ip_src} matches the target IP {target_ipv6} address")
            print(f"Source port: {tcp_sport} destination port: {tcp_dport}")
            if tcp_dport == 443:
                ipv6HttpsPacket = True
                if not (nonXM_ipv6_start_port <= tcp_sport <= nonXM_ipv6_end_port):
                    ipv6UnexpectedhttpSrcport = True

def write_test_result_to_json(mac_address, test_ID, result, description):
    test_result = {
        "Device_Mac": mac_address,
        "Test_ID": test_ID,
        "Result": result,
        "Description": description
    }

    file_name = f"test_results_{test_name}_{mac_address}.json"

    try:
        with open(file_name, 'r') as json_file:
            existing_data = json.load(json_file)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        existing_data = {"test_results": []}

    existing_data["test_results"].append(test_result)

    with open(file_name, 'w') as json_file:
        json.dump(existing_data, json_file, indent=4)

    print("Test result data has been written to", file_name)

def validateNonXMBoostSrcPort():
    global ipv4HttpPacket; ipv4HttpPacket = False
    global ipv4HttpsPacket; ipv4HttpsPacket = False
    global ipv4UnexpectedhttpSrcport; ipv4UnexpectedhttpSrcport = False
    global ipv4UnexpectedhttpsSrcport; ipv4UnexpectedhttpsSrcport = False
    global ipv6HttpPacket; ipv6HttpPacket = False
    global ipv6HttpsPacket; ipv6HttpsPacket = False
    global ipv6UnexpectedhttpSrcport; ipv6UnexpectedhttpSrcport = False
    global ipv6UnexpectedhttpsSrcport; ipv6UnexpectedhttpsSrcport = False
    ipv4TestFlag = False; ipv6TestFlag = False; testFlag = False

    print("Validate the source port of NonXMBoost Client")
    sniff(filter=f"tcp and (ip or ip6) and (dst port 80 or dst port 443)", prn=nonXMBoost_packet_handler, store=0, timeout=60)

    # IPv4 validation
    if ipv4HttpPacket and ipv4HttpsPacket:
        if ipv4UnexpectedhttpSrcport or ipv4UnexpectedhttpsSrcport:
            ipv4description = "Source port received is in SpeedBoost range"
        else:
            ipv4TestFlag = True
            ipv4description = "Success"
    else:
        ipv4description = "Expected packets not received"

    # IPv6 validation
    if ipv6HttpPacket and ipv6HttpsPacket:
        if ipv6UnexpectedhttpSrcport or ipv6UnexpectedhttpsSrcport:
            ipv6description = "Source port received is in SpeedBoost range"
        else:
            ipv6TestFlag = True
            ipv6description = "Success"
    else:
        ipv6description = "Expected packets not received"

    if ipv4TestFlag and ipv6TestFlag:
        testFlag = True
    description = f"NonXMBoost Client(IPv4-{ipv4description}, IPv6-{ipv6description}) "
    return testFlag, description

def validateXMBoostSrcPort():
    global ipv4HttpPacket; ipv4HttpPacket = False
    global ipv4HttpsPacket; ipv4HttpsPacket = False
    global ipv4UnexpectedhttpSrcport; ipv4UnexpectedhttpSrcport = False
    global ipv4UnexpectedhttpsSrcport; ipv4UnexpectedhttpsSrcport = False
    global ipv6HttpPacket; ipv6HttpPacket = False
    global ipv6HttpsPacket; ipv6HttpsPacket = False
    global ipv6UnexpectedhttpSrcport; ipv6UnexpectedhttpSrcport = False
    global ipv6UnexpectedhttpsSrcport; ipv6UnexpectedhttpsSrcport = False
    ipv4TestFlag = False; ipv6TestFlag = False; testFlag = False

    print(f"Validate the source port of XMBoost Client")
    sniff(filter=f"tcp and (ip or ip6) and (dst port 80 or dst port 443)", prn=XMBoost_packet_handler, store=0, timeout=60)

    # IPv4 validation
    if ipv4HttpPacket and ipv4HttpsPacket:
        if ipv4UnexpectedhttpSrcport or ipv4UnexpectedhttpsSrcport:
            ipv4description = "Source port received is not in SpeedBoost range"
        else:
            ipv4TestFlag = True
            ipv4description = "Success"
    else:
        ipv4description = "Expected packets not received"

    # IPv6 validation
    if ipv6HttpPacket and ipv6HttpsPacket:
        if ipv6UnexpectedhttpSrcport or ipv6UnexpectedhttpsSrcport:
            ipv6description = "Source port received is not in SpeedBoost range"
        else:
            ipv6TestFlag = True
            ipv6description = "Success"
    else:
        ipv6description = "Expected packets not received"

    if ipv4TestFlag and ipv6TestFlag:
        testFlag = True
    description = f"XMBoost Client(IPv4-{ipv4description}, IPv6-{ipv6description}) "
    return testFlag, description

def checkNormalSrcPort():
    global ipv4HttpsPacket; ipv4HttpsPacket = False
    global ipv4UnexpectedhttpsSrcport; ipv4UnexpectedhttpsSrcport = False
    global ipv6HttpsPacket; ipv6HttpsPacket = False
    global ipv6UnexpectedhttpsSrcport; ipv6UnexpectedhttpsSrcport = False

    ipv4TestFlag = False; ipv6TestFlag = False; testFlag = False
    print(f"Validate the source port of NonXMBoost Client when source port is within speedboost range")

    sniff(filter=f"tcp and (ip or ip6) and (dst port 443)", prn=packet_capture, store=0, timeout=60)

    # IPv4 validation
    if ipv4HttpsPacket:
        if  ipv4UnexpectedhttpsSrcport:
            ipv4description = "Source port received is not in Normal range"
        else:
            ipv4TestFlag = True
            ipv4description = "Success"
    else:
        ipv4description = "Expected packets not received"

    # IPv6 validation
    if ipv6HttpsPacket:
        if  ipv6UnexpectedhttpsSrcport:
            ipv6description = "Source port received is not in Normal range"
        else:
            ipv6TestFlag = True
            ipv6description = "Success"
    else:
        ipv6description = "Expected packets not received"

    if ipv4TestFlag and ipv6TestFlag:
        testFlag = True
    description = f"NonXMBoost Client with XM port(IPv4-{ipv4description}, IPv6-{ipv6description})"
    return testFlag, description

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
    else:
        result = "Failed"
        description = f"Failed to get the value of {parameter}"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)
    return getValue

def webpa_set(mac_address, parameter, value, type):
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
    else:
       print(f"Failed to set the value of {parameter}")

def fetch_ports(parameter):
    ipv4_start_port = 0
    ipv4_end_port = 0
    ipv6_start_port = 0
    ipv6_end_port = 0
    portRange = webpa_get(mac_address, parameter)
    #Extract IPv4 & IPv6 port range
    port_ranges_split = portRange.split(',')
    for range_info in port_ranges_split:
        if 'IPv4' in range_info:
            port_values = range_info.split()[2:]
            if len(port_values) >= 2:
                ipv4_start_port = int(port_values[0])
                ipv4_end_port = int(port_values[1])
        elif 'IPv6' in range_info:
            port_values = range_info.split()[2:]
            if len(port_values) >= 2:
                ipv6_start_port = int(port_values[0])
                ipv6_end_port = int(port_values[1])
    return ipv4_start_port, ipv4_end_port, ipv6_start_port, ipv6_end_port

def set_blob(mac_address, subdoc, json):
    post_command = f"java -jar {utility_path} blob_enable {mac_address} {subdoc} {json}"
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
        print("Successfully added the speedboost client")
        return True
    else:
        print("Failed to add the XMBoost Client")
        return False

if __name__ == "__main__":
    global XM_ipv4_start_port; XM_ipv4_start_port = None
    global XM_ipv4_end_port; XM_ipv4_end_port = None
    global XM_ipv6_start_port; XM_ipv6_start_port = None
    global XM_ipv6_end_port; XM_ipv6_end_port = None

    global nonXM_ipv4_start_port; nonXM_ipv4_start_port = None
    global nonXM_ipv4_end_port; nonXM_ipv4_end_port = None
    global nonXM_ipv6_start_port; nonXM_ipv6_start_port = None
    global nonXM_ipv6_end_port; nonXM_ipv6_end_port = None

    global target_ipv6; target_ipv6 = None

    if len(sys.argv) < 4:
        print("Usage: python3 srcPortValidation.py <test_ID> <mac_address> <client_mac> <gateway_Wan_IPv4>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    client_mac = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    pvdEnable = webpa_get(mac_address, pvdParameter)
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in the device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if len(sys.argv) == 5:
        target_ipv4 = sys.argv[4]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        target_ipv4 = webpa_get(mac_address, parameter)

    target_ipv6Prefix = webpa_get(mac_address, "Device.IP.Interface.1.IPv6Prefix.1.Prefix")
    target_ipv6 = ipaddress.IPv6Network(target_ipv6Prefix)

    xmPortParameter = "Device.X_RDK_Speedboost.PortRanges"
    XM_ipv4_start_port, XM_ipv4_end_port, XM_ipv6_start_port, XM_ipv6_end_port = fetch_ports(xmPortParameter)
    print(f"Speedboost Port Range - IPv4: {XM_ipv4_start_port}-{XM_ipv4_end_port}, IPv6: {XM_ipv6_start_port}-{XM_ipv6_end_port}")

    portParameter = "Device.X_RDK_Speedboost.NormalPortRange"
    nonXM_ipv4_start_port, nonXM_ipv4_end_port, nonXM_ipv6_start_port, nonXM_ipv6_end_port = fetch_ports(portParameter)
    print(f"Normal Port Range- IPv4: {nonXM_ipv4_start_port}-{nonXM_ipv4_end_port}, IPv6: {nonXM_ipv6_start_port}-{nonXM_ipv6_end_port}")

    if pvdEnable == "false":
        webpa_set(mac_address, pvdParameter, True, 3)
    time.sleep(15)
    Enabled = webpa_get(mac_address, pvdParameter)
    if Enabled != "true":
        result = "Failed"
        Description = "Failed to enable speedboost feature"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Validate the NonXMBoost client source port
    result1, description1 = validateNonXMBoostSrcPort()

    mac = client_mac.replace(":", "")
    data = {
        "device_mac_list": [mac],
        "duration": 1
    }

    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]

    # Add speedboost client
    subdoc = "xmspeedboost"
    response = set_blob(mac_address, subdoc, encoded_json)
    if not response:
        result = "Failed"
        description = "Failed to add the XMBoost Client"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)

    currentDevices = webpa_get(mac_address, "Device.X_RDK_Speedboost.CurrentDeviceList")
    if currentDevices:
        device_list = currentDevices.split(',')
        if client_mac in device_list:
            print("Speedboost client added")
        else:
            result = "Failed"
            description = "Failed to add the XMBoost Client"
            write_test_result_to_json(mac_address, test_ID, result, description)
            webpa_set(mac_address, pvdParameter, pvdEnable, 3)
            sys.exit(1)
    else:
        result = "Failed"
        description = "Failed to add the XMBoost Client"
        write_test_result_to_json(mac_address, test_ID, result, description)
        webpa_set(mac_address, pvdParameter, pvdEnable, 3)
        sys.exit(1)

    time.sleep(20)

    # Validate the Speedboost client source port
    result2, description2 = validateXMBoostSrcPort()

    # Validate the NonXMBoost client source port when the request enforced with XMBoost port range
    result3, description3 = checkNormalSrcPort()

    if result1 and result2 and result3:
        result = "Passed"
    else:
        result = "Failed"
    description = description1 + description2 + description3

    webpa_set(mac_address, pvdParameter, pvdEnable, 3)
    write_test_result_to_json(mac_address, test_ID, result, description)
