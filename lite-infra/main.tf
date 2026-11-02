# =============================================================================
# lite-infra/main.tf - the cheap option: ONE Lightsail instance running Docker
# Compose with Odoo + its own PostgreSQL container.
#
# Deliberately absent, as required:
#   no EKS, no ALB, no NAT Gateway, no RDS, no VPC plumbing, no ElastiCache.
# What you get instead:
#   a $5/month Lightsail bundle with a static IP, a firewall, and cloud-init
#   that installs Docker and brings docker-compose.lite.yml up.
#
# Same tool as the rest of the repo: Terraform (see full-infra/terraform/, which
# pins the same provider generation). No new IaC tool is introduced.
#
#   cd lite-infra
#   cp terraform.tfvars.example terraform.tfvars   # set the admin email
#   terraform init && terraform plan
#   terraform apply
#
# Cost: see README.md in this directory. The short version is $5.00/month for
# the instance plus ~$0.10/month for the billing alarm metric, and $0.00 for the
# static IP while it is attached to a running instance.
# =============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Local state on purpose: one instance, one operator, no shared backend to
  # pay for or secure. If you outgrow this, copy the commented S3 backend from
  # full-infra/terraform/main.tf.
}

# Main region: Lightsail is offered in a subset of regions; eu-north-1 is what
# the rest of this repo already uses (see full-infra/terraform/variables.tf).
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Option      = "lite"
    }
  }
}

# Billing metrics (AWS/Billing, EstimatedCharges) only exist in us-east-1, no
# matter which region you actually run in. This alias exists purely so the
# $5 alarm in billing.tf can read them.
provider "aws" {
  alias  = "billing"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Option      = "lite"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.environment}-lite"

  # DATABASE_URL for the app. Placeholder passwords: this file is committed, so
  # nothing here may be a real credential. `terraform apply` can override the
  # database password through var.db_password without editing any file.
  database_url = format(
    "postgresql://%s:%s@db:5432/%s",
    var.db_user,
    var.db_password,
    var.db_name,
  )
}
