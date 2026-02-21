# Cloudflare Pages Project for SecretZero Documentation
resource "cloudflare_pages_project" "secretzero_docs" {
  account_id        = var.cloudflare_account_id
  name              = var.project_name
  production_branch = var.production_branch

  # Build configuration for MkDocs
  build_config {
    build_caching   = true
    build_command   = var.build_command
    destination_dir = var.build_output_dir
    root_dir        = "/"

    # Optional: Enable Web Analytics
    web_analytics_token = var.enable_web_analytics && var.web_analytics_token != "" ? var.web_analytics_token : null
  }

  # GitHub source configuration (optional)
  dynamic "source" {
    for_each = var.enable_github_integration ? [1] : []
    content {
      type = "github"
      config {
        owner                         = var.github_repo_owner
        repo_name                     = var.github_repo_name
        production_branch             = var.production_branch
        pr_comments_enabled           = true
        deployments_enabled           = true
        production_deployments_enabled = true
        preview_deployment_setting    = "all"
        preview_branch_includes       = var.preview_branch_includes
        preview_branch_excludes       = var.preview_branch_excludes
      }
    }
  }

  # Deployment configuration
  deployment_configs {
    production {
      compatibility_date  = "2026-02-21"
      compatibility_flags = ["nodejs_compat"]
    }

    preview {
      compatibility_date  = "2026-02-21"
      compatibility_flags = ["nodejs_compat"]
    }
  }
}

# Custom domain for the Pages project
resource "cloudflare_pages_domain" "docs_domain" {
  account_id   = var.cloudflare_account_id
  project_name = cloudflare_pages_project.secretzero_docs.name
  domain       = var.domain_name

  depends_on = [
    cloudflare_pages_project.secretzero_docs,
    cloudflare_record.docs_cname
  ]
}

# DNS CNAME record pointing to the Pages project
resource "cloudflare_record" "docs_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "docs"
  content = "${var.project_name}.pages.dev"
  type    = "CNAME"
  proxied = true
  comment = "Cloudflare Pages project for SecretZero documentation"
}

# Optional: DNS record for www subdomain redirect
resource "cloudflare_record" "www_docs_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "www.docs"
  content = var.domain_name
  type    = "CNAME"
  proxied = true
  comment = "Redirect www.docs to docs"
}
