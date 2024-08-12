import json
import os
import subprocess
from s3 import download_file_from_bucket


def lambda_handler(event, context):
    query_params = event.get("queryStringParameters", {})
    app_name = query_params.get("app_name")
    env = query_params.get("env")
    bucket_key = query_params.get("bucket_key")
    process(app_name, env, bucket_key)
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Deployment successfully triggered",
            }
        ),
    }


def deploy_app(app_name, env):
    stack_name = f"{env}-compute-{app_name}"
    deployment_args = [
        "nohup",
        "sam",
        "deploy",
        "--no-confirm-changeset",
        "--no-fail-on-empty-changeset",
        "--capabilities CAPABILITY_IAM",
        "--resolve-s3",
        "--stack-name",
        stack_name,
        "--parameter-overrides",
        f"Env={env}",
        "--tags",
        f"app={app_name}",
        f"env={env}",
        f"user:poja={app_name}",
    ]
    subprocess.run(deployment_args, capture_output=False, text=False)


def process(app_name, env, bucket_key):
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    file_path = download_file_from_bucket(bucket_name, bucket_key)
    os.chdir(file_path)
    deploy_app(app_name, env)
