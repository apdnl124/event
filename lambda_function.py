import json
import boto3
import uuid
from datetime import datetime
import urllib.parse

# AWS 클라이언트 초기화
s3_client = boto3.client('s3')
mediaconvert_client = boto3.client('mediaconvert')

# 설정값
MEDIACONVERT_ROLE_ARN = 'arn:aws:iam::YOUR_ACCOUNT_ID:role/MediaConvertServiceRole'
OUTPUT_BUCKET = 'your-converted-videos-bucket'
MEDIACONVERT_ENDPOINT = None  # 런타임에 설정

def lambda_handler(event, context):
    """
    S3 업로드 이벤트를 받아서 MediaConvert로 SD 변환 작업을 시작하는 Lambda 함수
    """
    
    try:
        # EventBridge에서 온 S3 이벤트 파싱
        detail = event['detail']
        bucket_name = detail['bucket']['name']
        object_key = urllib.parse.unquote_plus(detail['object']['key'])
        
        print(f"처리할 파일: s3://{bucket_name}/{object_key}")
        
        # 동영상 파일인지 확인
        if not is_video_file(object_key):
            print(f"동영상 파일이 아님: {object_key}")
            return {
                'statusCode': 200,
                'body': json.dumps('동영상 파일이 아니므로 처리하지 않음')
            }
        
        # MediaConvert 엔드포인트 설정
        setup_mediaconvert_endpoint()
        
        # MediaConvert 작업 생성
        job_id = create_mediaconvert_job(bucket_name, object_key)
        
        if job_id:
            print(f"MediaConvert 작업 생성 성공: {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'MediaConvert 작업이 시작되었습니다',
                    'job_id': job_id,
                    'input_file': f"s3://{bucket_name}/{object_key}"
                })
            }
        else:
            raise Exception("MediaConvert 작업 생성 실패")
            
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def is_video_file(file_key):
    """동영상 파일 확장자 확인"""
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v']
    return any(file_key.lower().endswith(ext) for ext in video_extensions)

def setup_mediaconvert_endpoint():
    """MediaConvert 엔드포인트 설정"""
    global mediaconvert_client, MEDIACONVERT_ENDPOINT
    
    if not MEDIACONVERT_ENDPOINT:
        try:
            response = mediaconvert_client.describe_endpoints()
            MEDIACONVERT_ENDPOINT = response['Endpoints'][0]['Url']
            mediaconvert_client = boto3.client('mediaconvert', endpoint_url=MEDIACONVERT_ENDPOINT)
            print(f"MediaConvert 엔드포인트 설정: {MEDIACONVERT_ENDPOINT}")
        except Exception as e:
            print(f"MediaConvert 엔드포인트 설정 실패: {e}")
            raise

def create_mediaconvert_job(input_bucket, input_key):
    """MediaConvert 작업 생성 - FHD를 SD로 변환"""
    
    # 파일명에서 확장자 분리
    file_name = input_key.split('/')[-1]
    name_without_ext = file_name.rsplit('.', 1)[0]
    
    # 입력 및 출력 경로 설정
    input_path = f"s3://{input_bucket}/{input_key}"
    output_path = f"s3://{OUTPUT_BUCKET}/converted/"
    
    # 작업 설정
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
                    "Name": "SD_Conversion",
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
                            "NameModifier": "_SD",
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
                                    "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
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
        "Priority": 0
    }
    
    try:
        # 작업 생성
        response = mediaconvert_client.create_job(**job_settings)
        job_id = response['Job']['Id']
        
        print(f"MediaConvert 작업 생성됨: {job_id}")
        print(f"입력: {input_path}")
        print(f"출력: {output_path}")
        
        return job_id
        
    except Exception as e:
        print(f"MediaConvert 작업 생성 실패: {e}")
        return None
