# =============================================================================
# lite-infra/outputs.tf
# =============================================================================

output "instance_name" {
  description = "Lightsail instance name (needed for start/stop, snapshots, and deploy/lite-aws.sh)"
  value       = aws_lightsail_instance.app.name
}

output "static_ip" {
  description = "Public static IP of the instance"
  value       = aws_lightsail_static_ip.this.ip_address
}

output "app_url" {
  description = "Where the app answers once cloud-init has finished (HTTP, port 80)"
  value       = "http://${aws_lightsail_static_ip.this.ip_address}/web/login"
}

output "ssh_command" {
  description = "SSH command using the generated key"
  value       = "ssh -i lite-infra-key.pem ubuntu@${aws_lightsail_static_ip.this.ip_address}"
}

output "ssh_private_key" {
  description = "Generated SSH private key. Only set when var.ssh_public_key was empty. Write it with: terraform output -raw ssh_private_key > lite-infra-key.pem && chmod 600 lite-infra-key.pem"
  value       = aws_lightsail_key_pair.this.private_key
  sensitive   = true
}

output "database_url" {
  description = "DATABASE_URL as the app sees it. Contains the placeholder password unless var.db_password was overridden"
  value       = local.database_url
  sensitive   = true
}

output "billing_alarm_topic_arn" {
  description = "SNS topic the $5 billing alarm publishes to"
  value       = aws_sns_topic.billing.arn
}

output "monthly_cost_estimate_usd" {
  description = "What this stack is expected to bill per month, in USD"
  value = {
    lightsail_nano_bundle  = 5.00
    static_ip_attached     = 0.00
    sns_email_notification = 0.00
    cloudwatch_alarm       = 0.10
    total                  = 5.10
  }
}
