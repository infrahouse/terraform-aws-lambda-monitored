locals {
  # Build in a temporary directory to avoid polluting source directory
  # This ensures dependencies are always installed fresh and source stays clean
  build_directory = "${path.root}/.build/${var.function_name}"

  # Generate deterministic hash from all triggers that affect the package
  package_hash = md5(
    join(
      "-", [
        local.source_files_hash,
        local.requirements_file != "none" ? filemd5(local.requirements_file) : "none",
        var.architecture,
        var.python_version,
        var.function_name,
        local.module_version, # Include module version to trigger rebuild on upgrades
      ]
    )
  )

  # Output filename based on package hash
  package_filename = "${var.function_name}-${local.package_hash}.zip"
  zip_output_path  = "${path.root}/.build/${local.package_filename}"

  # Use package_hash as source_code_hash for Lambda
  # This is more reliable than file hashing since it's based on inputs
  source_code_hash = base64encode(local.package_hash)
}

# Package Lambda function with dependencies using custom script
# This script builds the package AND creates the zip file
resource "null_resource" "lambda_package" {
  triggers = {
    source_hash       = local.source_files_hash
    requirements_hash = local.requirements_file != "none" ? filemd5(local.requirements_file) : ""
    architecture      = var.architecture
    python_version    = var.python_version
    function_name     = var.function_name
    module_version    = local.module_version # Trigger rebuild on module upgrades
    package_hash      = local.package_hash   # Trigger on any package content change
  }

  provisioner "local-exec" {
    command = join(
      " ",
      [
        "${path.module}/scripts/package.sh",
        "'${var.lambda_source_dir}'",
        "'${local.requirements_file}'",
        "'${local.build_directory}'",
        "'${local.zip_output_path}'",
        "'${var.architecture}'",
        "'${var.python_version}'"
      ]
    )
  }
}
