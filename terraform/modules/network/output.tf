output "vpc_id" {
  value = aws_vpc.aws_vpc.id
}

output "public_subnet_ids" {
  description = "IDs of the two public subnets."
  value       = [
    aws_subnet.aws_public_subnet-a.id,
    aws_subnet.aws_public_subnet-b.id,
  ]
}

output "security_group_id" {
  value = aws_security_group.aws-sg.id
}