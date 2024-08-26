import json
from subprocess import Popen, PIPE
import boto3
from botocore.exceptions import ClientError
import zipfile
import os
import stat

TMP_DIR_PATH = "/tmp"
API_EVENT_SOURCE = "api.jcloudify.app.event1"
EVENT_STACK_TARGET = "EVENT_STACK_1"


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    for records in event["Records"]:
        print(f"Received records: {json.dumps(records)}")
        body = json.loads(records["body"])
        detail = body["detail"]
        process_deployment(detail)

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


def download_file_from_bucket(bucket_key):
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    file_exists = check_if_file_exists(bucket_name, bucket_key)
    try:
        destination_file_path = f"/tmp/{get_filename_from_bucket_key(bucket_key)}"
        if file_exists:
            print(f"Downloading {bucket_key} to {destination_file_path}")
            get_s3_client().download_file(
                bucket_name, bucket_key, destination_file_path
            )
            return destination_file_path
        else:
            raise FileExistsError(f"The file {bucket_key} does not exist.")
    except ClientError as e:
        print(f"Error downloading file {bucket_key}: {e}")
        raise e


def get_filename_from_bucket_key(bucket_key):
    normalized_path = os.path.normpath(bucket_key)
    return os.path.basename(normalized_path)


def unzip_build_file(zip_path, destination_path):
    print(f"Unzipping {zip_path} build file")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(destination_path)


def set_write_permission(directory):
    for root, dirs, files in os.walk(directory):
        os.chmod(root, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)

        for d in dirs:
            os.chmod(os.path.join(root, d), stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)

        for f in files:
            os.chmod(os.path.join(root, f), stat.S_IWUSR | stat.S_IRUSR)


def execute_commands(commands):
    results = []
    for command in commands:
        result = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)

        stdout, stderr = result.communicate()

        results.append(
            {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": result.returncode,
            }
        )
    return results


def get_compute_stack_crupdated_event(user_id, app_id, env_id, stack_name):
    data = {
        "userId": user_id,
        "appId": app_id,
        "envId": env_id,
        "stackName": stack_name,
        "eventSource": API_EVENT_SOURCE,
        "eventStack": EVENT_STACK_TARGET,
    }
    return data


def get_event_bridge_client():
    return boto3.client("events")


def send_event(user_id, app_id, env_id, env, app_name):
    stack_name = f"{env}-compute-{app_name}"
    event_bus_name = os.getenv("AWS_EVENTBRIDGE_BUS")
    event_bridge_client = get_event_bridge_client()
    data = get_compute_stack_crupdated_event(user_id, app_id, env_id, stack_name)
    print(f"Events to send: {data}")
    response = event_bridge_client.put_events(
        Entries=[
            {
                "Source": API_EVENT_SOURCE,
                "DetailType": "api.jcloudify.app.endpoint.event.model.ComputeStackCrupdated",
                "Detail": json.dumps(data),
                "EventBusName": event_bus_name,
            },
        ]
    )
    print(response)


def get_built_project_from_s3(bucket_key):
    zip_build_file = download_file_from_bucket(bucket_key)
    unzip_build_file(zip_build_file, TMP_DIR_PATH)
    set_write_permission(f"{TMP_DIR_PATH}/.aws-sam")


def trigger_app_deployment(app_name, env):
    stack_name = f"{env}-compute-{app_name}"
    print(f"Deploying {stack_name}")
    deployment_command = [
        f"cd /tmp && export HOME=/tmp && sam deploy --no-confirm-changeset "
        f"--no-fail-on-empty-changeset --capabilities CAPABILITY_IAM "
        f"--resolve-s3 --stack-name {stack_name} --parameter-overrides "
        f"Env={env} --tags app={app_name} env={env} user:poja={app_name} &",
    ]
    print(execute_commands(deployment_command))


def deploy_app(app_name, env, bucket_key):
    get_built_project_from_s3(bucket_key)
    trigger_app_deployment(app_name, env)


def process_deployment(event_details):
    app_name = event_details.get("app_name")
    env_name: str = event_details.get("environment_type")
    bucket_key = event_details.get("formatted_bucket_key")
    app_id = event_details.get("app_id")
    user_id = event_details.get("user_id")
    env_id = event_details.get("env_id")
    deploy_app(app_name, env_name.lower(), bucket_key)
    send_event(user_id, app_id, env_id, env_name.lower(), app_name)
