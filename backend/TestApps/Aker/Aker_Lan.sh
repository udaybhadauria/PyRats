#!/bin/bash

test_case="$1"
cm_mac="$2"

sleep 20

start_time=$(date +%s)

#=============================================================
#Websites reachability
#=============================================================

# Initialize counters
worked1=0
not_worked1=0

# Define an array of website URLs
websites=("github.com")

# Function to perform ping test for each website
perform_ping_test() {
    local website=$1
    echo "Ping test for $website:"
    if ping -c 1 "$website" &> /dev/null; then
        echo "$website is reachable."
        ((worked1++))
    else
        echo "$website is unreachable."
        ((not_worked1++))
    fi
}

# Loop through each website and perform ping test
for site in "${websites[@]}"; do
    perform_ping_test "$site"
done

#=============================================================
# Pause Page Validation
#=============================================================

successful_urls=()
failure_urls=()

# Define a list of URLs
urls=(
    "http://ipv4c.tlund.se/"
    "http://ipv6c.tlund.se/"
    "http://dual.tlund.se/"
    "http://dualc.tlund.se/"
    "http://ipv6-only.tlund.se/"
    "http://vulnweb.com/"
    "http://testphp.vulnweb.com"
    "http://testhtml5.vulnweb.com"
    "http://testaspnet.vulnweb.com"
    "http://testasp.vulnweb.com"
)

# Initialize counters
worked2=0
not_worked2=0

# Iterate over each URL in the list
for url in "${urls[@]}"; do
    # Run curl command with a timeout of 10 seconds
    if curl -s --max-time 10 "$url" | grep -qi "This device is paused"; then
        echo "Website is successfully paused/blocked: $url"
        successful_urls+=("$url")
        ((worked2++))
    else
        echo "Website is failed to pause or block: $url"
        failure_urls+=("$url")
        ((not_worked2++))
    fi
done

# Output the count of URLs that worked and did not work
echo "URLs that worked: $worked2"
echo "URLs that did not work: $not_worked2"

# Prepare the results as per above validations
if [ $worked2 -ge 7 ] && [ $not_worked1 -ge 1 ]; then
  result="Passed"
  desc="Pause Page is successfully published for http websites."
  #desc="Pause Page is successfully published for ${successful_urls[@]}"
elif [ $worked1 -ne 0 ]; then
  result="Failed"
  desc="Internet is reachable, Client is NOT blocked."
else
  result="Failed"
  desc="Pause Page is failed to publish for ${failure_urls[@]}"
fi

filename="test_results_Aker_"$cm_mac".json"
echo "{
 \"test_results\": [
    {
      \"Device_Mac\": \"$cm_mac\",
      \"Test_ID\": $test_case,
      \"Result\": \"$result\",
      \"Description\": \"$desc\"
    }
  ]
}" > "$filename"

end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Elapsed Time: $elapsed_time seconds"