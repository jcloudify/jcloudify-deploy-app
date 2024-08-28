import json
from subprocess import Popen, PIPE
import boto3
from botocore.exceptions import ClientError
import zipfile
import os
import stat
import shutil
import filecmp

TMP_DIR_PATH = "/tmp"
API_EVENT_SOURCE = "api.jcloudify.app.event1"
EVENT_STACK_TARGET = "EVENT_STACK_1"
DEPLOY_STACK_SOURCE_PATTERN = "app.jcloudify.app.deployer.event.deploy"
CHECK_TEMPLATE_PATTERN = "app.jcloudify.app.deployer.event.check"


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    for records in event["Records"]:
        print(f"Received records: {json.dumps(records)}")
        body = json.loads(records["body"])
        source = body["source"]
        detail = body["detail"]
        if source == DEPLOY_STACK_SOURCE_PATTERN:
            process_deployment(detail)
        if source == CHECK_TEMPLATE_PATTERN:
            print(process_template_check(detail))

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


def unzip_file(zip_path, destination_path):
    print(f"Unzipping {zip_path} file")
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


def get_compute_stack_crupdated_event_model(user_id, app_id, env_id, stack_name):
    data = {
        "userId": user_id,
        "appId": app_id,
        "envId": env_id,
        "stackName": stack_name,
        "eventSource": API_EVENT_SOURCE,
        "eventStack": EVENT_STACK_TARGET,
    }
    return data


def get_template_integrity_check_done_event_model(
    user_id,
    app_id,
    env_id,
    built_project_bucket_key,
    built_env_info,
    deployment_conf_id,
    status,
):
    data = {
        "userId": user_id,
        "appId": app_id,
        "envId": env_id,
        "builtProjectBucketKey": built_project_bucket_key,
        "builtEnvInfo": built_env_info,
        "deploymentConfId": deployment_conf_id,
        "status": status,
    }
    return data


def get_event_bridge_client():
    return boto3.client("events")


def send_event(event_details, event_detail_type):
    event_bus_name = os.getenv("AWS_EVENTBRIDGE_BUS")
    event_bridge_client = get_event_bridge_client()
    print(f"Events to send: {event_details}")
    response = event_bridge_client.put_events(
        Entries=[
            {
                "Source": API_EVENT_SOURCE,
                "DetailType": event_detail_type,
                "Detail": json.dumps(event_details),
                "EventBusName": event_bus_name,
            },
        ]
    )
    print(response)


def send_stack_crupdated_event(user_id, app_id, env_id, env, app_name):
    stack_name = f"{env}-compute-{app_name}"
    details = get_compute_stack_crupdated_event_model(
        user_id, app_id, env_id, stack_name
    )
    stack_crupdated_event_detail_type = (
        "api.jcloudify.app.endpoint.event.model.ComputeStackCrupdated"
    )
    send_event(details, stack_crupdated_event_detail_type)


def get_built_project_from_s3(bucket_key):
    zip_build_file = download_file_from_bucket(bucket_key)
    unzip_file(zip_build_file, TMP_DIR_PATH)
    project_path = f"{TMP_DIR_PATH}/.aws-sam"
    set_write_permission(project_path)
    return project_path


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
    send_stack_crupdated_event(user_id, app_id, env_id, env_name.lower(), app_name)


def get_mock_project_from_s3():
    print("Get mock project from s3")
    mock_project_bucket_key = os.getenv("MOCK_PROJECT_BUCKET_KEY")
    mock_project_folder_name = os.getenv("MOCK_PROJECT_FOLDER_NAME")
    zipped_mocked_project = download_file_from_bucket(mock_project_bucket_key)
    unzip_file(zipped_mocked_project, TMP_DIR_PATH)
    mock_project_folder_path = f"{TMP_DIR_PATH}/{mock_project_folder_name}"
    set_write_permission(mock_project_folder_path)
    return mock_project_folder_path


def trigger_project_build(project_path):
    execute_commands([f"cd {project_path} && chmod +x ./gradlew"])
    print(
        execute_commands(
            [f"cd {project_path} && export HOME={project_path} && sam build"]
        )
    )


def check_if_files_are_identical(file1, file2):
    return filecmp.cmp(file1, file2, shallow=False)


def process_template_check(event_details):
    built_project_bucket_key = event_details.get("built_project_bucket_key")
    template_file_bucket_key = event_details.get("template_file_bucket_key")
    app_id = event_details.get("app_id")
    user_id = event_details.get("user_id")
    env_id = event_details.get("env_id")
    built_env_info = event_details.get("built_env_info")
    deployment_conf_id = event_details.get("deployment_conf_id")
    mock_project_path = get_mock_project_from_s3()
    original_template_file_path = download_file_from_bucket(template_file_bucket_key)
    shutil.copy(original_template_file_path, f"{mock_project_path}/template.yml")
    print("Trigger project build")
    print(trigger_project_build(mock_project_path))
    project_path = get_built_project_from_s3(built_project_bucket_key)
    print("Built project successfully downloaded: {}".format(project_path))
    project_built_template = f"{project_path}/build/template.yaml"
    generated_built_template = f"{mock_project_path}/.aws-sam/build/template.yaml"
    print("Check files")
    to_send_event_detail_type = (
        "api.jcloudify.app.endpoint.event.model.TemplateIntegrityCheckDone"
    )
    check_result = check_if_files_are_identical(
        project_built_template, generated_built_template
    )
    print(f"Is file authentic: {check_result}")
    integrity_status = "AUTHENTIC" if check_result else "CORRUPTED"
    to_send_event_details = get_template_integrity_check_done_event_model(
        user_id,
        app_id,
        env_id,
        built_project_bucket_key,
        built_env_info,
        deployment_conf_id,
        integrity_status,
    )
    send_event(to_send_event_details, to_send_event_detail_type)
