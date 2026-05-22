# NimbusKart Staging Infrastructure (LocalStack Proof of Concept)

This folder conatins the resuable terraform code and modules for provisioning the basic cloud framework on localstack.

## How to run locally
# Note: ensure localstack is running and credentials are there in env
``` bash
    
    # 1. Clone Repo
    git clone git@github.com:bh-gaur/devops-assignment.git

    # 2. Move to terraform folder
    cd terraform

    # Set fake credentials (LocalStack doesn't validate them)
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
    export AWS_DEFAULT_REGION=us-east-1

    # 3. Format verification
    terraform fmt -check -recursive

    # 4. Schema compliance syntax verification
    terraform init
    terraform validate

    # 5. Execution preview against targeted LocalStack endpoints
    terraform plan

    # 6. Roll out infrastructure block mappings
    terraform apply -auto-approve

    # 7. Install python packages
    cd ../janitor && pip install -r requirements.txt

    # 8. Run janitor.py
    python3 janitor.py --dry-run --endpoint-url http://localhost:4566
```

## Trade-offs
Try to add more resources check in janitor.py for resource and cost optimzation.
Make the terraform module to resusability.
 
## Decisions & deviations

* **Port 22 open to 0.0.0.0/0:** Exposes SSH to the entire internet. Restrict ssh_ingress_cidr to a bastion IP, VPN CIDR, or office range before promoting beyond staging.

* **Web instances in public subnets:** Direct public IPs on application servers skip standard defence-in-depth. Production should place compute in private subnets behind an ALB, with no public IP assigned.

* **S3 noncurrent-version expiry only:** Deleting old versions after 30 days is correct, but a transition rule to Glacier Instant Retrieval before expiry would cut storage costs while preserving the retention window.

* **Orphan EBS volume is intentional here:** Created as a known signal for the Part B waste scanner. In any real environment an unattached volume is pure spend — flag and remove via the scanner's --delete mode or a cost-governance policy.


## AI usage disclosure
* Chatgpt for janitor script logic implementation and theory part in .md files
* Claude for fix terraform code error