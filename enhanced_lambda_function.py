import json
import boto3
import uuid
from datetime import datetime
import urllib.parse
import os

# AWS 클라이언트 초기화
s3_client = boto3.client('s3')
mediaconvert_client = boto3.client('mediaconvert')
events_client = boto3.client('events')  # EventBridge 클라이언트 추가

# 설정값
MEDIACONVERT_ROLE_ARN = os.environ.get('MEDIACONVERT_ROLE_ARN', 'arn:aws:iam::YOUR_ACCOUNT_ID:role/MediaConvertServiceRole')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'your-converted-videos-bucket')
ANALYSIS_BUCKET = os.environ.get('ANALYSIS_BUCKET', 'your-analysis-bucket')
MEDIACONVERT_ENDPOINT = None  # 런타임에 설정

# 지원하는 입력 동영상 포맷 (모두 MP4로 변환됨)
SUPPORTED_VIDEO_FORMATS = {
    '.mp4': 'MP4',
    '.mov': 'QuickTime',
    '.avi': 'AVI',
    '.mkv': 'Matroska',
    '.wmv': 'Windows Media',
    '.flv': 'Flash Video',
    '.webm': 'WebM',
    '.m4v': 'iTunes Video',
    '.3gp': '3GPP',
    '.mts': 'AVCHD',
    '.m2ts': 'Blu-ray',
    '.vob': 'DVD Video'
}

def lambda_handler(event, context):
    """
    S3 업로드 이벤트를 받아서 MediaConvert로 MP4 변환 작업을 시작하는 Lambda 함수
    변환 완료 후 EventBridge를 통해 분석 Lambda들을 트리거합니다.
    """
    
    try:
        # EventBridge에서 온 이벤트 타입 확인
        if 'source' in event and event['source'] == 'aws.mediaconvert':
            # MediaConvert 완료 이벤트 처리
            return handle_mediaconvert_completion(event, context)
        else:
            # S3 업로드 이벤트 처리
            return handle_s3_upload(event, context)
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def handle_s3_upload(event, context):
    """S3 업로드 이벤트 처리 - 동영상 변환 시작"""
    
    try:
        # EventBridge에서 온 S3 이벤트 파싱
        detail = event['detail']
        bucket_name = detail['bucket']['name']
        object_key = urllib.parse.unquote_plus(detail['object']['key'])
        
        print(f"🎬 처리할 파일: s3://{bucket_name}/{object_key}")
        
        # 동영상 파일인지 확인
        input_format = get_video_format(object_key)
        if not input_format:
            print(f"❌ 지원하지 않는 파일 형식: {object_key}")
            return {
                'statusCode': 200,
                'body': json.dumps('지원하지 않는 동영상 파일이므로 처리하지 않음')
            }
        
        print(f"📹 입력 포맷: {input_format} → 출력 포맷: MP4")
        
        # MediaConvert 엔드포인트 설정
        setup_mediaconvert_endpoint()
        
        # MediaConvert 작업 생성 (항상 MP4로 변환)
        job_id = create_mp4_conversion_job(bucket_name, object_key, input_format)
        
        if job_id:
            print(f"✅ MediaConvert 작업 생성 성공: {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'{input_format}을 MP4로 변환 작업이 시작되었습니다',
                    'job_id': job_id,
                    'input_file': f"s3://{bucket_name}/{object_key}",
                    'input_format': input_format,
                    'output_format': 'MP4'
                })
            }
        else:
            raise Exception("MediaConvert 작업 생성 실패")
            
    except Exception as e:
        print(f"❌ S3 업로드 처리 오류: {str(e)}")
        raise

def handle_mediaconvert_completion(event, context):
    """MediaConvert 완료 이벤트 처리 - 분석 Lambda들 트리거"""
    
    try:
        detail = event['detail']
        job_status = detail['status']
        job_id = detail['jobId']
        
        print(f"🎬 MediaConvert 작업 상태: {job_status} (Job ID: {job_id})")
        
        if job_status == 'COMPLETE':
            # 변환 완료된 파일 정보 추출
            output_files = []
            if 'outputGroupDetails' in detail:
                for group in detail['outputGroupDetails']:
                    if 'outputDetails' in group:
                        for output in group['outputDetails']:
                            if 'outputFilePaths' in output:
                                output_files.extend(output['outputFilePaths'])
            
            print(f"📁 변환 완료된 파일들: {output_files}")
            
            # 분석 Lambda들을 위한 EventBridge 이벤트 발송
            analysis_event_sent = send_analysis_trigger_event(job_id, output_files, detail)
            
            if analysis_event_sent:
                print(f"✅ 분석 트리거 이벤트 발송 완료")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': '동영상 변환 완료 및 분석 작업 시작',
                        'job_id': job_id,
                        'output_files': output_files,
                        'analysis_triggered': True
                    })
                }
            else:
                print(f"⚠️ 분석 트리거 이벤트 발송 실패")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': '동영상 변환 완료, 분석 트리거 실패',
                        'job_id': job_id,
                        'output_files': output_files,
                        'analysis_triggered': False
                    })
                }
        
        elif job_status == 'ERROR':
            print(f"❌ MediaConvert 작업 실패: {job_id}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': f'MediaConvert 작업 실패: {job_id}',
                    'job_id': job_id
                })
            }
        
        else:
            print(f"ℹ️ MediaConvert 작업 진행 중: {job_status}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'MediaConvert 작업 진행 중: {job_status}',
                    'job_id': job_id
                })
            }
            
    except Exception as e:
        print(f"❌ MediaConvert 완료 처리 오류: {str(e)}")
        raise

def send_analysis_trigger_event(job_id, output_files, mediaconvert_detail):
    """분석 Lambda들을 트리거하기 위한 EventBridge 이벤트 발송"""
    
    try:
        # 분석용 커스텀 이벤트 생성
        analysis_event = {
            'Source': 'custom.video-pipeline',
            'DetailType': 'Video Analysis Required',
            'Detail': json.dumps({
                'mediaconvert_job_id': job_id,
                'converted_files': output_files,
                'analysis_bucket': ANALYSIS_BUCKET,
                'timestamp': datetime.utcnow().isoformat(),
                'original_mediaconvert_detail': mediaconvert_detail,
                'analysis_types': ['rekognition', 'twelvelabs', 'transcribe']
            })
        }
        
        # EventBridge로 이벤트 발송
        response = events_client.put_events(
            Entries=[analysis_event]
        )
        
        print(f"📡 분석 트리거 이벤트 발송: {response}")
        
        # 발송 성공 여부 확인
        if response['FailedEntryCount'] == 0:
            print(f"✅ 분석 트리거 이벤트 발송 성공")
            return True
        else:
            print(f"❌ 분석 트리거 이벤트 발송 실패: {response['Entries']}")
            return False
            
    except Exception as e:
        print(f"❌ 분석 트리거 이벤트 발송 오류: {str(e)}")
        return False

def get_video_format(file_key):
    """동영상 파일 포맷 확인 및 반환"""
    file_extension = os.path.splitext(file_key.lower())[1]
    return SUPPORTED_VIDEO_FORMATS.get(file_extension)

def setup_mediaconvert_endpoint():
    """MediaConvert 엔드포인트 설정"""
    global mediaconvert_client, MEDIACONVERT_ENDPOINT
    
    if not MEDIACONVERT_ENDPOINT:
        try:
            response = mediaconvert_client.describe_endpoints()
            MEDIACONVERT_ENDPOINT = response['Endpoints'][0]['Url']
            mediaconvert_client = boto3.client('mediaconvert', endpoint_url=MEDIACONVERT_ENDPOINT)
            print(f"🔗 MediaConvert 엔드포인트 설정: {MEDIACONVERT_ENDPOINT}")
        except Exception as e:
            print(f"❌ MediaConvert 엔드포인트 설정 실패: {e}")
            raise

def create_mp4_conversion_job(input_bucket, input_key, input_format):
    """MediaConvert 작업 생성 - 모든 입력 포맷을 MP4로 변환"""
    
    # 파일명에서 확장자 분리
    file_name = input_key.split('/')[-1]
    name_without_ext = os.path.splitext(file_name)[0]
    
    # 입력 및 출력 경로 설정
    input_path = f"s3://{input_bucket}/{input_key}"
    output_path = f"s3://{OUTPUT_BUCKET}/converted/"
    
    print(f"📁 입력: {input_path}")
    print(f"📁 출력: {output_path}{name_without_ext}_converted.mp4")
    
    # 작업 설정 - 항상 MP4로 출력
    job_settings = {
        "Role": MEDIACONVERT_ROLE_ARN,
        "Settings": {
            "Inputs": [
                {
                    "FileInput": input_path,
                    "AudioSelectors": {
                        "Audio Selector 1": {
                            "DefaultSelection": "DEFAULT"
                        }
                    },
                    "VideoSelector": {},
                    "TimecodeSource": "ZEROBASED"
                }
            ],
            "OutputGroups": [
                {
                    "Name": f"{input_format}_to_MP4_Conversion",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": output_path,
                            "DestinationSettings": {
                                "S3Settings": {
                                    "StorageClass": "STANDARD"
                                }
                            }
                        }
                    },
                    "Outputs": [
                        {
                            "NameModifier": "_converted",
                            "VideoDescription": {
                                "Width": 720,
                                "Height": 480,
                                "ScalingBehavior": "DEFAULT",
                                "TimecodeInsertion": "DISABLED",
                                "AntiAlias": "ENABLED",
                                "Sharpness": 50,
                                "CodecSettings": {
                                    "Codec": "H_264",
                                    "H264Settings": {
                                        "InterlaceMode": "PROGRESSIVE",
                                        "NumberReferenceFrames": 3,
                                        "Syntax": "DEFAULT",
                                        "Softness": 0,
                                        "GopClosedCadence": 1,
                                        "GopSize": 90,
                                        "Slices": 1,
                                        "GopBReference": "DISABLED",
                                        "SlowPal": "DISABLED",
                                        "SpatialAdaptiveQuantization": "ENABLED",
                                        "TemporalAdaptiveQuantization": "ENABLED",
                                        "FlickerAdaptiveQuantization": "DISABLED",
                                        "EntropyEncoding": "CABAC",
                                        "Bitrate": 2000000,
                                        "FramerateControl": "INITIALIZE_FROM_SOURCE",
                                        "RateControlMode": "CBR",
                                        "CodecProfile": "MAIN",
                                        "Telecine": "NONE",
                                        "MinIInterval": 0,
                                        "AdaptiveQuantization": "HIGH",
                                        "CodecLevel": "AUTO",
                                        "FieldEncoding": "PAFF",
                                        "SceneChangeDetect": "ENABLED",
                                        "QualityTuningLevel": "SINGLE_PASS",
                                        "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                                        "UnregisteredSeiTimecode": "DISABLED",
                                        "GopSizeUnits": "FRAMES",
                                        "ParControl": "INITIALIZE_FROM_SOURCE",
                                        "NumberBFramesBetweenReferenceFrames": 2,
                                        "RepeatPps": "DISABLED"
                                    }
                                }
                            },
                            "AudioDescriptions": [
                                {
                                    "AudioTypeControl": "FOLLOW_INPUT",
                                    "AudioSourceName": "Audio Selector 1",
                                    "CodecSettings": {
                                        "Codec": "AAC",
                                        "AacSettings": {
                                            "AudioDescriptionBroadcasterMix": "NORMAL",
                                            "Bitrate": 128000,
                                            "RateControlMode": "CBR",
                                            "CodecProfile": "LC",
                                            "CodingMode": "CODING_MODE_2_0",
                                            "RawFormat": "NONE",
                                            "SampleRate": 48000,
                                            "Specification": "MPEG4"
                                        }
                                    },
                                    "LanguageCodeControl": "FOLLOW_INPUT"
                                }
                            ],
                            "ContainerSettings": {
                                "Container": "MP4",
                                "Mp4Settings": {
                                    "CslgAtom": "INCLUDE",
                                    "FreeSpaceBox": "EXCLUDE",
                                    "MoovPlacement": "PROGRESSIVE_DOWNLOAD",
                                    "Mp4MajorBrand": "isom"
                                }
                            }
                        }
                    ]
                }
            ],
            "AdAvailOffset": 0,
            "TimecodeConfig": {
                "Source": "ZEROBASED"
            }
        },
        "AccelerationSettings": {
            "Mode": "DISABLED"
        },
        "StatusUpdateInterval": "SECONDS_60",
        "Priority": 0,
        "UserMetadata": {
            "InputFormat": input_format,
            "OutputFormat": "MP4",
            "ConversionType": "Format_Standardization",
            "AnalysisRequired": "true"
        }
    }
    
    try:
        # 작업 생성
        response = mediaconvert_client.create_job(**job_settings)
        job_id = response['Job']['Id']
        
        print(f"🎬 MediaConvert 작업 생성됨: {job_id}")
        print(f"📹 변환: {input_format} → MP4")
        print(f"📊 설정: 720x480, H.264, AAC, 2Mbps")
        
        return job_id
        
    except Exception as e:
        print(f"❌ MediaConvert 작업 생성 실패: {e}")
        return None
