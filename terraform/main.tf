provider "aws" {
  region = var.region

  endpoints {
    ec2 = "http://localhost:4566"      # LocalStack endpoint for EC2
    s3  = "http://localhost:4566"      # LocalStack endpoint for S3
  }
}

locals {
  mandatory_tags = {                  # Common tags for all resources
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

module "network" {                   # Network module to create VPC, subnets, and security group
  source           = "./modules/network"
  vpc_cidr         = var.vpc_cidr
  region           = var.region
  subnet_cidr_a    = var.subnet_cidr_a
  subnet_cidr_b    = var.subnet_cidr_b
  ssh_allowed_cidr = var.ssh_allowed_cidr
  tags             = local.mandatory_tags
}

resource "aws_instance" "web-app-1" {   # EC2 instance for web application
  instance_type          = var.instance_type
  ami                    = var.ami_id
  vpc_security_group_ids = [module.network.security_group_id]
  tags                   = merge(local.mandatory_tags, { Name = "web tier" })
}

resource "aws_instance" "web-app-2" {     
  instance_type          = var.instance_type
  ami                    = var.ami_id
  vpc_security_group_ids = [module.network.security_group_id]
  tags                   = merge(local.mandatory_tags, { Name = "web tier" })
}

## We can use count for creating multiple instances.


# S3 bucket for storing application logs
resource "aws_s3_bucket" "aws_s3" {          
  bucket = "${var.project_name}-${var.environment}-s3-bucket"
  tags   = local.mandatory_tags
}


# Enable versioning for the S3 bucket
resource "aws_s3_bucket_versioning" "aws_s3_versioning" {       
  bucket = aws_s3_bucket.aws_s3.id
  versioning_configuration {
    status = "Enabled"
  }
}


 # Lifecycle rule to expire objects after 30 days
resource "aws_s3_bucket_lifecycle_configuration" "aws_s3_lifecycle" {    
  bucket = aws_s3_bucket.aws_s3.id
  rule {
    id     = "expire-objects-after-30-days"
    status = "Enabled"
    expiration {
      days = 30
    }
  }
}


# EBS volume for additional storage
resource "aws_ebs_volume" "aws_ebs" {             
  availability_zone = "us-east-1a"
  size              = 8
  tags              = merge(local.mandatory_tags, { Name = "ebs volume" })
}
