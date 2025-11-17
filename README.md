# aws-s3-to-ecr-backup

Serverless backup & cleanup utility for AWS: 
periodically copies objects from S3 into Amazon ECR as image layers
and removes untagged images to keep the registry clean.

All business logic is implemented in a single Python Lambda function,
and all infrastructure is provisioned via Terraform.

---

## Features

- 🔁 Periodic backup from S3 to ECR (driven by CloudWatch Events schedule)
- 📦 Each S3 object is stored as a separate image in ECR
- 🧹 Minimal cleanup: automatic deletion of untagged images in ECR
- 🧩 Fully managed via Terraform (IAM role, Lambda, CloudWatch rule)
- 🔐 No long-running instances, fully serverless

---

## Architecture Overview

**Components:**

- **AWS Lambda**
  - Python 3.11
  - Reads objects from S3
  - Uploads content to ECR as a simple OCI-compatible manifest
  - Removes untagged images in the target ECR repository

- **Amazon S3**
  - Source of objects to be backed up
  - Optional key prefix filter to limit which objects are processed

- **Amazon ECR**
  - Target registry that stores backup "images"
  - Repository is created automatically if it does not exist

- **Amazon CloudWatch Events (EventBridge)**
  - Triggers Lambda function on a schedule (e.g., every hour)

- **IAM Role**
  - Allows Lambda to read from S3, push to ECR, and write logs

---

## How It Works (High-Level)

1. CloudWatch Events triggers the Lambda function on a schedule  
   (for example: `rate(1 hour)`).

2. Lambda:
   - Ensures that the target ECR repository exists (creates it if needed).
   - Lists all S3 objects in the configured bucket (optionally filtered by prefix).
   - For each object:
     - Downloads the object bytes from S3.
     - Calculates a SHA-256 hash and uses it as the image tag.
     - Uploads the file content as a single layer to ECR.
     - Creates a simple image manifest referencing this layer.

3. After all objects are processed, Lambda performs minimal cleanup:
   - Lists all **untagged** images in the ECR repository.
   - Deletes these untagged images in a single batch request.

---

## Project Structure

```text
aws-s3-to-ecr-backup/
├── lambda/
│   └── handler.py          # Lambda function code (Python)
├── terraform/
│   ├── main.tf             # Main Terraform resources
│   ├── variables.tf        # Input variables
│   ├── outputs.tf          # Useful outputs
│   ├── versions.tf         # Terraform & provider configuration
│   └── terraform.tfvars    # User-provided values (not committed)
└── README.md

## Prerequisites

AWS account
IAM user or role with enough permissions to:
Create and manage Lambda functions
Read from S3
Create and manage ECR repositories and images
Manage CloudWatch Events rules
Create IAM roles for Lambda
Terraform
AWS CLI
AWS CLI configured locally:

```
aws configure
aws sts get-caller-identity
```

## Configuration

All configuration is controlled via Terraform variables.

variables.tf

Key variables:
```
aws_region – AWS region for all resources
project_name – prefix for resource names
s3_bucket_name – source S3 bucket
s3_prefix_filter – optional key prefix to limit which objects to process
ecr_repository_name – target ECR repository
lambda_timeout – Lambda timeout in seconds
lambda_memory_size – Lambda memory in MB
schedule_expression – CloudWatch Events schedule expression
```

terraform.tfvars example
```
aws_region          = "us-east-1"
project_name        = "s3-to-ecr-backup"
s3_bucket_name      = "my-test-bucket"
s3_prefix_filter    = ""
ecr_repository_name = "s3-backup-repo"
schedule_expression = "rate(1 hour)"
```
Do not commit terraform.tfvars to a public repository if it contains any sensitive data.

## Deployment

From the terraform/ directory:

```
terraform init
terraform validate
terraform plan
terraform apply
```

Terraform will:

Package lambda/handler.py into lambda/handler.zip using archive_file data source
Create IAM role and inline policy for Lambda
Create Lambda function with environment variables
Create CloudWatch Events rule and target
Grant Events permission to invoke the Lambda
After apply completes, outputs will show:
Lambda function name
CloudWatch rule name
Lambda role ARN

## Verifying the Deployment

1. Check Lambda in AWS Console

Go to AWS Console → Lambda
You should see a function named similar to:
s3-to-ecr-backup-lambda

2. Check CloudWatch Events rule

Go to CloudWatch → Rules (EventBridge)
You should see a rule with the configured schedule_expression.

3. Check ECR repository

Go to ECR console
Repository s3-backup-repo will be created lazily (on the first Lambda run).
After Lambda runs at least once, you should see images with tags derived from SHA-256 hashes.

4. Check logs

Go to CloudWatch Logs → Log groups
Find log group for the Lambda function
Inspect logs for lines like:
Processing S3 object: <key>
Uploaded as image tag: <hash>
Deleted X untagged images.

## Cleanup

To delete all created resources:

```
cd terraform/
terraform destroy
```

This will remove:

Lambda function
IAM role and inline policy
CloudWatch Events rule and target
Lambda invoke permission

Note: The ECR repository itself is created by the Lambda function at runtime.
If needed, delete it manually from the ECR console.

## Limitations

The Lambda function uses a very minimal image manifest and a single layer
that just stores raw file bytes. It is not meant to be a fully-featured container build system.

Image content is not runnable as a container; it serves as a storage/backup mechanism.

Only untagged images are cleaned up automatically.
Tagged images are preserved and must be managed manually if needed.