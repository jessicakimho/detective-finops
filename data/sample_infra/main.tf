# Inspection/remediation fixture only. The local demo never runs Terraform.
# Supply existing private networking and a GPU-ready AMI before any real use.
terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      project     = "gpu-finops-detective"
      environment = "demo"
      managed_by  = "terraform"
    }
  }
}

variable "gpu_ami_id" {
  type        = string
  description = "Existing x86_64 GPU-ready AMI with NVIDIA drivers and the inference runtime."
}

variable "private_subnet_id" {
  type        = string
  description = "Existing private subnet with access to model artifacts and observability endpoints."
}

variable "inference_security_group_ids" {
  type        = list(string)
  description = "Existing groups permitting inference traffic only from the internal service tier."

  validation {
    condition     = length(var.inference_security_group_ids) > 0
    error_message = "Supply at least one inference security group."
  }
}

variable "inference_instance_profile" {
  type        = string
  description = "Existing least-privilege instance profile for model reads and telemetry publishing."
}

# Intentionally kept running overnight and on weekends despite zero demand.
# P4d has eight A100 GPUs; high VRAM occupancy alone does not justify downsizing.
resource "aws_instance" "recommendation_inference" {
  ami                         = var.gpu_ami_id
  instance_type               = "p4d.24xlarge"
  subnet_id                   = var.private_subnet_id
  vpc_security_group_ids      = var.inference_security_group_ids
  iam_instance_profile        = var.inference_instance_profile
  associate_public_ip_address = false
  monitoring                  = true

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 200
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name          = "recommendation-llm-inference"
    service       = "recommendation-llm"
    cost_center   = "ai-platform"
    workload      = "inference"
    schedule      = "always-on"
    demo_resource = "i-00000000000000001"
  }
}

output "inference_instance_id" {
  value       = aws_instance.recommendation_inference.id
  description = "Real ID if deployed; the local dataset uses a synthetic ID instead."
}
