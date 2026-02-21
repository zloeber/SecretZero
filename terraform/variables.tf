variable "cloudflare_api_token" {
  description = "Cloudflare API token with permissions to manage Pages and DNS"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for secret0.com domain"
  type        = string
}

variable "project_name" {
  description = "Name of the Cloudflare Pages project"
  type        = string
  default     = "secretzero-docs"
}

variable "domain_name" {
  description = "Custom domain name for the documentation site"
  type        = string
  default     = "docs.secret0.com"
}

variable "production_branch" {
  description = "Git branch to use for production deployments"
  type        = string
  default     = "main"
}

variable "build_command" {
  description = "Command to build the site"
  type        = string
  default     = "mkdocs build"
}

variable "build_output_dir" {
  description = "Directory containing the built site"
  type        = string
  default     = "site"
}

variable "github_repo_owner" {
  description = "GitHub repository owner/organization"
  type        = string
  default     = "zloeber"
}

variable "github_repo_name" {
  description = "GitHub repository name"
  type        = string
  default     = "SecretZero"
}

variable "enable_github_integration" {
  description = "Enable GitHub integration for automatic deployments"
  type        = bool
  default     = true
}

variable "preview_branch_includes" {
  description = "Branches to include for preview deployments"
  type        = list(string)
  default     = ["*"]
}

variable "preview_branch_excludes" {
  description = "Branches to exclude from preview deployments"
  type        = list(string)
  default     = []
}

variable "enable_web_analytics" {
  description = "Enable Cloudflare Web Analytics"
  type        = bool
  default     = false
}

variable "web_analytics_token" {
  description = "Cloudflare Web Analytics token (optional)"
  type        = string
  default     = ""
  sensitive   = true
}
