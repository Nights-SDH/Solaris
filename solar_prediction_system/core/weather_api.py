"""
기상 데이터 API 클래스
NASA POWER API와의 연동을 담당
"""
import requests
import time
from typing import Dict, Optional, Tuple
from config import get_config

config = get_config()

class WeatherAPI:
    """NASA POWER API를 사용한 기상 데이터 클래스"""
    
    def __init__(self):
        self.base_url = config.NASA_POWER_BASE_URL
        self.api_key = config.NASA_POWER_API_KEY
        self.params = config.NASA_POWER_PARAMS
        self.community = config.NASA_POWER_COMMUNITY
    
    def get_ghi_data(self, lat: float, lon: float) -> Optional[float]:
        """
        특정 위치의 연평균 GHI 데이터 조회
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            연평균 GHI 값 (kWh/m²/년) 또는 None
        """
        url = (
            f'{self.base_url}?parameters={self.params}&'
            f'community={self.community}&latitude={lat}&longitude={lon}&format=JSON'
        )
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            ghi = data['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
            
            return float(ghi)
            
        except requests.exceptions.RequestException as e:
            print(f"API 요청 오류: {e}")
            return None
        except KeyError as e:
            print(f"데이터 파싱 오류: {e}")
            return None
        except Exception as e:
            print(f"예상치 못한 오류: {e}")
            return None
    
    def get_monthly_ghi_data(self, lat: float, lon: float) -> Optional[Dict]:
        """
        특정 위치의 월별 GHI 데이터 조회
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            월별 GHI 데이터 딕셔너리 또는 None
        """
        url = (
            f'{self.base_url}?parameters={self.params}&'
            f'community={self.community}&latitude={lat}&longitude={lon}&format=JSON'
        )
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            monthly_data = data['properties']['parameter']['ALLSKY_SFC_SW_DWN']
            
            # 연간 평균 제외하고 월별 데이터만 추출
            monthly_ghi = {
                month: value for month, value in monthly_data.items() 
                if month != 'ANN'
            }
            
            return monthly_ghi
            
        except requests.exceptions.RequestException as e:
            print(f"API 요청 오류: {e}")
            return None
        except Exception as e:
            print(f"예상치 못한 오류: {e}")
            return None
    
    def get_temperature_data(self, lat: float, lon: float) -> Optional[Dict]:
        """
        특정 위치의 온도 데이터 조회
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            온도 데이터 딕셔너리 또는 None
        """
        url = (
            f'{self.base_url}?parameters=T2M&'
            f'community={self.community}&latitude={lat}&longitude={lon}&format=JSON'
        )
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            temp_data = data['properties']['parameter']['T2M']
            
            return temp_data
            
        except requests.exceptions.RequestException as e:
            print(f"온도 데이터 요청 오류: {e}")
            return None
        except Exception as e:
            print(f"예상치 못한 오류: {e}")
            return None
    
    def batch_get_ghi_data(self, locations: list, delay: float = 1.0) -> Dict[Tuple[float, float], float]:
        """
        여러 위치의 GHI 데이터를 일괄 조회
        
        Args:
            locations: [(lat, lon), ...] 형태의 위치 리스트
            delay: API 호출 간 지연 시간 (초)
            
        Returns:
            {(lat, lon): ghi_value} 형태의 딕셔너리
        """
        results = {}
        
        for i, (lat, lon) in enumerate(locations):
            print(f"데이터 조회 중... {i+1}/{len(locations)} - ({lat}, {lon})")
            
            ghi = self.get_ghi_data(lat, lon)
            if ghi is not None:
                results[(lat, lon)] = ghi
            
            # API 제한 준수를 위한 지연
            if i < len(locations) - 1:
                time.sleep(delay)
        
        return results
    
    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """
        좌표 유효성 검증
        
        Args:
            lat: 위도 (-90 ~ 90)
            lon: 경도 (-180 ~ 180)
            
        Returns:
            유효한 좌표인지 여부
        """
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return False
        
        if not (-90 <= lat <= 90):
            return False
        
        if not (-180 <= lon <= 180):
            return False
        
        return True
    
    def is_korea_region(self, lat: float, lon: float) -> bool:
        """
        한국 지역 범위 내 좌표인지 확인
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            한국 지역 내 좌표인지 여부
        """
        lat_min, lat_max = config.KOREA_LAT_RANGE
        lon_min, lon_max = config.KOREA_LON_RANGE
        
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max
    
    def get_fallback_ghi(self, lat: float, lon: float) -> float:
        """
        API 실패시 대체 GHI 값 반환 (한국 지역 평균)
        
        Args:
            lat: 위도
            lon: 경도
            
        Returns:
            대체 GHI 값
        """
        if self.is_korea_region(lat, lon):
            # 한국 지역별 대략적인 GHI 값
            if lat < 34.5:  # 제주도
                return 1350
            elif lat < 36.0:  # 남부지방
                return 1280
            elif lat < 37.5:  # 중부지방
                return 1220
            else:  # 북부지방
                return 1180
        else:
            # 세계 평균
            return 1200