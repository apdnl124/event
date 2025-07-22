import json
import boto3
import os
import requests
from datetime import datetime

# AWS 클라이언트 초기화
s3_client = boto3.client('s3')

# 설정값
ANALYSIS_BUCKET = os.environ.get('ANALYSIS_BUCKET', 'your-analysis-bucket')
TWELVE_LABS_API_KEY = os.environ.get('TWELVE_LABS_API_KEY', 'your-api-key')
TWELVE_LABS_BASE_URL = 'https://api.twelvelabs.io/v1.2'

def lambda_handler(event, context):
    """
    Twelve Labs를 사용한 고급 동영상 분석 Lambda 함수
    - 장면별 상세 분석
    - 행동 및 활동 인식
    - 비디오 요약 생성
    - 시간대별 하이라이트 추출
    - 자연어 기반 비디오 검색 인덱싱
    """
    
    try:
        print(f"📊 Twelve Labs 분석 시작")
        
        # EventBridge에서 온 분석 요청 이벤트 파싱
        detail = event['detail']
        converted_files = detail['converted_files']
        mediaconvert_job_id = detail['mediaconvert_job_id']
        
        print(f"📹 분석할 파일들: {converted_files}")
        print(f"🎬 MediaConvert Job ID: {mediaconvert_job_id}")
        
        analysis_results = []
        
        for file_path in converted_files:
            print(f"📊 Twelve Labs 분석 시작: {file_path}")
            
            # 동영상 분석 수행
            file_analysis = analyze_video_with_twelvelabs(file_path)
            
            if file_analysis:
                analysis_results.append({
                    'file_path': file_path,
                    'analysis_type': 'twelvelabs',
                    'analysis_result': file_analysis,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # 분석 결과를 S3에 저장
        if analysis_results:
            result_saved = save_analysis_results(mediaconvert_job_id, analysis_results, 'twelvelabs')
            
            if result_saved:
                print(f"✅ Twelve Labs 분석 완료 및 결과 저장")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Twelve Labs 분석 완료',
                        'mediaconvert_job_id': mediaconvert_job_id,
                        'analyzed_files_count': len(analysis_results),
                        'analysis_type': 'twelvelabs'
                    })
                }
            else:
                print(f"⚠️ Twelve Labs 분석 완료, 결과 저장 실패")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Twelve Labs 분석 완료, 결과 저장 실패',
                        'mediaconvert_job_id': mediaconvert_job_id
                    })
                }
        else:
            print(f"❌ Twelve Labs 분석 결과 없음")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Twelve Labs 분석 결과 없음',
                    'mediaconvert_job_id': mediaconvert_job_id
                })
            }
            
    except Exception as e:
        print(f"❌ Twelve Labs 분석 오류: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'analysis_type': 'twelvelabs'
            })
        }

def analyze_video_with_twelvelabs(file_path):
    """Twelve Labs를 사용한 고급 동영상 분석"""
    
    try:
        headers = {
            'x-api-key': TWELVE_LABS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        analysis_result = {
            'video_indexing': None,
            'scene_analysis': None,
            'activity_recognition': None,
            'video_summary': None,
            'highlights': None,
            'search_index': None
        }
        
        # 1. 비디오 인덱싱 (업로드 및 처리)
        try:
            print(f"📤 비디오 인덱싱 시작...")
            
            # 인덱스 생성 (엔진 설정)
            index_data = {
                'engine_name': 'marengo2.6',  # Twelve Labs의 최신 엔진
                'engine_options': ['visual', 'conversation', 'text_in_video'],
                'index_name': f'video_analysis_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}'
            }
            
            index_response = requests.post(
                f'{TWELVE_LABS_BASE_URL}/indexes',
                headers=headers,
                json=index_data
            )
            
            if index_response.status_code == 201:
                index_id = index_response.json()['_id']
                print(f"✅ 인덱스 생성 완료: {index_id}")
                
                # 비디오 업로드
                video_data = {
                    'index_id': index_id,
                    'url': file_path,  # S3 URL
                    'transcription_file': None,
                    'disable_video_stream': False
                }
                
                upload_response = requests.post(
                    f'{TWELVE_LABS_BASE_URL}/tasks',
                    headers=headers,
                    json=video_data
                )
                
                if upload_response.status_code == 201:
                    task_id = upload_response.json()['_id']
                    print(f"📤 비디오 업로드 작업 ID: {task_id}")
                    
                    # 처리 완료 대기 (실제로는 웹훅 사용 권장)
                    import time
                    time.sleep(60)  # 실제 구현에서는 비동기 처리 권장
                    
                    # 처리 상태 확인
                    status_response = requests.get(
                        f'{TWELVE_LABS_BASE_URL}/tasks/{task_id}',
                        headers=headers
                    )
                    
                    if status_response.status_code == 200:
                        task_status = status_response.json()
                        analysis_result['video_indexing'] = task_status
                        print(f"✅ 비디오 인덱싱 완료")
                        
                        if task_status['status'] == 'ready':
                            video_id = task_status['video_id']
                            
                            # 2. 장면 분석
                            analysis_result['scene_analysis'] = get_scene_analysis(index_id, video_id, headers)
                            
                            # 3. 활동 인식
                            analysis_result['activity_recognition'] = get_activity_recognition(index_id, video_id, headers)
                            
                            # 4. 비디오 요약
                            analysis_result['video_summary'] = get_video_summary(index_id, video_id, headers)
                            
                            # 5. 하이라이트 추출
                            analysis_result['highlights'] = get_video_highlights(index_id, video_id, headers)
                            
                            # 6. 검색 인덱스 생성
                            analysis_result['search_index'] = create_search_index(index_id, video_id, headers)
            
        except Exception as e:
            print(f"⚠️ Twelve Labs 인덱싱 실패: {str(e)}")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ Twelve Labs 분석 실패: {str(e)}")
        return None

def get_scene_analysis(index_id, video_id, headers):
    """장면별 상세 분석"""
    try:
        print(f"🎬 장면 분석 시작...")
        
        search_data = {
            'query': 'Describe all scenes in detail',
            'index_id': index_id,
            'search_options': ['visual', 'conversation'],
            'filter': {
                'video_id': video_id
            }
        }
        
        response = requests.post(
            f'{TWELVE_LABS_BASE_URL}/search',
            headers=headers,
            json=search_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 장면 분석 완료")
            return result
        else:
            print(f"⚠️ 장면 분석 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 장면 분석 오류: {str(e)}")
        return None

def get_activity_recognition(index_id, video_id, headers):
    """행동 및 활동 인식"""
    try:
        print(f"🏃 활동 인식 시작...")
        
        search_data = {
            'query': 'What activities and actions are happening in the video?',
            'index_id': index_id,
            'search_options': ['visual'],
            'filter': {
                'video_id': video_id
            }
        }
        
        response = requests.post(
            f'{TWELVE_LABS_BASE_URL}/search',
            headers=headers,
            json=search_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 활동 인식 완료")
            return result
        else:
            print(f"⚠️ 활동 인식 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 활동 인식 오류: {str(e)}")
        return None

def get_video_summary(index_id, video_id, headers):
    """비디오 요약 생성"""
    try:
        print(f"📝 비디오 요약 시작...")
        
        summary_data = {
            'video_id': video_id,
            'type': 'summary'
        }
        
        response = requests.post(
            f'{TWELVE_LABS_BASE_URL}/summarize',
            headers=headers,
            json=summary_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 비디오 요약 완료")
            return result
        else:
            print(f"⚠️ 비디오 요약 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 비디오 요약 오류: {str(e)}")
        return None

def get_video_highlights(index_id, video_id, headers):
    """하이라이트 추출"""
    try:
        print(f"⭐ 하이라이트 추출 시작...")
        
        highlight_data = {
            'video_id': video_id,
            'type': 'highlight'
        }
        
        response = requests.post(
            f'{TWELVE_LABS_BASE_URL}/summarize',
            headers=headers,
            json=highlight_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 하이라이트 추출 완료")
            return result
        else:
            print(f"⚠️ 하이라이트 추출 실패: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 하이라이트 추출 오류: {str(e)}")
        return None

def create_search_index(index_id, video_id, headers):
    """검색 인덱스 생성"""
    try:
        print(f"🔍 검색 인덱스 생성 시작...")
        
        # 다양한 검색 쿼리로 인덱스 테스트
        search_queries = [
            'people in the video',
            'objects and items',
            'text and signs',
            'emotions and expressions',
            'locations and settings'
        ]
        
        search_results = {}
        
        for query in search_queries:
            search_data = {
                'query': query,
                'index_id': index_id,
                'search_options': ['visual', 'conversation', 'text_in_video'],
                'filter': {
                    'video_id': video_id
                }
            }
            
            response = requests.post(
                f'{TWELVE_LABS_BASE_URL}/search',
                headers=headers,
                json=search_data
            )
            
            if response.status_code == 200:
                search_results[query] = response.json()
        
        print(f"✅ 검색 인덱스 생성 완료")
        return search_results
        
    except Exception as e:
        print(f"❌ 검색 인덱스 생성 오류: {str(e)}")
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
