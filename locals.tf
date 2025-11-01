locals {
  module         = "infrahouse/lambda-monitored/aws"
  module_version = "0.1.0"

  default_module_tags = {
    created_by_module = local.module
  }

  tags = merge(var.tags, local.default_module_tags)
}
