import boto3
import base64
import hashlib
import os
import logging
from botocore.exceptions import ClientError

# Configure basic logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client("s3")
ecr_client = boto3.client("ecr")

# Environment variables provided by Terraform
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
S3_PREFIX_FILTER = os.environ.get("S3_PREFIX_FILTER", "")
ECR_REPO_NAME = os.environ.get("ECR_REPO_NAME")


def ensure_repository_exists():
    """
    Ensure the ECR repository exists. If not, create it.
    """
    try:
        response = ecr_client.describe_repositories(
            repositoryNames=[ECR_REPO_NAME]
        )
        logger.info(f"ECR repository '{ECR_REPO_NAME}' already exists.")
        return response["repositories"][0]["repositoryUri"]

    except ecr_client.exceptions.RepositoryNotFoundException:
        logger.info(f"ECR repository '{ECR_REPO_NAME}' not found, creating...")
        response = ecr_client.create_repository(
            repositoryName=ECR_REPO_NAME
        )
        return response["repository"]["repositoryUri"]


def upload_to_ecr(object_key, file_bytes):
    """
    Upload content to ECR as a very basic placeholder image.
    This does NOT build a real Docker container. It creates a dummy image layer 
    to store file content efficiently.

    The purpose is minimal functionality: backup S3 file into ECR registry.
    """
    logger.info(f"Uploading S3 object '{object_key}' to ECR...")

    # Compute a simple tag based on object file hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:12]
    image_tag = f"{file_hash}"

    # Authenticate with ECR
    auth = ecr_client.get_authorization_token()
    token = base64.b64decode(auth["authorizationData"][0]["authorizationToken"])
    username, password = token.decode().split(":")

    registry = auth["authorizationData"][0]["proxyEndpoint"]

    # Create a single layer (file content)
    try:
        layer_upload = ecr_client.initiate_layer_upload(
            repositoryName=ECR_REPO_NAME
        )
        upload_id = layer_upload["uploadId"]

        ecr_client.upload_layer_part(
            repositoryName=ECR_REPO_NAME,
            uploadId=upload_id,
            partFirstByte=0,
            partLastByte=len(file_bytes) - 1,
            layerPartBlob=file_bytes,
        )

        layer_digest = f"sha256:{hashlib.sha256(file_bytes).hexdigest()}"

        ecr_client.complete_layer_upload(
            repositoryName=ECR_REPO_NAME,
            uploadId=upload_id,
            layerDigests=[layer_digest],
        )

        response = ecr_client.put_image(
            repositoryName=ECR_REPO_NAME,
            imageManifest=f"""
            {{
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {{
                    "mediaType": "application/vnd.oci.image.config.v1+json",
                    "digest": "{layer_digest}",
                    "size": {len(file_bytes)}
                }},
                "layers": [
                    {{
                        "mediaType": "application/vnd.oci.image.layer.v1.tar",
                        "digest": "{layer_digest}",
                        "size": {len(file_bytes)}
                    }}
                ]
            }}
            """,
            imageTag=image_tag,
        )

        logger.info(f"Uploaded as image tag: {image_tag}")
        return image_tag

    except ClientError as e:
        logger.error(f"Failed to upload to ECR: {e}")
        raise

    def cleanup_untagged_images():
    """
    Delete all untagged images in the target ECR repository.
    This is a minimal cleanup logic for MVP.
    """
    logger.info("Starting cleanup: deleting untagged images...")

    try:
        images = ecr_client.describe_images(
            repositoryName=ECR_REPO_NAME,
            filter={"tagStatus": "UNTAGGED"}
        )
    except ClientError as e:
        logger.error(f"Failed to describe images for cleanup: {e}")
        return

    image_ids = images.get("imageDetails", [])

    if not image_ids:
        logger.info("No untagged images found")
        return

    batch = [
        {"imageDigest": img["imageDigest"]}
        for img in image_ids
        if "imageDigest" in img
    ]

    try:
        delete_result = ecr_client.batch_delete_image(
            repositoryName=ECR_REPO_NAME,
            imageIds=batch
        )
        deleted = delete_result.get("imageIds", [])
        failures = delete_result.get("failures", [])

        logger.info(f"Deleted {len(deleted)} untagged images.")
        if failures:
            logger.warning(f"Some images failed to delete: {failures}")

    except ClientError as e:
        logger.error(f"Failed to delete untagged images: {e}")    


def lambda_handler(event, context):
    """
    Entry point for the Lambda function.
    This function:
    1. Ensures ECR repository exists.
    2. Lists S3 objects with optional prefix filter.
    3. For each object, downloads it and uploads to ECR.
    """

    logger.info("Lambda function started.")

    repo_uri = ensure_repository_exists()
    logger.info(f"ECR repository URI: {repo_uri}")

    # List objects in S3 bucket
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=S3_PREFIX_FILTER
        )
    except ClientError as e:
        logger.error(f"Error reading S3 bucket: {e}")
        raise

    if "Contents" not in response:
        logger.info("No objects to process.")
        return {"status": "no_objects"}

    results = []

    for obj in response["Contents"]:
        key = obj["Key"]
        logger.info(f"Processing S3 object: {key}")

        # Download file from S3
        try:
            s3_object = s3_client.get_object(
                Bucket=S3_BUCKET_NAME,
                Key=key
            )
            file_bytes = s3_object["Body"].read()

        except ClientError as e:
            logger.error(f"Error downloading S3 object '{key}': {e}")
            continue

        # Upload as simple image layer
        image_tag = upload_to_ecr(key, file_bytes)

        results.append({
            "object_key": key,
            "image_tag": image_tag
        })

    logger.info(f"Backup completed for {len(results)} objects.")
    return {"status": "success", "items": results}
