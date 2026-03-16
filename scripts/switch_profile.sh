#!/bin/bash

switch_profile() {
	case $1 in
	lcl)
		export AWS_PROFILE=lcl
		export AWS_ACCESS_KEY_ID=test
		export AWS_SECRET_ACCESS_KEY=test
		export AWS_DEFAULT_REGION=us-east-1
		export LOCALSTACK_ENDPOINT=http://localhost:4566
		echo "Switched to LocalStack profile"
		;;
	dev)
		export AWS_PROFILE=dev
		unset AWS_ACCESS_KEY_ID
		unset AWS_SECRET_ACCESS_KEY
		export AWS_DEFAULT_REGION=us-east-1
		echo "Switched to AWS dev profile (uses AWS_PROFILE credentials)"
		;;
	*)
		echo "Usage: switch_profile [lcl|dev]"
		;;
	esac
}

switch_profile $1
