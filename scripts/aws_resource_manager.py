import boto3
import click
import itertools
import functools
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from botocore.exceptions import ClientError


class AWSResource(BaseModel):
    service: str
    resource_type: str
    identifier: str
    details: Optional[Dict[str, Any]] = None


class AWSResourceManager:
    def __init__(self):
        self.session = boto3.Session()
        self.sts_client = self.session.client("sts")

    def confirm_access(self) -> bool:
        """Confirm AWS access using STS."""
        try:
            self.sts_client.get_caller_identity()
            return True
        except ClientError:
            return False

    @functools.lru_cache(maxsize=None)
    def get_client(self, service_name: str):
        """Get a boto3 client for the specified service."""
        return self.session.client(service_name)

    def list_resources(
        self, service: str, list_func: str, key: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """Generic method to list resources from a service."""
        client = self.get_client(service)
        method = getattr(client, list_func)
        response = method(**kwargs)
        return response.get(key, [])

    def delete_resource(self, service: str, delete_func: str, **kwargs) -> bool:
        """Generic method to delete a resource."""
        client = self.get_client(service)
        method = getattr(client, delete_func)
        try:
            method(**kwargs)
            return True
        except ClientError:
            return False

    def audit_s3(self) -> List[AWSResource]:
        """Audit S3 buckets."""
        s3 = self.session.resource("s3")
        return [
            AWSResource(
                service="s3",
                resource_type="bucket",
                identifier=bucket.name,
                details={"creation_date": str(bucket.creation_date)},
            )
            for bucket in s3.buckets.all()
            if any(prefix in bucket.name.lower() for prefix in ["mla", "aif", "c01"])
        ]

    def audit_lambda(self) -> List[AWSResource]:
        """Audit Lambda functions."""
        functions = self.list_resources("lambda", "list_functions", "Functions")
        return [
            AWSResource(
                service="lambda",
                resource_type="function",
                identifier=func["FunctionName"],
                details=func,
            )
            for func in functions
            if any(prefix in func["FunctionName"].lower() for prefix in ["mla", "aif"])
        ]

    def audit_sagemaker(self) -> List[AWSResource]:
        """Audit SageMaker resources."""
        resources = []

        # Notebook instances
        notebooks = self.list_resources(
            "sagemaker", "list_notebook_instances", "NotebookInstances"
        )
        resources.extend(
            [
                AWSResource(
                    service="sagemaker",
                    resource_type="notebook_instance",
                    identifier=notebook["NotebookInstanceName"],
                    details=notebook,
                )
                for notebook in notebooks
                if any(
                    prefix in notebook["NotebookInstanceName"].lower()
                    for prefix in ["mla", "aif"]
                )
            ]
        )

        # Models
        models = self.list_resources("sagemaker", "list_models", "Models")
        resources.extend(
            [
                AWSResource(
                    service="sagemaker",
                    resource_type="model",
                    identifier=model["ModelName"],
                    details=model,
                )
                for model in models
                if any(
                    prefix in model["ModelName"].lower() for prefix in ["mla", "aif"]
                )
            ]
        )

        return resources

    def audit_dynamodb(self) -> List[AWSResource]:
        """Audit DynamoDB tables."""
        tables = self.list_resources("dynamodb", "list_tables", "TableNames")
        return [
            AWSResource(service="dynamodb", resource_type="table", identifier=table)
            for table in tables
            if any(prefix in table.lower() for prefix in ["mla", "aif"])
        ]

    def audit_cloudwatch(self) -> List[AWSResource]:
        """Audit CloudWatch resources."""
        # For simplicity, we'll just check for metric alarms
        alarms = self.list_resources("cloudwatch", "describe_alarms", "MetricAlarms")
        return [
            AWSResource(
                service="cloudwatch",
                resource_type="alarm",
                identifier=alarm["AlarmName"],
                details=alarm,
            )
            for alarm in alarms
            if any(prefix in alarm["AlarmName"].lower() for prefix in ["mla", "aif"])
        ]

    def audit_kinesis(self) -> List[AWSResource]:
        """Audit Kinesis streams."""
        streams = self.list_resources("kinesis", "list_streams", "StreamNames")
        return [
            AWSResource(service="kinesis", resource_type="stream", identifier=stream)
            for stream in streams
            if any(prefix in stream.lower() for prefix in ["mla", "aif"])
        ]

    def audit_glue(self) -> List[AWSResource]:
        """Audit Glue resources."""
        databases = self.list_resources("glue", "get_databases", "DatabaseList")
        return [
            AWSResource(
                service="glue",
                resource_type="database",
                identifier=database["Name"],
                details=database,
            )
            for database in databases
            if any(prefix in database["Name"].lower() for prefix in ["mla", "aif"])
        ]

    def audit_all_resources(self) -> List[AWSResource]:
        """Audit all resources across services."""
        audit_functions = [
            self.audit_s3,
            self.audit_lambda,
            self.audit_sagemaker,
            self.audit_dynamodb,
            self.audit_cloudwatch,
            self.audit_kinesis,
            self.audit_glue,
        ]
        return list(itertools.chain.from_iterable(func() for func in audit_functions))

    def cleanup_resource(self, resource: AWSResource) -> bool:
        """Clean up a specific resource."""
        if resource.service == "s3":
            # We don't delete S3 buckets, just return False
            return False
        elif resource.service == "lambda":
            return self.delete_resource(
                "lambda", "delete_function", FunctionName=resource.identifier
            )
        elif resource.service == "sagemaker":
            if resource.resource_type == "notebook_instance":
                return self.delete_resource(
                    "sagemaker",
                    "delete_notebook_instance",
                    NotebookInstanceName=resource.identifier,
                )
            elif resource.resource_type == "model":
                return self.delete_resource(
                    "sagemaker", "delete_model", ModelName=resource.identifier
                )
        elif resource.service == "dynamodb":
            return self.delete_resource(
                "dynamodb", "delete_table", TableName=resource.identifier
            )
        elif resource.service == "cloudwatch":
            return self.delete_resource(
                "cloudwatch", "delete_alarms", AlarmNames=[resource.identifier]
            )
        elif resource.service == "kinesis":
            return self.delete_resource(
                "kinesis", "delete_stream", StreamName=resource.identifier
            )
        elif resource.service == "glue":
            return self.delete_resource(
                "glue", "delete_database", Name=resource.identifier
            )
        return False


@click.command()
@click.option(
    "--clean", is_flag=True, help="Clean up resources instead of just auditing"
)
def main(clean: bool):
    """Audit and optionally clean up AWS resources related to MLA or AIF certifications."""
    manager = AWSResourceManager()

    if not manager.confirm_access():
        click.echo("Failed to confirm AWS access. Please check your credentials.")
        return

    resources = manager.audit_all_resources()

    if not resources:
        click.echo("No resources found related to MLA or AIF certifications.")
        return

    click.echo(f"Found {len(resources)} resources:")
    for resource in resources:
        if resource.service == "s3":
            click.echo(
                f"- {resource.service}: {resource.resource_type} - {resource.identifier} (Created: {resource.details['creation_date']})"
            )
        else:
            click.echo(
                f"- {resource.service}: {resource.resource_type} - {resource.identifier}"
            )

    if clean:
        click.echo("Cleaning up resources (S3 buckets will not be deleted)...")
        for resource in resources:
            if resource.service != "s3":
                if manager.cleanup_resource(resource):
                    click.echo(
                        f"Deleted {resource.service} {resource.resource_type}: {resource.identifier}"
                    )
                else:
                    click.echo(
                        f"Failed to delete {resource.service} {resource.resource_type}: {resource.identifier}"
                    )
            else:
                click.echo(f"Skipped deletion of S3 bucket: {resource.identifier}")
    else:
        click.echo(
            "Run with --clean to remove these resources (S3 buckets will not be deleted)."
        )


if __name__ == "__main__":
    main()
