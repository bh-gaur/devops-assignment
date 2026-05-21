"""
AWS cost constants used for Janitor dry-run estimates.

Sources:
- EBS gp3 pricing: $0.08 per GB-month in us-east-1.
  https://aws.amazon.com/ebs/pricing/
- Elastic IP pricing for unused addresses: $0.005 per hour = $3.60 per 30-day month.
  https://aws.amazon.com/ec2/pricing/on-demand/#Elastic_IP_Addresses
- Stopped EC2 instance cost estimate: $12.00 per month as a simple heuristic.
  This is an illustrative default and not a specific AWS list price.
"""

EBS_GP3_GB_MONTHLY_COST = 0.08
EIP_UNUSED_HOURLY_COST = 0.005
EIP_MONTHLY_COST = round(EIP_UNUSED_HOURLY_COST * 24 * 30, 2)
STOPPED_INSTANCE_MONTHLY_COST = 12.00
