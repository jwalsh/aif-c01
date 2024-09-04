#!/usr/bin/env bash

# Test HTTP
for H in http https
do
    for U in httpbin.org/ip wal.sh
    do
	curl -v -x http://localhost:3128 $H://$U
    done 
done 

# Test with environment variables
export HTTP_PROXY=http://localhost:3128
export HTTPS_PROXY=http://localhost:3128
curl -v http://httpbin.org/ip

docker run --rm alpine/curl -v -x http://host.docker.internal:3128 http://httpbin.org/ip
