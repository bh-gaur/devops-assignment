output "vpc_id" {
  value = module.network.vpc_id
}

output "subnet_ids" {
  value = [

    module.network.public_subnet_ids[0],
    module.network.public_subnet_ids[1],
  ]
}

output "bucket_name" {
  value = aws_s3_bucket.aws_s3.id
}

output "security_group_id" {
  value = module.network.security_group_id
}

