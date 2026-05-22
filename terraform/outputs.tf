output "vpc_id" {
  value = module.network.aws_vpc.id
}

output "subnet_ids" {
  value = module.network.aws_subnet.aws_public_subnet_a.ids
}

output "bucket_name" {
  value = aws_s3_bucket.aws_s3.id
}

