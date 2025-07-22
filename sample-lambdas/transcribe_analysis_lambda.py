import json
import boto3
import os
from datetime import datetime
import time

# AWS 클라이언트 초기화
transcribe_client = boto3.client('transcribe')
s3_client = boto3.client('s3')

# 설정값
ANALYSIS_BUCKET = os.environ.get('ANALYSIS_BUCKET', 'your-analysis-bucket')

def lambda_handler(event, context):
    """
    AWS Transcribe를 사용한 음성 텍스트 변환 Lambda 함수
    - 음성을 텍스트로 변환
    - 화자 구분 (Speaker Diarization)
    - 타임스탬프 포함 자막 생성
    - 다국어 지원
    - 키워드 및 구문 감지
    """
    
    try:
        print(f"🎤 Transcribe 분석 시작")
        
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
            
            print(f"🎤 Transcribe 분석 시작: s3://{bucket_name}/{object_key}")
            
            # 음성 텍스트 변환 수행
            file_analysis = analyze_audio_with_transcribe(bucket_name, object_key)
            
            if file_analysis:
                analysis_results.append({
                    'file_path': file_path,
                    'analysis_type': 'transcribe',
                    'analysis_result': file_analysis,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # 분석 결과를 S3에 저장
        if analysis_results:
            result_saved = save_analysis_results(mediaconvert_job_id, analysis_results, 'transcribe')
            
            if result_saved:
                print(f"✅ Transcribe 분석 완료 및 결과 저장")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Transcribe 분석 완료',
                        'mediaconvert_job_id': mediaconvert_job_id,
                        'analyzed_files_count': len(analysis_results),
                        'analysis_type': 'transcribe'
                    })
                }
            else:
                print(f"⚠️ Transcribe 분석 완료, 결과 저장 실패")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Transcribe 분석 완료, 결과 저장 실패',
                        'mediaconvert_job_id': mediaconvert_job_id
                    })
                }
        else:
            print(f"❌ Transcribe 분석 결과 없음")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Transcribe 분석 결과 없음',
                    'mediaconvert_job_id': mediaconvert_job_id
                })
            }
            
    except Exception as e:
        print(f"❌ Transcribe 분석 오류: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'analysis_type': 'transcribe'
            })
        }

def analyze_audio_with_transcribe(bucket_name, object_key):
    """AWS Transcribe를 사용한 음성 텍스트 변환"""
    
    try:
        analysis_result = {
            'transcription': None,
            'speaker_diarization': None,
            'language_identification': None,
            'content_redaction': None,
            'custom_vocabulary': None,
            'subtitle_files': []
        }
        
        # 작업 이름 생성
        job_name = f"transcribe-job-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{object_key.replace('/', '-').replace('.', '-')}"
        
        # 미디어 파일 URI
        media_uri = f"s3://{bucket_name}/{object_key}"
        
        # 1. 기본 음성 텍스트 변환
        try:
            print(f"📝 기본 음성 텍스트 변환 시작...")
            
            transcribe_response = transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={
                    'MediaFileUri': media_uri
                },
                MediaFormat='mp4',  # 변환된 파일은 MP4
                LanguageCode='ko-KR',  # 한국어 기본, 자동 감지도 가능
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 10,
                    'ShowAlternatives': True,
                    'MaxAlternatives': 3,
                    'VocabularyFilterMethod': 'mask'
                },
                OutputBucketName=ANALYSIS_BUCKET,
                OutputKey=f"transcribe/{job_name}/",
                Subtitles={
                    'Formats': ['vtt', 'srt'],
                    'OutputStartIndex': 1
                }
            )
            
            print(f"📝 Transcribe 작업 시작: {job_name}")
            
            # 작업 완료 대기
            max_wait_time = 600  # 10분 최대 대기
            wait_time = 0
            
            while wait_time < max_wait_time:
                time.sleep(30)
                wait_time += 30
                
                # 작업 상태 확인
                job_status = transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )
                
                status = job_status['TranscriptionJob']['TranscriptionJobStatus']
                print(f"📝 Transcribe 작업 상태: {status}")
                
                if status == 'COMPLETED':
                    # 결과 처리
                    transcript_uri = job_status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                    
                    # 자막 파일 URI들
                    if 'Subtitles' in job_status['TranscriptionJob']:
                        subtitle_files = job_status['TranscriptionJob']['Subtitles']['SubtitleFileUris']
                        analysis_result['subtitle_files'] = subtitle_files
                        print(f"📄 자막 파일 생성: {len(subtitle_files)}개")
                    
                    # 전사 결과 다운로드
                    transcript_content = download_transcript_result(transcript_uri)
                    analysis_result['transcription'] = transcript_content
                    
                    print(f"✅ 기본 음성 텍스트 변환 완료")
                    break
                    
                elif status == 'FAILED':
                    failure_reason = job_status['TranscriptionJob'].get('FailureReason', 'Unknown error')
                    print(f"❌ Transcribe 작업 실패: {failure_reason}")
                    break
            
            # 작업 정리
            try:
                transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                print(f"🗑️ Transcribe 작업 정리 완료")
            except Exception as e:
                print(f"⚠️ Transcribe 작업 정리 실패: {str(e)}")
            
        except Exception as e:
            print(f"⚠️ 기본 음성 텍스트 변환 실패: {str(e)}")
        
        # 2. 언어 식별 (다국어 지원)
        try:
            print(f"🌐 언어 식별 시작...")
            
            lang_job_name = f"{job_name}-lang-id"
            
            lang_response = transcribe_client.start_transcription_job(
                TranscriptionJobName=lang_job_name,
                Media={
                    'MediaFileUri': media_uri
                },
                MediaFormat='mp4',
                IdentifyLanguage=True,
                LanguageOptions=['ko-KR', 'en-US', 'ja-JP', 'zh-CN'],
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 5
                }
            )
            
            # 언어 식별 결과 대기
            time.sleep(60)
            
            lang_job_status = transcribe_client.get_transcription_job(
                TranscriptionJobName=lang_job_name
            )
            
            if lang_job_status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                identified_language = lang_job_status['TranscriptionJob'].get('IdentifiedLanguageScore')
                analysis_result['language_identification'] = identified_language
                print(f"✅ 언어 식별 완료")
            
            # 정리
            try:
                transcribe_client.delete_transcription_job(TranscriptionJobName=lang_job_name)
            except:
                pass
            
        except Exception as e:
            print(f"⚠️ 언어 식별 실패: {str(e)}")
        
        # 3. 콘텐츠 편집 (민감한 정보 마스킹)
        try:
            print(f"🔒 콘텐츠 편집 시작...")
            
            redaction_job_name = f"{job_name}-redaction"
            
            redaction_response = transcribe_client.start_transcription_job(
                TranscriptionJobName=redaction_job_name,
                Media={
                    'MediaFileUri': media_uri
                },
                MediaFormat='mp4',
                LanguageCode='ko-KR',
                ContentRedaction={
                    'RedactionType': 'PII',
                    'RedactionOutput': 'redacted_and_unredacted'
                },
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 5
                }
            )
            
            # 콘텐츠 편집 결과 대기
            time.sleep(60)
            
            redaction_job_status = transcribe_client.get_transcription_job(
                TranscriptionJobName=redaction_job_name
            )
            
            if redaction_job_status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                redacted_transcript_uri = redaction_job_status['TranscriptionJob']['Transcript']['RedactedTranscriptFileUri']
                redacted_content = download_transcript_result(redacted_transcript_uri)
                analysis_result['content_redaction'] = redacted_content
                print(f"✅ 콘텐츠 편집 완료")
            
            # 정리
            try:
                transcribe_client.delete_transcription_job(TranscriptionJobName=redaction_job_name)
            except:
                pass
            
        except Exception as e:
            print(f"⚠️ 콘텐츠 편집 실패: {str(e)}")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ Transcribe 분석 실패: {str(e)}")
        return None

def download_transcript_result(transcript_uri):
    """전사 결과 파일 다운로드"""
    
    try:
        import urllib.request
        
        with urllib.request.urlopen(transcript_uri) as response:
            transcript_data = json.loads(response.read().decode('utf-8'))
        
        # 전사 결과 정리
        processed_result = {
            'full_transcript': transcript_data.get('results', {}).get('transcripts', [{}])[0].get('transcript', ''),
            'items': transcript_data.get('results', {}).get('items', []),
            'speaker_labels': transcript_data.get('results', {}).get('speaker_labels', {}),
            'job_name': transcript_data.get('jobName'),
            'account_id': transcript_data.get('accountId'),
            'status': transcript_data.get('status')
        }
        
        return processed_result
        
    except Exception as e:
        print(f"❌ 전사 결과 다운로드 실패: {str(e)}")
        return None

def create_custom_subtitle_file(transcript_data, format_type='srt'):
    """커스텀 자막 파일 생성"""
    
    try:
        if format_type == 'srt':
            return create_srt_subtitle(transcript_data)
        elif format_type == 'vtt':
            return create_vtt_subtitle(transcript_data)
        else:
            return None
            
    except Exception as e:
        print(f"❌ 자막 파일 생성 실패: {str(e)}")
        return None

def create_srt_subtitle(transcript_data):
    """SRT 형식 자막 생성"""
    
    try:
        srt_content = []
        items = transcript_data.get('items', [])
        
        subtitle_index = 1
        current_sentence = []
        start_time = None
        
        for item in items:
            if item['type'] == 'pronunciation':
                if start_time is None:
                    start_time = float(item['start_time'])
                
                current_sentence.append(item['alternatives'][0]['content'])
                
                # 문장 끝 감지 (마침표, 물음표, 느낌표)
                if item['alternatives'][0]['content'] in ['.', '?', '!']:
                    end_time = float(item['end_time'])
                    
                    # 시간 형식 변환
                    start_srt = seconds_to_srt_time(start_time)
                    end_srt = seconds_to_srt_time(end_time)
                    
                    # SRT 항목 생성
                    srt_content.append(f"{subtitle_index}")
                    srt_content.append(f"{start_srt} --> {end_srt}")
                    srt_content.append(" ".join(current_sentence))
                    srt_content.append("")
                    
                    subtitle_index += 1
                    current_sentence = []
                    start_time = None
        
        return "\n".join(srt_content)
        
    except Exception as e:
        print(f"❌ SRT 자막 생성 실패: {str(e)}")
        return None

def seconds_to_srt_time(seconds):
    """초를 SRT 시간 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

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
        
        # 자막 파일들도 별도 저장
        for result in analysis_results:
            if 'subtitle_files' in result['analysis_result'] and result['analysis_result']['subtitle_files']:
                for subtitle_uri in result['analysis_result']['subtitle_files']:
                    try:
                        # 자막 파일 다운로드 및 재저장
                        subtitle_filename = subtitle_uri.split('/')[-1]
                        subtitle_key = f"analysis/{analysis_type}/subtitles/{job_id}_{subtitle_filename}"
                        
                        import urllib.request
                        with urllib.request.urlopen(subtitle_uri) as response:
                            subtitle_content = response.read()
                        
                        s3_client.put_object(
                            Bucket=ANALYSIS_BUCKET,
                            Key=subtitle_key,
                            Body=subtitle_content,
                            ContentType='text/plain'
                        )
                        
                        print(f"📄 자막 파일 저장: s3://{ANALYSIS_BUCKET}/{subtitle_key}")
                        
                    except Exception as e:
                        print(f"⚠️ 자막 파일 저장 실패: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 분석 결과 저장 실패: {str(e)}")
        return False
