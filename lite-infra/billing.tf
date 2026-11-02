# =============================================================================
# lite-infra/billing.tf - the $5/month guard rail.
#
# Two things make this work in Terraform:
#   * AWS/Billing EstimatedCharges is published ONLY in us-east-1, which is why
#     the alarm uses the aliased provider from main.tf.
#   * The metric has to be enabled once per account ("Receive Billing Alerts"
#     in the Billing console). Terraform cannot toggle that preference; if the
#     alarm sits in INSUFFICIENT_DATA, that checkbox is the reason.
# =============================================================================

resource "aws_sns_topic" "billing" {
  provider = aws.billing
  name     = "${local.name_prefix}-billing-alarm"
}

resource "aws_sns_topic_subscription" "billing_email" {
  provider  = aws.billing
  count     = var.billing_alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.billing.arn
  protocol  = "email"
  endpoint  = var.billing_alarm_email
}

resource "aws_cloudwatch_metric_alarm" "estimated_charges" {
  provider = aws.billing

  alarm_name        = "${local.name_prefix}-estimated-charges-over-${var.billing_alarm_threshold_usd}usd"
  alarm_description = "Estimated AWS charges for this account have exceeded ${var.billing_alarm_threshold_usd} USD. This lite stack is meant to stay at or below that."

  namespace   = "AWS/Billing"
  metric_name = "EstimatedCharges"
  statistic   = "Maximum"
  period      = 21600 # 6 hours: the metric is published a few times a day, so a
  #                     shorter period only creates gaps.
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.billing_alarm_threshold_usd

  dimensions = {
    Currency = "USD"
  }

  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.billing.arn]
  ok_actions    = [aws_sns_topic.billing.arn]
}
