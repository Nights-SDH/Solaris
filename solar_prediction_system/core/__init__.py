"""
core 모듈 - 태양광 발전량 예측 시스템의 핵심 로직

이 모듈은 다음 컴포넌트들을 포함합니다:
- solar_calculator: 태양광 발전량 계산 엔진
- weather_api: NASA POWER API 연동
- financial_analysis: 경제성 분석
- optimization: 각도 최적화 알고리즘
"""

from .solar_calculator import SolarCalculator
from .weather_api import WeatherAPI
from .financial_analysis import FinancialAnalyzer
from .optimization import AngleOptimizer

__version__ = "1.0.0"
__author__ = "Solar Prediction Team"

# 편의를 위한 단축 함수들
def create_solar_system():
    """통합 태양광 시스템 분석 객체 생성"""
    solar_calc = SolarCalculator()
    weather_api = WeatherAPI()
    financial_analyzer = FinancialAnalyzer()
    angle_optimizer = AngleOptimizer(solar_calc)
    
    return {
        'calculator': solar_calc,
        'weather': weather_api,
        'financial': financial_analyzer,
        'optimizer': angle_optimizer
    }

def quick_analysis(lat, lon, tilt=30, azimuth=180):
    """빠른 태양광 발전량 분석"""
    system = create_solar_system()
    
    # GHI 데이터 조회
    ghi = system['weather'].get_ghi_data(lat, lon)
    if ghi is None:
        ghi = system['weather'].get_fallback_ghi(lat, lon)
    
    # 발전량 계산
    result = system['calculator'].calculate_pv_energy(lat, lon, tilt, azimuth, ghi)
    
    return {
        'location': {'lat': lat, 'lon': lon},
        'ghi': ghi,
        'energy_result': result
    }

__all__ = [
    'SolarCalculator',
    'WeatherAPI', 
    'FinancialAnalyzer',
    'AngleOptimizer',
    'create_solar_system',
    'quick_analysis'
]