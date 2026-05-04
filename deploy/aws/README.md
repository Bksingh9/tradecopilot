# AWS deploy (Terraform)

> Educational use only. Not financial advice.

What this provisions:

- **VPC** (10.40.0.0/16) with two public + two private subnets, NAT GW per AZ.
- **ALB** (public) → **ECS Fargate** API service in private subnets.
- **ECS Fargate worker** (no inbound) running `app.workers.ai_worker`.
- **RDS Postgres 16** (private), **ElastiCache Redis 7** (private).
- **ECR** repo for the API/worker image.
- **S3 + CloudFront** for the frontend (private bucket, OAC).
- **SSM Parameter Store** for secrets (`JWT_SECRET`, Fernet key, AI service token, etc.).

## Prereqs

- Terraform ≥ 1.6, AWS CLI v2, Docker.
- AWS account + credentials (`aws configure`).
- A globally-unique S3 bucket name for the frontend.

## Steps

```bash
cd deploy/aws

# 1. Create a tfvars file:
cat > terraform.tfvars <<EOF
project              = "tradecopilot"
region               = "us-east-1"
azs                  = ["us-east-1a", "us-east-1b"]
frontend_bucket_name = "tradecopilot-frontend-$RANDOM"   # must be globally unique
# domain_name        = "tradecopilot.example.com"        # optional; needs ACM cert in this region
EOF

# 2. Plan + apply (this provisions the network + DBs + ALB; image push comes next).
terraform init
terraform apply -auto-approve

# 3. Replace the Fernet key placeholder.
aws ssm put-parameter --overwrite \
  --name /tradecopilot/SECRETS_FERNET_KEY \
  --type SecureString \
  --value "$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# 4. Build + push the API image. Terraform prints the exact commands:
terraform output -raw build_and_push_command | bash

# 5. Build + sync the frontend.
ALB=$(terraform output -raw alb_dns)
BUCKET=$(terraform output -raw frontend_bucket)
( cd ../../frontend && VITE_API_BASE="http://$ALB" npm ci && VITE_API_BASE="http://$ALB" npm run build )
aws s3 sync ../../frontend/dist/ "s3://$BUCKET/" --delete
aws cloudfront create-invalidation \
  --distribution-id "$(aws cloudfront list-distributions \
        --query 'DistributionList.Items[?Origins.Items[0].DomainName==`'$BUCKET'.s3.us-east-1.amazonaws.com`].Id' \
        --output text)" \
  --paths '/*'
```

## Verify

```bash
ALB=$(terraform output -raw alb_dns)
WEB=$(terraform output -raw frontend_url)

curl -s "http://$ALB/health/core"
open "$WEB"
```

## Cost shape

A single-AZ minimum ish: ~$15-40/mo idle on `db.t4g.micro` + `cache.t4g.micro` + 1 Fargate task + ALB. Two NAT gateways are the dominant cost — drop one if you don't need cross-AZ HA in dev.

## Pgvector

```bash
DB_URL=$(terraform output -raw database_url)
psql "$DB_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
aws ssm put-parameter --overwrite --name /tradecopilot/VECTOR_BACKEND --type String --value pgvector  # if you wire this into the task def
```
