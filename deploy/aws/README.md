# UZone AWS Deployment

This directory contains a pragmatic AWS deployment baseline for the repo root:

- `terraform/`: VPC, ALB, ECS Fargate, ECR, CloudWatch, and RDS Postgres
- `build-and-push.sh`: builds the production images and pushes them to ECR
- `tail-ecs-logs.sh`: tails staging or prod frontend/backend CloudWatch logs
- [LOGGING_RUNBOOK.md](./LOGGING_RUNBOOK.md): how to tail staging/prod ECS logs and inspect service events

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

The ALB ARN and listener ARN(s) must belong to the same AWS account and region as the credentials you use for Terraform. If they come from another account, AWS will reject the lookup with a `DescribeLoadBalancers` validation error.

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

The easiest path for both staging and production is to use `deploy-from-env.sh` with the matching environment file:

```bash
# staging
ENV_FILE=.env-deploy.staging DEPLOY_ENVIRONMENT=staging ./deploy/aws/deploy-from-env.sh

# production
ENV_FILE=.env-deploy.prod DEPLOY_ENVIRONMENT=prod ./deploy/aws/deploy-from-env.sh
```

Keep `.env-deploy` as the shared baseline and create `.env-deploy.prod` locally when you need a production deploy file. The production file should stay untracked.

The script will:

- source the selected `.env-deploy.*` file
- generate `terraform.tfvars`
- build and push the application images
- apply Terraform
- run smoke tests against the deployed environment
- select a Terraform workspace scoped to the current AWS account, so state from another account is not reused accidentally

If `TERRAFORM_WORKSPACE` is set in your shell, `deploy-from-env.sh` now refuses to run unless it exactly matches the derived workspace for the selected environment and AWS account. In normal use, leave it unset and let the script choose the workspace for you.
If ECS services were deleted and are showing up as `INACTIVE`, the deploy script now skips importing them and lets Terraform recreate them instead of failing on a stale import.

Make sure the `AWS_PROFILE` value inside the selected env file exists in your local AWS config. The deploy scripts will use the profile you provide, and if you leave it unset they will fall back to your default AWS CLI profile.
Set `UZONE_TAG_ENV` and `UZONE_TAG_NAME` in `.env-deploy.staging` and your local `.env-deploy.prod` if you want provider-level default tags applied automatically to every AWS resource. In this setup, `Env` is `dev` for staging and `prod` for production, and `Name` is `gridics-zoning-suite`.
Set `UZONE_DB_ENGINE_VERSION` if you need to pin the RDS Postgres version explicitly. The current deploy files use `16.13`.
Set `AGENTIC_PUBLIC_BASE_URL` and `LETTERS_PUBLIC_BASE_URL` in `.env-deploy.staging` and your local `.env-deploy.prod`
to define the canonical public URLs for the assistant and letters experiences. `deploy-from-env.sh`
mirrors those into `NEXT_PUBLIC_AGENTIC_PUBLIC_BASE_URL` and `NEXT_PUBLIC_LETTERS_PUBLIC_BASE_URL`
for the frontend build/runtime.

The deploy flow also includes a title smoke test for the agentic home page and the jurisdiction picker so the browser tab never leaks a real jurisdiction name there. If you want to run it manually against a deployed environment, use:

```bash
./deploy/aws/verify-select-jurisdiction-title.sh https://st1-agentic.gridics.com
```

You can still do the first deployment without a custom domain:

- leave `certificate_arn = ""`
- use the ALB DNS name over HTTP
- verify ECS, RDS, migrations, and page routing first
- `deploy-from-env.sh` now uses the Terraform `alb_dns_name` automatically for smoke tests unless you explicitly set `SMOKE_TEST_BASE_URL`
- Set `SKIP_SMOKE_TESTS=1` when you do not want the deploy to wait for post-apply health checks, such as during an instance swap or rolling rollout
- if `AGENTIC_PUBLIC_BASE_URL` is set in `.env-deploy.staging` or your local `.env-deploy.prod`, the deploy script will smoke test that assistant public URL before falling back to the ALB hostname

After that, add a real domain or subdomain you control, request an ACM certificate, set `certificate_arn`, and re-apply Terraform to enable HTTPS.

If you use `deploy-from-env.sh`, an existing `certificate_arn` already present in `terraform.tfvars` is now preserved automatically. You only need to set it again when you are intentionally changing certificates. You can also force a specific value with `UZONE_AWS_CERTIFICATE_ARN` or `CERTIFICATE_ARN_OVERRIDE`.

For additional safety, `deploy-from-env.sh` now prints a warning when `DEPLOY_ENVIRONMENT=prod` and `certificate_arn` is empty, so it is harder to accidentally roll out production without HTTPS.

1. Initialize Terraform inputs.

```bash
cd deploy/aws/terraform
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

For the current app configuration in [.env](/workspaces/gridics-zoning-cookbook/.env), also set:

- `backend_environment.UZONE_AUTH_PROVIDER = "clerk"`
- `backend_environment.UZONE_CLERK_JWKS_URL`
- `backend_environment.UZONE_CLERK_AUTHORIZED_PARTIES`
- `backend_environment.UZONE_ASSETS_PREFIX`
- `frontend_environment.GRIDICS_CLERK_ORGANIZATION_SLUG`
- `frontend_environment.AGENTIC_PUBLIC_BASE_URL`
- `frontend_environment.LETTERS_PUBLIC_BASE_URL`
- `frontend_environment.NEXT_PUBLIC_AGENTIC_PUBLIC_BASE_URL`
- `frontend_environment.NEXT_PUBLIC_LETTERS_PUBLIC_BASE_URL`
- `frontend_environment.NEXT_PUBLIC_CLERK_JWKS_URL`
- `frontend_secret_arns.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `frontend_secret_arns.CLERK_SECRET_KEY`

If you rely on a fixed Gridics org id in the UI, also set:

- `frontend_secret_arns.GRIDICS_CLERK_ORGANIZATION_ID`

Do not copy the current `.env` secrets into Terraform files. Store them in AWS Secrets Manager or SSM first.

Jurisdiction assets are now stored in S3 instead of the ECS container filesystem. The deploy creates a bucket named `gridics-uzones` and passes it to the backend as `UZONE_ASSETS_BUCKET`. Objects are stored under jurisdiction-specific prefixes so assets are not mixed between tenants.

Example bootstrap commands are in:

- [secrets-bootstrap.example.sh](/workspaces/gridics-zoning-cookbook/deploy/aws/secrets-bootstrap.example.sh)

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
ENV_FILE=.env-deploy.staging SMOKE_TEST_BASE_URL=https://uzones.dev ./deploy/aws/deploy-from-env.sh
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

The current [.env](/workspaces/gridics-zoning-cookbook/.env) contains Clerk keys. Those should be treated as compromised once they live in a repo or shared workspace. Rotate them in Clerk before using this AWS deployment.

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
- `tag_env`
- `tag_name`

Use `backend_secret_arns` and `frontend_secret_arns` for secrets already stored in AWS Secrets Manager or SSM Parameter Store.

Common backend variables:

- `UZONE_AUTH_PROVIDER`
- `UZONE_PAYMENT_PROVIDERS`
- `UZONE_DEFAULT_PAYMENT_PROVIDER`
- `UZONE_EMAIL_PROVIDER`
- `UZONE_EMAIL_FROM`
- `UZONE_CLERK_JWKS_URL`
- `UZONE_CLERK_AUTHORIZED_PARTIES`
- `UZONE_DB_ENGINE_VERSION`
- `AGENTIC_PUBLIC_BASE_URL`
- `LETTERS_PUBLIC_BASE_URL`

Common frontend variables:

- `CLERK_SECRET_KEY`
- `NEXT_PUBLIC_AGENTIC_PUBLIC_BASE_URL`
- `NEXT_PUBLIC_LETTERS_PUBLIC_BASE_URL`
- `NEXT_PUBLIC_CLERK_JWKS_URL`

## Notes

- This baseline keeps ECS tasks in public subnets to avoid NAT Gateway cost and complexity. Security groups still limit inbound traffic to the ALB.
- For AWS deploys, use `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` as the database inputs. Terraform builds `UZONE_DATABASE_URL` for ECS automatically from the RDS instance it creates.
- Backend migrations run automatically on container startup.
- Demo seed data is disabled in production containers.
- If you need HTTPS, issue an ACM certificate and set `certificate_arn`.
- If you need a custom domain, attach Route 53 records to the ALB after the initial deploy.
- If you are deploying into an existing staging VPC, supply the VPC and subnet IDs through `use_existing_vpc` / `existing_*_subnet_ids` instead of letting Terraform create a new network.
- If you are deploying through an existing shared ALB, also supply `use_existing_alb`, the ALB ARN, at least one listener ARN, a host header, and `public_base_url`.
- The deploy is fastest when you leave Terraform state imports alone after the first successful run and let Docker use its layer cache.
- Set `SKIP_BOOTSTRAP_IMPORT=1` once the stack is already imported into Terraform state.
- Set `FORCE_NO_CACHE=1` only when you want a clean Docker rebuild.

## Troubleshooting

When a deploy succeeds but the site still fails in the browser, check the live ECS service events and CloudWatch logs first.

The Terraform outputs give you the deployed cluster and service names:

```bash
terraform -chdir=deploy/aws/terraform output -raw ecs_cluster_name
terraform -chdir=deploy/aws/terraform output -raw frontend_service_name
terraform -chdir=deploy/aws/terraform output -raw backend_service_name
```

Useful AWS CLI commands:

```bash
# Service health and recent ECS events
aws ecs describe-services \
  --cluster "$(terraform -chdir=deploy/aws/terraform output -raw ecs_cluster_name)" \
  --services \
    "$(terraform -chdir=deploy/aws/terraform output -raw frontend_service_name)" \
    "$(terraform -chdir=deploy/aws/terraform output -raw backend_service_name)" \
  --profile staging \
  --region us-east-1 \
  --query 'services[].{name:serviceName,running:runningCount,pending:pendingCount,events:events[0:5].message}' \
  --output table

# Tail frontend logs
aws logs tail \
  "/ecs/$(terraform -chdir=deploy/aws/terraform output -raw frontend_service_name)" \
  --profile staging \
  --region us-east-1 \
  --since 30m \
  --follow

# Tail backend logs
aws logs tail \
  "/ecs/$(terraform -chdir=deploy/aws/terraform output -raw backend_service_name)" \
  --profile staging \
  --region us-east-1 \
  --since 30m \
  --follow
```

If the frontend only fails in the browser and the ECS logs stay clean, that usually points to a hydration or runtime error in Next.js rather than an API or container startup failure. In that case, capture the browser console stack trace before changing infrastructure.

The frontend also reports browser `error` and `unhandledrejection` events to `/api/client-error`, so those failures should show up in the frontend CloudWatch log stream once the app is running.

If you need to reproduce the browser issue directly from this workspace, use a headless browser against the live URL and record console output:

```bash
# On Ubuntu 24.04, install the system libraries Chromium needs first.
# The Playwright helper is the easiest route if you have sudo:
sudo npx playwright install-deps chromium

# If you prefer the explicit apt packages on Ubuntu 24.04, this is the minimum
# set that fixed the missing-shared-library error in this workspace:
sudo apt-get update
sudo apt-get install -y libnspr4 libnss3 libasound2t64

# Install Playwright browsers once if needed
npx playwright install chromium

# Run a one-off repro that captures console errors and the rendered body
NODE_PATH="$(npm root -g 2>/dev/null):${NODE_PATH:-}" \
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 \
node <<'NODE'
const { chromium } = require('playwright')

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
  const page = await browser.newPage()
  const messages = []

  page.on('console', (msg) => messages.push({ type: msg.type(), text: msg.text() }))
  page.on('pageerror', (err) => messages.push({ type: 'pageerror', text: String(err) }))
  page.on('requestfailed', (req) =>
    messages.push({
      type: 'requestfailed',
      text: `${req.method()} ${req.url()} ${req.failure()?.errorText || ''}`.trim(),
    }),
  )

  const response = await page.goto('https://st1-agentic.gridics.com/', {
    waitUntil: 'networkidle',
    timeout: 120000,
  })

  console.log(JSON.stringify({
    status: response && response.status(),
    url: page.url(),
    title: await page.title(),
    text: await page.locator('body').innerText().catch(() => ''),
    messages,
  }, null, 2))

  await browser.close()
})()
NODE
```

If Playwright cannot run on the host because browser libraries are missing, fall back to the CloudWatch client-error log path above and/or capture the browser console stack trace from a local machine that can launch Chromium.
