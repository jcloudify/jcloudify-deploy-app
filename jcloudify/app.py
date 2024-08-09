import json
import subprocess
from s3 import download_file_from_bucket


def lambda_handler(event, context):
    result = subprocess.run(["sam", "--version"], capture_output=True, text=True)
    print(result.stdout)
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "hello world",
            }
        ),
    }


def deploy_app(app_name, env):
    stack_name = f'{env}-compute-{app_name}'
    deployment_args = ['nohup', 'sam', 'deploy', '--no-confirm-changeset', '--no-fail-on-empty-changeset',
                       '--capabilities CAPABILITY_IAM', '--resolve-s3', '--stack-name', stack_name,
                       '--parameter-overrides', f'Env={env}', '--tags', f'app={app_name}',
                       f'env={env}', f'user:poja={app_name}']
    subprocess.run(deployment_args, capture_output=False, text=False)
