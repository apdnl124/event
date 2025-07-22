# 변수 정의
variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "input_bucket_name" {
  description = "입력 동영상 S3 버킷 이름"
  type        = string
  default     = "video-input-bucket"
}

variable "output_bucket_name" {
  description = "변환된 동영상 S3 버킷 이름"
  type        = string
  default     = "video-output-bucket"
}

variable "account_id" {
  description = "AWS 계정 ID"
  type        = string
}

# Provider 설정
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

# S3 버킷 - 입력용
resource "aws_s3_bucket" "input_bucket" {
  bucket = var.input_bucket_name
}

resource "aws_s3_bucket_notification" "input_bucket_notification" {
  bucket      = aws_s3_bucket.input_bucket.id
  eventbridge = true
}

# S3 버킷 - 출력용
resource "aws_s3_bucket" "output_bucket" {
  bucket = var.output_bucket_name
}

# IAM 역할 - Lambda 실행용
resource "aws_iam_role" "lambda_execution_role" {
  name = "VideoConversionLambdaRole"

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

# IAM 정책 - Lambda 실행용
resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "VideoConversionLambdaPolicy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
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
      },
      {
        Effect = "Allow"
        Action = [
          "mediaconvert:CreateJob",
          "mediaconvert:GetJob",
          "mediaconvert:DescribeEndpoints"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = aws_iam_role.mediaconvert_service_role.arn
      }
    ]
  })
}

# IAM 역할 - MediaConvert 서비스용
resource "aws_iam_role" "mediaconvert_service_role" {
  name = "MediaConvertServiceRole"

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

# IAM 정책 - MediaConvert 서비스용
resource "aws_iam_role_policy" "mediaconvert_service_policy" {
  name = "MediaConvertServicePolicy"
  role = aws_iam_role.mediaconvert_service_role.id

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
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.input_bucket.arn,
          aws_s3_bucket.output_bucket.arn
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

# Lambda 함수
resource "aws_lambda_function" "video_converter" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "video-conversion-lambda"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      OUTPUT_BUCKET = aws_s3_bucket.output_bucket.bucket
      MEDIACONVERT_ROLE_ARN = aws_iam_role.mediaconvert_service_role.arn
    }
  }
}

# EventBridge 규칙
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
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.s3_video_upload.name
  target_id = "VideoConversionLambdaTarget"
  arn       = aws_lambda_function.video_converter.arn
}

# Lambda 권한 - EventBridge에서 호출 허용
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
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
