import boto3
from botocore.exceptions import ClientError


def get_s3_client():
    return boto3.client('s3')


def check_if_file_exists(bucket_name, key):
    try:
        get_s3_client().head_object(Bucket=bucket_name, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        else:
            raise e


def download_file_from_bucket(bucket_name, key, download_path):
    file_exists = check_if_file_exists(bucket_name, key)
    try:
        if file_exists:
            get_s3_client().download_file(bucket_name, key, download_path)
            return download_path
        else:
            raise FileExistsError(f"The file {key} does not exist.")
    except ClientError as e:
        print(f"Error downloading file {key}: {e}")
        raise e
