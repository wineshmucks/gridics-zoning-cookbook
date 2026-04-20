# AWS Logs Runbook

Use this when the app errors in staging or production and you need the live ECS logs.

## What to look at

The frontend and backend containers write to these CloudWatch log groups:

- `frontend`: `/ecs/<project>-<environment>-frontend`
- `backend`: `/ecs/<project>-<environment>-backend`

For this repo the generated names are usually:

- staging frontend: `/ecs/gridics-uzone-staging-frontend`
- staging backend: `/ecs/gridics-uzone-staging-backend`
- prod frontend: `/ecs/gridics-uzone-prod-frontend`
- prod backend: `/ecs/gridics-uzone-prod-backend`

The deploy script also imports those names into Terraform state when it boots existing resources.

## Tail logs

Use the AWS profile for the target environment, then tail the group directly:

```bash
AWS_PROFILE=staging aws logs tail /ecs/gridics-uzone-staging-frontend --follow --since 30m --region us-east-1
AWS_PROFILE=staging aws logs tail /ecs/gridics-uzone-staging-backend --follow --since 30m --region us-east-1
```

For production:

```bash
AWS_PROFILE=prod aws logs tail /ecs/gridics-uzone-prod-frontend --follow --since 30m --region us-east-1
AWS_PROFILE=prod aws logs tail /ecs/gridics-uzone-prod-backend --follow --since 30m --region us-east-1
```

If you want a one-command helper from the repo root, use:

```bash
./deploy/aws/tail-ecs-logs.sh staging
./deploy/aws/tail-ecs-logs.sh prod backend
./deploy/aws/tail-ecs-logs.sh staging frontend
```

If you do not know the active environment name, derive it from the Terraform workspace or the deploy command you are using. The deploy script sets the workspace to `<DEPLOY_ENVIRONMENT>-<ACCOUNT_ID>`.

## What to inspect first

1. Frontend logs for server-rendered page crashes, build-time env problems, and browser client-error reports.
2. Backend logs for API exceptions, agent runs, ECS task startup failures, and deployment health checks.
3. ECS service events if the tasks are still rolling or repeatedly restarting.

## Useful commands

Show ECS service status:

```bash
AWS_PROFILE=staging aws ecs describe-services \
  --cluster gridics-uzone-staging-cluster \
  --services gridics-uzone-staging-frontend gridics-uzone-staging-backend \
  --region us-east-1
```

Show recent service events:

```bash
AWS_PROFILE=staging aws ecs describe-services \
  --cluster gridics-uzone-staging-cluster \
  --services gridics-uzone-staging-frontend gridics-uzone-staging-backend \
  --region us-east-1 \
  --query 'services[].events[0:10].[createdAt,message]' \
  --output table
```

If the deploy is using an existing shared ALB, the fastest way to identify whether routing or tasks are failing is:

1. Check the ECS service events.
2. Tail the backend log group.
3. Tail the frontend log group.
4. Check the ALB target health only after the task logs look healthy.
