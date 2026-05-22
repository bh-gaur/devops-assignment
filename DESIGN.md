## Multi-cloud reality

- Core orchestration layer: handles scheduling, policy evaluation, dry-run versus delete mode, reporting, and provider plugin loading.
- Cloud provider adapter interface: defines methods like listResources(), fetchTags(), evaluateRetention(), and deleteResource().
- AWS implementation: concrete adapter for EC2, S3, RDS, IAM, etc.
- GCP implementation: concrete adapter for Compute Engine, Cloud Storage, Pub/Sub, BigQuery, etc.
- Azure implementation: concrete adapter for VM, Blob Storage, SQL, Functions, etc.
- Policy engine: independent module for retention rules, whitelist rules, and safety checks.
- Audit/logging module: centralized event publishing and metrics collection.

This separation ensures the core orchestrator remains unchanged when adding new clouds; only a new provider adapter is required.

## Permissions

- --dry-run mode: read-only permissions for listing resources, reading tags/labels, and describing metadata.
- --delete mode: all dry-run permissions plus delete permissions for the specific resource types being cleaned.

Minimal IAM policy for read-only mode:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "s3:ListAllMyBuckets",
        "s3:GetBucketTagging",
        "s3:ListBucket",
        "rds:DescribeDBInstances",
        "rds:ListTagsForResource",
        "iam:ListRoles",
        "iam:GetRole",
        "cloudwatch:ListMetrics",
        "tag:GetResources"
      ],
      "Resource": "*"
    }
  ]
}
```

## Safety net

1. Failure mode: Deleting resources tied to production services because tags were missing or inconsistent.
   - Guardrail: require explicit protect/retain tags on production resources and skip any resource without expected tag metadata.
2. Failure mode: Deleting resources in the wrong account/region due to misconfigured inventory or stale cache.
   - Guardrail: verify account/region context before deletion, require a separate approval step for cross-account or cross-region cleanup, and keep a dry-run audit report before any delete run.

## Observability

- `janitor.resources_scanned`: source = Janitor core, destination = CloudWatch/Stackdriver/Azure Monitor, alert if scan count drops to zero for a production schedule period.
- `janitor.resources_marked_for_deletion`: source = policy engine, destination = CloudWatch/Stackdriver/Azure Monitor, alert if marked-for-deletion count spikes above a configured daily threshold.
- `janitor.resources_deleted`: source = deletion module, destination = CloudWatch/Stackdriver/Azure Monitor, alert if delete count is non-zero outside approved maintenance windows.
- `janitor.delete_failures`: source = deletion module, destination = CloudWatch/Stackdriver/Azure Monitor, alert if failure rate exceeds 5% or if any critical resource delete fails.
- `janitor.dry_run_vs_delete_ratio`: source = core orchestrator, destination = CloudWatch/Stackdriver/Azure Monitor, alert if delete runs happen without a preceding dry-run within the same policy cycle.

## What you did not build

I think for UI with better guidelines for efficiently check and report of orphan resources.