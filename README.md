# 🎬 AWS 동영상 자동 변환 파이프라인

S3에 동영상을 업로드하면 EventBridge가 반응하여 Lambda 함수가 실행되고, MediaConvert를 통해 자동으로 SD 화질로 변환하여 다시 S3에 저장하는 완전 자동화된 파이프라인입니다.

## 🏗️ 아키텍처

```
S3 업로드 → EventBridge 이벤트 → Lambda 함수 → MediaConvert 작업 → 변환된 파일을 S3에 저장
```

## 📁 프로젝트 구조

```
├── lambda_function.py              # Lambda 함수 메인 코드
├── eventbridge-rule.json          # EventBridge 규칙 설정
├── deploy.sh                      # 자동 배포 스크립트
├── iam-policies/                  # IAM 정책 파일들
│   ├── lambda-execution-policy.json
│   ├── lambda-trust-policy.json
│   ├── mediaconvert-service-policy.json
│   └── mediaconvert-trust-policy.json
├── terraform/                     # Terraform 배포 코드
│   └── main.tf
└── README.md                      # 이 파일
```

## 🚀 빠른 시작

### 1. 자동 배포 (추천)

```bash
# 저장소 클론
git clone https://github.com/apdnl124/event.git
cd event

# 배포 스크립트 실행
./deploy.sh
```

### 2. Terraform 배포

```bash
cd terraform

# 변수 설정
export TF_VAR_account_id=$(aws sts get-caller-identity --query Account --output text)

# Terraform 초기화 및 배포
terraform init
terraform plan
terraform apply
```

## 📋 주요 기능

### 🎯 지원하는 동영상 포맷
- `.mp4`, `.mov`, `.avi`, `.mkv`
- `.wmv`, `.flv`, `.webm`, `.m4v`

### 🔄 변환 설정
- **입력**: FHD (1920x1080) 또는 그 이상
- **출력**: SD (720x480)
- **코덱**: H.264 (비디오) + AAC (오디오)
- **비트레이트**: 2Mbps (비디오) + 128kbps (오디오)

### ⚡ 자동화 기능
- S3 업로드 즉시 변환 시작
- 동영상 파일 자동 감지
- 변환 완료 후 자동 저장
- 실시간 로그 모니터링

## 🔧 수동 설정
## 🔐 권한 설정 상세 가이드

AWS 동영상 변환 파이프라인은 **최소 권한 원칙**에 따라 보안이 강화된 IAM 역할과 정책으로 구성됩니다.

### 🏗️ 권한 아키텍처

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│  Lambda Function │───▶│  MediaConvert   │
│                 │    │                  │    │                 │
│ • Lambda 호출   │    │ • S3 읽기/쓰기   │    │ • S3 읽기/쓰기  │
│   권한          │    │ • MediaConvert   │    │ • 비디오 변환   │
└─────────────────┘    │   작업 생성      │    └─────────────────┘
                       │ • 로그 작성      │
                       │ • 역할 전달      │
                       └──────────────────┘
```

### 🎯 IAM 역할 구조

#### 1. **Lambda 실행 역할 (VideoConversionLambdaRole)**

**목적**: Lambda 함수가 AWS 서비스들과 상호작용할 수 있도록 하는 역할

**신뢰 정책 (Trust Policy)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**권한 정책 (Permission Policy)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Sid": "S3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-input-video-bucket/*",
        "arn:aws:s3:::your-converted-videos-bucket/*"
      ]
    },
    {
      "Sid": "MediaConvertAccess",
      "Effect": "Allow",
      "Action": [
        "mediaconvert:CreateJob",
        "mediaconvert:GetJob",
        "mediaconvert:DescribeEndpoints"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassRoleToMediaConvert",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::YOUR_ACCOUNT_ID:role/MediaConvertServiceRole"
    }
  ]
}
```

#### 2. **MediaConvert 서비스 역할 (MediaConvertServiceRole)**

**목적**: MediaConvert 서비스가 S3 버킷에 접근하여 파일을 읽고 쓸 수 있도록 하는 역할

**신뢰 정책**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "mediaconvert.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**권한 정책**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-input-video-bucket/*",
        "arn:aws:s3:::your-converted-videos-bucket/*"
      ]
    },
    {
      "Sid": "S3BucketListAccess",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": [
        "arn:aws:s3:::your-input-video-bucket",
        "arn:aws:s3:::your-converted-videos-bucket"
      ]
    }
  ]
}
```

### ⚡ EventBridge 권한 설정

#### **EventBridge → Lambda 호출 권한**

EventBridge가 Lambda 함수를 호출할 수 있도록 하는 리소스 기반 정책:

```json
{
  "Sid": "AllowEventBridgeInvocation",
  "Effect": "Allow",
  "Principal": {
    "Service": "events.amazonaws.com"
  },
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:region:account:function:video-conversion-lambda",
  "Condition": {
    "ArnEquals": {
      "aws:SourceArn": "arn:aws:events:region:account:rule/S3VideoUploadRule"
    }
  }
}
```

### 🛡️ 보안 원칙

#### **1. 최소 권한 원칙 (Principle of Least Privilege)**
- 각 서비스는 **작업 수행에 필요한 최소한의 권한**만 부여
- 불필요한 관리자 권한이나 와일드카드 권한 사용 금지
- 특정 리소스에만 접근 가능하도록 제한

#### **2. 역할 분리 (Separation of Duties)**
```
Lambda 역할:
├── 함수 실행 및 로깅
├── S3 파일 읽기/쓰기
├── MediaConvert 작업 생성
└── 서비스 역할 전달

MediaConvert 역할:
├── S3 파일 읽기 (입력)
├── S3 파일 쓰기 (출력)
└── 버킷 목록 조회
```

#### **3. 리소스 기반 제한**
```json
// ❌ 잘못된 예 - 모든 S3 버킷 접근
"Resource": "arn:aws:s3:::*/*"

// ✅ 올바른 예 - 특정 버킷만 접근
"Resource": [
  "arn:aws:s3:::specific-input-bucket/*",
  "arn:aws:s3:::specific-output-bucket/*"
]
```

#### **4. 조건부 접근 제어**
```json
{
  "Condition": {
    "StringEquals": {
      "s3:x-amz-server-side-encryption": "AES256"
    },
    "IpAddress": {
      "aws:SourceIp": "203.0.113.0/24"
    }
  }
}
```

### 🔧 권한 설정 방법

#### **Terraform을 사용한 권한 설정**

```hcl
# Lambda 실행 역할 생성
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

  tags = {
    Purpose = "VideoConversion"
    Environment = "Production"
  }
}

# Lambda 권한 정책 연결
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
        Resource = "arn:aws:logs:${var.aws_region}:${var.account_id}:*"
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
          "${aws_s3_bucket.output_bucket.arn}/*"
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
      }
    ]
  })
}

# EventBridge → Lambda 호출 권한
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.video_converter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_video_upload.arn
}
```

#### **AWS CLI를 사용한 권한 설정**

```bash
# 1. Lambda 실행 역할 생성
aws iam create-role \
  --role-name VideoConversionLambdaRole \
  --assume-role-policy-document file://iam-policies/lambda-trust-policy.json \
  --description "Lambda execution role for video conversion pipeline"

# 2. Lambda 권한 정책 연결
aws iam put-role-policy \
  --role-name VideoConversionLambdaRole \
  --policy-name VideoConversionLambdaPolicy \
  --policy-document file://iam-policies/lambda-execution-policy.json

# 3. MediaConvert 서비스 역할 생성
aws iam create-role \
  --role-name MediaConvertServiceRole \
  --assume-role-policy-document file://iam-policies/mediaconvert-trust-policy.json \
  --description "Service role for MediaConvert to access S3 buckets"

# 4. MediaConvert 권한 정책 연결
aws iam put-role-policy \
  --role-name MediaConvertServiceRole \
  --policy-name MediaConvertServicePolicy \
  --policy-document file://iam-policies/mediaconvert-service-policy.json

# 5. EventBridge → Lambda 호출 권한 부여
aws lambda add-permission \
  --function-name video-conversion-lambda \
  --statement-id allow-eventbridge-invocation \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:region:account:rule/S3VideoUploadRule
```

### 🔍 권한 검증 및 테스트

#### **1. IAM Policy Simulator 사용**
```bash
# Lambda 역할의 S3 접근 권한 테스트
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::account:role/VideoConversionLambdaRole \
  --action-names "s3:GetObject" \
  --resource-arns "arn:aws:s3:::input-bucket/test-video.mp4"

# MediaConvert 작업 생성 권한 테스트
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::account:role/VideoConversionLambdaRole \
  --action-names "mediaconvert:CreateJob" \
  --resource-arns "*"
```

#### **2. 실제 권한 테스트**
```bash
# Lambda 함수 로그에서 권한 관련 오류 확인
aws logs filter-log-events \
  --log-group-name /aws/lambda/video-conversion-lambda \
  --filter-pattern "AccessDenied OR Forbidden OR Unauthorized"

# MediaConvert 작업 실패 원인 확인
aws mediaconvert get-job --id JOB_ID \
  --query 'Job.Messages[?Type==`ERROR`]'
```

#### **3. 권한 감사**
```bash
# 역할에 연결된 정책 목록 확인
aws iam list-attached-role-policies --role-name VideoConversionLambdaRole
aws iam list-role-policies --role-name VideoConversionLambdaRole

# 정책 내용 상세 확인
aws iam get-role-policy \
  --role-name VideoConversionLambdaRole \
  --policy-name VideoConversionLambdaPolicy
```

### 🚨 보안 모범 사례

#### **1. 정기적인 권한 검토**
```bash
# 사용되지 않는 권한 식별
aws iam generate-service-last-accessed-details \
  --arn arn:aws:iam::account:role/VideoConversionLambdaRole

# 권한 사용 내역 확인
aws iam get-service-last-accessed-details \
  --job-id JOB_ID
```

#### **2. CloudTrail을 통한 권한 사용 모니터링**
```json
{
  "eventSource": "iam.amazonaws.com",
  "eventName": "AssumeRole",
  "userIdentity": {
    "type": "AWSService",
    "principalId": "lambda.amazonaws.com"
  },
  "resources": [
    {
      "ARN": "arn:aws:iam::account:role/VideoConversionLambdaRole"
    }
  ]
}
```

#### **3. 권한 경계 (Permission Boundaries) 설정**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:*",
        "mediaconvert:*",
        "logs:*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Deny",
      "Action": [
        "iam:*",
        "organizations:*",
        "account:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### 🔧 트러블슈팅

#### **일반적인 권한 오류들**

**1. `AccessDenied: User is not authorized to perform iam:PassRole`**
```bash
# 해결: Lambda 역할에 PassRole 권한 추가
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::account:role/MediaConvertServiceRole"
}
```

**2. `AccessDenied: Access Denied (Service: Amazon S3)`**
```bash
# 해결: S3 버킷 정책 및 IAM 권한 확인
aws s3api get-bucket-policy --bucket your-bucket-name
```

**3. `InvalidParameterValue: The role defined for the function cannot be assumed by Lambda`**
```bash
# 해결: 신뢰 정책에 lambda.amazonaws.com 추가
{
  "Principal": {
    "Service": "lambda.amazonaws.com"
  }
}
```

#### **권한 디버깅 도구**

```bash
# 1. 현재 사용자/역할 확인
aws sts get-caller-identity

# 2. 역할 상세 정보 확인
aws iam get-role --role-name VideoConversionLambdaRole

# 3. 정책 시뮬레이션
aws iam simulate-principal-policy \
  --policy-source-arn ROLE_ARN \
  --action-names ACTION_NAME \
  --resource-arns RESOURCE_ARN

# 4. CloudTrail 이벤트 확인
aws logs filter-log-events \
  --log-group-name CloudTrail/APIGatewayExecutionLogs \
  --filter-pattern "AccessDenied"
```

### 📋 권한 체크리스트

배포 전 다음 항목들을 확인하세요:

- [ ] **Lambda 실행 역할 생성됨**
- [ ] **MediaConvert 서비스 역할 생성됨**
- [ ] **S3 버킷 접근 권한 설정됨**
- [ ] **MediaConvert 작업 생성 권한 설정됨**
- [ ] **CloudWatch 로그 권한 설정됨**
- [ ] **EventBridge → Lambda 호출 권한 설정됨**
- [ ] **IAM PassRole 권한 설정됨**
- [ ] **권한 정책이 최소 권한 원칙을 따름**
- [ ] **리소스 ARN이 정확히 지정됨**
- [ ] **신뢰 정책이 올바른 서비스를 지정함**

이러한 권한 설정을 통해 **보안이 강화되고 안정적인 동영상 변환 파이프라인**을 구축할 수 있습니다! 🔐

### 1. S3 버킷 생성
```bash
# 입력용 버킷
aws s3 mb s3://your-input-video-bucket

# 출력용 버킷  
aws s3 mb s3://your-output-video-bucket

# EventBridge 알림 활성화
aws s3api put-bucket-notification-configuration \
  --bucket your-input-video-bucket \
  --notification-configuration '{"EventBridgeConfiguration": {}}'
```

### 2. IAM 역할 생성
```bash
# Lambda 실행 역할
aws iam create-role \
  --role-name VideoConversionLambdaRole \
  --assume-role-policy-document file://iam-policies/lambda-trust-policy.json

# MediaConvert 서비스 역할
aws iam create-role \
  --role-name MediaConvertServiceRole \
  --assume-role-policy-document file://iam-policies/mediaconvert-trust-policy.json
```

### 3. Lambda 함수 배포
```bash
# 코드 패키징
zip lambda_function.zip lambda_function.py

# 함수 생성
aws lambda create-function \
  --function-name video-conversion-lambda \
  --runtime python3.9 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/VideoConversionLambdaRole \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_function.zip
```

### 4. EventBridge 규칙 설정
```bash
# 규칙 생성
aws events put-rule \
  --name S3VideoUploadRule \
  --event-pattern file://eventbridge-rule.json

# 타겟 추가
aws events put-targets \
  --rule S3VideoUploadRule \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:video-conversion-lambda"
```

## 📊 모니터링

### CloudWatch 로그 확인
```bash
# Lambda 함수 로그 실시간 모니터링
aws logs tail /aws/lambda/video-conversion-lambda --follow

# 특정 시간대 로그 조회
aws logs filter-log-events \
  --log-group-name /aws/lambda/video-conversion-lambda \
  --start-time 1640995200000
```

### MediaConvert 작업 상태 확인
```bash
# 작업 목록 조회
aws mediaconvert list-jobs --max-results 10

# 특정 작업 상태 확인
aws mediaconvert get-job --id JOB_ID
```

## 🎬 사용 방법

1. **동영상 업로드**
   ```bash
   aws s3 cp your-video.mp4 s3://your-input-video-bucket/
   ```

2. **자동 처리 시작**
   - EventBridge가 S3 이벤트 감지
   - Lambda 함수 자동 실행
   - MediaConvert 작업 생성

3. **결과 확인**
   ```bash
   aws s3 ls s3://your-output-video-bucket/converted/
   ```

## 💰 예상 비용

### 월 100개 동영상 처리 기준:
- **Lambda**: ~$1 (실행 시간 기준)
- **MediaConvert**: ~$15 (처리 시간 기준)
- **S3**: ~$5 (저장 용량 기준)
- **EventBridge**: ~$0.1 (이벤트 수 기준)
- **총 예상 비용**: ~$21/월

## 🔧 커스터마이징

### 변환 설정 변경
`lambda_function.py`의 `create_mediaconvert_job` 함수에서 다음 설정을 수정할 수 있습니다:

```python
# 해상도 변경
"Width": 1280,    # HD: 1280x720
"Height": 720,

# 비트레이트 변경  
"Bitrate": 3000000,  # 3Mbps

# 오디오 설정 변경
"Bitrate": 192000,   # 192kbps
"SampleRate": 48000  # 48kHz
```

### 지원 포맷 추가
`is_video_file` 함수에서 확장자를 추가할 수 있습니다:

```python
video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.your_format']
```

## 🚨 주의사항

1. **권한 설정**: IAM 역할에 필요한 최소 권한만 부여
2. **비용 관리**: 대용량 파일 처리 시 비용 증가 주의
3. **타임아웃**: Lambda 함수 타임아웃을 적절히 설정 (최대 15분)
4. **동시 실행**: Lambda 동시 실행 제한 고려

## 🔍 트러블슈팅

### 일반적인 문제들:

**1. Lambda 함수가 실행되지 않음**
- EventBridge 규칙 확인
- Lambda 권한 확인
- S3 EventBridge 알림 활성화 확인

**2. MediaConvert 작업 실패**
- IAM 역할 권한 확인
- 입력 파일 형식 확인
- S3 버킷 접근 권한 확인

**3. 변환된 파일이 없음**
- MediaConvert 작업 상태 확인
- 출력 버킷 권한 확인
- CloudWatch 로그 확인

## 📞 지원

문제가 발생하면 다음을 확인해주세요:
1. CloudWatch 로그
2. MediaConvert 작업 상태
3. IAM 권한 설정
4. S3 버킷 설정

---

**🎬 AWS 동영상 자동 변환 파이프라인으로 효율적인 미디어 처리를 경험해보세요!**
