#!/bin/bash

# 동영상 자동 변환 파이프라인 배포 스크립트

echo "🎬 동영상 자동 변환 파이프라인 배포 시작"

# 변수 설정
AWS_REGION="ap-northeast-2"
INPUT_BUCKET="video-input-$(date +%s)"
OUTPUT_BUCKET="video-output-$(date +%s)"
LAMBDA_FUNCTION_NAME="video-conversion-lambda"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "📋 설정 정보:"
echo "  - AWS 리전: $AWS_REGION"
echo "  - 입력 버킷: $INPUT_BUCKET"
echo "  - 출력 버킷: $OUTPUT_BUCKET"
echo "  - 계정 ID: $ACCOUNT_ID"

# 1. S3 버킷 생성
echo "📦 S3 버킷 생성 중..."
aws s3 mb s3://$INPUT_BUCKET --region $AWS_REGION
aws s3 mb s3://$OUTPUT_BUCKET --region $AWS_REGION

# 2. S3 EventBridge 알림 활성화
echo "🔔 S3 EventBridge 알림 활성화..."
aws s3api put-bucket-notification-configuration \
  --bucket $INPUT_BUCKET \
  --notification-configuration '{
    "EventBridgeConfiguration": {}
  }'

# 3. IAM 역할 생성 - Lambda 실행용
echo "🔐 IAM 역할 생성 중..."
aws iam create-role \
  --role-name VideoConversionLambdaRole \
  --assume-role-policy-document file://iam-policies/lambda-trust-policy.json

# Lambda 실행 정책 첨부
sed "s/your-input-video-bucket/$INPUT_BUCKET/g; s/your-converted-videos-bucket/$OUTPUT_BUCKET/g; s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" \
  iam-policies/lambda-execution-policy.json > /tmp/lambda-execution-policy.json

aws iam put-role-policy \
  --role-name VideoConversionLambdaRole \
  --policy-name VideoConversionLambdaPolicy \
  --policy-document file:///tmp/lambda-execution-policy.json

# 4. IAM 역할 생성 - MediaConvert 서비스용
aws iam create-role \
  --role-name MediaConvertServiceRole \
  --assume-role-policy-document file://iam-policies/mediaconvert-trust-policy.json

# MediaConvert 서비스 정책 첨부
sed "s/your-input-video-bucket/$INPUT_BUCKET/g; s/your-converted-videos-bucket/$OUTPUT_BUCKET/g" \
  iam-policies/mediaconvert-service-policy.json > /tmp/mediaconvert-service-policy.json

aws iam put-role-policy \
  --role-name MediaConvertServiceRole \
  --policy-name MediaConvertServicePolicy \
  --policy-document file:///tmp/mediaconvert-service-policy.json

# 5. Lambda 함수 코드 준비
echo "📝 Lambda 함수 코드 준비 중..."
sed "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g; s/your-converted-videos-bucket/$OUTPUT_BUCKET/g" \
  lambda_function.py > /tmp/lambda_function.py

# Lambda 배포 패키지 생성
cd /tmp
zip lambda_function.zip lambda_function.py
cd -

# 6. Lambda 함수 생성
echo "⚡ Lambda 함수 생성 중..."
sleep 10  # IAM 역할 전파 대기

aws lambda create-function \
  --function-name $LAMBDA_FUNCTION_NAME \
  --runtime python3.9 \
  --role arn:aws:iam::$ACCOUNT_ID:role/VideoConversionLambdaRole \
  --handler lambda_function.lambda_handler \
  --zip-file fileb:///tmp/lambda_function.zip \
  --timeout 300 \
  --environment Variables="{OUTPUT_BUCKET=$OUTPUT_BUCKET,MEDIACONVERT_ROLE_ARN=arn:aws:iam::$ACCOUNT_ID:role/MediaConvertServiceRole}"

# 7. EventBridge 규칙 생성
echo "📡 EventBridge 규칙 생성 중..."
sed "s/your-input-video-bucket/$INPUT_BUCKET/g; s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" \
  eventbridge-rule.json > /tmp/eventbridge-rule.json

aws events put-rule \
  --name S3VideoUploadRule \
  --event-pattern file:///tmp/eventbridge-rule.json \
  --state ENABLED

# 8. EventBridge 타겟 추가
aws events put-targets \
  --rule S3VideoUploadRule \
  --targets "Id"="1","Arn"="arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:function:$LAMBDA_FUNCTION_NAME"

# 9. Lambda 권한 추가 - EventBridge에서 호출 허용
aws lambda add-permission \
  --function-name $LAMBDA_FUNCTION_NAME \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:$AWS_REGION:$ACCOUNT_ID:rule/S3VideoUploadRule

echo "✅ 배포 완료!"
echo ""
echo "📋 배포된 리소스:"
echo "  - 입력 S3 버킷: s3://$INPUT_BUCKET"
echo "  - 출력 S3 버킷: s3://$OUTPUT_BUCKET"
echo "  - Lambda 함수: $LAMBDA_FUNCTION_NAME"
echo "  - EventBridge 규칙: S3VideoUploadRule"
echo ""
echo "🎬 사용 방법:"
echo "  1. s3://$INPUT_BUCKET 에 동영상 파일 업로드"
echo "  2. 자동으로 SD 변환 작업 시작"
echo "  3. 변환된 파일은 s3://$OUTPUT_BUCKET/converted/ 에 저장"
echo ""
echo "🔍 모니터링:"
echo "  - Lambda 로그: aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow"
echo "  - MediaConvert 작업: AWS 콘솔에서 확인"

# 임시 파일 정리
rm -f /tmp/lambda-execution-policy.json /tmp/mediaconvert-service-policy.json /tmp/lambda_function.py /tmp/lambda_function.zip /tmp/eventbridge-rule.json
