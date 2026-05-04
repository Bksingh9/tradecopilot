resource "aws_lb" "this" {
  name               = "${var.project}-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  tags               = { project = var.project }
}

resource "aws_lb_target_group" "api" {
  name        = "${var.project}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  health_check {
    path                = "/health/core"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 4
    interval            = 30
    matcher             = "200-299"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# HTTPS listener — populated only when var.domain_name is provided AND an
# ACM cert with that name exists in this region. Comment out if not needed.
data "aws_acm_certificate" "this" {
  count       = var.domain_name == "" ? 0 : 1
  domain      = var.domain_name
  most_recent = true
  statuses    = ["ISSUED"]
}

resource "aws_lb_listener" "https" {
  count             = var.domain_name == "" ? 0 : 1
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = data.aws_acm_certificate.this[0].arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
