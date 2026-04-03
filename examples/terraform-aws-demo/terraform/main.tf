terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
}

resource "random_password" "test_db_password" {
  length = 32
  special = true
  upper = true
  lower = true
  numeric = true
  override_special = "\"@/\\`"
}

resource "random_string" "test_api_key" {
  length = 48
}

resource "random_string" "more_secure_api_key" {
  length = 48
}

resource "random_password" "test_secret_json" {
  length = 24
  special = true
}

resource "aws_ssm_parameter" "test_db_password" {
  name = "/test/database/password"
  value = random_password.test_db_password.result
  type = "SecureString"
  overwrite = true
}

resource "aws_ssm_parameter" "test_api_key" {
  name = "/test/api/key"
  value = random_string.test_api_key.result
  type = "SecureString"
  overwrite = true
}

resource "aws_secretsmanager_secret" "more_secure_api_key_meta" {
  name = "/test/api/key"
  description = "Random API key for testing"
}

resource "aws_secretsmanager_secret_version" "more_secure_api_key" {
  secret_id = aws_secretsmanager_secret.more_secure_api_key_meta.id
  secret_string = random_string.more_secure_api_key.result
}

resource "aws_secretsmanager_secret" "test_secret_json_meta" {
  name = "test/json-secret"
  description = "Test secret stored in LocalStack Secrets Manager"
}

resource "aws_secretsmanager_secret_version" "test_secret_json" {
  secret_id = aws_secretsmanager_secret.test_secret_json_meta.id
  secret_string = random_password.test_secret_json.result
}
