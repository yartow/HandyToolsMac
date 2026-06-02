#!/bin/bash

# Define your search and replace strings
old_string="\*\*\[\^([0-9]+)\]\*\*"
new_string="\*\*\1\*\*"

# Get the content from the clipboard using pbpaste
clipboard_content=$(pbpaste)

# Perform the search and replace using sed
new_content=$(echo "$clipboard_content" | sed -E "s/${old_string}/${new_string}/g")

old_string="\[\^[[:alnum:]]+\]"
new_string=""

# Perform the search and replace using sed
new_content=$(echo "$new_content" | sed -E "s/${old_string}/${new_string}/g")

# Put the modified content back to the clipboard using pbcopy
echo -n "$new_content" | pbcopy
