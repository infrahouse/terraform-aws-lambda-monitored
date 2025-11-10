locals {
  # We want to build the package - i.e. install dependencies in the same directory.
  build_directory = var.lambda_source_dir

  # Generate deterministic hash from all triggers that affect the package
  package_hash = md5(
    join(
      "-", [
        local.source_files_hash,
        local.requirements_file != "none" ? filemd5(local.requirements_file) : "none",
        var.architecture,
        var.python_version,
        var.function_name,
      ]
    )
  )

  # Output filename based on package hash
  package_filename = "${var.function_name}-${local.package_hash}.zip"
}

# Package Lambda function with dependencies using custom script
# This prepares a build directory with source code and dependencies
resource "null_resource" "install_python_dependencies" {
  triggers = {
    source_hash       = local.source_files_hash
    requirements_hash = local.requirements_file != "none" ? filemd5(local.requirements_file) : ""
    architecture      = var.architecture
    python_version    = var.python_version
    function_name     = var.function_name

  }

  provisioner "local-exec" {
    command = join(
      " ",
      [
        "${path.module}/scripts/package.sh",
        "'${var.lambda_source_dir}'",
        "'${local.requirements_file}'",
        "'${local.build_directory}'",
        "'${var.architecture}'",
        "'${var.python_version}'"
      ]
    )
  }
}

# Archive the prepared build directory
data "archive_file" "lambda_source_hash" {
  type        = "zip"
  source_dir  = local.build_directory
  output_path = "${path.root}/.build/${local.package_filename}"
  excludes    = ["__pycache__", "*.pyc", "*.pyo"]

  depends_on = [
    null_resource.install_python_dependencies
  ]
}
