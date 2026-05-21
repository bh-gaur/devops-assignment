variable "vpc_cidr" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "region" {
  type = string
}

variable "subnet_cidr_a" {
  type = string
}

variable "subnet_cidr_b" {
  type = string
}

variable "ssh_allowed_cidr" {
  type = string
}