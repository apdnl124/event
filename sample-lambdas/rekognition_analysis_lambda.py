import json
import boto3
import os
from datetime import datetime
import urllib.parse

# AWS 클라이언트 초기화
rekognition_client = boto3.client('rekognition')
s3_client = boto3.client('s3')

# 설정값
ANALYSIS_BUCKET = os.environ.get('ANALYSIS_BUCKET', 'your-analysis-bucket')

def lambda_handler(event, context):
    """
    Rekognition을 사용한 동영상 분석 Lambda 함수
    - 객체 감지
    - 얼굴 인식 및 감정 분석
    - 텍스트 추출 (OCR)
    - 부적절한 콘텐츠 감지
    """
    
    try:
        print(f"🔍 Rekognition 분석 시작")
        
        # EventBridge에서 온 분석 요청 이벤트 파싱
        detail = event['detail']
        converted_files = detail['converted_files']
        mediaconvert_job_id = detail['mediaconvert_job_id']
        
        print(f"📹 분석할 파일들: {converted_files}")
        print(f"🎬 MediaConvert Job ID: {mediaconvert_job_id}")
        
        analysis_results = []
        
        for file_path in converted_files:
            # S3 경로에서 버킷과 키 추출
            if file_path.startswith('s3://'):
                path_parts = file_path.replace('s3://', '').split('/', 1)
                bucket_name = path_parts[0]
                object_key = path_parts[1] if len(path_parts) > 1 else ''
            else:
                print(f"⚠️ 잘못된 S3 경로 형식: {file_path}")
                continue
            
            print(f"🔍 Rekognition 분석 시작: s3://{bucket_name}/{object_key}")
            
            # 동영상 분석 수행
            file_analysis = analyze_video_with_rekognition(bucket_name, object_key)
            
            if file_analysis:
                analysis_results.append({
                    'file_path': file_path,
                    'analysis_type': 'rekognition',
                    'analysis_result': file_analysis,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # 분석 결과를 S3에 저장
        if analysis_results:
            result_saved = save_analysis_results(mediaconvert_job_id, analysis_results, 'rekognition')
            
            if result_saved:
                print(f"✅ Rekognition 분석 완료 및 결과 저장")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Rekognition 분석 완료',
                        'mediaconvert_job_id': mediaconvert_job_id,
                        'analyzed_files_count': len(analysis_results),
                        'analysis_type': 'rekognition'
                    })
                }
            else:
                print(f"⚠️ Rekognition 분석 완료, 결과 저장 실패")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Rekognition 분석 완료, 결과 저장 실패',
                        'mediaconvert_job_id': mediaconvert_job_id
                    })
                }
        else:
            print(f"❌ Rekognition 분석 결과 없음")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Rekognition 분석 결과 없음',
                    'mediaconvert_job_id': mediaconvert_job_id
                })
            }
            
    except Exception as e:
        print(f"❌ Rekognition 분석 오류: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'analysis_type': 'rekognition'
            })
        }

def analyze_video_with_rekognition(bucket_name, object_key):
    """Rekognition을 사용한 동영상 분석"""
    
    try:
        analysis_result = {
            'labels': [],
            'faces': [],
            'text': [],
            'moderation': [],
            'celebrities': []
        }
        
        # 1. 라벨 감지 (객체, 장면, 활동 등)
        try:
            print(f"🏷️ 라벨 감지 시작...")
            label_response = rekognition_client.start_label_detection(
                Video={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                },
                MinConfidence=70.0,
                Features=['GENERAL_LABELS']
            )
            
            job_id = label_response['JobId']
            print(f"🏷️ 라벨 감지 작업 ID: {job_id}")
            
            # 작업 완료 대기 (실제로는 비동기 처리 권장)
            import time
            time.sleep(30)  # 실제 구현에서는 SQS나 SNS 사용 권장
            
            # 결과 조회
            label_result = rekognition_client.get_label_detection(JobId=job_id)
            
            if label_result['JobStatus'] == 'SUCCEEDED':
                analysis_result['labels'] = label_result.get('Labels', [])
                print(f"✅ 라벨 감지 완료: {len(analysis_result['labels'])}개 라벨")
            
        except Exception as e:
            print(f"⚠️ 라벨 감지 실패: {str(e)}")
        
        # 2. 얼굴 감지
        try:
            print(f"👤 얼굴 감지 시작...")
            face_response = rekognition_client.start_face_detection(
                Video={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                },
                FaceAttributes='ALL'
            )
            
            job_id = face_response['JobId']
            print(f"👤 얼굴 감지 작업 ID: {job_id}")
            
            time.sleep(30)
            
            face_result = rekognition_client.get_face_detection(JobId=job_id)
            
            if face_result['JobStatus'] == 'SUCCEEDED':
                analysis_result['faces'] = face_result.get('Faces', [])
                print(f"✅ 얼굴 감지 완료: {len(analysis_result['faces'])}개 얼굴")
            
        except Exception as e:
            print(f"⚠️ 얼굴 감지 실패: {str(e)}")
        
        # 3. 텍스트 감지
        try:
            print(f"📝 텍스트 감지 시작...")
            text_response = rekognition_client.start_text_detection(
                Video={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                }
            )
            
            job_id = text_response['JobId']
            print(f"📝 텍스트 감지 작업 ID: {job_id}")
            
            time.sleep(30)
            
            text_result = rekognition_client.get_text_detection(JobId=job_id)
            
            if text_result['JobStatus'] == 'SUCCEEDED':
                analysis_result['text'] = text_result.get('TextDetections', [])
                print(f"✅ 텍스트 감지 완료: {len(analysis_result['text'])}개 텍스트")
            
        except Exception as e:
            print(f"⚠️ 텍스트 감지 실패: {str(e)}")
        
        # 4. 부적절한 콘텐츠 감지
        try:
            print(f"🚫 콘텐츠 조정 감지 시작...")
            moderation_response = rekognition_client.start_content_moderation(
                Video={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                },
                MinConfidence=60.0
            )
            
            job_id = moderation_response['JobId']
            print(f"🚫 콘텐츠 조정 작업 ID: {job_id}")
            
            time.sleep(30)
            
            moderation_result = rekognition_client.get_content_moderation(JobId=job_id)
            
            if moderation_result['JobStatus'] == 'SUCCEEDED':
                analysis_result['moderation'] = moderation_result.get('ModerationLabels', [])
                print(f"✅ 콘텐츠 조정 완료: {len(analysis_result['moderation'])}개 항목")
            
        except Exception as e:
            print(f"⚠️ 콘텐츠 조정 실패: {str(e)}")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ Rekognition 분석 실패: {str(e)}")
        return None

def save_analysis_results(job_id, analysis_results, analysis_type):
    """분석 결과를 S3에 저장"""
    
    try:
        # 결과 파일 경로 생성
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        result_key = f"analysis/{analysis_type}/{job_id}_{timestamp}_results.json"
        
        # 결과 데이터 준비
        result_data = {
            'mediaconvert_job_id': job_id,
            'analysis_type': analysis_type,
            'timestamp': datetime.utcnow().isoformat(),
            'results': analysis_results
        }
        
        # S3에 저장
        s3_client.put_object(
            Bucket=ANALYSIS_BUCKET,
            Key=result_key,
            Body=json.dumps(result_data, indent=2),
            ContentType='application/json'
        )
        
        print(f"💾 분석 결과 저장 완료: s3://{ANALYSIS_BUCKET}/{result_key}")
        return True
        
    except Exception as e:
        print(f"❌ 분석 결과 저장 실패: {str(e)}")
        return False
