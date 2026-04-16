import subprocess
import sys
import json
import time
import importlib
import random

test_name = "XMBoostSourcePort"
time_out = 15

def test_website_access(httpWebsite, httpsWebsite):
    testFlag = False
    try:
        http_curl_process = subprocess.run(['curl', '--connect-timeout', str(time_out), '-k', '-I', httpWebsite], capture_output=True, text=True)
        https_curl_process = subprocess.run(['curl', '--connect-timeout', str(time_out), '-k', '-I', httpsWebsite], capture_output=True, text=True)

        if http_curl_process.returncode == 0 and https_curl_process.returncode == 0:
            if 'HTTP/1.1 200 OK' in http_curl_process.stdout and 'HTTP/1.1 200 OK' in https_curl_process.stdout:
                testFlag = True
                description = "Success"
            else:
                description = "Failed to access"
        else:
            description = "Error occurred"
    except Exception as e:
        description = "Error occurred"

    return testFlag, description

def test_netcat(port, target_ip):
    srcPort = str(port)
    testFlag = False

    netcat_command = ["netcat", "-z", "-v", "-w", "15", target_ip, "443", "-p", srcPort]
    process = subprocess.Popen(netcat_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.communicate()

    if process.returncode == 0:
        testFlag = True
        description = "Success"
    else:
        description = "Failed to access"

    return testFlag, description

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

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python3 serveraccess.py <test_ID> <mac_address> <webserver_IPv4> <webserver_IPv6>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    target_ipv4 = sys.argv[3]
    target_ipv6 = sys.argv[4]

    print(f"ipv4 - {target_ipv4} , ipv6 - {target_ipv6}")
    ipv4HttpSite = "http://"+target_ipv4+"/"
    ipv4HttpsSite = "https://"+target_ipv4+"/"
    ipv6HttpSite = "http://["+target_ipv6+"]"
    ipv6HttpsSite = "https://["+target_ipv6+"]:443"

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    pvdParameter = "Device.RouterAdvertisement.X_RDK_PvD.Enable"
    pvdEnable = webpa_get(mac_address, pvdParameter)
    if pvdEnable is None or pvdEnable == "" or pvdEnable.lower() == "null":
        result = "NoSupp"
        description = "SpeedBoost feature is not supported in device"
        write_test_result_to_json(mac_address, test_ID, result, description)
        time.sleep(5)
        sys.exit(1)

    xmPortParameter = "Device.X_RDK_Speedboost.PortRanges"
    XM_ipv4_start_port, XM_ipv4_end_port, XM_ipv6_start_port, XM_ipv6_end_port = fetch_ports(xmPortParameter)
    print(f"Speedboost ports - IPv4: {XM_ipv4_start_port}-{XM_ipv4_end_port} IPv6: {XM_ipv6_start_port}-{XM_ipv6_end_port}")

    time.sleep(40)
    print("Access Server 1")
    ipv4Result1, ipv4Description1 = test_website_access(ipv4HttpSite, ipv4HttpsSite)
    ipv6Result1, ipv6Description1 = test_website_access(ipv6HttpSite, ipv6HttpsSite)

    time.sleep(90)
    print("Access Server 2")
    ipv4Result2, ipv4Description2 = test_website_access(ipv4HttpSite, ipv4HttpsSite)
    ipv6Result2, ipv6Description2 = test_website_access(ipv6HttpSite, ipv6HttpsSite)

    time.sleep(60)
    print("Access Server 3")
    random_port1 = random.randint(XM_ipv4_start_port, XM_ipv4_end_port)
    random_port2 = random.randint(XM_ipv6_start_port, XM_ipv6_end_port)
    while random_port1 == random_port2:
        random_port2 = random.randint(XM_ipv6_start_port, XM_ipv6_end_port)

    ipv4Result3, ipv4Description3 = test_netcat(random_port1, target_ipv4)
    ipv6Result3, ipv6Description3 = test_netcat(random_port2, target_ipv6)

    if ipv4Result1 and ipv6Result1 and ipv4Result2 and ipv6Result2 and ipv4Result3 and ipv6Result3:
        result = "Passed"
    else:
        result = "Failed"
    description = f"ServerAccess1(IPv4-{ipv4Description1}, IPv6-{ipv6Description1}) ServerAccess2(IPv4-{ipv4Description2}, IPv6-{ipv6Description2}) ServerAccess with XM port(IPv4-{ipv4Description3}, IPv6-{ipv6Description3})"
    write_test_result_to_json(mac_address, test_ID, result, description)
