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
