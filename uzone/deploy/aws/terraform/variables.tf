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

variable "certificate_arn" {
  description = "Optional ACM certificate ARN for HTTPS on the ALB."
  type        = string
  default     = ""
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
  default     = "16.6"
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
