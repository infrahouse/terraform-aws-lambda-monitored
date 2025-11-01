variable "python_version" {
  description = "Python runtime version. Must be one of https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html"
  type        = string
  default     = "python3.12"

  validation {
    condition     = can(regex("^python3\\.(9|10|11|12|13)$", var.python_version))
    error_message = "Python version must be one of: python3.9, python3.10, python3.11, python3.12, python3.13"
  }
}

variable "architecture" {
  description = "Instruction set architecture for the Lambda function. Valid values: x86_64 or arm64"
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.architecture)
    error_message = "Architecture must be either x86_64 or arm64"
  }
}

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9-_]+$", var.function_name))
    error_message = "Function name must contain only alphanumeric characters, hyphens, and underscores"
  }
}

variable "handler" {
  description = "Lambda function handler (format: file.function_name)"
  type        = string
  default     = "main.lambda_handler"
}

variable "timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900
    error_message = "Timeout must be between 1 and 900 seconds"
  }
}

variable "memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 128

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "Memory size must be between 128 and 10240 MB"
  }
}

variable "environment_variables" {
  description = "Map of environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "lambda_source_dir" {
  description = "Path to the directory containing Lambda function source code"
  type        = string
}

variable "requirements_file" {
  description = <<-EOF
    Path to requirements.txt file for Python dependencies.
    Dependencies will be installed with platform-specific wheels for the target architecture.
    If not specified, the module will automatically look for requirements.txt in var.lambda_source_dir.
    Set to null to explicitly skip dependency installation.
  EOF
  type        = string
  default     = null
}

variable "cloudwatch_log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 365

  validation {
    condition = contains(
      [
        0, 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653
      ],
      var.cloudwatch_log_retention_days
    )
    error_message = "Log retention must be a valid CloudWatch Logs retention period"
  }
}

variable "description" {
  description = "Description of the Lambda function"
  type        = string
  default     = null
}

variable "additional_iam_policy_arns" {
  description = "List of IAM policy ARNs to attach to the Lambda execution role"
  type        = list(string)
  default     = []
}

# Monitoring and Alerting Variables

variable "alarm_emails" {
  description = "List of email addresses to receive alarm notifications. AWS will send confirmation emails that must be accepted. At least one email is required."
  type        = list(string)

  validation {
    condition     = length(var.alarm_emails) > 0
    error_message = "At least one email address must be provided for alarm notifications"
  }
}

variable "alarm_topic_arns" {
  description = "List of existing SNS topic ARNs to send alarms to (for advanced integrations like PagerDuty, Slack, etc.)"
  type        = list(string)
  default     = []
}

variable "sns_topic_name" {
  description = "Name for the SNS topic. If not provided, defaults to '<function_name>-alarms'"
  type        = string
  default     = null
}

variable "enable_error_alarms" {
  description = "Enable CloudWatch alarms for Lambda errors"
  type        = bool
  default     = true
}

variable "alert_strategy" {
  description = "Alert strategy: 'immediate' (alert on any error) or 'threshold' (alert when error rate exceeds threshold)"
  type        = string
  default     = "immediate"

  validation {
    condition     = contains(["immediate", "threshold"], var.alert_strategy)
    error_message = "Alert strategy must be either 'immediate' or 'threshold'"
  }
}

variable "error_rate_threshold" {
  description = "Error rate percentage threshold for 'threshold' alert strategy (0-100)"
  type        = number
  default     = 5.0

  validation {
    condition     = var.error_rate_threshold >= 0 && var.error_rate_threshold <= 100
    error_message = "Error rate threshold must be between 0 and 100"
  }
}

variable "error_rate_evaluation_periods" {
  description = "Number of evaluation periods for error rate alarm"
  type        = number
  default     = 2

  validation {
    condition     = var.error_rate_evaluation_periods >= 1
    error_message = "Evaluation periods must be at least 1"
  }
}

variable "error_rate_datapoints_to_alarm" {
  description = "Number of datapoints that must breach threshold to trigger alarm"
  type        = number
  default     = 2

  validation {
    condition     = var.error_rate_datapoints_to_alarm >= 1
    error_message = "Datapoints to alarm must be at least 1"
  }
}

variable "enable_throttle_alarms" {
  description = "Enable CloudWatch alarms for Lambda throttling"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Map of tags to assign to resources"
  type        = map(string)
  default     = {}
}
