# SNS topic for Lambda alarms
resource "aws_sns_topic" "alarms" {
  name = var.sns_topic_name != null ? var.sns_topic_name : "${var.function_name}-alarms"

  tags = local.tags
}

# Email subscriptions for alarm notifications
resource "aws_sns_topic_subscription" "alarm_emails" {
  for_each = toset(var.alarm_emails)

  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = each.value
}

# Combine module-created topic with external topics
locals {
  all_alarm_topic_arns = concat(
    [aws_sns_topic.alarms.arn],
    var.alarm_topic_arns
  )
}