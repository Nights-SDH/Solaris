"""
태양광 발전량 예측 시스템 설정 파일
"""
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

class Config:
    """기본 설정"""
    # Flask 설정
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    PORT = int(os.getenv('PORT', 5000))
    
    # API 키
    NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')
    NASA_POWER_API_KEY = os.getenv('NASA_POWER_API_KEY')
    
    # 태양광 시스템 기본값
    DEFAULT_SYSTEM_EFFICIENCY = float(os.getenv('DEFAULT_SYSTEM_EFFICIENCY', 0.85))
    DEFAULT_INVERTER_EFFICIENCY = float(os.getenv('DEFAULT_INVERTER_EFFICIENCY', 0.96))
    DEFAULT_LOSSES = float(os.getenv('DEFAULT_LOSSES', 0.14))
    DEFAULT_ALBEDO = float(os.getenv('DEFAULT_ALBEDO', 0.2))
    
    # 경제성 분석 기본값
    DEFAULT_INSTALL_COST_PER_KW = int(os.getenv('DEFAULT_INSTALL_COST_PER_KW', 1500000))
    DEFAULT_ELECTRICITY_PRICE = int(os.getenv('DEFAULT_ELECTRICITY_PRICE', 120))
    DEFAULT_ANNUAL_DEGRADATION = float(os.getenv('DEFAULT_ANNUAL_DEGRADATION', 0.005))
    DEFAULT_LIFETIME = int(os.getenv('DEFAULT_LIFETIME', 25))
    
    # 지역 설정 (한국 기준)
    KOREA_LAT_RANGE = (33.0, 38.0)
    KOREA_LON_RANGE = (126.0, 130.0)
    DEFAULT_LOCATION = (36.5, 127.8)  # 대전 (한국 중부)
    
    # 데이터 파일 경로
    HEATMAP_DATA_PATH = 'data/heat_data.json'
    DATA_DIR = 'data'
    
    # NASA POWER API 설정
    NASA_POWER_BASE_URL = 'https://power.larc.nasa.gov/api/temporal/climatology/point'
    NASA_POWER_PARAMS = 'ALLSKY_SFC_SW_DWN'
    NASA_POWER_COMMUNITY = 'RE'
    
    # 계산 매개변수
    OPTIMIZATION_TILT_RANGE = (0, 90, 5)  # (시작, 끝, 간격)
    OPTIMIZATION_AZIMUTH_RANGE = (90, 271, 10)
    
    # 온도 모델 매개변수
    MONTHLY_TEMP_KOREA = [-2.4, 0.4, 5.7, 12.5, 17.8, 22.2, 24.9, 25.7, 21.2, 14.8, 7.2, -0.1]
    MONTHLY_GHI_RATIO = [0.6, 0.7, 0.9, 1.1, 1.2, 1.1, 1.0, 1.1, 1.0, 0.9, 0.7, 0.6]

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    FLASK_DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """운영 환경 설정"""
    FLASK_DEBUG = False
    FLASK_ENV = 'production'

# 환경에 따른 설정 선택
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """현재 환경의 설정 반환"""
    env = os.getenv('FLASK_ENV', 'default')
    return config.get(env, config['default'])