#!/bin/sh

# Directory containing the folders
#main_dir=$(getent passwd $USER | cut -d: -f6)
main_dir="/home/rats"
# File path
FILE="/var/tmp/sw_version.txt"

# Check if the file exists
if [ ! -f "$FILE" ]; then
    echo "File not found!"
    exit 1
fi

# Initialize keep_folder1 to ensure it has a default or empty value
keep_folder1=""

# Read the file line by line
while IFS= read -r line
do
    # Assign the first non-empty line to keep_folder1 and break
    if [ -n "$line" ]; then
        keep_folder1="$line"
        break
    fi
done < "$FILE"

# Validate if keep_folder1 got a value
if [ -z "$keep_folder1" ]; then
    echo "No version info found in the file."
    exit 1
fi
echo "Shirish: main directory : $main_dir"
# Change to the directory
cd "$main_dir" || { echo "Failed to change directory to $main_dir"; exit 1; }

# List of other folders to keep
keep_folder2="RATS-release"
keep_folder3="RATS"

# Iterate over each item in the directory
for folder in RATS-*; do
    # Check if this folder should be kept
    if [ "$folder" != "$keep_folder1" ] && [ "$folder" != "$keep_folder2" ] && [ "$folder" != "$keep_folder3" ]; then
        if [ -d "$folder" ]; then
            echo "Removing $folder..."
            rm -rf "$folder"
        fi
    fi
done

echo "Cleanup complete."
