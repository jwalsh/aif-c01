#!/bin/bash

REPO_URL="https://api.github.com/repos/cognitect-labs/aws-api/contents/deps.edn"
DEPS_CONTENT=$(curl -s $REPO_URL | jq -r '.content' | base64 --decode)
echo "$DEPS_CONTENT" | grep -oP "com\.cognitect\.aws/\K(\w+)\s+\{:mvn/version\s+\"(\d+\.\d+\.\d+\.\d+)\"" |
	while read -r line; do
		SERVICE=$(echo $line | cut -d' ' -f1)
		VERSION=$(echo $line | cut -d' ' -f2)
		echo "[com.cognitect.aws/$SERVICE \"$VERSION\"]"
	done
