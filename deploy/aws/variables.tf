variable "project" {
  description = "Tag prefix and resource name prefix."
  type        = string
  default     = "tradecopilot"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "azs" {
  description = "Two availability zones for the public + private subnets."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "api_image_tag" {
  description = "ECR image tag to deploy for the API + worker (push to ECR before terraform apply)."
  type        = string
  default     = "latest"
}

variable "frontend_bucket_name" {
  description = "Globally-unique S3 bucket name for the static frontend."
  type        = string
}

variable "domain_name" {
  description = "Optional custom domain (e.g. tradecopilot.example.com). Leave blank to use the default CloudFront domain."
  type        = string
  default     = ""
}
