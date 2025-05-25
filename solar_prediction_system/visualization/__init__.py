"""
visualization 모듈 - 데이터 시각화 및 차트 생성

이 모듈은 다음 컴포넌트들을 포함합니다:
- chart_generator: 모든 차트 생성 기능
- heatmap: 히트맵 생성 및 처리
- plotting_utils: 공통 플롯팅 유틸리티
"""

from .chart_generator import ChartGenerator

__version__ = "1.0.0"
__author__ = "Solar Prediction Team"

# 기본 차트 생성기 인스턴스
default_chart_generator = ChartGenerator()

# 편의 함수들
def create_monthly_chart(monthly_energy):
    """월별 발전량 차트 생성 (편의 함수)"""
    return default_chart_generator.generate_monthly_chart(monthly_energy)

def create_roi_chart(financial_data):
    """ROI 차트 생성 (편의 함수)"""
    return default_chart_generator.generate_roi_chart(financial_data)

def create_angle_heatmap(energy_matrix, tilt_range, azimuth_range):
    """각도 히트맵 생성 (편의 함수)"""
    return default_chart_generator.generate_angle_heatmap(energy_matrix, tilt_range, azimuth_range)

__all__ = [
    'ChartGenerator',
    'default_chart_generator',
    'create_monthly_chart',
    'create_roi_chart', 
    'create_angle_heatmap'
]