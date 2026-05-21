# Janitor DESIGN

This short design describes how to make the Janitor multi-cloud extensible, the minimal IAM policy for read-only (dry-run) operation, safety-net guardrails for deletion, observability metrics for FinOps, and a short note on intentionally omitted features.

**Multi-Cloud Architecture (how to add GCP/Azure without rewriting core)**

- Overview: keep a small, cloud-agnostic core that implements the orchestration, rules evaluation, dry-run simulation, audit trail, and pluggable provider drivers that contain all cloud-specific API calls and IAM expectations.

- Primary module boundaries (responsibilities):
  - Core Orchestrator: run schedules, take CLI args (`--dry-run` / `--delete`), coordinate scan -> evaluate -> action workflows, enforce global guardrails, emit events/metrics. No cloud APIs here.
  - Inventory & Tag Resolver (cloud-agnostic): normalises provider resource metadata into a canonical resource model (id, type, name, account/project, region, tags, lastSeen, dependencies). Accepts provider-specific adapters to populate model.
  - Policy Engine: declarative rules (age, tag patterns, last-used metrics, cost thresholds) expressed in a provider-agnostic rule language. Returns `Keep | Quarantine | DeleteCandidate` decisions with rationales and evidence.
  - Provider Adapter Interface (plugin contract): typed interface the core calls for each provider: `list_resources(filters)`, `get_tags(resource)`, `snapshot(resource)`, `simulate_delete(resource)`, `delete(resource)`, `describe_usage(resource)`. Each cloud (AWS, GCP, Azure) implements this interface.
  - Provider Implementations (aws/, gcp/, azure/): concrete drivers that translate the adapter calls into API calls, handle paging, rate-limit backoff, and map provider error codes to canonical error types.
  - Safety & Execution Layer: implements pre-checks, approval gates, backup/snapshot orchestration, staged deletion (quarantine window), and a “kill-switch” that halts deletions across providers.
  - Audit & State Store: append-only audit log (S3/GCS/blob) and a small local state DB (sqlite/postgres) recording runs, candidates, and tombstones for reconciliation and forensics.
  - Observability + Notification: metrics exporter (Prometheus and CloudWatch support) and event publisher (Slack / PagerDuty / SIEM).

- How adding GCP works (no core rewrite): implement a `gcp.Adapter` that conforms to the Provider Adapter Interface and a small IAM role for the GCP service account. Core orchestrator calls the adapter via the same API used for AWS. Provider-specific differences (e.g. resource names, label conventions) are handled by the Inventory normaliser.

- Packaging/runtimes: keep adapters as small modules under `janitor/providers/*`. Packaging them as independent pip packages or optional imports keeps the core lightweight and allows per-cloud CI checks.

**Permissions: dry-run vs delete**

- Principle: `--dry-run` must be strictly read-only and able to access the metadata required for decisions (list, describe, read tags, read metrics). `--delete` requires fine-grained write/delete permission per resource type and optionally snapshot/backups permissions.

- Examples (delete-mode extra perms):
  - EC2: `TerminateInstances`, `DeleteVolume`, `DeregisterImage`.
  - S3: `DeleteObject`, `DeleteBucket` (and optionally `PutObject` to move to quarantine bucket).
  - RDS: `DeleteDBInstance`, `DeleteDBSnapshot` (or `CreateDBSnapshot` to back up first).
  - IAM/Organizations: typically *no* deletion of IAM principals — treat IAM and org-level resources as protected unless explicitly allowed.

- Minimal AWS read-only (dry-run) IAM policy (JSON). This policy contains only listing/describe actions and the tagging API the Janitor needs to evaluate candidates:

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
        "ec2:DescribeImages",
        "ec2:DescribeTags",
        "ec2:DescribeVpcEndpoints",
        "ec2:DescribeNetworkInterfaces",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:GetBucketTagging",
        "rds:DescribeDBInstances",
        "rds:DescribeDBSnapshots",
        "lambda:ListFunctions",
        "lambda:GetFunctionConfiguration",
        "eks:ListClusters",
        "eks:DescribeCluster",
        "elasticloadbalancing:DescribeLoadBalancers",
        "autoscaling:DescribeAutoScalingGroups",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "resourcegroupstaggingapi:GetResources",
        "tag:GetResources",
        "organizations:DescribeAccount",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

Notes about the policy above: include only the calls required by your rules (e.g., if you do not evaluate EKS clusters, remove `eks:*`). For cross-account/organization setups the Janitor should run in the account where inventory is owned or assume per-account roles with these read-only permissions.

**Safety net — two specific dangerous failure modes and guardrails**

1) Mistagging / Tag-value mis-evaluation leading to production deletion

  - Failure mode: A deployment pipeline accidentally removes or replaces a tag (for example `env:prod` → `env:production`) and the Janitor's rule `delete-if-tag-missing` will mark previously protected production resources for deletion.
  - Guardrails:
    - Protected whitelist: explicit `protected_accounts` and `protected_resource_types` configuration; anything in those lists is never auto-deleted.
    - Tag allowlist and canonicalisation: rules must match canonical tag keys and values (canonicaliser converts `production` → `prod` only for evaluation, but canonical tag presence is required). Do not rely on absence-of-tag alone to delete — prefer an explicit `janitor:eligible=true` tag to permit deletion.
    - Multi-check policy: require at least two independent checks before deletion (tag-based AND idle-metric-based AND age threshold). Example: a resource must be both untagged and have 0 inbound traffic for 30 days.
    - Human-in-the-loop escalation for high-impact resources: any candidate above a cost or criticality threshold is placed into a quarantine pipeline that requires an approval from two on-call engineers before final deletion.

2) Deleting resources with transient dependencies (race with deployments)

  - Failure mode: The Janitor identifies and deletes an AMI or snapshot that is still referenced by a rolling deployment or an autoscaling group, causing in-flight instances to fail boot and an outage.
  - Guardrails:
    - Dependency graph check: before delete, query infrastructure (ASG, CloudFormation stacks, deployment records) for references to the resource; refuse deletion if any reference exists.
    - Last-used heuristic and metric-check: require `lastSeen` > X days and zero usage metric (e.g., `NetworkIn==0` and `CPUUtilization==0`) for a configurable cooldown period.
    - Pre-delete snapshot/backups for unsafe resource classes: take an automated snapshot (or copy to quarantine bucket) and verify snapshot creation success before deleting the primary resource.
    - Staged deletion: mark resource as `Quarantine` for N days and emit audit event; only after the quarantine window expires and there were no reversal events do we perform final delete.

**Observability — metrics, sources, and alert thresholds**

Publish metrics to both a centralized metrics backend (Prometheus + Grafana for FinOps dashboards) and native cloud metrics (CloudWatch / GCP Monitoring) so FinOps can monitor both Janitor health and business impact.

- `janitor.resources_scanned_total` (source: Janitor inventory step, exported to Prometheus and a CloudWatch custom metric)
  - Meaning: count of resources evaluated in a run.
  - Alert threshold: anomaly if a run scans less than 10% of expected inventory for two consecutive runs (suggests broken discovery). Fire a `warning` if below 10% for 2 runs.

- `janitor.delete_candidates_total` (source: policy engine output, exported to Prometheus & CloudWatch)
  - Meaning: number of resources marked as `DeleteCandidate` during a run.
  - Alert threshold: if `delete_candidates_total / resources_scanned_total > 0.10` (10%) for a single run AND the total candidates > 50, create a `pagerduty` incident for manual review (possible mass-mistagging or misconfiguration).

- `janitor.deletions_attempted_total` and `janitor.deletions_failed_total` (source: execution layer; both exported)
  - Meaning: attempted deletes and failed deletes.
  - Alert thresholds: if `deletions_failed_total > 5` in a 1-hour window, create a `warning` alert; if `deletions_failed_total > 20` or `deletions_failed_total / deletions_attempted_total > 0.25` then escalate to `pagerduty`.

- `janitor.unintended_deletions_total` (source: audit + reconciliation job that compares tombstones vs service discovery)
  - Meaning: count of deletions that later appear in service manifests or are referenced by active resources (a match indicates a probable unintended deletion).
  - Alert threshold: any `unintended_deletions_total > 0` should be a Sev1 incident; route to on-call and FinOps immediately.

- Publishing targets & retention: push Prometheus metrics via a Pushgateway or exporter; emit CloudWatch custom metrics using `PutMetricData` (helps correlate with other AWS alarms). Send high-severity alerts to PagerDuty and summary digests to FinOps Slack channel.

**What I did not build (scoping)**

I did not implement a UI for manual approvals, a full multi-account orchestration flow for automatic cross-account role provisioning, nor did I include an automated remediation playbook for recovering deleted resources. I left these out because the core goals were to define an extensible multi-cloud architecture, precise IAM boundaries, concrete guardrails, and observable metrics — all of which form the safe foundation for later UX, automation for role setup, and automated recovery playbooks.

---

If you'd like, I can also:
- generate a companion `janitor/providers/gcp/README.md` sketching the minimal GCP IAM roles and API calls required, or
- create a small OpenAPI-like interface description for the Provider Adapter Interface.
