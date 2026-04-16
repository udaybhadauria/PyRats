import sys
import socket
import subprocess
import re
import time
import json
import importlib
import shutil

test_name = "Connectivity"

# Check if traceroute utility is installed
if shutil.which("traceroute") is None:
    print("traceroute is not installed. Installing...")
    subprocess.run(["sudo", "apt-get", "install", "-y", "traceroute"], check=True)

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

check_package('python3-pip')

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

check_python_package('requests')

import requests

def test_dns_record(ip, dns_record):
    try:
        start_time = time.time()
        socket.getaddrinfo(dns_record, None, family=ip)
        end_time = time.time()
        return True, "✓"
    except Exception as e:
        return False, "✗"

def test_service_provider(url):
    try:
        start_time = time.time()
        requests.get(url)
        end_time = time.time()
        return True, "✓"
    except Exception as e:
        return False, "✗"

def test_curl(url):
    try:
        start_time = time.time()
        result = subprocess.run(["curl", "-o", "/dev/null", "-s", "-w", "%{http_code}", url],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        end_time = time.time()
        http_code = result.stdout.strip()
        if http_code == "200":
            return True, "✓"
        else:
            return False, "✗"
    except Exception as e:
        return False, "✗"

def test_traceroute(destination):
    try:
        result = subprocess.run(["traceroute", "-w", "2", destination],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        hops = len(re.findall(r'\n\s*\d+\s', result.stdout))
        return True, "✓"
    except Exception as e:
        return False, "✗"

def test_latency(destination):
    try:
        result = subprocess.run(["ping", "-c", "4", destination],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        avg_latency = re.search(r'rtt min/avg/max/mdev = \d+.\d+/(\d+.\d+)/\d+.\d+/\d+.\d+ ms', result.stdout)
        if avg_latency:
            return True, "✓"
        else:
            return False, "✗"
    except Exception as e:
        return False, "✗"

def test_jitter(destination):
    try:
        result = subprocess.run(["ping", "-c", "10", destination],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        mdev = re.search(r'rtt min/avg/max/mdev = \d+.\d+/\d+.\d+/\d+.\d+/(\d+.\d+) ms', result.stdout)
        if mdev:
            return True, "✓"
        else:
            return False, "✗"
    except Exception as e:
        return False, "✗"

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

    print(f"Test result data has been written to {file_name}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 Connectivity.py <test_ID> <mac_address>")
        sys.exit(1)

    test_ID = int(sys.argv[1])
    mac_address = sys.argv[2]

    successTestCount = 0
    FinalResult = "Test Results: "

    tests = [
        ("IPv4 DNS", test_dns_record, socket.AF_INET, "ipv4.test-ipv6.com"),
        ("IPv6 DNS", test_dns_record, socket.AF_INET6, "ipv6.test-ipv6.com"),
        ("Dual Stack DNS", test_dns_record, socket.AF_INET, "ds.test-ipv6.com"),
        ("Dual Stack DNS large packet", test_dns_record, socket.AF_INET, "cloudflare.com"),
        ("IPv6 large packet", test_dns_record, socket.AF_INET6, "cloudflare.com"),
        ("ISP's DNS", test_service_provider, "https://test-ipv6.com/"),
        ("IPv4 Provider", test_service_provider, "https://test-ipv4.com/"),
        ("IPv6 Provider", test_service_provider, "https://test-ipv6.com/"),
        ("cURL IPv4", test_curl, "https://test-ipv4.com/"),
        ("Traceroute IPv4", test_traceroute, "test-ipv4.com"),
        ("Latency IPv4", test_latency, "test-ipv4.com"),
        ("Jitter IPv4", test_jitter, "test-ipv4.com")
    ]

    for desc, func, *args in tests:
        passed, output = func(*args)
        if passed:
            successTestCount += 1
        FinalResult += f"{desc}-{output},"
    FinalResult = FinalResult.rstrip(",")

    connectivityScore = int((successTestCount / len(tests)) * 10)

    if connectivityScore == 10:
        result = "Passed"
    else:
        result = "Failed"
    description = f"Score: {connectivityScore}/10. {FinalResult}"

    write_test_result_to_json(mac_address, test_ID, result, description)
