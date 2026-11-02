# =============================================================================
# rds.tf - Multi-AZ PostgreSQL 16 for Odoo
#
# - db.t4g.medium (2 vCPU, 8 GB RAM)
# - Multi-AZ synchronous standby for HA
# - Automated backups 7 days + PITR
# - Custom parameter group tuned for Odoo
# - Credentials in AWS Secrets Manager (not Terraform state)
# =============================================================================

# ---------------------------------------------------------------------------
# Secrets Manager - store the master password separately
# ---------------------------------------------------------------------------
resource "random_password" "db_master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:?"
}

resource "aws_secretsmanager_secret" "db_master" {
  name                    = "${local.name_prefix}/rds/master-password"
  description             = "Master password for RDS PostgreSQL instance"
  recovery_window_in_days = 7

  tags = {
    Name = "${local.name_prefix}-rds-secret"
  }
}

resource "aws_secretsmanager_secret_version" "db_master" {
  secret_id = aws_secretsmanager_secret.db_master.id
  secret_string = jsonencode({
    username = var.db_master_username
    password = random_password.db_master.result
    host     = aws_db_instance.odoo.address
    port     = aws_db_instance.odoo.port
    dbname   = var.db_name
  })
}

# ---------------------------------------------------------------------------
# Secrets Manager - Odoo application user (lower-privilege)
# ---------------------------------------------------------------------------
resource "random_password" "db_odoo_user" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:?"
}

resource "aws_secretsmanager_secret" "db_odoo_user" {
  name                    = "${local.name_prefix}/rds/odoo-password"
  description             = "Odoo application password for RDS PostgreSQL"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "db_odoo_user" {
  secret_id = aws_secretsmanager_secret.db_odoo_user.id
  secret_string = jsonencode({
    username = "odoo_user"
    password = random_password.db_odoo_user.result
    host     = aws_db_instance.odoo.address
    port     = aws_db_instance.odoo.port
    dbname   = var.db_name
  })
}

# ---------------------------------------------------------------------------
# Parameter group - tuned for Odoo on 8 GB RAM instance
# ---------------------------------------------------------------------------
resource "aws_db_parameter_group" "odoo" {
  name   = "${local.name_prefix}-pg16"
  family = "postgres16"

  description = "Custom PostgreSQL 16 parameter group for Odoo"

  # Memory tuning (db.t4g.medium = 8 GB)
  # NOTE: RDS API rejects human-readable sizes ("4GB") - each parameter has
  # its own unit: shared_buffers/effective_cache_size/wal_buffers are in
  # 8 kB blocks; work_mem/maintenance_work_mem are in kB.
  parameter {
    name         = "shared_buffers"
    value        = "524288" # 4 GB in 8 kB blocks
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "effective_cache_size"
    value = "1572864" # 12 GB in 8 kB blocks
  }

  parameter {
    name  = "work_mem"
    value = "65536" # 64 MB in kB
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "1048576" # 1 GB in kB
  }

  # Connection limits
  # NOTE: max_connections is a static parameter - requires reboot to apply
  parameter {
    name         = "max_connections"
    value        = "200"
    apply_method = "pending-reboot"
  }

  # Query logging for diagnostics
  parameter {
    name  = "log_min_duration_statement"
    value = "200"
  }

  # Statistics for query planner
  parameter {
    name  = "random_page_cost"
    value = "1.1"
  }

  parameter {
    name  = "effective_io_concurrency"
    value = "200"
  }

  # WAL settings for durability
  # NOTE: wal_buffers is measured in 8 kB units on RDS (64 MB = 8192)
  # and is a static parameter - requires reboot to apply
  parameter {
    name         = "wal_buffers"
    value        = "8192"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  tags = {
    Name = "${local.name_prefix}-pg16-params"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ---------------------------------------------------------------------------
# DB subnet group - data subnets only (no internet)
# ---------------------------------------------------------------------------
resource "aws_db_subnet_group" "odoo" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = aws_subnet.data[*].id

  description = "Data subnets for RDS - no internet access"

  tags = {
    Name = "${local.name_prefix}-db-subnet-group"
  }
}

# ---------------------------------------------------------------------------
# RDS instance - Multi-AZ PostgreSQL 16
# ---------------------------------------------------------------------------
resource "aws_db_instance" "odoo" {
  identifier = "${local.name_prefix}-db"

  # TEMPORARY (free-tier): db.t4g.micro instead of var.db_instance_class (db.t4g.medium).
  # REVERT after account plan upgrade: restore to var.db_instance_class.
  engine               = "postgres"
  engine_version       = var.db_engine_version
  instance_class       = "db.t4g.micro" # TEMPORARY - revert to var.db_instance_class
  parameter_group_name = aws_db_parameter_group.odoo.name

  # Storage
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 200
  storage_type          = "gp3"
  storage_encrypted     = true

  # Database
  db_name  = var.db_name
  username = var.db_master_username
  password = random_password.db_master.result

  # TEMPORARY (free-tier): single-AZ instead of Multi-AZ.
  # REVERT after account plan upgrade: restore to multi_az = true.
  multi_az = false # TEMPORARY - revert to true

  # Networking - data subnets, isolated from internet
  db_subnet_group_name   = aws_db_subnet_group.odoo.name
  vpc_security_group_ids = [aws_security_group.data.id]
  publicly_accessible    = false
  port                   = 5432

  # TEMPORARY (free-tier): 1-day backups instead of var.db_backup_retention_period (7).
  # REVERT after account plan upgrade: restore to var.db_backup_retention_period.
  backup_retention_period   = 1 # TEMPORARY - revert to var.db_backup_retention_period
  backup_window             = var.db_backup_window
  maintenance_window        = var.db_maintenance_window
  copy_tags_to_snapshot     = true
  delete_automated_backups  = true
  final_snapshot_identifier = "${local.name_prefix}-final-snapshot"
  skip_final_snapshot       = false

  # TEMPORARY (free-tier): Performance Insights disabled.
  # REVERT after account plan upgrade: restore enabled=true / retention=7.
  performance_insights_enabled          = false # TEMPORARY - revert to true
  performance_insights_retention_period = 0     # TEMPORARY - revert to 7
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]

  # Protection
  deletion_protection = false

  # Require SSL connections
  apply_immediately = false

  tags = {
    Name = "${local.name_prefix}-rds"
  }

  lifecycle {
    prevent_destroy = false
  }
}

# ---------------------------------------------------------------------------
# IAM role for enhanced monitoring
# ---------------------------------------------------------------------------
resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ---------------------------------------------------------------------------
# CloudWatch alarms
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${local.name_prefix}-rds-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 10737418240 # 10 GB in bytes
  alarm_description   = "RDS free storage below 10 GB"
  alarm_actions       = []
  ok_actions          = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.odoo.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.name_prefix}-rds-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 160 # 80% of max_connections=200
  alarm_description   = "RDS connections above 80% of max"
  alarm_actions       = []
  ok_actions          = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.odoo.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name_prefix}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU above 80% sustained"
  alarm_actions       = []
  ok_actions          = []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.odoo.identifier
  }
}
