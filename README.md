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
