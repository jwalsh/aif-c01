#!/bin/bash

# Define an associative array for mapping certification IDs to their full names
declare -A cert_map=(
    [saa-c03]="AWS Certified Solutions Architect – Associate"
    [sap-c02]="AWS Certified Solutions Architect – Professional"
    [mls-c01]="AWS Certified Machine Learning – Specialty"
    [scs-c01]="AWS Certified Security – Specialty"
    [dop-c02]="AWS Certified DevOps Engineer – Professional"
    [dva-c02]="AWS Certified Developer – Associate"
    [soa-c02]="AWS Certified SysOps Administrator – Associate"
    [ans-c01]="AWS Certified Advanced Networking – Specialty"
    [dbs-c01]="AWS Certified Database – Specialty"
    [bds-c01]="AWS Certified Big Data – Specialty (replaced by DAS-C01)"
    [aif-c01]="AWS Certified AI Practitioner"
    [mla-c01]="AWS Certified Machine Learning Engineer Associate"
)

mkdir -p practice-tests/

# Loop through the certification IDs
for C in aif-c01 saa-c03 sap-c02 mls-c01 scs-c01 dop-c02 dva-c02 soa-c02 ans-c01 dbs-c01 bds-c01 mla-c01; do
    echo "Processing certification: $C (${cert_map[$C]})"
    
    # Inner loop for generating 5 practice tests
    for N in $(seq 1 5); do
        # Create practice test files
        touch "practice-tests/${C}-practice-0${N}.org"
        
        # Add content to the .org files using a heredoc
        cat <<EOF > "practice-tests/${C}-practice-0${N}.org"
#+TITLE: AWS Certification Preparation: ${cert_map[$C]} : Practice Exam $N
#+AUTHOR: John Doe
#+DATE: 2024-09-21
#+OPTIONS: toc:nil
#+LANGUAGE: en
#+DESCRIPTION: Study guide for AWS ${cert_map[$C]} certification practice exam.

EOF
    done
done
