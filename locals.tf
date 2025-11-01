locals {
  module         = "infrahouse/lambda-monitored/aws"
  module_version = "0.1.0"

  default_module_tags = {
    created_by_module = local.module
  }

  tags = merge(var.tags, local.default_module_tags)

  # Auto-detect requirements.txt in lambda_source_dir if not explicitly specified
  requirements_txt_path = "${var.lambda_source_dir}/requirements.txt"
  requirements_file = var.requirements_file != null ? var.requirements_file : (
    fileexists(local.requirements_txt_path) ? local.requirements_txt_path : "none"
  )
}
