from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta

import boto3
from botocore.config import Config


REQUIRED_TAGS = {"Project", "Environment", "Owner"}
DEFAULT_STOPPED_DAYS = 14


# =========================================================
# Cost Heuristics (example values)
# =========================================================

EBS_GP2_MONTHLY_COST = 8.00
EIP_MONTHLY_COST = 3.60
STOPPED_INSTANCE_MONTHLY_COST = 12.00


# =========================================================
# Report Schema Model
# =========================================================

@dataclass
class Finding:
    resource_id: str
    resource_type: str
    reason: str
    age_days: int
    estimated_monthly_cost_usd: float
    tags: dict
    suggested_action: str
    safe_to_auto_delete: bool

    # Optional extensible fields
    action_taken: str | None = None


# =========================================================
# Helpers
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--delete", action="store_true")

    parser.add_argument(
        "--stopped-days",
        type=int,
        default=DEFAULT_STOPPED_DAYS
    )

    parser.add_argument(
        "--region",
        default="us-east-1"
    )

    parser.add_argument(
        "--endpoint-url",
        default=None
    )

    return parser.parse_args()


def make_ec2_client(region, endpoint_url):
    return boto3.client(
        "ec2",
        region_name=region,
        endpoint_url=endpoint_url,
        config=Config(retries={"max_attempts": 3})
    )


def tags_to_dict(tags):
    if not tags:
        return {}
    return {t["Key"]: t["Value"] for t in tags}


def required_tag_projection(tags):
    """
    Required schema expects missing tags to exist with null values.
    """
    projected = {}

    for tag in REQUIRED_TAGS:
        projected[tag] = tags.get(tag)

    return projected


def is_protected(tags):
    return tags.get("Protected", "").lower() == "true"


def now_utc():
    return datetime.now(timezone.utc)


def calculate_age_days(dt):
    return (now_utc() - dt).days


def get_account_id(sts_client):
    return sts_client.get_caller_identity()["Account"]


# =========================================================
# Detection Functions
# =========================================================

def detect_unattached_volumes(ec2, delete_mode):
    findings = []

    response = ec2.describe_volumes(
        Filters=[
            {
                "Name": "status",
                "Values": ["available"]
            }
        ]
    )

    for volume in response["Volumes"]:
        volume_id = volume["VolumeId"]
        tags = tags_to_dict(volume.get("Tags"))
        create_time = volume["CreateTime"]

        finding = Finding(
            resource_id=volume_id,
            resource_type="ebs_volume",
            reason="unattached",
            age_days=calculate_age_days(create_time),
            estimated_monthly_cost_usd=EBS_GP2_MONTHLY_COST,
            tags=required_tag_projection(tags),
            suggested_action="delete",
            safe_to_auto_delete=not is_protected(tags)
        )

        if delete_mode and finding.safe_to_auto_delete:
            try:
                ec2.delete_volume(VolumeId=volume_id)
                finding.action_taken = "deleted"
            except Exception as e:
                finding.action_taken = f"delete_failed: {e}"

        findings.append(finding)

    return findings


def detect_old_stopped_instances(ec2, stopped_days, delete_mode):
    findings = []

    response = ec2.describe_instances(
        Filters=[
            {
                "Name": "instance-state-name",
                "Values": ["stopped"]
            }
        ]
    )

    cutoff = now_utc() - timedelta(days=stopped_days)

    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:

            launch_time = instance["LaunchTime"]

            if launch_time > cutoff:
                continue

            tags = tags_to_dict(instance.get("Tags"))

            finding = Finding(
                resource_id=instance["InstanceId"],
                resource_type="ec2_instance",
                reason=f"stopped_gt_{stopped_days}_days",
                age_days=calculate_age_days(launch_time),
                estimated_monthly_cost_usd=STOPPED_INSTANCE_MONTHLY_COST,
                tags=required_tag_projection(tags),
                suggested_action="terminate",
                safe_to_auto_delete=not is_protected(tags)
            )

            if delete_mode and finding.safe_to_auto_delete:
                try:
                    ec2.terminate_instances(
                        InstanceIds=[instance["InstanceId"]]
                    )
                    finding.action_taken = "terminated"
                except Exception as e:
                    finding.action_taken = f"terminate_failed: {e}"

            findings.append(finding)

    return findings


def detect_unassociated_eips(ec2, delete_mode):
    findings = []

    response = ec2.describe_addresses()

    for address in response["Addresses"]:

        if "AssociationId" in address:
            continue

        tags = tags_to_dict(address.get("Tags"))

        resource_id = address.get(
            "AllocationId",
            address.get("PublicIp")
        )

        age_days = 0

        finding = Finding(
            resource_id=resource_id,
            resource_type="elastic_ip",
            reason="unassociated",
            age_days=age_days,
            estimated_monthly_cost_usd=EIP_MONTHLY_COST,
            tags=required_tag_projection(tags),
            suggested_action="release",
            safe_to_auto_delete=not is_protected(tags)
        )

        if delete_mode and finding.safe_to_auto_delete:
            try:

                if "AllocationId" in address:
                    ec2.release_address(
                        AllocationId=address["AllocationId"]
                    )
                else:
                    ec2.release_address(
                        PublicIp=address["PublicIp"]
                    )

                finding.action_taken = "released"

            except Exception as e:
                finding.action_taken = f"release_failed: {e}"

        findings.append(finding)

    return findings


def detect_missing_tags(ec2):
    findings = []

    # -------------------------
    # Volumes
    # -------------------------
    volumes = ec2.describe_volumes()["Volumes"]

    for volume in volumes:
        tags = tags_to_dict(volume.get("Tags"))

        missing = REQUIRED_TAGS - set(tags.keys())

        if missing:
            findings.append(
                Finding(
                    resource_id=volume["VolumeId"],
                    resource_type="ebs_volume",
                    reason="missing_required_tags",
                    age_days=calculate_age_days(
                        volume["CreateTime"]
                    ),
                    estimated_monthly_cost_usd=0.0,
                    tags=required_tag_projection(tags),
                    suggested_action="tag_resource",
                    safe_to_auto_delete=False
                )
            )

    # -------------------------
    # Instances
    # -------------------------
    reservations = ec2.describe_instances()["Reservations"]

    for reservation in reservations:
        for instance in reservation["Instances"]:

            tags = tags_to_dict(instance.get("Tags"))

            missing = REQUIRED_TAGS - set(tags.keys())

            if missing:
                findings.append(
                    Finding(
                        resource_id=instance["InstanceId"],
                        resource_type="ec2_instance",
                        reason="missing_required_tags",
                        age_days=calculate_age_days(
                            instance["LaunchTime"]
                        ),
                        estimated_monthly_cost_usd=0.0,
                        tags=required_tag_projection(tags),
                        suggested_action="tag_resource",
                        safe_to_auto_delete=False
                    )
                )

    return findings


# =========================================================
# Reporting
# =========================================================

def write_report(
    findings,
    account_id,
    region
):
    total_waste = round(
        sum(f.estimated_monthly_cost_usd for f in findings),
        2
    )

    report = {
        "scan_timestamp": now_utc().strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "account_id": account_id,
        "region": region,
        "summary": {
            "total_orphans": len(findings),
            "estimated_monthly_waste_usd": total_waste
        },
        "findings": [
            asdict(f) for f in findings
        ]
    }

    with open("report.json", "w") as f:
        json.dump(report, f, indent=2)


def write_markdown_summary(findings):
    lines = [
        "# NimbusKart Waste Report",
        "",
        f"Generated: {now_utc().isoformat()}",
        "",
        f"Total Findings: {len(findings)}",
        ""
    ]

    for finding in findings:
        lines.extend([
            f"## {finding.resource_id}",
            "",
            f"- Type: `{finding.resource_type}`",
            f"- Reason: `{finding.reason}`",
            f"- Estimated Monthly Waste: `${finding.estimated_monthly_cost_usd}`",
            f"- Suggested Action: `{finding.suggested_action}`",
            f"- Safe To Auto Delete: `{finding.safe_to_auto_delete}`",
            ""
        ])

    with open("summary.md", "w") as f:
        f.write("\n".join(lines))


# =========================================================
# Main
# =========================================================

def main():

    args = parse_args()

    delete_mode = args.delete

    try:

        ec2 = make_ec2_client(
            args.region,
            args.endpoint_url
        )

        sts = boto3.client(
            "sts",
            region_name=args.region,
            endpoint_url=args.endpoint_url
        )

        account_id = get_account_id(sts)

        findings = []

        findings.extend(
            detect_unattached_volumes(
                ec2,
                delete_mode
            )
        )

        findings.extend(
            detect_old_stopped_instances(
                ec2,
                args.stopped_days,
                delete_mode
            )
        )

        findings.extend(
            detect_unassociated_eips(
                ec2,
                delete_mode
            )
        )

        findings.extend(
            detect_missing_tags(ec2)
        )

        write_report(
            findings,
            account_id,
            args.region
        )

        write_markdown_summary(findings)

        print(
            f"Scan complete. Findings: {len(findings)}"
        )

        # Required CI behavior
        if findings and not delete_mode:
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(f"Execution failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()