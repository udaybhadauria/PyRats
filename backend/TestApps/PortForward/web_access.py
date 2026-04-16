import subprocess
import sys
import json
import time
from urllib.parse import urlencode

test_name = "PortForward"
portForward_details = {}
portForward_rules = None
subdoc = "portforwarding"
new_port = 19897
PFparameter = "Device.NAT.X_Comcast_com_EnablePortMapping"

def webpa_get(mac_address, parameter):
    getValue = None
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
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
            print(f"Get for {parameter} failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    print(f"[ERROR] WebPA get for {parameter} failed")
    result = "Failed"
    description = f"WebPA get for {parameter} failed"
    write_test_result_to_json(mac_address, test_ID, result, description)
    sys.exit(1)

# Function to enable or disable the PortForward
def ChangePFStatus(mac_address, parameter, value):
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        set_command = f"java -jar {utility_path} webpa_set {mac_address} {parameter} {value} 3"
        set_response = subprocess.run(set_command, shell=True, capture_output=True, text=True).stdout
        response_lines = set_response.splitlines()
        response_code = None
        for line in response_lines:
            if line.startswith("Response_Code"):
                response_code = int(line.split('=')[1].strip())
                break
        if response_code == 200:
            return True
        print(f"Set for {parameter} failed, attempt {attempt + 1}/{max_retries}")
        if attempt < max_retries - 1:
            print(f"Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
    return False

# Function to fetch the rowid of the blob
def fetch_row_id():
    row_id = None
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        get_command = f"java -jar {utility_path} blob_get {mac_address} {subdoc}"
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
            print("Successfully got the portForwarding Rule")
            response_json = json.loads(response_body)
            response_data = response_json['output'].split('Response = ')
            json_data = json.loads(response_data[1])
            data = json_data['data']
            for item in data:
                if item['name'] == 'RATSPFTest':
                    row_id = item['row_id']
                    break
            return row_id
        else:
            print(f"Row ID fetch failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return row_id

# Function to fetch the Existing PF rule and check rule exist for same port using webcfg
def FetchPFBlob():
    global portForward_details
    response = False
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        get_command = f"java -jar {utility_path} blob_get {mac_address} {subdoc}"
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
            print("Successfully got the portForwarding Rule")
            response_json = json.loads(response_body)
            response_data = response_json['output'].split('Response = ')
            json_data = json.loads(response_data[1])
            data = json_data['data']
            for item in data:
                if int(item['wan_port_start']) <= new_port <= int(item['wan_port_end']):
                    print(f"PF rule found with port {new_port} using webcfg")
                    portForward_details['status'] = item['enabled']
                    portForward_details['client_ip'] = item['ip_address']
                    portForward_details['name'] = item['name']
                    portForward_details['protocol'] = item['protocol']
                    portForward_details['startPort'] = item['wan_port_start']
                    portForward_details['endPort'] = item['wan_port_end']
                    portForward_details['rowid'] = item['row_id']
                    response = True
                    break
            return response
        else:
            print(f"PortForwarding rule fetch failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    print("[ERROR] Webcfg fetch for PortForwarding rule failed")
    result = "Failed"
    description = "Webcfg fetch for PortForwarding rule failed"
    write_test_result_to_json(mac_address, test_ID, result, description)
    if PFEnable == "false":
        ChangePFStatus(mac_address, PFparameter, "false")
    sys.exit(1)

# Function to delete the blob
def delete_blob(group):
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        delete_command = f"java -jar {utility_path} blob_disable {mac_address} {subdoc} {group}"
        delete_response = subprocess.run(delete_command, shell=True, capture_output=True, text=True).stdout
        response_lines = delete_response.splitlines()
        response_code = None
        response_body = None
        for line in response_lines:
            if line.startswith("Response_Code"):
                response_code = int(line.split('=')[1].strip())
            elif line.startswith("Response_Body"):
                response_body = line
        if response_code == 200 and "DELETE Request Successful" in response_body:
            print("Successfully deleted the PortForwarding Rule")
            return True
        else:
            print(f"PortForwarding rule delete failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return False

# Function to Check any PF rule exists on same port using webpa
def CheckExistingPF():
    global portForward_rules
    index = None
    parameter = "Device.NAT.PortMapping."
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
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
            output_data = response_json["output"]
            rules = output_data[31:-4]
            if rules == "EMPTY" or rules == "" or rules is None or rules == "null":
                portForward_rules = []
                return index
            portForward_rules = json.loads(rules)
            lookup_dict = {item['name']: item['value'] for item in portForward_rules}
            for key, value in lookup_dict.items():
                if 'ExternalPortEndRange' in key:
                    values = key.split('.')
                    i = values[3]
                    startPort = lookup_dict.get(f"Device.NAT.PortMapping.{i}.ExternalPort")
                    endPort = lookup_dict.get(f"Device.NAT.PortMapping.{i}.ExternalPortEndRange")
                    if int(startPort) <= new_port <= int(endPort):
                        print(f"Found PF rule with Port {new_port}")
                        index = i
                        break
            return index
        else:
            print(f"Existing PortForwarding rules fetch for PortForwarding rules failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    print("[ERROR] WebPA fetch for PortForwarding rules failed ")
    result = "Failed"
    description = "WebPA fetch for PortForwarding rules failed"
    write_test_result_to_json(mac_address, test_ID, result, description)
    if PFEnable == "false":
        ChangePFStatus(mac_address, PFparameter, "false")
    sys.exit(1)

# Function to Check the PF rule is added
def checkPFAdded(client_ip):
    getResponse = False
    pfResponse = False
    parameter = "Device.NAT.PortMapping."
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
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
            getResponse = True
            response_json = json.loads(response_body)
            output_data = response_json["output"]
            rules = output_data[31:-4]
            if rules == "EMPTY":
                return getResponse, pfResponse
            nested_data = json.loads(rules)
            lookup_dict = {item['name']: item['value'] for item in nested_data}
            for key, value in lookup_dict.items():
                if 'Description' in key:
                    if value == "RATSPFTest":
                        values = key.split('.')
                        index = values[3]
                        external_port = lookup_dict.get(f"Device.NAT.PortMapping.{index}.ExternalPort")
                        external_port_end_range = lookup_dict.get(f"Device.NAT.PortMapping.{index}.ExternalPortEndRange")
                        internalClient = lookup_dict.get(f"Device.NAT.PortMapping.{index}.InternalClient")
                        if external_port == str(new_port) and external_port_end_range == str(new_port) and internalClient == client_ip:
                            pfResponse = True
                            print(f"Successfully added PortForward Rule on port {new_port}")
                            break
            return getResponse, pfResponse
        else:
            print(f"Failed to check PF rule added,, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return getResponse, pfResponse

# Function to collect the Existing PF rule data if rule exists with same port range
def collectPFData(index):
    global portForward_details
    for item in portForward_rules:
        if item['name'] == f"Device.NAT.PortMapping.{index}.Enable":
            portForward_details['Enable'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.Alias":
            portForward_details['Alias'] = item['value'] if item['value'] != '' else ' '
        elif item['name'] == f"Device.NAT.PortMapping.{index}.AllInterfaces":
            portForward_details['AllInterfaces'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.LeaseDuration":
            portForward_details['LeaseDuration'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.ExternalPort":
            portForward_details['ExternalPort'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.ExternalPortEndRange":
            portForward_details['ExternalPortEndRange'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.InternalPort":
            portForward_details['InternalPort'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.Protocol":
            portForward_details['Protocol'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.InternalClient":
            portForward_details['InternalClient'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.RemoteHost":
            portForward_details['RemoteHost'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.X_Comcast_com_PublicIP":
            portForward_details['X_Comcast_com_PublicIP'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.Description":
            portForward_details['Description'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.Interface":
            portForward_details['Interface'] = item['value']
        elif item['name'] == f"Device.NAT.PortMapping.{index}.X_CISCO_COM_InternalClientV6":
            portForward_details['X_CISCO_COM_InternalClientV6'] = item['value']

# Function to delete the Existing PF rule on same port using webpa
def DeleteExistingRule_Webpa(index):
    parameter = f"Device.NAT.PortMapping.{index}."
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        delete_command = f"java -jar {utility_path} webpa_deletetable {mac_address} {parameter}"
        delete_response = subprocess.run(delete_command, shell=True, capture_output=True, text=True).stdout
        response_lines = delete_response.splitlines()
        response_code = None
        response_body = None
        for line in response_lines:
            if line.startswith("Response_Code"):
                response_code = int(line.split('=')[1].strip())
            elif line.startswith("Response_Body"):
                start_index = line.find("Response_Body=")
                response_body = line[start_index + len("Response_Body="):]
        if response_code == 200 and "Success" in response_body:
            print("Deleted existing PortForward rule")
            return True
        else:
            print(f"Existing PortForward rule delete failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return False

# Function to add the existing PF rule using webpa
def AddExistingRule_webpa():
    parameter = "Device.NAT.PortMapping."
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        data = {
            "Enable": portForward_details['Enable'],
            "Alias": portForward_details['Alias'],
            "AllInterfaces": portForward_details['AllInterfaces'],
            "LeaseDuration": portForward_details['LeaseDuration'],
            "ExternalPort": portForward_details['ExternalPort'],
            "ExternalPortEndRange": portForward_details['ExternalPortEndRange'],
            "InternalPort": portForward_details['InternalPort'],
            "Protocol": portForward_details['Protocol'],
            "InternalClient": portForward_details['InternalClient'],
            "RemoteHost": portForward_details['RemoteHost'],
            "X_Comcast_com_PublicIP": portForward_details['X_Comcast_com_PublicIP'],
            "Interface": portForward_details['Interface'],
            "X_CISCO_COM_InternalClientV6": portForward_details['X_CISCO_COM_InternalClientV6'],
            "Description": portForward_details['Description']
        }
        # Encode the JSON object
        encoded_data = urlencode({"json": json.dumps(data)})
        encoded_json = encoded_data.split("=")[1]
        add_command = f"java -jar {utility_path} webpa_addtable {mac_address} {parameter} {encoded_json}"
        add_response = subprocess.run(add_command, shell=True, capture_output=True, text=True).stdout
        response_lines = add_response.splitlines()
        response_code = None
        response_body = None
        for line in response_lines:
            if line.startswith("Response_Code"):
                response_code = int(line.split('=')[1].strip())
            elif line.startswith("Response_Body"):
                start_index = line.find("Response_Body=")
                response_body = line[start_index + len("Response_Body="):]
        if response_code == 200 and "Success" in response_body:
            print("Restored existing PortForward rule")
            return
        else:
            print(f"Existing PortForward rule add failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)

# Function to enable blob
def set_blob(json_payload):
    max_retries = 5
    retry_delay = 10
    for attempt in range(max_retries):
        post_command = f"java -jar {utility_path} blob_enable {mac_address} {subdoc} {json_payload}"
        post_response = subprocess.run(post_command, shell=True, capture_output=True, text=True).stdout
        response_lines = post_response.splitlines()
        response_code = None
        response_body = None
        for line in response_lines:
            if line.startswith("Response_Code"):
                response_code = int(line.split('=')[1].strip())
            elif line.startswith("Response_Body"):
                start_index = line.find("Response_Body=")
                response_body = line[start_index + len("Response_Body="):]
        if response_code == 200 and "POST Request Successful" in response_body:
            print("[INFO] PortForward rule added")
            return True
        else:
            print(f"PortForward rule add failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
    return False

# Function to add the Existing PF rule on same port back
def AddExistingRule_webcfg():
    max_retries = 3
    retry_delay = 10
    for attempt in range(max_retries):
        # payload
        data = {
            "enabled": portForward_details['status'],
            "ip_address": portForward_details['client_ip'],
            "name": portForward_details['name'],
            "protocol": portForward_details['protocol'],
            "wan_port_end": portForward_details['endPort'],
            "wan_port_start": portForward_details['startPort']
        }
        # Encode the JSON object
        encoded_data = urlencode({"json": json.dumps(data)})
        encoded_json = encoded_data.split("=")[1]
        # Add PortForwarding Rule
        result = set_blob(encoded_json)
        if result:
            print("Restored existing PortForward rule via Webcfg")
            return
        else:
            print(f"Existing PortForward rule add via Webcfg failed, attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)

def deletePFAdded():
    # Get PortForwarding rules & fetch row_id
    row_id = fetch_row_id()
    # Delete the PortForwarding rule
    if row_id:
        group = f"portforwarding_configuration_table/row/{row_id}"
        delete_blob(group)

def test_website_access(website):
    try:
        # Run curl to access the website and capture headers
        curl_process = subprocess.run(['curl', '--connect-timeout', str(15), '-I', website], capture_output=True, text=True)
        # Check the return code of the subprocess
        if curl_process.returncode == 0:
            # Check if the HTTP response code is 200 (OK)
            if 'HTTP/1.1 200 OK' in curl_process.stdout:
                result = "Passed"
                description = "HTTP service access success"
            else:
                result = "Failed"
                description = "Failed to access HTTP service"
        else:
            result = "Failed"
            description = "Failed to access HTTP service"
    except Exception as e:
        result = "Failed"
        description = f"Failed to access HTTP service: {str(e)}"
    return result, description

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
    print("[INFO] Test result data has been written to", file_name)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 web_access.py <test_ID> <mac_address> <lan_client_ip> <gateway_wan_ip>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]
    client_ip = sys.argv[3]

    # Read the Utility path
    file_path = "/home/rats/RATS/Backend/Utility/jar_path.txt"
    with open(file_path, 'r') as file:
        utility_path = file.read().strip()

    if len(sys.argv) == 5:
        target_ip = sys.argv[4]
    else:
        parameter = "Device.DeviceInfo.X_COMCAST-COM_WAN_IP"
        target_ip = webpa_get(mac_address, parameter)

    # Check PortForward is enabled if not enable it
    global PFEnable
    PFEnable = webpa_get(mac_address, PFparameter)
    if PFEnable == "false":
        status = ChangePFStatus(mac_address, PFparameter, "true")
        if not status:
            print("[ERROR] WebPA set to enable PortForward failed")
            result = "Failed"
            description = "WebPA set to enable PortForward failed"
            write_test_result_to_json(mac_address, test_ID, result, description)
            sys.exit(1)
        time.sleep(5)

    Enabled = webpa_get(mac_address, PFparameter)
    if Enabled == "false":
        print("[ERROR] WebPA enable reported success, but PF status is disabled on device")
        result = "Failed"
        description = "PF status is disabled after enabled via WebPA"
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    # Check any PF rule added for same port using webpa
    index = CheckExistingPF()
    if index:
        # Fetch the PF blob using webconfig
        webcfgFound = FetchPFBlob()
        if webcfgFound:
            # Delete the PortForwarding rule using webconfig
            group = f"portforwarding_configuration_table/row/{portForward_details['rowid']}"
            deleteStatus = delete_blob(group)
            if not deleteStatus:
                print("[ERROR] Webcfg delete for existing PF rule failed")
                result = "Failed"
                description = "Webcfg delete for existing PF rule failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                if PFEnable == "false":
                    ChangePFStatus(mac_address, PFparameter, "false")
                sys.exit(1)
        else:
            collectPFData(index)
            # Delete the configuration using webpa
            deleteStatus = DeleteExistingRule_Webpa(index)
            if not deleteStatus:
                print("[ERROR] WebPA delete for existing PF rule failed")
                result = "Failed"
                description = "WebPA delete for existing PF rule failed"
                write_test_result_to_json(mac_address, test_ID, result, description)
                if PFEnable == "false":
                    ChangePFStatus(mac_address, PFparameter, "false")
                sys.exit(1)

        time.sleep(15)
        rule = CheckExistingPF()
        if rule:
            print("[ERROR] Existing PF rule not deleted")
            result = "Failed"
            description = "Existing PF rule not deleted"
            write_test_result_to_json(mac_address, test_ID, result, description)
            if PFEnable == "false":
                ChangePFStatus(mac_address, PFparameter, "false")
            sys.exit(1)
    else:
        print("[INFO] No PortForward Rule exists with same port")

    # payload
    data = {
        "enabled": True,
        "ip_address": client_ip,
        "name": "RATSPFTest",
        "protocol": "TCP/UDP",
        "wan_port_end": new_port,
        "wan_port_start": new_port
    }
    # Encode the JSON object
    encoded_data = urlencode({"json": json.dumps(data)})
    encoded_json = encoded_data.split("=")[1]
    # Add PortForwarding Rule
    response = set_blob(encoded_json)
    if not response:
        print("[ERROR] Webcfg add for PortForward rule failed")
        result = "Failed"
        description = "Webcfg add for PortForward rule failed"
        write_test_result_to_json(mac_address, test_ID, result, description)
        if index:
            if webcfgFound:
                AddExistingRule_webcfg()
            else:
                AddExistingRule_webpa()
        if PFEnable == "false":
            ChangePFStatus(mac_address, PFparameter, "false")
        sys.exit(1)

    print("[INFO]Waiting for 15 seconds for the PortForwarding rule to be re-applied in device")
    time.sleep(15)

    response, ruleAdded = checkPFAdded(client_ip)
    if not response:
        print("[ERROR] WebPA fetch failed after adding PortForward rule")
        result = "Failed"
        description = "WebPA fetch failed after adding PortForward rule"
        deletePFAdded()
        if index:
            if webcfgFound:
                AddExistingRule_webcfg()
            else:
                AddExistingRule_webpa()
        if PFEnable == "false":
            ChangePFStatus(mac_address, PFparameter, "false")
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    if not ruleAdded:
        print("[ERROR] PortForward rule not present on device after add")
        result = "Failed"
        description = "PortForward rule not present on device after add"
        deletePFAdded()
        if index:
            if webcfgFound:
                AddExistingRule_webcfg()
            else:
                AddExistingRule_webpa()
        if PFEnable == "false":
            ChangePFStatus(mac_address, PFparameter, "false")
        write_test_result_to_json(mac_address, test_ID, result, description)
        sys.exit(1)

    website = "http://" + target_ip + ":19897/"
    time.sleep(5)
    print("[INFO] Testing access to client HTTP service via PortForward")
    result, description = test_website_access(website)
    write_test_result_to_json(mac_address, test_ID, result, description)

    deletePFAdded()
    if index:
        if webcfgFound:
            AddExistingRule_webcfg()
        else:
            AddExistingRule_webpa()
    if PFEnable == "false":
        ChangePFStatus(mac_address, PFparameter, "false")
