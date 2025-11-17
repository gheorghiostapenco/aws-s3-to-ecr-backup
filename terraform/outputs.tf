output "lambda_function_name" {
  description = "Name of the backup Lambda function"
  value       = aws_lambda_function.backup.function_name
}

output "cloudwatch_event_rule_name" {
  description = "CloudWatch Events rule name"
  value       = aws_cloudwatch_event_rule.backup_schedule.name
}

output "lambda_role_arn" {
  description = "IAM role ARN used by the Lambda function"
  value       = aws_iam_role.lambda_role.arn
}
