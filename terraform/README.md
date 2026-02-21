# Terraform Configuration for SecretZero Documentation

This Terraform configuration deploys the SecretZero documentation site to Cloudflare Pages with a custom domain at `docs.secret0.com`.

## Overview

This configuration creates:
- **Cloudflare Pages Project**: Hosts the MkDocs-generated documentation
- **Custom Domain**: Configures `docs.secret0.com` as the custom domain
- **DNS Records**: Creates necessary CNAME records for the domain
- **GitHub Integration**: (Optional) Enables automatic deployments from GitHub
- **Build Configuration**: Configured for MkDocs static site generation

## Prerequisites

1. **Cloudflare Account** with access to:
   - Cloudflare Pages
   - DNS management for `secret0.com` domain

2. **Cloudflare API Token** with permissions:
   - Account: Cloudflare Pages (Edit)
   - Zone: DNS (Edit)
   - Create at: https://dash.cloudflare.com/profile/api-tokens

3. **GitHub Repository** (if using GitHub integration):
   - Connect your GitHub account to Cloudflare Pages
   - See: https://developers.cloudflare.com/pages/get-started/git-integration/

4. **Terraform** installed (version >= 1.0)
   - Install: https://www.terraform.io/downloads

## Quick Start

### 1. Configure Variables

Copy the example variables file and fill in your values:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and add your:
- `cloudflare_api_token` - Your Cloudflare API token
- `cloudflare_account_id` - Your Cloudflare account ID
- `cloudflare_zone_id` - Zone ID for secret0.com domain

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review the Plan

```bash
terraform plan
```

This will show you what resources will be created.

### 4. Apply the Configuration

```bash
terraform apply
```

Review the changes and type `yes` to confirm.

## Configuration Options

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `cloudflare_api_token` | Cloudflare API token | `abc123...` |
| `cloudflare_account_id` | Cloudflare account ID | `023e105f4ecef8ad9ca31a8372d0c353` |
| `cloudflare_zone_id` | Zone ID for secret0.com | `def456...` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | `secretzero-docs` | Name of the Pages project |
| `domain_name` | `docs.secret0.com` | Custom domain name |
| `production_branch` | `main` | Git branch for production |
| `build_command` | `mkdocs build` | Command to build the site |
| `build_output_dir` | `site` | Directory with built files |
| `enable_github_integration` | `true` | Enable GitHub deployments |
| `github_repo_owner` | `zloeber` | GitHub repository owner |
| `github_repo_name` | `SecretZero` | GitHub repository name |
| `preview_branch_includes` | `["*"]` | Branches for preview deploys |
| `enable_web_analytics` | `false` | Enable Cloudflare Analytics |

## Outputs

After applying, Terraform will output:

```
pages_project_id         - ID of the Pages project
pages_project_url        - URL of the .pages.dev site
custom_domain            - Your custom domain
custom_domain_url        - URL of your custom domain
custom_domain_status     - Status of domain configuration
dns_record_id            - DNS record ID
production_branch        - Production branch name
framework_detected       - Auto-detected framework
latest_deployment        - Latest deployment details
```

View outputs at any time:
```bash
terraform output
```

## GitHub Integration

If you enable GitHub integration (`enable_github_integration = true`), you must:

1. **Connect GitHub to Cloudflare**:
   - Visit https://dash.cloudflare.com/
   - Go to Pages → Connect to Git
   - Authorize Cloudflare with your GitHub account

2. **Configure Repository**:
   - Set `github_repo_owner` to your GitHub username/org
   - Set `github_repo_name` to your repository name

3. **Automatic Deployments**:
   - Production: Deploys on push to `main` branch
   - Preview: Deploys for all other branches and PRs

## Manual Deployments (Without GitHub)

If you prefer manual deployments without GitHub integration:

1. Set `enable_github_integration = false` in `terraform.tfvars`

2. Build your docs:
   ```bash
   mkdocs build
   ```

3. Deploy using Wrangler CLI:
   ```bash
   npx wrangler pages deploy site --project-name=secretzero-docs
   ```

## DNS Configuration

The configuration creates:

1. **docs.secret0.com** → CNAME to `{project_name}.pages.dev`
2. **www.docs.secret0.com** → CNAME to `docs.secret0.com` (redirect)

Both records are proxied through Cloudflare CDN for:
- DDoS protection
- SSL/TLS encryption
- Performance optimization
- Analytics

## Custom Domain Verification

After applying, the custom domain may take a few minutes to activate:

1. Check status in outputs:
   ```bash
   terraform output custom_domain_status
   ```

2. Expected statuses:
   - `initializing` - Domain setup in progress
   - `pending` - Verification in progress
   - `active` - Domain is live ✓
   - `error` - Check Cloudflare dashboard

3. Verify SSL certificate:
   ```bash
   curl -I https://docs.secret0.com
   ```

## Build Configuration

The default build configuration:

```hcl
build_config {
  build_caching   = true              # Enable build caching
  build_command   = "mkdocs build"    # MkDocs build command
  destination_dir = "site"            # Output directory
  root_dir        = "/"               # Repository root
}
```

For custom builds, override in `terraform.tfvars`:
```hcl
build_command    = "npm run build"
build_output_dir = "dist"
```

## Preview Deployments

Preview deployments are created for:
- All branches (except production)
- Pull requests

Configure which branches get previews:

```hcl
preview_branch_includes = ["develop", "staging", "feature/*"]
preview_branch_excludes = ["temp/*"]
```

Preview URLs: `{branch-name}.{project-name}.pages.dev`

## Web Analytics (Optional)

To enable Cloudflare Web Analytics:

1. Create analytics site in Cloudflare dashboard
2. Get the analytics token
3. Set in `terraform.tfvars`:
   ```hcl
   enable_web_analytics = true
   web_analytics_token  = "your-token"
   ```

## Troubleshooting

### "Pages project not found"
- Verify `cloudflare_account_id` is correct
- Check API token has Pages permissions

### "Zone not found"
- Verify `cloudflare_zone_id` is correct
- Check API token has DNS permissions for the zone

### "GitHub integration failed"
- Ensure GitHub account is connected to Cloudflare
- Visit: https://dash.cloudflare.com/ → Pages → Connect to Git

### "Custom domain not activating"
- Wait 5-10 minutes for DNS propagation
- Check DNS records in Cloudflare dashboard
- Verify domain ownership in Pages settings

### "Build failures"
- Check build command in `build_config`
- Verify `destination_dir` matches MkDocs output
- Review build logs in Cloudflare Pages dashboard

## Resources

- **Cloudflare Pages Docs**: https://developers.cloudflare.com/pages/
- **Terraform Cloudflare Provider**: https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs
- **MkDocs Documentation**: https://www.mkdocs.org/
- **SecretZero Project**: https://github.com/zloeber/SecretZero

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

This will remove:
- Cloudflare Pages project
- Custom domain configuration
- DNS records

**Note**: This does not delete the GitHub repository or disconnect GitHub integration.

## Security Notes

1. **Never commit `terraform.tfvars`** - It contains sensitive tokens
2. **Use separate tokens** for different environments
3. **Limit token permissions** to only what's needed
4. **Rotate tokens periodically**
5. **Store tokens securely** (e.g., secrets manager, environment variables)

## CI/CD Integration

For automated Terraform in CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Terraform Apply
  env:
    TF_VAR_cloudflare_api_token: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    TF_VAR_cloudflare_account_id: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    TF_VAR_cloudflare_zone_id: ${{ secrets.CLOUDFLARE_ZONE_ID }}
  run: |
    cd terraform
    terraform init
    terraform apply -auto-approve
```

## Environment-Specific Configurations

For multiple environments (staging, production):

1. Use separate `.tfvars` files:
   ```
   terraform.prod.tfvars
   terraform.staging.tfvars
   ```

2. Apply with specific vars:
   ```bash
   terraform apply -var-file=terraform.prod.tfvars
   ```

3. Use workspaces:
   ```bash
   terraform workspace new production
   terraform workspace select production
   terraform apply
   ```

## License

This configuration is part of the SecretZero project (Apache-2.0 License).

---

**Last Updated**: February 2026  
**Terraform Version**: >= 1.0  
**Cloudflare Provider**: ~> 5.0
