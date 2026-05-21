resource "aws_vpc" "aws_vpc" {
  cidr_block = var.vpc_cidr
  tags       = var.tags
}

resource "aws_subnet" "aws_public_subnet-a" {
  vpc_id            = aws_vpc.aws_vpc.id
  cidr_block        = var.subnet_cidr_a
  availability_zone = "${var.region}a"
  tags              = var.tags
}

resource "aws_subnet" "aws_public_subnet-b" {
  vpc_id            = aws_vpc.aws_vpc.id
  cidr_block        = var.subnet_cidr_b
  availability_zone = "${var.region}b"
  tags              = var.tags
}

resource "aws_security_group" "aws-sg" {
  name   = "aws-sg"
  vpc_id = aws_vpc.aws_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}