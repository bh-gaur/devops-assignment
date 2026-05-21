# NimbusKart Staging Infrastructure (LocalStack Proof of Concept)

This folder contains the reusable Terraform blueprints provisioning the basic cloud framework for NimbusKart's staging layer.

## Execution Sequence

```bash
# 1. Format verification
terraform fmt -check -recursive

# 2. Schema compliance syntax verification
terraform init
terraform validate

# 3. Execution preview against targeted LocalStack endpoints
terraform plan

# 4. Roll out infrastructure block mappings
terraform apply -auto-approve
```

## Decisions & deviations

* **Vulnerable Port 22 Exposition (`0.0.0.0/0`):** Exposing administrative interfaces to any global point bypasses primary vector security perimeters; it should strictly point to a secure engineering proxy network block or explicit workspace CIDR.
* **Public Placement of Web Compute Compute Layers:** Provisioning public IPs straight onto business application servers breaks standard multi-tier isolation architectures; compute infrastructure should reside behind a public application load balancer (ALB) deep inside hidden private subnets.
* **Redundant Non-Current S3 Lifecycle Strategy:** Purging backdated elements after 30 days is a great security mechanism, but standard configurations should transition them into cheaper Glacier storage classes before final termination to protect data retention pipelines.
* **Isolated Orphan EBS Storage Target Allocation:** Provisioning decoupled network blocks consumes budget overhead without functional utility; unused structures must be monitored and eliminated via continuous platform policies like a cost janitor.
* **Hardcoded Non-Resilient Volume Target Location Mapping:** Locking the isolated storage footprint strictly inside the default AZ (`us-east-1a`) breaks resilience strategies; cross-regional reference flags must explicitly fetch regional indices directly from dynamic subnets inside the topology module.

