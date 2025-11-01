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
  description = "Path to the requirements.txt file for Python dependencies"
  type        = string
  default     = ""
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

variable "tags" {
  description = "Map of tags to assign to resources"
  type        = map(string)
  default     = {}
}
