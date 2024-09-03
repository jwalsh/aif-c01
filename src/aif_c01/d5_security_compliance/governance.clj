(ns aif-c01.d5-security-compliance.governance)

(defn list-aws-security-services []
  ["IAM" "KMS" "CloudTrail"])

(defn describe-data-governance-strategies []
  [:data-classification :access-control :encryption :auditing])
