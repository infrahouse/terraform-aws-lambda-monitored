locals {
  module         = "infrahouse/lambda-monitored/aws"
  module_version = "0.3.5"

  default_module_tags = {
    created_by_module = local.module
  }

  tags = merge(var.tags, local.default_module_tags)

  # Auto-detect requirements.txt in lambda_source_dir if not explicitly specified
  requirements_txt_path = "${var.lambda_source_dir}/requirements.txt"
  requirements_file = var.requirements_file != null ? var.requirements_file : (
    fileexists(local.requirements_txt_path) ? local.requirements_txt_path : "none"
  )

  # Calculate hash of all source files for change detection
  # This avoids circular dependency with archive_file
  lambda_source_files = fileset(var.lambda_source_dir, "**/*.py")
  source_files_hash = md5(join("", [
    for f in local.lambda_source_files : filemd5("${var.lambda_source_dir}/${f}")
  ]))
}
