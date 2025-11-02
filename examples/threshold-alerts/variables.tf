variable "aws_region" {
  description = "AWS region for Lambda deployment"
  type        = string
  default     = "us-west-2"
}

variable "alarm_emails" {
  description = "Email addresses to receive alarm notifications when error rate exceeds threshold"
  type        = list(string)

  validation {
    condition     = length(var.alarm_emails) > 0
    error_message = "At least one email address must be provided for alarm notifications"
  }
}