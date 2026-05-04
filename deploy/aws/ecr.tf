resource "aws_ecr_repository" "api" {
  name                 = "${var.project}-api"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = { project = var.project }
}

# Push the image after `terraform apply` and before `aws ecs update-service`.
# Terraform output `ecr_login_command` shows the exact docker login + push.
