import os
import json
import pandas as pd
from typing import Dict, List, Optional
from config import get_config

config = get_config()

def ensure_directories():
    """필요한 디렉토리들 생성"""
    directories = [
        config.DATA_DIR,
        'web/static/generated_charts',
        'logs',
        'data/cache',
        'data/sample_data'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ 디렉토리 확인/생성: {directory}")

def load_json_file(file_path: str) -> Optional[Dict]:
    """JSON 파일 로드"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"⚠️ 파일이 존재하지 않습니다: {file_path}")
            return None
    except Exception as e:
        print(f"❌ JSON 파일 로드 오류: {file_path} - {str(e)}")
        return None

def save_json_file(data: Dict, file_path: str) -> bool:
    """JSON 파일 저장"""
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON 파일 저장 완료: {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ JSON 파일 저장 오류: {file_path} - {str(e)}")
        return False

def load_csv_file(file_path: str) -> Optional[pd.DataFrame]:
    """CSV 파일 로드"""
    try:
        if os.path.exists(file_path):
            return pd.read_csv(file_path, encoding='utf-8')
        else:
            print(f"⚠️ 파일이 존재하지 않습니다: {file_path}")
            return None
    except Exception as e:
        print(f"❌ CSV 파일 로드 오류: {file_path} - {str(e)}")
        return None

def save_csv_file(df: pd.DataFrame, file_path: str) -> bool:
    """CSV 파일 저장"""
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"✅ CSV 파일 저장 완료: {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ CSV 파일 저장 오류: {file_path} - {str(e)}")
        return False

def get_file_size(file_path: str) -> Optional[int]:
    """파일 크기 조회 (바이트)"""
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        else:
            return None
    except Exception as e:
        print(f"❌ 파일 크기 조회 오류: {file_path} - {str(e)}")
        return None

def format_file_size(size_bytes: int) -> str:
    """파일 크기를 읽기 쉬운 형태로 변환"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def clean_temp_files(temp_dir: str = "temp", max_age_hours: int = 24):
    """임시 파일 정리"""
    import time
    
    if not os.path.exists(temp_dir):
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    cleaned_count = 0
    
    try:
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    cleaned_count += 1
        
        if cleaned_count > 0:
            print(f"✅ 임시 파일 정리 완료: {cleaned_count}개 파일 삭제")
            
    except Exception as e:
        print(f"❌ 임시 파일 정리 오류: {str(e)}")

def backup_file(file_path: str, backup_dir: str = "backups") -> bool:
    """파일 백업"""
    try:
        if not os.path.exists(file_path):
            print(f"⚠️ 백업할 파일이 존재하지 않습니다: {file_path}")
            return False
        
        # 백업 디렉토리 생성
        os.makedirs(backup_dir, exist_ok=True)
        
        # 백업 파일명 생성 (타임스탬프 포함)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        backup_filename = f"{name}_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # 파일 복사
        import shutil
        shutil.copy2(file_path, backup_path)
        
        print(f"✅ 파일 백업 완료: {file_path} -> {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ 파일 백업 오류: {file_path} - {str(e)}")
        return False

def create_sample_data():
    """샘플 데이터 파일 생성"""
    sample_data_dir = "data/sample_data"
    os.makedirs(sample_data_dir, exist_ok=True)
    
    # 1. 샘플 위치 데이터
    sample_locations = [
        {"name": "서울", "lat": 37.5665, "lon": 126.9780},
        {"name": "부산", "lat": 35.1796, "lon": 129.0756},
        {"name": "대구", "lat": 35.8714, "lon": 128.6014},
        {"name": "인천", "lat": 37.4563, "lon": 126.7052},
        {"name": "광주", "lat": 35.1595, "lon": 126.8526},
        {"name": "대전", "lat": 36.3504, "lon": 127.3845},
        {"name": "울산", "lat": 35.5384, "lon": 129.3114},
        {"name": "세종", "lat": 36.4800, "lon": 127.2890},
        {"name": "제주", "lat": 33.4996, "lon": 126.5312}
    ]
    
    save_json_file(sample_locations, f"{sample_data_dir}/korea_cities.json")
    
    # 2. 시스템 프리셋 데이터
    system_presets = {
        "residential_3kw": {
            "name": "주택용 3kW",
            "capacity": 3.0,
            "module_count": 12,
            "module_power": 250,
            "cost_per_kw": 1500000,
            "description": "일반 가정용 소형 시스템"
        },
        "commercial_10kw": {
            "name": "상업용 10kW", 
            "capacity": 10.0,
            "module_count": 40,
            "module_power": 250,
            "cost_per_kw": 1300000,
            "description": "소규모 상업시설용"
        }
    }
    
    save_json_file(system_presets, f"{sample_data_dir}/system_presets.json")
    
    # 3. 샘플 발전량 데이터 (CSV)
    sample_energy_data = pd.DataFrame({
        'month': range(1, 13),
        'month_name': ['1월', '2월', '3월', '4월', '5월', '6월', 
                      '7월', '8월', '9월', '10월', '11월', '12월'],
        'ghi': [65, 85, 120, 150, 170, 165, 155, 160, 140, 120, 85, 60],
        'energy_kwh_per_kwp': [60, 75, 105, 130, 145, 140, 135, 140, 125, 105, 75, 55]
    })
    
    save_csv_file(sample_energy_data, f"{sample_data_dir}/sample_monthly_energy.csv")
    
    print("✅ 샘플 데이터 생성 완료")

def validate_file_format(file_path: str, allowed_formats: List[str]) -> bool:
    """파일 형식 검증"""
    try:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        return ext in [f.lower() if f.startswith('.') else f'.{f.lower()}' for f in allowed_formats]
        
    except Exception as e:
        print(f"❌ 파일 형식 검증 오류: {file_path} - {str(e)}")
        return False

def get_directory_info(directory: str) -> Dict:
    """디렉토리 정보 조회"""
    try:
        if not os.path.exists(directory):
            return {"exists": False}
        
        file_count = 0
        total_size = 0
        file_types = {}
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    total_size += size
                    file_count += 1
                    
                    _, ext = os.path.splitext(file)
                    ext = ext.lower()
                    file_types[ext] = file_types.get(ext, 0) + 1
                    
                except OSError:
                    continue
        
        return {
            "exists": True,
            "file_count": file_count,
            "total_size": total_size,
            "total_size_formatted": format_file_size(total_size),
            "file_types": file_types
        }
        
    except Exception as e:
        print(f"❌ 디렉토리 정보 조회 오류: {directory} - {str(e)}")
        return {"exists": False, "error": str(e)}

def compress_files(file_paths: List[str], output_path: str) -> bool:
    """파일들을 ZIP으로 압축"""
    try:
        import zipfile
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    arcname = os.path.basename(file_path)
                    zipf.write(file_path, arcname)
                else:
                    print(f"⚠️ 파일을 찾을 수 없습니다: {file_path}")
        
        print(f"✅ 파일 압축 완료: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ 파일 압축 오류: {str(e)}")
        return False

def extract_files(zip_path: str, extract_dir: str) -> bool:
    """ZIP 파일 압축 해제"""
    try:
        import zipfile
        
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        print(f"✅ 파일 압축 해제 완료: {zip_path} -> {extract_dir}")
        return True
        
    except Exception as e:
        print(f"❌ 파일 압축 해제 오류: {str(e)}")
        return False

def create_directory_structure():
    """전체 프로젝트 디렉토리 구조 생성"""
    directories = [
        "core",
        "visualization", 
        "web/routes",
        "web/templates",
        "web/static/css",
        "web/static/js", 
        "web/static/images",
        "web/static/generated_charts",
        "data",
        "data/cache",
        "data/sample_data",
        "utils",
        "tests",
        "logs",
        "backups",
        "temp"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # __init__.py 파일 생성
    init_files = [
        "core/__init__.py",
        "visualization/__init__.py", 
        "web/__init__.py",
        "web/routes/__init__.py",
        "utils/__init__.py",
        "tests/__init__.py"
    ]
    
    for init_file in init_files:
        if not os.path.exists(init_file):
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write('"""\n')
                f.write(f'{os.path.dirname(init_file).replace("/", ".").replace("\\", ".")} 모듈\n')
                f.write('"""\n')
    
    print("✅ 프로젝트 디렉토리 구조 생성 완료")

def log_file_operation(operation: str, file_path: str, success: bool, details: str = ""):
    """파일 작업 로그 기록"""
    import datetime
    
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    today = datetime.datetime.now().strftime("%Y%m%d")
    log_file = f"{log_dir}/file_operations_{today}.log"
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if success else "FAILED"
    
    log_entry = f"[{timestamp}] {operation} - {status} - {file_path}"
    if details:
        log_entry += f" - {details}"
    log_entry += "\n"
    
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"❌ 로그 기록 오류: {str(e)}")

def read_text_file(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """텍스트 파일 읽기"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        else:
            print(f"⚠️ 파일이 존재하지 않습니다: {file_path}")
            return None
    except Exception as e:
        print(f"❌ 텍스트 파일 읽기 오류: {file_path} - {str(e)}")
        return None

def write_text_file(content: str, file_path: str, encoding: str = 'utf-8') -> bool:
    """텍스트 파일 쓰기"""
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        
        print(f"✅ 텍스트 파일 저장 완료: {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ 텍스트 파일 저장 오류: {file_path} - {str(e)}")
        return False

def delete_file_safe(file_path: str) -> bool:
    """파일 안전 삭제"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ 파일 삭제 완료: {file_path}")
            log_file_operation("DELETE", file_path, True)
            return True
        else:
            print(f"⚠️ 삭제할 파일이 존재하지 않습니다: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ 파일 삭제 오류: {file_path} - {str(e)}")
        log_file_operation("DELETE", file_path, False, str(e))
        return False

def copy_file_safe(src_path: str, dst_path: str) -> bool:
    """파일 안전 복사"""
    try:
        import shutil
        
        if not os.path.exists(src_path):
            print(f"⚠️ 원본 파일이 존재하지 않습니다: {src_path}")
            return False
        
        # 대상 디렉토리 생성
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        
        shutil.copy2(src_path, dst_path)
        print(f"✅ 파일 복사 완료: {src_path} -> {dst_path}")
        log_file_operation("COPY", f"{src_path} -> {dst_path}", True)
        return True
        
    except Exception as e:
        print(f"❌ 파일 복사 오류: {src_path} -> {dst_path} - {str(e)}")
        log_file_operation("COPY", f"{src_path} -> {dst_path}", False, str(e))
        return False

def get_files_by_extension(directory: str, extension: str) -> List[str]:
    """특정 확장자의 파일들 목록 반환"""
    try:
        if not os.path.exists(directory):
            return []
        
        files = []
        extension = extension.lower()
        if not extension.startswith('.'):
            extension = '.' + extension
        
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                if filename.lower().endswith(extension):
                    files.append(os.path.join(root, filename))
        
        return files
        
    except Exception as e:
        print(f"❌ 파일 목록 조회 오류: {directory} - {str(e)}")
        return []