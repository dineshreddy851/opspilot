variable "aws_region" {
  description = "AWS Region where the development stack is deployed."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be a valid AWS Region name such as us-east-1."
  }
}

variable "environment" {
  description = "Short environment name used in resource names and tags."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.environment))
    error_message = "environment must be 2-16 lowercase letters, numbers, or hyphens."
  }
}

variable "owner" {
  description = "Owner value applied to all supported AWS resources."
  type        = string
  default     = "Dinesh"

  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "owner cannot be empty."
  }
}

variable "log_retention_days" {
  description = "Retention in days for application CloudWatch log groups."
  type        = number
  default     = 14

  validation {
    condition = contains(
      [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653],
      var.log_retention_days,
    )
    error_message = "log_retention_days must be a CloudWatch Logs supported retention value."
  }
}

variable "cloudtrail_retention_days" {
  description = "Days to retain multi-Region CloudTrail management-event logs in S3."
  type        = number
  default     = 90

  validation {
    condition     = var.cloudtrail_retention_days >= 30 && var.cloudtrail_retention_days <= 3650
    error_message = "cloudtrail_retention_days must be between 30 and 3650."
  }
}

variable "operations_alert_email" {
  description = "Optional email address subscribed to operational CloudWatch alarms."
  type        = string
  default     = ""
}

variable "bedrock_enabled" {
  description = "Enable Amazon Bedrock Converse tool selection with deterministic fallback."
  type        = bool
  default     = false
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock foundation model ID used for Converse tool selection."
  type        = string
  default     = "amazon.nova-lite-v1:0"

  validation {
    condition     = can(regex("^[a-z0-9.-]+:[a-z0-9.-]+$", var.bedrock_model_id))
    error_message = "bedrock_model_id must be a foundation model ID such as amazon.nova-lite-v1:0."
  }
}

variable "cognito_callback_urls" {
  description = "Allowed OAuth callback URLs for the public development app client."
  type        = list(string)
  default     = ["http://localhost:3000/callback"]

  validation {
    condition     = length(var.cognito_callback_urls) > 0
    error_message = "At least one Cognito callback URL is required."
  }
}

variable "cognito_logout_urls" {
  description = "Allowed logout URLs for the public development app client."
  type        = list(string)
  default     = ["http://localhost:3000"]

  validation {
    condition     = length(var.cognito_logout_urls) > 0
    error_message = "At least one Cognito logout URL is required."
  }
}

variable "web_allowed_origins" {
  description = "Additional development origins allowed to call the HTTP API."
  type        = list(string)
  default     = ["http://localhost:3000"]

  validation {
    condition     = alltrue([for origin in var.web_allowed_origins : can(regex("^https?://", origin))])
    error_message = "Every web_allowed_origins entry must begin with http:// or https://."
  }
}

variable "approval_email" {
  description = "Optional email address subscribed to controlled-action approval notifications."
  type        = string
  default     = ""
}

variable "approval_timeout_seconds" {
  description = "Seconds the workflow waits for an approval callback."
  type        = number
  default     = 3600

  validation {
    condition     = var.approval_timeout_seconds >= 60 && var.approval_timeout_seconds <= 86400
    error_message = "approval_timeout_seconds must be between 60 and 86400."
  }
}

variable "approval_workflow_timeout_seconds" {
  description = "Maximum total duration for a controlled-action workflow."
  type        = number
  default     = 7200

  validation {
    condition     = var.approval_workflow_timeout_seconds >= 120 && var.approval_workflow_timeout_seconds <= 172800
    error_message = "approval_workflow_timeout_seconds must be between 120 and 172800."
  }
}

variable "controlled_action_name" {
  description = "The only action the controlled-action workflow may execute."
  type        = string
  default     = "restart_approved_ecs_service"

  validation {
    condition     = var.controlled_action_name == "restart_approved_ecs_service"
    error_message = "Only restart_approved_ecs_service is allowed."
  }
}

variable "controlled_action_dry_run" {
  description = "Keep the dedicated mutation Lambda in dry-run mode."
  type        = bool
  default     = true
}

variable "controlled_action_ecs_cluster" {
  description = "Configured ECS cluster name for the controlled action."
  type        = string
  default     = "opspilot-demo"
}

variable "controlled_action_ecs_service" {
  description = "Configured ECS service name for the controlled action."
  type        = string
  default     = "opspilot-demo-service"
}

variable "controlled_action_ecs_service_arn" {
  description = "Exact ECS service ARN allowed when controlled_action_dry_run is false."
  type        = string
  default     = ""
}
