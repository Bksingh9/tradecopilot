resource "random_password" "jwt" {
  length  = 48
  special = false
}

resource "random_password" "fernet_seed" {
  length  = 32
  special = false
}

# Fernet keys must be 32 bytes urlsafe-base64. The simplest reliable way is to
# pin a value once via terraform import / manual put. As a bootstrap, we put a
# clearly-marked placeholder; rotate it after the first deploy.
resource "aws_ssm_parameter" "jwt_secret" {
  name  = "/${var.project}/JWT_SECRET"
  type  = "SecureString"
  value = random_password.jwt.result
}

resource "aws_ssm_parameter" "fernet_key" {
  name  = "/${var.project}/SECRETS_FERNET_KEY"
  type  = "SecureString"
  # CHANGE THIS AFTER FIRST DEPLOY: aws ssm put-parameter --overwrite --name /tradecopilot/SECRETS_FERNET_KEY \
  #   --type SecureString --value "$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  value = "REPLACE-WITH-FERNET-KEY"
  lifecycle { ignore_changes = [value] }
}

resource "aws_ssm_parameter" "ai_service_url" {
  name  = "/${var.project}/AI_SERVICE_URL"
  type  = "String"
  value = ""
  lifecycle { ignore_changes = [value] }
}

resource "aws_ssm_parameter" "ai_service_api_key" {
  name  = "/${var.project}/AI_SERVICE_API_KEY"
  type  = "SecureString"
  value = "set-me-after-deploy"
  lifecycle { ignore_changes = [value] }
}

resource "aws_ssm_parameter" "ai_worker_admin_token" {
  name  = "/${var.project}/AI_WORKER_ADMIN_TOKEN"
  type  = "SecureString"
  value = "set-me-after-deploy"
  lifecycle { ignore_changes = [value] }
}
