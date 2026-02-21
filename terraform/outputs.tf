output "pages_project_id" {
  description = "ID of the Cloudflare Pages project"
  value       = cloudflare_pages_project.secretzero_docs.id
}

output "pages_project_subdomain" {
  description = "Cloudflare subdomain for the Pages project"
  value       = cloudflare_pages_project.secretzero_docs.subdomain
}

output "pages_project_url" {
  description = "URL of the Cloudflare Pages project"
  value       = "https://${cloudflare_pages_project.secretzero_docs.subdomain}.pages.dev"
}

output "custom_domain" {
  description = "Custom domain configured for the site"
  value       = var.domain_name
}

output "custom_domain_url" {
  description = "URL of the custom domain"
  value       = "https://${var.domain_name}"
}

output "custom_domain_status" {
  description = "Status of the custom domain configuration"
  value       = cloudflare_pages_domain.docs_domain.status
}

output "dns_record_id" {
  description = "ID of the DNS CNAME record"
  value       = cloudflare_record.docs_cname.id
}

output "production_branch" {
  description = "Production branch of the project"
  value       = cloudflare_pages_project.secretzero_docs.production_branch
}

output "framework_detected" {
  description = "Framework detected by Cloudflare Pages"
  value       = cloudflare_pages_project.secretzero_docs.framework
}

output "latest_deployment" {
  description = "Details of the latest deployment"
  value = {
    id         = try(cloudflare_pages_project.secretzero_docs.latest_deployment[0].id, null)
    url        = try(cloudflare_pages_project.secretzero_docs.latest_deployment[0].url, null)
    created_on = try(cloudflare_pages_project.secretzero_docs.latest_deployment[0].created_on, null)
  }
  sensitive = false
}
