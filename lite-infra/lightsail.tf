# =============================================================================
# lite-infra/lightsail.tf - the one instance, its IP, its firewall, its key.
# =============================================================================

# ---------------------------------------------------------------------------
# SSH key
# ---------------------------------------------------------------------------
# Two modes:
#   * var.ssh_public_key set  -> that key is installed, you already hold the pair
#   * var.ssh_public_key ""   -> Lightsail generates a pair and Terraform exposes
#                                the private key as a sensitive output
# The generated private key lands in terraform.tfstate. That is acceptable for a
# single-operator $5 box (the state is gitignored), and it is called out in the
# README because it is a real trade-off, not an accident.
resource "aws_lightsail_key_pair" "this" {
  name       = "${local.name_prefix}-key"
  public_key = var.ssh_public_key != "" ? var.ssh_public_key : null

  lifecycle {
    # Rotating the key must not silently recreate the server (and its data).
    ignore_changes = [public_key]
  }
}

# ---------------------------------------------------------------------------
# Instance
# ---------------------------------------------------------------------------
resource "aws_lightsail_instance" "app" {
  name              = local.name_prefix
  availability_zone = var.availability_zone
  blueprint_id      = var.blueprint_id
  bundle_id         = var.bundle_id
  key_pair_name     = aws_lightsail_key_pair.this.name
  ip_address_type   = "dualstack"

  # cloud-init. Lightsail takes user_data as a single line, so the real script
  # is templated, base64-encoded and decoded on the box: no shell quoting
  # survives the trip, and the script itself stays readable in boot.sh.tftpl.
  user_data = join("", [
    "#!/bin/bash\n",
    "echo '",
    base64encode(templatefile("${path.module}/boot.sh.tftpl", {
      repo_url     = var.repo_url
      repo_branch  = var.repo_branch
      app_image    = var.app_image
      db_name      = var.db_name
      db_user      = var.db_user
      db_password  = var.db_password
      database_url = local.database_url
      compose_b64  = base64encode(file("${path.module}/docker-compose.lite.yml"))
    })),
    "' | base64 -d > /opt/lite-boot.sh && bash /opt/lite-boot.sh >> /var/log/lite-boot.log 2>&1\n",
  ])

  tags = {
    Name = local.name_prefix
  }
}

# ---------------------------------------------------------------------------
# Static IP
# ---------------------------------------------------------------------------
# A static IP is free while it is attached to a RUNNING instance. It exists so
# the address survives a stop/start - a plain Lightsail IP does not.
resource "aws_lightsail_static_ip" "this" {
  name = "${local.name_prefix}-ip"
}

resource "aws_lightsail_static_ip_attachment" "this" {
  static_ip_name = aws_lightsail_static_ip.this.name
  instance_name  = aws_lightsail_instance.app.name
}

# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------
# Only two ports: 22 for administration and 80 for the app. 443 is deliberately
# NOT opened because this option serves plain HTTP - terminate TLS properly
# (Caddy/nginx + a certificate) before you put anything real on it.
#
# Postgres (5432) is never exposed: it is only reachable from the app container
# over the compose network.
locals {
  # One entry per open port, each carrying its own CIDR list. Written as data so
  # the dynamic block below cannot silently drop all but the first CIDR.
  lite_public_ports = [
    { proto = "tcp", port = 22, cidrs = var.ssh_allowed_cidrs },
    { proto = "tcp", port = 80, cidrs = var.http_allowed_cidrs },
  ]
}

resource "aws_lightsail_instance_public_ports" "this" {
  instance_name = aws_lightsail_instance.app.name

  dynamic "port_info" {
    for_each = local.lite_public_ports

    content {
      protocol  = port_info.value.proto
      from_port = port_info.value.port
      to_port   = port_info.value.port
      cidrs     = port_info.value.cidrs
    }
  }
}
