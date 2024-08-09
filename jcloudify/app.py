import json
import subprocess


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
