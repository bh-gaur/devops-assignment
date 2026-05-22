output "vpc_id" {
  value = module.aws_vpc.id
}

output "subnet_ids" {
  value = module.aws_subnet.aws_public_subnet_a.ids
}

output "bucket_name" {
  value = aws_s3_bucket.aws_s3.id
}

