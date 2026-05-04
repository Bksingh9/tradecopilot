output "alb_dns" {
  value       = aws_lb.this.dns_name
  description = "ALB hostname — point your browser / DNS / frontend at this."
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_login_command" {
  value = "aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${local.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

output "build_and_push_command" {
  value = <<EOT
# from repo root:
docker build -t ${aws_ecr_repository.api.repository_url}:${var.api_image_tag} backend
docker push ${aws_ecr_repository.api.repository_url}:${var.api_image_tag}
aws ecs update-service --cluster ${aws_ecs_cluster.this.name} --service ${aws_ecs_service.api.name}    --force-new-deployment
aws ecs update-service --cluster ${aws_ecs_cluster.this.name} --service ${aws_ecs_service.worker.name} --force-new-deployment
EOT
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "frontend_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "database_url" {
  value     = local.database_url
  sensitive = true
}
