locals {
  module         = "infrahouse/lambda-monitored/aws"
  module_version = "1.0.4"

  default_module_tags = {
    created_by_module = local.module
    function_name     = var.function_name
  }

  tags = merge(var.tags, local.default_module_tags)

  # Sanitize function name for S3 bucket (S3 only allows lowercase alphanumeric and hyphens)
  # Original function name is preserved in tags
  sanitized_function_name = lower(
    replace(
      replace(var.function_name, "_", "-"),
      "/[^a-z0-9-]/",
      ""
    )
  )

  # Auto-detect requirements.txt in lambda_source_dir if not explicitly specified
  requirements_txt_path = "${var.lambda_source_dir}/requirements.txt"
  requirements_file = var.requirements_file != null ? var.requirements_file : (
    fileexists(local.requirements_txt_path) ? local.requirements_txt_path : "none"
  )

  # Calculate hash of source files for change detection
  # Only tracks files specified in source_code_files variable, excluding installed dependencies
  lambda_source_files = flatten([
    for pattern in var.source_code_files : fileset(var.lambda_source_dir, pattern)
  ])
  source_files_hash = md5(
    join(
      "",
      [
        for f in local.lambda_source_files : filemd5(
          "${var.lambda_source_dir}/${f}"
        )
      ]
    )
  )

  # Lambda Insights extension layer (only used when memory alarm is enabled).
  # AWS publishes the layer under the 580247275435 account in every region. Version and
  # layer name differ by architecture. The ARN is overridable via var.lambda_insights_layer_arn.
  # Versions pinned from https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Lambda-Insights-extension-versions.html
  lambda_insights_publisher_account = "580247275435"
  lambda_insights_layer_defaults = {
    x86_64 = "arn:aws:lambda:${data.aws_region.current.name}:${local.lambda_insights_publisher_account}:layer:LambdaInsightsExtension:56"
    arm64  = "arn:aws:lambda:${data.aws_region.current.name}:${local.lambda_insights_publisher_account}:layer:LambdaInsightsExtension-Arm64:20"
  }
  lambda_insights_enabled = var.memory_utilization_threshold_percent != null
  lambda_insights_layer_arn = local.lambda_insights_enabled ? (
    var.lambda_insights_layer_arn != null ? var.lambda_insights_layer_arn : local.lambda_insights_layer_defaults[var.architecture]
  ) : null
}
