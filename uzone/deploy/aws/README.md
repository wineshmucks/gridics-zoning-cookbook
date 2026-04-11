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
- `assets`: Amazon S3

The default Terraform path creates its own VPC, subnets, and ALB. For staging in an existing AWS network, set:

- `use_existing_vpc = true`
- `existing_vpc_id`
- `existing_public_subnet_ids`
- `existing_private_subnet_ids`
- optionally `assets_bucket_name` if `gridics-uzones` is already taken in the target account

If you also need to reuse an existing shared ALB, set:

- `use_existing_alb = true`
- `existing_alb_arn`
- at least one of:
  - `existing_alb_http_listener_arn`
  - `existing_alb_https_listener_arn`
- `existing_alb_host_header`
- `public_base_url`

Routing is path-based:

- `/` -> frontend
- `/api/*` -> backend

For a shared ALB, those routes are additionally scoped by the host header you configure in `existing_alb_host_header`, for example `staging.example.com`.

## Prerequisites

- Terraform `>= 1.6`
- AWS CLI v2
- Docker
- an AWS account with permissions for ECS, ECR, IAM, ALB, VPC, CloudWatch, and RDS
- S3 access for jurisdiction-scoped asset uploads and deletes

## Install AWS Tooling

Install the required local tools before running the deploy scripts.

### macOS

```bash
brew install awscli terraform
brew install --cask docker
```

Then start Docker Desktop and verify:

```bash
aws --version
terraform version
docker --version
```

### Ubuntu or Debian

Install Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Install AWS CLI v2:

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

Install Terraform:

```bash
wget -O- https://apt.releases.hashicorp.com/gpg | \
  gpg --dearmor | \
  sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(. /etc/os-release && echo "$VERSION_CODENAME") main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update
sudo apt-get install -y terraform
```

Verify:

```bash
aws --version
terraform version
docker --version
```

### Configure AWS Credentials

If you do not already have credentials configured on the machine:

```bash
aws configure
```

Provide:

- AWS Access Key ID
- AWS Secret Access Key
- default region, for example `us-east-1`
- default output format, for example `json`

Then confirm the active account:

```bash
aws sts get-caller-identity
```

## Deploy Flow

You can do the first deployment without a custom domain:

- leave `certificate_arn = ""`
- use the ALB DNS name over HTTP
- verify ECS, RDS, migrations, and page routing first
- `deploy-from-env.sh` now uses the Terraform `alb_dns_name` automatically for smoke tests unless you explicitly set `SMOKE_TEST_BASE_URL`
- if `UZONE_PUBLIC_BASE_URL` is set in `.env-deploy`, the deploy script will smoke test that public URL before falling back to the ALB hostname

After that, add a real domain or subdomain you control, request an ACM certificate, set `certificate_arn`, and re-apply Terraform to enable HTTPS.

If you use `deploy-from-env.sh`, an existing `certificate_arn` already present in `terraform.tfvars` is now preserved automatically. You only need to set it again when you are intentionally changing certificates. You can also force a specific value with `UZONE_AWS_CERTIFICATE_ARN` or `CERTIFICATE_ARN_OVERRIDE`.

For additional safety, `deploy-from-env.sh` now prints a warning when `DEPLOY_ENVIRONMENT=prod` and `certificate_arn` is empty, so it is harder to accidentally roll out production without HTTPS.

1. Initialize Terraform inputs.

```bash
cd uzone/deploy/aws/terraform
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars`.

Minimum values:

- `aws_region`
- `app_allowed_origins`
- `db_name`
- `db_username`
- `db_password`

For an existing staging VPC, also set:

- `use_existing_vpc = true`
- `existing_vpc_id`
- `existing_public_subnet_ids`
- `existing_private_subnet_ids`
- `assets_bucket_name` if you want a non-default S3 bucket name

For an existing shared ALB, also set:

- `use_existing_alb = true`
- `existing_alb_arn`
- `existing_alb_host_header`
- `public_base_url`
- `existing_alb_http_listener_arn` and/or `existing_alb_https_listener_arn`
- optional listener rule priorities if the defaults conflict:
  - `existing_alb_api_rule_priority`
  - `existing_alb_frontend_rule_priority`

For the current app configuration in [uzone/.env](/workspaces/gridics-zoning-cookbook/uzone/.env), also set:

- `backend_environment.UZONE_AUTH_PROVIDER = "clerk"`
- `backend_environment.UZONE_CLERK_JWKS_URL`
- `backend_environment.UZONE_CLERK_AUTHORIZED_PARTIES`
- `backend_environment.UZONE_ASSETS_PREFIX`
- `frontend_environment.GRIDICS_CLERK_ORGANIZATION_SLUG`
- `frontend_secret_arns.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `frontend_secret_arns.CLERK_SECRET_KEY`

If you rely on a fixed Gridics org id in the UI, also set:

- `frontend_secret_arns.GRIDICS_CLERK_ORGANIZATION_ID`

Do not copy the current `.env` secrets into Terraform files. Store them in AWS Secrets Manager or SSM first.

Jurisdiction assets are now stored in S3 instead of the ECS container filesystem. The deploy creates a bucket named `gridics-uzones` and passes it to the backend as `UZONE_ASSETS_BUCKET`. Objects are stored under jurisdiction-specific prefixes so assets are not mixed between tenants.

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

7. Open the deployed entrypoint.

```bash
terraform output -raw alb_dns_name
```

If Terraform created a dedicated ALB, this first URL will look like:

- `http://<alb-name>.us-east-1.elb.amazonaws.com`

Use it for infrastructure validation only.

If you reused an existing shared ALB, `alb_dns_name` will return that existing ALB hostname. In that mode, the preferred validation path is still your configured `public_base_url`. If DNS is not ready yet, the deploy script can also smoke test the ALB hostname with the matching host header.

If you want the deploy script to smoke test a real custom domain instead of the ALB hostname, override it explicitly:

```bash
SMOKE_TEST_BASE_URL=https://uzones.dev ./deploy-from-env.sh
```

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
- For AWS deploys, use `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` as the database inputs. Terraform builds `UZONE_DATABASE_URL` for ECS automatically from the RDS instance it creates.
- Backend migrations run automatically on container startup.
- Demo seed data is disabled in production containers.
- If you need HTTPS, issue an ACM certificate and set `certificate_arn`.
- If you need a custom domain, attach Route 53 records to the ALB after the initial deploy.
- If you are deploying into an existing staging VPC, supply the VPC and subnet IDs through `use_existing_vpc` / `existing_*_subnet_ids` instead of letting Terraform create a new network.
- If you are deploying through an existing shared ALB, also supply `use_existing_alb`, the ALB ARN, at least one listener ARN, a host header, and `public_base_url`.
