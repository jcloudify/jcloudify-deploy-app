import json
import subprocess
import boto3
from botocore.exceptions import ClientError
import zipfile
import os
import stat

TMP_DIR_PATH = "/tmp"


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


def get_s3_client():
    return boto3.client("s3")


def check_if_file_exists(bucket_name, key):
    try:
        get_s3_client().head_object(Bucket=bucket_name, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise e


def download_file_from_bucket(bucket_name, key):
    file_exists = check_if_file_exists(bucket_name, key)
    try:
        destination_file_path = f"/tmp/{get_filename_from_bucket_key(key)}"
        if file_exists:
            get_s3_client().download_file(bucket_name, key, destination_file_path)
            return destination_file_path
        else:
            raise FileExistsError(f"The file {key} does not exist.")
    except ClientError as e:
        print(f"Error downloading file {key}: {e}")
        raise e


def get_filename_from_bucket_key(bucket_key):
    normalized_path = os.path.normpath(bucket_key)
    return os.path.basename(normalized_path)


def unzip_build_file(zip_path, destination_path):
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(destination_path)


def set_write_permission(directory):
    for root, dirs, files in os.walk(directory):
        os.chmod(root, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)

        for d in dirs:
            os.chmod(os.path.join(root, d), stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)

        for f in files:
            os.chmod(os.path.join(root, f), stat.S_IWUSR | stat.S_IRUSR)


def deploy_app(app_name, env):
    stack_name = f"{env}-compute-{app_name}"
    deployment_args = [
        "nohup",
        "sam",
        "deploy",
        "--no-confirm-changeset",
        "--no-fail-on-empty-changeset",
        "--capabilities",
        "CAPABILITY_IAM",
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
    os.chdir(TMP_DIR_PATH)
    subprocess.run(deployment_args, capture_output=False, text=False, env={'HOME': "/tmp"})


def process(app_name, env, bucket_key):
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    zip_build_file = download_file_from_bucket(bucket_name, bucket_key)
    unzip_build_file(zip_build_file, TMP_DIR_PATH)
    set_write_permission(f"{TMP_DIR_PATH}/.aws-sam")
    deploy_app(app_name, env)
