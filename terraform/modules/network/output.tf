output "vpc_id" {
  value = aws_vpc.aws_vpc.id
}

output "subnet_id_a" {
  value = aws_subnet.aws_public_subnet-a.id
}

output "subnet_id_b" {
  value = aws_subnet.aws_public_subnet-b.id
}

output "security_group_id" {
  value = aws_security_group.aws-sg.id
}