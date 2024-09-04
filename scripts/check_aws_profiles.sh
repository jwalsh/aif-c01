#!/bin/bash

required_profiles=("lcl" "dev")
missing_profiles=()

echo "Checking AWS profiles..."

for profile in "${required_profiles[@]}"; do
    if ! aws configure list-profiles | grep -q "^$profile$"; then
        missing_profiles+=("$profile")
    fi
done

if [ ${#missing_profiles[@]} -eq 0 ]; then
    echo "All required AWS profiles are present."
    exit 0
else
    echo "The following required AWS profiles are missing:"
    for profile in "${missing_profiles[@]}"; do
        echo "- $profile"
    done
    echo "Please create the missing profiles using 'aws configure --profile <profile_name>'"
    exit 1
fi
