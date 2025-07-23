import json
import boto3
import uuid
from datetime import datetime
import urllib.parse
import os

# AWS 클라이언트 초기화
s3_client = boto3.client('s3')
mediaconvert_client = boto3.client('mediaconvert')

# 설정값
MEDIACONVERT_ROLE_ARN = os.environ.get('MEDIACONVERT_ROLE_ARN')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')
MEDIACONVERT_ENDPOINT = None  # 런타임에 설정

# 지원하는 입력 동영상 포맷
SUPPORTED_VIDEO_FORMATS = {
    '.mp4': 'MP4',
    '.mov': 'QuickTime',
    '.avi': 'AVI',
    '.mkv': 'Matroska',
    '.wmv': 'Windows Media',
    '.flv': 'Flash Video',
    '.webm': 'WebM',
    '.m4v': 'iTunes Video'
}

def lambda_handler(event, context):
    """
    S3 업로드 이벤트를 받아서 MediaConvert로 SD 변환 작업을 시작하는 Lambda 함수
    비용 최적화를 위해 분석 기능은 제거됨
    """
    
    try:
        print(f"🎬 동영상 변환 Lambda 시작")
        print(f"📥 받은 이벤트: {json.dumps(event, indent=2)}")
        
        # EventBridge에서 온 S3 이벤트 파싱
        if 'detail' in event and 'bucket' in event['detail']:
            # EventBridge S3 이벤트
            bucket_name = event['detail']['bucket']['name']
            object_key = urllib.parse.unquote_plus(event['detail']['object']['key'])
        else:
            print("❌ 지원하지 않는 이벤트 형식")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': '지원하지 않는 이벤트 형식'})
            }
        
        print(f"📁 버킷: {bucket_name}")
        print(f"📄 파일: {object_key}")
        
        # 파일 확장자 확인
        file_extension = os.path.splitext(object_key)[1].lower()
        if file_extension not in SUPPORTED_VIDEO_FORMATS:
            print(f"⚠️ 지원하지 않는 파일 형식: {file_extension}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'지원하지 않는 파일 형식: {file_extension}'})
            }
        
        # MediaConvert 엔드포인트 가져오기
        global MEDIACONVERT_ENDPOINT
        if not MEDIACONVERT_ENDPOINT:
            MEDIACONVERT_ENDPOINT = get_mediaconvert_endpoint()
            mediaconvert_client = boto3.client('mediaconvert', endpoint_url=MEDIACONVERT_ENDPOINT)
        
        # MediaConvert 작업 생성
        job_id = create_mediaconvert_job(bucket_name, object_key)
        
        if job_id:
            print(f"✅ MediaConvert 작업 시작됨: {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': '동영상 변환 작업이 시작되었습니다',
                    'job_id': job_id,
                    'input_file': f"s3://{bucket_name}/{object_key}",
                    'output_bucket': OUTPUT_BUCKET
                })
            }
        else:
            print(f"❌ MediaConvert 작업 생성 실패")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'MediaConvert 작업 생성 실패'})
            }
            
    except Exception as e:
        print(f"❌ Lambda 실행 오류: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_mediaconvert_endpoint():
    """MediaConvert 엔드포인트 URL 가져오기"""
    try:
        response = mediaconvert_client.describe_endpoints()
        return response['Endpoints'][0]['Url']
    except Exception as e:
        print(f"❌ MediaConvert 엔드포인트 가져오기 실패: {str(e)}")
        raise e

def create_mediaconvert_job(bucket_name, object_key):
    """MediaConvert 작업 생성"""
    
    try:
        # 작업 ID 생성
        job_id = str(uuid.uuid4())
        
        # 입력 파일 경로
        input_uri = f"s3://{bucket_name}/{object_key}"
        
        # 출력 파일 경로 (확장자를 .mp4로 변경)
        base_name = os.path.splitext(object_key)[0]
        output_key = f"converted/{base_name}_sd.mp4"
        output_uri = f"s3://{OUTPUT_BUCKET}/{output_key}"
        
        print(f"🔄 변환 시작: {input_uri} → {output_uri}")
        
        # MediaConvert 작업 설정
        job_settings = {
            "Role": MEDIACONVERT_ROLE_ARN,
            "Settings": {
                "Inputs": [
                    {
                        "AudioSelectors": {
                            "Audio Selector 1": {
                                "Offset": 0,
                                "DefaultSelection": "DEFAULT",
                                "ProgramSelection": 1
                            }
                        },
                        "VideoSelector": {
                            "ColorSpace": "FOLLOW"
                        },
                        "FilterEnable": "AUTO",
                        "PsiControl": "USE_PSI",
                        "FilterStrength": 0,
                        "DeblockFilter": "DISABLED",
                        "DenoiseFilter": "DISABLED",
                        "TimecodeSource": "EMBEDDED",
                        "FileInput": input_uri
                    }
                ],
                "OutputGroups": [
                    {
                        "Name": "File Group",
                        "OutputGroupSettings": {
                            "Type": "FILE_GROUP_SETTINGS",
                            "FileGroupSettings": {
                                "Destination": f"s3://{OUTPUT_BUCKET}/converted/"
                            }
                        },
                        "Outputs": [
                            {
                                "NameModifier": f"_{base_name}_sd",
                                "Preset": None,
                                "VideoDescription": {
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
                                            "Bitrate": 1500000,  # 1.5 Mbps for SD
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
                                    },
                                    "AfdSignaling": "NONE",
                                    "DropFrameTimecode": "ENABLED",
                                    "RespondToAfd": "NONE",
                                    "ColorMetadata": "INSERT",
                                    "Width": 720,  # SD width
                                    "Height": 480  # SD height
                                },
                                "AudioDescriptions": [
                                    {
                                        "AudioTypeControl": "FOLLOW_INPUT",
                                        "CodecSettings": {
                                            "Codec": "AAC",
                                            "AacSettings": {
                                                "AudioDescriptionBroadcasterMix": "NORMAL",
                                                "Bitrate": 96000,
                                                "RateControlMode": "CBR",
                                                "CodecProfile": "LC",
                                                "CodingMode": "CODING_MODE_2_0",
                                                "RawFormat": "NONE",
                                                "SampleRate": 48000,
                                                "Specification": "MPEG4"
                                            }
                                        },
                                        "LanguageCodeControl": "FOLLOW_INPUT",
                                        "AudioSourceName": "Audio Selector 1"
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
                ]
            }
        }
        
        # MediaConvert 작업 제출
        response = mediaconvert_client.create_job(
            Role=MEDIACONVERT_ROLE_ARN,
            Settings=job_settings["Settings"],
            Queue="Default"
        )
        
        actual_job_id = response['Job']['Id']
        print(f"✅ MediaConvert 작업 생성 완료: {actual_job_id}")
        
        return actual_job_id
        
    except Exception as e:
        print(f"❌ MediaConvert 작업 생성 실패: {str(e)}")
        return None
