# 비용 최적화된 동영상 변환 파이프라인
# 분석 Lambda들 제거하여 비용 절약

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 변수 정의
variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "프로젝트 이름"
  type        = string
  default     = "video-conversion-pipeline"
}

# S3 버킷들
resource "aws_s3_bucket" "input_bucket" {
  bucket = "${var.project_name}-input-${random_string.bucket_suffix.result}"
}

resource "aws_s3_bucket" "output_bucket" {
  bucket = "${var.project_name}-output-${random_string.bucket_suffix.result}"
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 버킷 설정
resource "aws_s3_bucket_versioning" "input_bucket_versioning" {
  bucket = aws_s3_bucket.input_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "output_bucket_versioning" {
  bucket = aws_s3_bucket.output_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 EventBridge 알림 설정
resource "aws_s3_bucket_notification" "input_bucket_notification" {
  bucket      = aws_s3_bucket.input_bucket.id
  eventbridge = true
}

# Lambda 실행 역할
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Lambda 권한 정책
resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "VideoConversionLambdaPolicy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "LogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.input_bucket.arn,
          "${aws_s3_bucket.input_bucket.arn}/*",
          aws_s3_bucket.output_bucket.arn,
          "${aws_s3_bucket.output_bucket.arn}/*"
        ]
      },
      {
        Sid = "MediaConvertAccess"
        Effect = "Allow"
        Action = [
          "mediaconvert:*"
        ]
        Resource = "*"
      },
      {
        Sid = "IAMPassRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.mediaconvert_role.arn
      }
    ]
  })
}

# MediaConvert 서비스 역할
resource "aws_iam_role" "mediaconvert_role" {
  name = "${var.project_name}-mediaconvert-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "mediaconvert.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "mediaconvert_policy" {
  name = "MediaConvertServicePolicy"
  role = aws_iam_role.mediaconvert_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.input_bucket.arn}/*",
          "${aws_s3_bucket.output_bucket.arn}/*"
        ]
      }
    ]
  })
}

# Lambda 함수 패키징
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambda_function.py"
  output_path = "lambda_function.zip"
}

# 동영상 변환 Lambda 함수
resource "aws_lambda_function" "video_converter" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-converter"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900
  memory_size     = 512
  
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  
  environment {
    variables = {
      MEDIACONVERT_ROLE_ARN = aws_iam_role.mediaconvert_role.arn
      OUTPUT_BUCKET = aws_s3_bucket.output_bucket.bucket
    }
  }
}

# CloudWatch 로그 그룹
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.video_converter.function_name}"
  retention_in_days = 14
}

# EventBridge 규칙: S3 업로드 → 변환 Lambda
resource "aws_cloudwatch_event_rule" "s3_video_upload" {
  name        = "s3-video-upload-rule"
  description = "S3에 동영상 파일이 업로드되면 Lambda 함수를 트리거"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.input_bucket.bucket]
      }
      object = {
        key = [
          { suffix = ".mp4" },
          { suffix = ".mov" },
          { suffix = ".avi" },
          { suffix = ".mkv" },
          { suffix = ".wmv" },
          { suffix = ".flv" },
          { suffix = ".webm" },
          { suffix = ".m4v" }
        ]
      }
    }
  })
}

# EventBridge 타겟
resource "aws_cloudwatch_event_target" "conversion_lambda_target" {
  rule      = aws_cloudwatch_event_rule.s3_video_upload.name
  target_id = "VideoConversionLambda"
  arn       = aws_lambda_function.video_converter.arn
}

# Lambda 권한
resource "aws_lambda_permission" "allow_eventbridge_conversion" {
  statement_id  = "AllowEventBridgeConversion"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.video_converter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_video_upload.arn
}

# 출력값
output "input_bucket_name" {
  description = "입력 S3 버킷 이름"
  value       = aws_s3_bucket.input_bucket.bucket
}

output "output_bucket_name" {
  description = "출력 S3 버킷 이름"
  value       = aws_s3_bucket.output_bucket.bucket
}

output "lambda_function_name" {
  description = "Lambda 함수 이름"
  value       = aws_lambda_function.video_converter.function_name
}

output "eventbridge_rule_name" {
  description = "EventBridge 규칙 이름"
  value       = aws_cloudwatch_event_rule.s3_video_upload.name
}
