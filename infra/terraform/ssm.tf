# =============================================================================
# ssm.tf - SSM Session Manager endpoints (the SSH replacement)
#
# WHY THIS FILE EXISTS
#   The app tier has NO SSH. No security group opens port 22, no key pair
#   exists, and the instances sit in private subnets with no public IP, so
#   there is no path in over SSH at all.
#
#   That only works if the instances can still be reached for operations, so
#   host access is SSM Session Manager. Session Manager is an *outbound* flow
#   from the instance to the SSM service, but the app subnets route
#   0.0.0.0/0 to the NAT gateway - every session would be billed as NAT data
#   processing and would traverse the public internet.
#
#   These three interface endpoints keep the agent-to-SSM traffic inside the
#   VPC over the AWS private network instead:
#     ssm           - the control channel (StartSession, DescribeInstance)
#     ssmmessages   - the data channel that carries the interactive shell
#     ec2messages   - the agent's message-polling endpoint
#
#   This is the same pattern as the S3 gateway endpoint in subnets.tf: pull
#   traffic off the NAT and onto a private path.
#
# REFERENCES
#   Ubuntu OpenSSH guide  - https://ubuntu.com/server/docs/how-to/security/openssh-server/
#   (kept as the reference for *what we deliberately do not do*: no sshd
#   exposure, no port 22 ingress, key-based auth only if SSH were ever
#   reintroduced)
# =============================================================================

# ---------------------------------------------------------------------------
# Security group - interface endpoints accept 443 from the app tier only
# ---------------------------------------------------------------------------
resource "aws_security_group" "ssm" {
  name        = "${local.name_prefix}-ssm-sg"
  description = "SSM interface endpoints - inbound 443 from app tier only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-ssm-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "ssm_from_app" {
  security_group_id            = aws_security_group.ssm.id
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "HTTPS from app tier only (SSM agent)"
}

# ---------------------------------------------------------------------------
# The three interface endpoints the SSM agent needs.
#
# private_dns_enabled = true makes each service's public hostname resolve to
# the endpoint's private ENI inside the VPC, so the agent needs no
# configuration change - it keeps calling ssm.<region>.amazonaws.com and the
# VPC DNS sends it to the ENI.
#
# Placed in the APP subnets (not public): the only consumers are the app-tier
# instances, and the endpoints must be reachable by them without crossing a
# route-table boundary.
# ---------------------------------------------------------------------------
locals {
  ssm_endpoint_services = {
    ssm         = "com.amazonaws.${var.aws_region}.ssm"
    ssmmessages = "com.amazonaws.${var.aws_region}.ssmmessages"
    ec2messages = "com.amazonaws.${var.aws_region}.ec2messages"
  }
}

resource "aws_vpc_endpoint" "ssm" {
  for_each = local.ssm_endpoint_services

  vpc_id              = aws_vpc.main.id
  service_name        = each.value
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.app[*].id
  security_group_ids  = [aws_security_group.ssm.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.name_prefix}-${each.key}-endpoint"
  }
}
