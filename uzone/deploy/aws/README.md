# UZone AWS Deployment

This directory contains a pragmatic AWS deployment baseline for `uzone/`:

- `terraform/`: VPC, ALB, ECS Fargate, ECR, CloudWatch, and RDS Postgres
- `build-and-push.sh`: builds the production images and pushes them to ECR

## Architecture

- `frontend`: Next.js container on ECS Fargate
- `backend`: FastAPI container on ECS Fargate
- `database`: Amazon RDS for PostgreSQL
- `ingress`: Application Load Balancer
- `images`: Amazon ECR

Routing is path-based:

- `/` -> frontend
- `/api/*` -> backend

## Prerequisites

- Terraform `>= 1.6`
- AWS CLI v2
- Docker
- an AWS account with permissions for ECS, ECR, IAM, ALB, VPC, CloudWatch, and RDS

## Deploy Flow

You can do the first deployment without a custom domain:

- leave `certificate_arn = ""`
- use the ALB DNS name over HTTP
- verify ECS, RDS, migrations, and page routing first

After that, add a real domain or subdomain you control, request an ACM certificate, set `certificate_arn`, and re-apply Terraform to enable HTTPS.

1. Initialize Terraform inputs.

```bash
cd uzone/deploy/aws/terraform
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars`.

Minimum values:

- `aws_region`
- `app_allowed_origins`
- `db_username`
- `db_password`

For the current app configuration in [uzone/.env](/workspaces/gridics-zoning-cookbook/uzone/.env), also set:

- `backend_environment.UZONE_AUTH_PROVIDER = "clerk"`
- `backend_environment.UZONE_CLERK_JWKS_URL`
- `backend_environment.UZONE_CLERK_AUTHORIZED_PARTIES`
- `frontend_environment.GRIDICS_CLERK_ORGANIZATION_SLUG`
- `frontend_secret_arns.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `frontend_secret_arns.CLERK_SECRET_KEY`

If you rely on a fixed Gridics org id in the UI, also set:

- `frontend_secret_arns.GRIDICS_CLERK_ORGANIZATION_ID`

Do not copy the current `.env` secrets into Terraform files. Store them in AWS Secrets Manager or SSM first.

Example bootstrap commands are in:

- [secrets-bootstrap.example.sh](/workspaces/gridics-zoning-cookbook/uzone/deploy/aws/secrets-bootstrap.example.sh)

3. Create the ECR repositories first.

```bash
terraform init
terraform apply \
  -target=aws_ecr_repository.backend \
  -target=aws_ecr_repository.frontend
```

4. Build and push the application images.

```bash
export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_or_pk_test_if_you_use_clerk

../build-and-push.sh \
  us-east-1 \
  "$(terraform output -raw backend_ecr_repository_url)" \
  "$(terraform output -raw frontend_ecr_repository_url)" \
  "$(date +%Y%m%d%H%M%S)"
```

5. Set those same tags in `terraform.tfvars`.

```hcl
backend_image_tag  = "20260309010101"
frontend_image_tag = "20260309010101"
```

6. Apply the full stack.

```bash
terraform apply
```

7. Open the deployed ALB hostname.

```bash
terraform output -raw alb_dns_name
```

This first URL will look like:

- `http://<alb-name>.us-east-1.elb.amazonaws.com`

Use it for infrastructure validation only.

## Recommended Mapping From The Current `.env`

Use these values as the starting point, replacing local URLs with your real public domain:

- `app_allowed_origins = "https://uzone.example.com"`
- `backend_environment.UZONE_AUTH_PROVIDER = "clerk"`
- `backend_environment.UZONE_PAYMENT_PROVIDERS = "manual"`
- `backend_environment.UZONE_DEFAULT_PAYMENT_PROVIDER = "manual"`
- `backend_environment.UZONE_EMAIL_PROVIDER = "console"`
- `backend_environment.UZONE_EMAIL_FROM = "noreply@your-domain.com"`
- `backend_environment.UZONE_CLERK_JWKS_URL = "https://your-clerk-instance.clerk.accounts.dev/.well-known/jwks.json"`
- `backend_environment.UZONE_CLERK_AUTHORIZED_PARTIES = "https://uzone.example.com"`
- `frontend_environment.GRIDICS_CLERK_ORGANIZATION_SLUG = "gridics-1773003104274716658"` if you want to preserve the current slug-based behavior exactly

Store these outside Terraform state when they are sensitive:

- `frontend_secret_arns.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `frontend_secret_arns.CLERK_SECRET_KEY`
- `frontend_secret_arns.GRIDICS_CLERK_ORGANIZATION_ID` if used
- `backend_secret_arns.UZONE_STRIPE_SECRET_KEY`
- `backend_secret_arns.UZONE_STRIPE_WEBHOOK_SECRET`
- `backend_secret_arns.UZONE_RESEND_API_KEY`

## Important Caveat

The current [uzone/.env](/workspaces/gridics-zoning-cookbook/uzone/.env) contains Clerk keys. Those should be treated as compromised once they live in a repo or shared workspace. Rotate them in Clerk before using this AWS deployment.

## Clerk Caveat For HTTP-First Deploys

An HTTP-first ALB deploy is fine for validating AWS infrastructure, but it is not the final production auth configuration.

Clerk's current docs indicate production setups expect a real domain, and production account portal URLs are based on that domain:

- https://clerk.com/docs/guides/account-portal/getting-started
- https://clerk.com/docs/deployments/deploy-expo

Inference from those docs:

- use the HTTP-only ALB hostname to validate the stack
- do not treat that hostname as the final production Clerk configuration
- switch to a real domain before final production rollout

## Environment Variables

Use plain Terraform maps for non-secret config:

- `backend_environment`
- `frontend_environment`

Use `backend_secret_arns` and `frontend_secret_arns` for secrets already stored in AWS Secrets Manager or SSM Parameter Store.

Common backend variables:

- `UZONE_AUTH_PROVIDER`
- `UZONE_PAYMENT_PROVIDERS`
- `UZONE_DEFAULT_PAYMENT_PROVIDER`
- `UZONE_EMAIL_PROVIDER`
- `UZONE_EMAIL_FROM`
- `UZONE_CLERK_JWKS_URL`
- `UZONE_CLERK_AUTHORIZED_PARTIES`

Common frontend variables:

- `CLERK_SECRET_KEY`

## Notes

- This baseline keeps ECS tasks in public subnets to avoid NAT Gateway cost and complexity. Security groups still limit inbound traffic to the ALB.
- Backend migrations run automatically on container startup.
- Demo seed data is disabled in production containers.
- If you need HTTPS, issue an ACM certificate and set `certificate_arn`.
- If you need a custom domain, attach Route 53 records to the ALB after the initial deploy.
