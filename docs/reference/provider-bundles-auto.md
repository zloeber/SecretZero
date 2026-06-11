# Provider Bundles (Auto-Generated)

This page is generated from the live `BundleRegistry` and provider class metadata.
It complements the hand-written workflow pages under `user-guide/providers/*`.

## Provider Bundle Matrix

| Bundle | Version | Provider kind | Provider class path | Target kinds | Auth methods | Required dependency |
|---|---|---|---|---|---|---|
| `ansible_vault` | `1.0.0` | `ansible_vault` | `secretzero.providers.ansible_vault:AnsibleVaultProvider` | `ansible_vault_file` | `password`, `password_env` | `ansible_vault` (`secretzero[ansible_vault]`) |
| `aws` | `1.0.0` | `aws` | `secretzero.providers.aws:AWSProvider` | `secrets_manager`, `ssm_parameter` | `ambient`, `assume_role`, `token` | `boto3` (`secretzero[aws]`) |
| `azure` | `1.0.0` | `azure` | `secretzero.providers.azure:AzureProvider` | `azure_keyvault`, `key_vault` | `ambient`, `token` | `azure.identity` (`secretzero[azure]`) |
| `entra-agent-id` | `1.0.0` | `entra-agent-id` | `secretzero.providers.entra_agent_id:EntraAgentIdProvider` | None | `default`, `service_principal`, `token` | `azure.identity` (`secretzero[entra_agent_id]`) |
| `git_crypt` | `1.0.0` | `git_crypt` | `secretzero.providers.git_crypt:GitCryptProvider` | `git_crypt_file` | `ambient` | None |
| `github` | `1.0.0` | `github` | `secretzero.providers.github:GitHubProvider` | `github_secret` | `oauth_device`, `token` | `github` (`secretzero[github]`) |
| `gitlab` | `1.0.0` | `gitlab` | `secretzero.providers.gitlab:GitLabProvider` | `gitlab_group_variable`, `gitlab_variable` | `token` | `gitlab` (`secretzero[gitlab]`) |
| `infisical` | `1.0.0` | `infisical` | `secretzero.providers.infisical:InfisicalProvider` | None | None declared | None |
| `jenkins` | `1.0.0` | `jenkins` | `secretzero.providers.jenkins:JenkinsProvider` | `jenkins_credential` | `token` | `jenkins` (`secretzero[jenkins]`) |
| `keeper` | `1.1.0` | `keeper` | `secretzero.providers.keeper:KeeperProvider` | `keeper_record` | `default`, `token` | `keepercommander` (`secretzero[keeper]`) |
| `kubernetes` | `1.0.0` | `kubernetes` | `secretzero.providers.kubernetes:KubernetesProvider` | `external_secret`, `kubernetes_secret` | `ambient`, `kubeconfig` | `kubernetes` (`secretzero[kubernetes]`) |
| `sops` | `1.0.0` | `sops` | `secretzero.providers.sops:SopsProvider` | `sops_file` | `ambient` | None |
| `vault` | `1.0.0` | `vault` | `secretzero.providers.vault:VaultProvider` | `kv`, `vault_kv` | `ambient`, `token` | `hvac` (`secretzero[vault]`) |
| `vercel` | `1.0.0` | `vercel` | `secretzero.providers.vercel:VercelProvider` | `vercel_env` | `token` | `requests` (`secretzero[vercel]`) |

## Notes

- Discovery includes built-in bundle manifests and any installed third-party entry points.
- Missing optional dependencies can prevent provider classes from loading.
- Regenerate via `task docs:generate:provider-bundles`.
