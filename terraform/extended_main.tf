# 확장된 동영상 변환 및 분석 파이프라인 Terraform 설정

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

variable "analysis_bucket_name" {
  description = "분석 결과 S3 버킷 이름"
  type        = string
  default     = "video-analysis-bucket"
}

variable "account_id" {
  description = "AWS 계정 ID"
  type        = string
}

# 외부 분석 Lambda 함수 ARN들 (선택사항)
variable "rekognition_lambda_arn" {
  description = "Rekognition 분석 Lambda 함수 ARN"
  type        = string
  default     = ""
}

variable "twelvelabs_lambda_arn" {
  description = "Twelve Labs 분석 Lambda 함수 ARN"
  type        = string
  default     = ""
}

variable "transcribe_lambda_arn" {
  description = "Transcribe 분석 Lambda 함수 ARN"
  type        = string
  default     = ""
}

# Twelve Labs API 키 (선택사항)
variable "twelvelabs_api_key" {
  description = "Twelve Labs API 키"
  type        = string
  default     = ""
  sensitive   = true
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

# S3 버킷들
resource "aws_s3_bucket" "input_bucket" {
  bucket = var.input_bucket_name
}

resource "aws_s3_bucket" "output_bucket" {
  bucket = var.output_bucket_name
}

resource "aws_s3_bucket" "analysis_bucket" {
  bucket = var.analysis_bucket_name
}

# S3 EventBridge 알림 설정
resource "aws_s3_bucket_notification" "input_bucket_notification" {
  bucket      = aws_s3_bucket.input_bucket.id
  eventbridge = true
}

# IAM 역할들
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

# 확장된 Lambda 권한 정책 (EventBridge 발송 권한 포함)
resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "VideoConversionLambdaPolicy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid = "S3BucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.input_bucket.arn}/*",
          "${aws_s3_bucket.output_bucket.arn}/*",
          "${aws_s3_bucket.analysis_bucket.arn}/*"
        ]
      },
      {
        Sid = "MediaConvertAccess"
        Effect = "Allow"
        Action = [
          "mediaconvert:CreateJob",
          "mediaconvert:GetJob",
          "mediaconvert:DescribeEndpoints"
        ]
        Resource = "*"
      },
      {
        Sid = "PassRoleToMediaConvert"
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = aws_iam_role.mediaconvert_service_role.arn
      },
      {
        Sid = "EventBridgeAccess"
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# MediaConvert 서비스 역할
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

# 분석 Lambda들을 위한 IAM 역할
resource "aws_iam_role" "analysis_lambda_role" {
  name = "VideoAnalysisLambdaRole"

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

resource "aws_iam_role_policy" "analysis_lambda_policy" {
  name = "VideoAnalysisLambdaPolicy"
  role = aws_iam_role.analysis_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid = "S3BucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.output_bucket.arn}/*",
          "${aws_s3_bucket.analysis_bucket.arn}/*"
        ]
      },
      {
        Sid = "RekognitionAccess"
        Effect = "Allow"
        Action = [
          "rekognition:*"
        ]
        Resource = "*"
      },
      {
        Sid = "TranscribeAccess"
        Effect = "Allow"
        Action = [
          "transcribe:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda 함수 패키징
data "archive_file" "conversion_lambda_zip" {
  type        = "zip"
  source_file = "../enhanced_lambda_function.py"
  output_path = "conversion_lambda_function.zip"
}

data "archive_file" "rekognition_lambda_zip" {
  type        = "zip"
  source_file = "../sample-lambdas/rekognition_analysis_lambda.py"
  output_path = "rekognition_lambda_function.zip"
}

data "archive_file" "twelvelabs_lambda_zip" {
  type        = "zip"
  source_file = "../sample-lambdas/twelvelabs_analysis_lambda.py"
  output_path = "twelvelabs_lambda_function.zip"
}

data "archive_file" "transcribe_lambda_zip" {
  type        = "zip"
  source_file = "../sample-lambdas/transcribe_analysis_lambda.py"
  output_path = "transcribe_lambda_function.zip"
}

# 메인 변환 Lambda 함수
resource "aws_lambda_function" "video_converter" {
  filename         = data.archive_file.conversion_lambda_zip.output_path
  function_name    = "video-conversion-lambda"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "enhanced_lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  source_code_hash = data.archive_file.conversion_lambda_zip.output_base64sha256

  environment {
    variables = {
      OUTPUT_BUCKET = aws_s3_bucket.output_bucket.bucket
      ANALYSIS_BUCKET = aws_s3_bucket.analysis_bucket.bucket
      MEDIACONVERT_ROLE_ARN = aws_iam_role.mediaconvert_service_role.arn
    }
  }
}

# Rekognition 분석 Lambda 함수
resource "aws_lambda_function" "rekognition_analyzer" {
  filename         = data.archive_file.rekognition_lambda_zip.output_path
  function_name    = "rekognition-analysis-lambda"
  role            = aws_iam_role.analysis_lambda_role.arn
  handler         = "rekognition_analysis_lambda.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900  # 15분 (Rekognition 작업 대기 시간 고려)
  source_code_hash = data.archive_file.rekognition_lambda_zip.output_base64sha256

  environment {
    variables = {
      ANALYSIS_BUCKET = aws_s3_bucket.analysis_bucket.bucket
    }
  }
}

# Twelve Labs 분석 Lambda 함수
resource "aws_lambda_function" "twelvelabs_analyzer" {
  filename         = data.archive_file.twelvelabs_lambda_zip.output_path
  function_name    = "twelvelabs-analysis-lambda"
  role            = aws_iam_role.analysis_lambda_role.arn
  handler         = "twelvelabs_analysis_lambda.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900
  source_code_hash = data.archive_file.twelvelabs_lambda_zip.output_base64sha256

  environment {
    variables = {
      ANALYSIS_BUCKET = aws_s3_bucket.analysis_bucket.bucket
      TWELVE_LABS_API_KEY = var.twelvelabs_api_key
    }
  }
}

# Transcribe 분석 Lambda 함수
resource "aws_lambda_function" "transcribe_analyzer" {
  filename         = data.archive_file.transcribe_lambda_zip.output_path
  function_name    = "transcribe-analysis-lambda"
  role            = aws_iam_role.analysis_lambda_role.arn
  handler         = "transcribe_analysis_lambda.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900
  source_code_hash = data.archive_file.transcribe_lambda_zip.output_base64sha256

  environment {
    variables = {
      ANALYSIS_BUCKET = aws_s3_bucket.analysis_bucket.bucket
    }
  }
}

# EventBridge 규칙 1: S3 업로드 → 변환 Lambda
resource "aws_cloudwatch_event_rule" "s3_video_upload" {
  name        = "s3-video-upload-rule"
  description = "S3에 동영상 파일이 업로드되면 변환 Lambda 함수를 트리거"

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

# EventBridge 규칙 2: MediaConvert 완료 → 변환 Lambda (상태 업데이트용)
resource "aws_cloudwatch_event_rule" "mediaconvert_completion" {
  name        = "mediaconvert-completion-rule"
  description = "MediaConvert 작업 완료 시 변환 Lambda 함수를 트리거"

  event_pattern = jsonencode({
    source      = ["aws.mediaconvert"]
    detail-type = ["MediaConvert Job State Change"]
    detail = {
      status = ["COMPLETE", "ERROR"]
    }
  })
}

# EventBridge 규칙 3: 커스텀 분석 트리거 → 분석 Lambda들
resource "aws_cloudwatch_event_rule" "video_analysis_trigger" {
  name        = "video-analysis-trigger-rule"
  description = "동영상 변환 완료 후 분석 Lambda 함수들을 트리거"

  event_pattern = jsonencode({
    source      = ["custom.video-pipeline"]
    detail-type = ["Video Analysis Required"]
    detail = {
      analysis_types = {
        exists = true
      }
      converted_files = {
        exists = true
      }
    }
  })
}

# EventBridge 타겟들
resource "aws_cloudwatch_event_target" "conversion_lambda_target" {
  rule      = aws_cloudwatch_event_rule.s3_video_upload.name
  target_id = "VideoConversionLambdaTarget"
  arn       = aws_lambda_function.video_converter.arn
}

resource "aws_cloudwatch_event_target" "mediaconvert_completion_target" {
  rule      = aws_cloudwatch_event_rule.mediaconvert_completion.name
  target_id = "MediaConvertCompletionTarget"
  arn       = aws_lambda_function.video_converter.arn
}

resource "aws_cloudwatch_event_target" "rekognition_analysis_target" {
  rule      = aws_cloudwatch_event_rule.video_analysis_trigger.name
  target_id = "RekognitionAnalysisTarget"
  arn       = aws_lambda_function.rekognition_analyzer.arn
}

resource "aws_cloudwatch_event_target" "twelvelabs_analysis_target" {
  rule      = aws_cloudwatch_event_rule.video_analysis_trigger.name
  target_id = "TwelveLabsAnalysisTarget"
  arn       = aws_lambda_function.twelvelabs_analyzer.arn
}

resource "aws_cloudwatch_event_target" "transcribe_analysis_target" {
  rule      = aws_cloudwatch_event_rule.video_analysis_trigger.name
  target_id = "TranscribeAnalysisTarget"
  arn       = aws_lambda_function.transcribe_analyzer.arn
}

# Lambda 권한들
resource "aws_lambda_permission" "allow_eventbridge_conversion" {
  statement_id  = "AllowEventBridgeConversion"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.video_converter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_video_upload.arn
}

resource "aws_lambda_permission" "allow_eventbridge_mediaconvert" {
  statement_id  = "AllowEventBridgeMediaConvert"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.video_converter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.mediaconvert_completion.arn
}

resource "aws_lambda_permission" "allow_eventbridge_rekognition" {
  statement_id  = "AllowEventBridgeRekognition"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rekognition_analyzer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.video_analysis_trigger.arn
}

resource "aws_lambda_permission" "allow_eventbridge_twelvelabs" {
  statement_id  = "AllowEventBridgeTwelveLabs"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.twelvelabs_analyzer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.video_analysis_trigger.arn
}

resource "aws_lambda_permission" "allow_eventbridge_transcribe" {
  statement_id  = "AllowEventBridgeTranscribe"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.transcribe_analyzer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.video_analysis_trigger.arn
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

output "analysis_bucket_name" {
  description = "분석 결과 S3 버킷 이름"
  value       = aws_s3_bucket.analysis_bucket.bucket
}

output "lambda_functions" {
  description = "생성된 Lambda 함수들"
  value = {
    conversion_lambda = aws_lambda_function.video_converter.function_name
    rekognition_lambda = aws_lambda_function.rekognition_analyzer.function_name
    twelvelabs_lambda = aws_lambda_function.twelvelabs_analyzer.function_name
    transcribe_lambda = aws_lambda_function.transcribe_analyzer.function_name
  }
}

output "eventbridge_rules" {
  description = "생성된 EventBridge 규칙들"
  value = {
    s3_upload_rule = aws_cloudwatch_event_rule.s3_video_upload.name
    mediaconvert_completion_rule = aws_cloudwatch_event_rule.mediaconvert_completion.name
    analysis_trigger_rule = aws_cloudwatch_event_rule.video_analysis_trigger.name
  }
}
