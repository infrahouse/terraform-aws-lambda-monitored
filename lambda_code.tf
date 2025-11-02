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
        "'${path.module}/.build/${var.function_name}'",
        "'${var.architecture}'",
        "'${var.python_version}'"
      ]
    )
  }
}

# Archive the prepared build directory
data "archive_file" "lambda_source_hash" {
  type        = "zip"
  source_dir  = "${path.module}/.build/${var.function_name}"
  output_path = "${path.module}/.build/${var.function_name}.zip"
  excludes    = ["__pycache__", "*.pyc", "*.pyo"]

  depends_on = [
    null_resource.install_python_dependencies
  ]
}
