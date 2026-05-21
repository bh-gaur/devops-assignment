variable "region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "devops-assignment"
}

variable "environment" {
  default = "staging"
}

variable "owner" {
  default = "Bhupender"
}

variable "vpc_cidr" {
  default = "10.20.0.0/16"
}

variable "subnet_cidr_a" {
  default = "10.20.1.0/24"
}

variable "subnet_cidr_b" {
  default = "10.20.2.0/24"
}

variable "ssh_allowed_cidr" {
  default = "0.0.0.0/0"
}

variable "instance_type" {
  default = "t3.micro"
}

variable "ami_id" {
  default = "ami-04b4f1a9cf54c11d0"
  type    = string
}