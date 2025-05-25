"""
utils 모듈 - 공통 유틸리티 함수들

이 모듈은 다음 유틸리티들을 포함합니다:
- file_utils: 파일 처리 유틸리티
- data_validation: 데이터 검증 함수들
- constants: 상수 정의
"""

from .file_utils import (
    ensure_directories,
    load_json_file,
    save_json_file,
    load_csv_file,
    save_csv_file,
    create_sample_data,
    create_directory_structure,
    backup_file,
    clean_temp_files
)

__version__ = "1.0.0"
__author__ = "Solar Prediction Team"

# 프로젝트 초기화 함수
def initialize_project():
    """프로젝트 전체 초기화"""
    print("🚀 태양광 발전량 예측 시스템 초기화 시작...")
    
    # 1. 디렉토리 구조 생성
    print("📁 디렉토리 구조 생성 중...")
    create_directory_structure()
    
    # 2. 필요한 디렉토리 확인
    print("📂 필수 디렉토리 확인 중...")
    ensure_directories()
    
    # 3. 샘플 데이터 생성
    print("📊 샘플 데이터 생성 중...")
    create_sample_data()
    
    print("✅ 프로젝트 초기화 완료!")
    print("🌐 이제 python main.py 명령으로 서버를 시작할 수 있습니다.")

# 프로젝트 정리 함수
def cleanup_project():
    """프로젝트 정리 (임시 파일 삭제 등)"""
    print("🧹 프로젝트 정리 시작...")
    
    # 임시 파일 정리
    clean_temp_files("temp", 24)
    clean_temp_files("web/static/generated_charts", 48)
    
    print("✅ 프로젝트 정리 완료!")

__all__ = [
    # 파일 유틸리티
    'ensure_directories',
    'load_json_file',
    'save_json_file', 
    'load_csv_file',
    'save_csv_file',
    'create_sample_data',
    'backup_file',
    'clean_temp_files',
    
    # 프로젝트 관리
    'initialize_project',
    'cleanup_project'
]