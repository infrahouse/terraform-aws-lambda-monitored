# Get current AWS caller identity to detect provider role
data "aws_caller_identity" "current" {}

# S3 bucket for Lambda deployment packages
module "lambda_bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.2.0"

  bucket_prefix = substr("${var.function_name}-lambda", 0, 37)
  tags = merge(
    local.tags,
    {
      function_name = var.function_name
    }
  )
}

# Upload Lambda package to S3
resource "aws_s3_object" "lambda_package" {
  bucket = module.lambda_bucket.bucket_name
  key    = "${var.function_name}/${data.archive_file.lambda_source_hash.output_md5}.zip"
  source = data.archive_file.lambda_source_hash.output_path

  depends_on = [
    null_resource.install_python_dependencies
  ]

  tags = local.tags

  provisioner "local-exec" {
    interpreter = ["timeout", "60", "bash", "-c"]
    command = templatefile(
      "${path.module}/scripts/wait_for_s3_object.sh",
      {
        bucket_name       = module.lambda_bucket.bucket_name
        object_key        = "${var.function_name}/${data.archive_file.lambda_source_hash.output_md5}.zip"
        caller_account_id = data.aws_caller_identity.current.account_id
        caller_arn        = data.aws_caller_identity.current.arn
      }
    )
  }
}
