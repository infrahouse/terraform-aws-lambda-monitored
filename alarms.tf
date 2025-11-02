# CloudWatch alarm for immediate error notifications
# Triggers on any Lambda error
resource "aws_cloudwatch_metric_alarm" "errors_immediate" {
  count = var.enable_error_alarms && var.alert_strategy == "immediate" ? 1 : 0

  alarm_name          = "${var.function_name}-errors-immediate"
  alarm_description   = "Lambda function ${var.function_name} has errors - immediate alert"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }

  alarm_actions = local.all_alarm_topic_arns

  tags = local.tags
}

# CloudWatch alarm for error rate threshold
# Triggers when error rate exceeds configured threshold
resource "aws_cloudwatch_metric_alarm" "errors_threshold" {
  count = var.enable_error_alarms && var.alert_strategy == "threshold" ? 1 : 0

  alarm_name          = "${var.function_name}-errors-threshold"
  alarm_description   = "Lambda function ${var.function_name} error rate exceeds ${var.error_rate_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.error_rate_evaluation_periods
  threshold           = var.error_rate_threshold
  treat_missing_data  = "notBreaching"
  datapoints_to_alarm = var.error_rate_datapoints_to_alarm

  metric_query {
    id          = "error_rate"
    expression  = "(errors / invocations) * 100"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 60
      stat        = "Sum"

      dimensions = {
        FunctionName = aws_lambda_function.this.function_name
      }
    }
    return_data = false
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 60
      stat        = "Sum"

      dimensions = {
        FunctionName = aws_lambda_function.this.function_name
      }
    }
    return_data = false
  }

  alarm_actions = local.all_alarm_topic_arns

  tags = local.tags
}

# CloudWatch alarm for Lambda throttling
# Triggers when Lambda invocations are throttled
resource "aws_cloudwatch_metric_alarm" "throttles" {
  count = var.enable_throttle_alarms ? 1 : 0

  alarm_name          = "${var.function_name}-throttles"
  alarm_description   = "Lambda function ${var.function_name} is being throttled"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }

  alarm_actions = local.all_alarm_topic_arns

  tags = local.tags
}