variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Logical name prefix for all created resources"
  type        = string
  default     = "s3-to-ecr-backup"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket that contains objects to back up to ECR"
  type        = string
}

variable "s3_prefix_filter" {
  description = "Optional S3 key prefix to filter objects"
  type        = string
  default     = ""
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository where images will be stored"
  type        = string
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
}

variable "schedule_expression" {
  description = "CloudWatch Events schedule expression (cron or rate)"
  type        = string
  default     = "rate(1 hour)"
}
