#!/bin/bash

# Destination directory where the folders will be moved
destination_directory="/path/to/destination"
~/Downloads/Bear

# Today's date in YYYY-MM-DD format
today_date=$(date +%Y-%m-%d)

# Find all directories in ~/Downloads created today and move them to the destination directory
# making sure it accepts spaces in the name
find ~/Downloads -type d -newermt "$(date -j -v0H -v0M -v0S +%Y-%m-%d)" ! -newermt "$(date -j -v+1d -v0H -v0M -v0S +%Y-%m-%d)" -exec sh -c 'mkdir -p "/users/andrewyong/Downloads/Bear" && mv "$@" "/users/andrewyong/Downloads/Bear/"' _ {} +
