data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  api_image  = "${aws_ecr_repository.api.repository_url}:${var.api_image_tag}"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project}-worker"
  retention_in_days = 14
}

resource "aws_iam_role" "task_execution" {
  name = "${var.project}-task-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution_basic" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_ssm" {
  name = "${var.project}-task-execution-ssm"
  role = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["ssm:GetParameters", "ssm:GetParameter", "ssm:GetParametersByPath", "kms:Decrypt"],
      Resource = "*"
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.project}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_ecs_cluster" "this" {
  name = "${var.project}-cluster"
  setting { name = "containerInsights" value = "enabled" }
}

# --- API task -------------------------------------------------------------
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = local.api_image
    essential = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "APP_ENV", value = "prod" },
      { name = "AI_COACH_BACKEND", value = "fake" },
      { name = "VECTOR_BACKEND", value = "memory" },
      { name = "DATABASE_URL", value = local.database_url },
      { name = "REDIS_URL", value = local.redis_url },
      { name = "KILL_SWITCH_HARD_DAILY_LOSS_PCT", value = "5.0" },
      { name = "KILL_SWITCH_HARD_MAX_OPEN_POSITIONS", value = "20" },
    ]
    secrets = [
      { name = "JWT_SECRET",         valueFrom = aws_ssm_parameter.jwt_secret.arn },
      { name = "SECRETS_FERNET_KEY", valueFrom = aws_ssm_parameter.fernet_key.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request,sys;urllib.request.urlopen('http://localhost:8000/health/core',timeout=2)\" || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "${var.project}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https, aws_lb_listener.http]
}

# --- Worker task ----------------------------------------------------------
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "worker"
    image     = local.api_image
    essential = true
    command   = ["python", "-m", "app.workers.ai_worker"]
    environment = [
      { name = "APP_ENV", value = "prod" },
      { name = "AI_COACH_BACKEND", value = "external" },
      { name = "VECTOR_BACKEND", value = "memory" },
      { name = "DATABASE_URL", value = local.database_url },
      { name = "REDIS_URL", value = local.redis_url },
      { name = "API_BASE_URL", value = "http://${aws_lb.this.dns_name}" },
    ]
    secrets = [
      { name = "JWT_SECRET",            valueFrom = aws_ssm_parameter.jwt_secret.arn },
      { name = "SECRETS_FERNET_KEY",    valueFrom = aws_ssm_parameter.fernet_key.arn },
      { name = "AI_SERVICE_URL",        valueFrom = aws_ssm_parameter.ai_service_url.arn },
      { name = "AI_SERVICE_API_KEY",    valueFrom = aws_ssm_parameter.ai_service_api_key.arn },
      { name = "AI_WORKER_ADMIN_TOKEN", valueFrom = aws_ssm_parameter.ai_worker_admin_token.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.project}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}
