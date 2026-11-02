# =============================================================================
# lite-infra/variables.tf
# =============================================================================

variable "project" {
  description = "Project name, used as the first half of every resource name"
  type        = string
  default     = "odoo-invoice-agent"
}

variable "environment" {
  description = "Environment name (free-form; 'lite' keeps the names short)"
  type        = string
  default     = "lite"
}

variable "aws_region" {
  description = "Region for the instance. Lightsail is only available in a subset of AWS regions"
  type        = string
  default     = "eu-north-1"
}

# ---------------------------------------------------------------------------
# The instance itself
# ---------------------------------------------------------------------------
variable "availability_zone" {
  description = "AZ inside aws_region. Must be a zone Lightsail offers: aws lightsail get-regions --include-availability-zones"
  type        = string
  default     = "eu-north-1a"
}

variable "bundle_id" {
  description = "Lightsail bundle. nano_3_0 is the $5/month tier (2 vCPU, 512 MB, 20 GB SSD, 1 TB transfer). Confirm with: aws lightsail get-bundles"
  type        = string
  default     = "nano_3_0"

  validation {
    condition     = can(regex("^nano_", var.bundle_id))
    error_message = "This option is budget-capped: pick a nano_* bundle ($5/month). Anything larger leaves the $5 target."
  }
}

variable "blueprint_id" {
  description = "OS image. 'ubuntu_24_04' is current; list them with: aws lightsail get-blueprints"
  type        = string
  default     = "ubuntu_24_04"
}

# ---------------------------------------------------------------------------
# What runs on it
# ---------------------------------------------------------------------------
variable "repo_url" {
  description = "Git URL the instance clones. Defaults to this repository"
  type        = string
  default     = "https://github.com/7ananSaif/odoo.git"
}

variable "repo_branch" {
  description = "Branch to check out on the instance"
  type        = string
  default     = "feature/invoice-ai-service"
}

variable "app_image" {
  description = <<-EOT
    Optional prebuilt image for the app. Empty (default) means the instance
    builds the repo's own ./Dockerfile on first boot - correct, but on a 5%
    baseline CPU it takes 30-60 minutes. Set this to an image you already
    pushed (e.g. "docker.io/you/odoo-invoice-agent:1.0") to skip that build.
    REQUIRES Docker Hub (or GHCR) as in both cases boot.sh pulls it.
  EOT
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Database (placeholders - see README for how to override)
# ---------------------------------------------------------------------------
variable "db_name" {
  description = "Odoo database name created on first boot"
  type        = string
  default     = "odoo"
}

variable "db_user" {
  description = "PostgreSQL user for the app"
  type        = string
  default     = "odoo"
}

variable "db_password" {
  description = "PostgreSQL password. The default is a LOCAL-ONLY placeholder and must be changed for anything reachable from the internet"
  type        = string
  default     = "change-me-lite-placeholder"
  sensitive   = true
}

# ---------------------------------------------------------------------------
# Access and alerting
# ---------------------------------------------------------------------------
variable "ssh_public_key" {
  description = "Optional SSH public key to install on the instance. Empty means Terraform creates a Lightsail key pair and exposes the private key as a sensitive output"
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed to reach SSH (22). Narrow this to your own IP; '0.0.0.0/0' means the whole internet"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "http_allowed_cidrs" {
  description = "CIDR blocks allowed to reach the app on port 80 (and 8069 while you are not behind a proxy)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "billing_alarm_email" {
  description = "Email subscribed to the $5 billing alarm SNS topic. Empty disables the subscription (the alarm still exists but notifies nobody)"
  type        = string
  default     = ""
}

variable "billing_alarm_threshold_usd" {
  description = "Alarm when estimated monthly charges exceed this many USD"
  type        = number
  default     = 5
}
