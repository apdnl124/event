# 🎬 AWS 동영상 자동 변환 파이프라인 (비용 최적화 버전)

S3에 동영상을 업로드하면 EventBridge가 반응하여 Lambda 함수가 실행되고, MediaConvert를 통해 자동으로 SD 화질로 변환하여 다시 S3에 저장하는 완전 자동화된 파이프라인입니다.

**🔥 비용 최적화**: 분석 Lambda들(Rekognition, TwelveLabs, Transcribe)을 제거하여 비용을 대폭 절약했습니다.

## 🏗️ 아키텍처

```
S3 업로드 → EventBridge 이벤트 → Lambda 함수 → MediaConvert 작업 → 변환된 파일을 S3에 저장
```

## 📁 프로젝트 구조

```
├── lambda_function.py              # 기존 Lambda 함수 (분석 포함)
├── optimized_lambda_function.py    # 최적화된 Lambda 함수 (변환만)
├── eventbridge-rule.json          # EventBridge 규칙 설정
├── deploy.sh                      # 자동 배포 스크립트
├── iam-policies/                  # IAM 정책 파일들
├── terraform/
│   ├── main.tf                    # 기존 Terraform (분석 포함)
│   └── optimized_main.tf          # 최적화된 Terraform (변환만)
└── README.md                      # 이 파일
```

## 💰 비용 비교

| 구성 | 300분 동영상 예상 비용 |
|------|----------------------|
| **기존 (분석 포함)** | $60-90 |
| **최적화 (변환만)** | $2-3 |
| **절약률** | **95% 절약** |

## 🚀 빠른 시작 (최적화 버전)

### 1. Terraform 배포

```bash
cd terraform

# 최적화된 버전 사용
cp optimized_main.tf main.tf

# 변수 설정
export TF_VAR_account_id=$(aws sts get-caller-identity --query Account --output text)

# Terraform 초기화 및 배포
terraform init
terraform plan
terraform apply
```

### 2. Lambda 함수 업데이트

```bash
# 최적화된 Lambda 함수 사용
cp optimized_lambda_function.py lambda_function.py

# 함수 업데이트 (Terraform apply 후)
aws lambda update-function-code \
  --function-name video-conversion-pipeline-converter \
  --zip-file fileb://lambda_function.zip
```

## 🔧 주요 변경사항

### ✅ 유지된 기능
- S3 동영상 업로드 감지
- EventBridge 자동 트리거
- MediaConvert SD 변환
- 자동화된 파이프라인

### ❌ 제거된 기능 (비용 절약)
- Rekognition 동영상 분석
- TwelveLabs 분석
- Transcribe 음성 인식
- 분석 결과 저장

### 💡 나중에 추가할 수 있는 기능
- 샘플링 기반 Rekognition 분석
- 선택적 장면 분석
- 비용 임계값 기반 분석

## 📊 지원 형식

**입력 형식**: `.mp4`, `.mov`, `.avi`, `.mkv`, `.wmv`, `.flv`, `.webm`, `.m4v`
**출력 형식**: `.mp4` (SD 720x480, 1.5Mbps)

## 🛠️ 설정

### 환경 변수
- `MEDIACONVERT_ROLE_ARN`: MediaConvert 서비스 역할 ARN
- `OUTPUT_BUCKET`: 변환된 파일 저장 버킷

### S3 버킷 구조
```
input-bucket/
├── video1.mp4
├── video2.mov
└── ...

output-bucket/
├── converted/
│   ├── video1_sd.mp4
│   ├── video2_sd.mp4
│   └── ...
```

## 🔍 모니터링

### CloudWatch 로그
- Lambda 실행 로그: `/aws/lambda/video-conversion-pipeline-converter`
- MediaConvert 작업 상태 확인

### 비용 모니터링
```bash
# 일일 비용 확인
aws ce get-cost-and-usage \
  --time-period Start=2025-07-22,End=2025-07-23 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## 🚨 주의사항

1. **MediaConvert 리전**: 일부 리전에서만 사용 가능
2. **파일 크기 제한**: Lambda 15분 타임아웃 고려
3. **동시 실행**: 기본 1000개 동시 실행 제한
4. **비용 모니터링**: 예상치 못한 대용량 파일 주의

## 🔄 향후 개선 계획

1. **스마트 분석**: 필요시에만 분석 실행
2. **배치 처리**: 여러 파일 동시 처리
3. **비용 알림**: 임계값 초과시 알림
4. **품질 선택**: SD/HD/FHD 선택 가능

## 📞 문의

이슈나 개선사항이 있으시면 GitHub Issues를 통해 연락주세요.

---

**💡 팁**: 분석이 필요한 경우, 변환된 SD 파일로 분석하면 비용을 크게 절약할 수 있습니다!
