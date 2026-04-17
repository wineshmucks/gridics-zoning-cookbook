variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
}

variable "project" {
  description = "Short project slug used in AWS resource names."
  type        = string
  default     = "uzone"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the deployment VPC."
  type        = string
  default     = "10.42.0.0/20"
}

variable "use_existing_vpc" {
  description = "When true, attach resources to an existing VPC and subnets instead of creating a new network."
  type        = bool
  default     = false
}

variable "use_existing_alb" {
  description = "When true, attach UZone to an existing Application Load Balancer instead of creating a dedicated ALB."
  type        = bool
  default     = false

  validation {
    condition     = var.use_existing_alb == false || var.use_existing_vpc == true
    error_message = "use_existing_alb requires use_existing_vpc=true so ECS services and target groups live in the same VPC as the shared ALB."
  }
}

variable "existing_alb_arn" {
  description = "Existing ALB ARN to use when use_existing_alb is true."
  type        = string
  default     = ""

  validation {
    condition = (
      var.use_existing_alb == false ||
      trimspace(var.existing_alb_arn) != ""
    )
    error_message = "When use_existing_alb is true, existing_alb_arn must be set."
  }
}

variable "existing_alb_http_listener_arn" {
  description = "Optional existing ALB HTTP listener ARN for shared-ALB routing."
  type        = string
  default     = ""
}

variable "existing_alb_https_listener_arn" {
  description = "Optional existing ALB HTTPS listener ARN for shared-ALB routing."
  type        = string
  default     = ""

  validation {
    condition = (
      var.use_existing_alb == false ||
      trimspace(var.existing_alb_http_listener_arn) != "" ||
      trimspace(var.existing_alb_https_listener_arn) != ""
    )
    error_message = "When use_existing_alb is true, set at least one of existing_alb_http_listener_arn or existing_alb_https_listener_arn."
  }
}

variable "existing_alb_host_header" {
  description = "Host header to match when routing UZone through an existing shared ALB, for example staging.example.com."
  type        = string
  default     = ""

  validation {
    condition = (
      var.use_existing_alb == false ||
      trimspace(var.existing_alb_host_header) != ""
    )
    error_message = "When use_existing_alb is true, existing_alb_host_header must be set so listener rules only match UZone traffic."
  }
}

variable "existing_alb_frontend_rule_priority" {
  description = "Listener rule priority for frontend traffic on a shared ALB."
  type        = number
  default     = 110
}

variable "existing_alb_api_rule_priority" {
  description = "Listener rule priority for /api traffic on a shared ALB."
  type        = number
  default     = 100

  validation {
    condition     = var.existing_alb_api_rule_priority != var.existing_alb_frontend_rule_priority
    error_message = "existing_alb_api_rule_priority and existing_alb_frontend_rule_priority must be different."
  }

  validation {
    condition     = var.existing_alb_api_rule_priority < var.existing_alb_frontend_rule_priority
    error_message = "existing_alb_api_rule_priority should be lower than existing_alb_frontend_rule_priority so /api rules win before the frontend catch-all rule."
  }
}

variable "existing_vpc_id" {
  description = "Existing VPC ID to use when use_existing_vpc is true."
  type        = string
  default     = ""

  validation {
    condition = (
      var.use_existing_vpc == false ||
      var.use_existing_alb == true ||
      trimspace(var.existing_vpc_id) != ""
    )
    error_message = "When use_existing_vpc is true, existing_vpc_id must be set unless use_existing_alb is also true and Terraform can derive the VPC from the shared ALB."
  }
}

variable "existing_public_subnet_ids" {
  description = "Existing public subnet IDs to use when use_existing_vpc is true."
  type        = list(string)
  default     = []

  validation {
    condition = (
      var.use_existing_vpc == false ||
      length(var.existing_public_subnet_ids) >= 2
    )
    error_message = "When use_existing_vpc is true, existing_public_subnet_ids must include at least two subnet IDs."
  }
}

variable "existing_private_subnet_ids" {
  description = "Existing private subnet IDs to use when use_existing_vpc is true."
  type        = list(string)
  default     = []

  validation {
    condition = (
      var.use_existing_vpc == false ||
      length(var.existing_private_subnet_ids) >= 2
    )
    error_message = "When use_existing_vpc is true, existing_private_subnet_ids must include at least two subnet IDs."
  }
}

variable "assets_bucket_name" {
  description = "S3 bucket name for jurisdiction assets."
  type        = string
  default     = "gridics-uzones"
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN for HTTPS on the ALB."
  type        = string
  default     = ""
}

variable "public_base_url" {
  description = "Canonical public base URL for the deployed app, for example https://staging.example.com."
  type        = string
  default     = ""

  validation {
    condition = (
      var.use_existing_alb == false ||
      trimspace(var.public_base_url) != ""
    )
    error_message = "When use_existing_alb is true, public_base_url must be set so the frontend can resolve the backend through the shared ALB hostname."
  }
}

variable "app_allowed_origins" {
  description = "Comma-separated origins allowed by the backend CORS config."
  type        = string
}

variable "db_name" {
  description = "RDS database name."
  type        = string
  default     = "uzone"
}

variable "db_username" {
  description = "RDS master username."
  type        = string
}

variable "db_password" {
  description = "RDS master password."
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_engine_version" {
  description = "Postgres engine version."
  type        = string
  default     = "16.13"
}

variable "db_allocated_storage" {
  description = "Initial RDS storage in GB."
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Autoscaling storage ceiling in GB."
  type        = number
  default     = 20
}

variable "db_backup_retention_period" {
  description = "RDS automated backup retention period."
  type        = number
  default     = 1
}

variable "db_deletion_protection" {
  description = "Protect the database from accidental deletion."
  type        = bool
  default     = false
}

variable "db_skip_final_snapshot" {
  description = "Skip the final snapshot on destroy."
  type        = bool
  default     = true
}

variable "backend_image_tag" {
  description = "Tag to deploy from the backend ECR repository."
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Tag to deploy from the frontend ECR repository."
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  description = "Backend task CPU units."
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Backend task memory in MiB."
  type        = number
  default     = 1024
}

variable "frontend_cpu" {
  description = "Frontend task CPU units."
  type        = number
  default     = 512
}

variable "frontend_memory" {
  description = "Frontend task memory in MiB."
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Number of backend tasks to run."
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Number of frontend tasks to run."
  type        = number
  default     = 1
}

variable "backend_environment" {
  description = "Additional non-secret backend environment variables."
  type        = map(string)
  default     = {}
}

variable "frontend_environment" {
  description = "Additional non-secret frontend environment variables."
  type        = map(string)
  default     = {}
}

variable "backend_secret_arns" {
  description = "Map of backend environment variable names to Secrets Manager or SSM ARNs."
  type        = map(string)
  default     = {}
}

variable "frontend_secret_arns" {
  description = "Map of frontend environment variable names to Secrets Manager or SSM ARNs."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}

variable "tag_env" {
  description = "Environment tag value applied to provider default tags."
  type        = string

  validation {
    condition     = trimspace(var.tag_env) != ""
    error_message = "tag_env must be set."
  }
}

variable "tag_name" {
  description = "Name tag value applied to provider default tags."
  type        = string

  validation {
    condition     = trimspace(var.tag_name) != ""
    error_message = "tag_name must be set."
  }
}
