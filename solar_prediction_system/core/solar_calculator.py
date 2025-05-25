"""
태양광 발전량 계산 엔진
"""
import numpy as np
import pandas as pd
import pvlib
from scipy.optimize import minimize
from config import get_config

config = get_config()

class SolarCalculator:
    """태양광 발전량 계산 클래스"""
    
    def __init__(self):
        self.config = config
    
    def get_solar_position(self, lat, lon, date_range):
        """특정 위치와 날짜 범위에 대한 태양 위치 계산"""
        return pvlib.solarposition.get_solarposition(date_range, lat, lon)
    
    def decompose_ghi(self, ghi_values, solar_zenith, times):
        """GHI를 DNI와 DHI로 분해"""
        return pvlib.irradiance.erbs(ghi_values, solar_zenith, times)
    
    def calculate_aoi(self, surface_tilt, surface_azimuth, solar_zenith, solar_azimuth):
        """태양광선의 입사각 계산"""
        return pvlib.irradiance.aoi(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth)
    
    def calculate_pv_energy(self, lat, lon, tilt, azimuth, ghi_annual, system_config=None):
        """상세한 태양광 발전량 계산"""
        # 시스템 기본 설정
        if system_config is None:
            system_config = self._get_default_system_config()
        
        # 1. 1년 시간 간격 생성 (매시간)
        times = pd.date_range(start='2023-01-01', end='2023-12-31 23:00:00', freq='H')
        
        # 2. 태양 위치 계산
        solpos = self.get_solar_position(lat, lon, times)
        
        # 3. 시간별 GHI 생성
        hourly_ghi = self._generate_hourly_ghi(ghi_annual, times)
        
        # 4. GHI를 DNI와 DHI로 분해
        irradiance = self.decompose_ghi(hourly_ghi, solpos['apparent_zenith'], times)
        dni = irradiance['dni'].fillna(0)
        dhi = irradiance['dhi'].fillna(0)
        
        # 5. 트래킹 시스템 처리
        surface_tilt, surface_azimuth = self._handle_tracking_system(
            solpos, tilt, azimuth, system_config['tracking_type']
        )
        
        # 6. 입사각 계산
        aoi_values = self.calculate_aoi(surface_tilt, surface_azimuth, 
                                       solpos['apparent_zenith'], solpos['azimuth'])
        
        # 7. 모듈 표면 일사량 계산
        poa_global = self._calculate_poa_irradiance(
            surface_tilt, surface_azimuth, dni, dhi, 
            solpos, aoi_values, hourly_ghi, system_config
        )
        
        # 8. 온도 효과 계산
        temp_factor = self._calculate_temperature_effect(times, poa_global, system_config)
        
        # 9. 총 효율 계산
        total_efficiency = (system_config['efficiency'] * 
                          system_config['inverter_efficiency'] * 
                          (1 - system_config['losses']) * temp_factor)
        
        # 10. 발전량 계산
        hourly_energy = poa_global * total_efficiency / 1000  # kWh/m²
        
        # 11. 결과 집계
        annual_energy = hourly_energy.sum()  # kWh/kWp/year
        monthly_energy = hourly_energy.groupby(times.month).sum()  # kWh/kWp/month
        
        # 12. 최적 각도 계산
        best_tilt, best_azimuth = self.find_optimal_angles(lat, lon, ghi_annual)
        
        return {
            'annual_energy': round(annual_energy, 1),
            'monthly_energy': monthly_energy.tolist(),
            'hourly_energy': hourly_energy.tolist(),
            'temp_effect': round((temp_factor.mean() - 1) * 100, 2),
            'optimal_tilt': best_tilt,
            'optimal_azimuth': best_azimuth
        }
    
    def _get_default_system_config(self):
        """기본 시스템 설정 반환"""
        return {
            'albedo': self.config.DEFAULT_ALBEDO,
            'efficiency': self.config.DEFAULT_SYSTEM_EFFICIENCY,
            'module_type': 'standard',
            'tracking_type': 'fixed',
            'bifacial_factor': 0,
            'inverter_efficiency': self.config.DEFAULT_INVERTER_EFFICIENCY,
            'losses': self.config.DEFAULT_LOSSES,
            'temp_model': 'sapm',
            'racking_model': 'open_rack'
        }
    
    def _generate_hourly_ghi(self, ghi_annual, times):
        """연간 평균 GHI를 시간별 분포로 변환"""
        # 월별 분포 비율
        monthly_ratio = np.array(self.config.MONTHLY_GHI_RATIO)
        monthly_ratio = monthly_ratio / monthly_ratio.mean()
        
        # 각 시간의 월 인덱스
        month_indices = np.array([t.month-1 for t in times])
        
        # 일중 변동 패턴
        daily_pattern = np.sin(np.pi * (times.hour) / 24) ** 2
        daily_pattern[times.hour < 6] = 0
        daily_pattern[times.hour > 18] = 0
        
        # 시간별 GHI 계산
        hourly_ghi = ghi_annual / 365 / daily_pattern.sum() * 24
        hourly_ghi = hourly_ghi * monthly_ratio[month_indices] * daily_pattern * 24
        
        return hourly_ghi
    
    def _handle_tracking_system(self, solpos, tilt, azimuth, tracking_type):
        """트래킹 시스템 처리"""
        if tracking_type == 'single_axis':
            tracking = pvlib.tracking.singleaxis(
                solpos['apparent_zenith'],
                solpos['azimuth'],
                axis_tilt=0,
                axis_azimuth=180,
                max_angle=60,
                backtrack=True,
                gcr=0.4
            )
            return tracking['surface_tilt'], tracking['surface_azimuth']
        else:
            # 고정 시스템
            return (np.full_like(solpos['apparent_zenith'], tilt),
                   np.full_like(solpos['azimuth'], azimuth))
    
    def _calculate_poa_irradiance(self, surface_tilt, surface_azimuth, dni, dhi, 
                                 solpos, aoi_values, hourly_ghi, system_config):
        """모듈 표면 일사량 계산"""
        # 하늘 산란일사량 계산
        poa_sky_diffuse = pvlib.irradiance.perez(
            surface_tilt, surface_azimuth, dhi, dni,
            solpos['apparent_zenith'], solpos['azimuth'],
            airmass=None
        )
        
        # 지면 반사 산란일사량
        poa_ground_diffuse = pvlib.irradiance.get_ground_diffuse(
            surface_tilt, hourly_ghi, system_config['albedo']
        )
        
        # 모듈 표면 일사량
        poa_irrad = pvlib.irradiance.poa_components(
            aoi_values, dni, poa_sky_diffuse, poa_ground_diffuse
        )
        
        poa_global = poa_irrad['poa_global'].fillna(0).clip(min=0)
        
        # 양면형 모듈 처리
        if system_config['bifacial_factor'] > 0:
            poa_rear = poa_ground_diffuse * system_config['bifacial_factor']
            poa_global = poa_global + poa_rear
        
        return poa_global
    
    def _calculate_temperature_effect(self, times, poa_global, system_config):
        """온도 효과 계산"""
        # 월별 평균 기온
        month_indices = np.array([t.month-1 for t in times])
        avg_monthly_temp = np.array(self.config.MONTHLY_TEMP_KOREA)
        temp_data = avg_monthly_temp[month_indices]
        
        # 모듈 온도 계산
        if system_config['temp_model'] == 'sapm':
            temp_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm'][system_config['racking_model']]
            temp_cell = pvlib.temperature.sapm_cell(
                poa_global, temp_data, 1.0, 
                temp_params['a'], temp_params['b'], temp_params['deltaT']
            )
        else:
            # 간단한 모델
            temp_cell = temp_data + 0.035 * poa_global
        
        # 온도 계수 적용 (25℃ 기준, 1℃당 0.4% 감소)
        temp_factor = 1 - 0.004 * (temp_cell - 25)
        temp_factor = temp_factor.clip(min=0.7, max=1.1)
        
        return temp_factor
    
    def find_optimal_angles(self, lat, lon, ghi_annual, albedo=0.2, system_efficiency=0.85):
        """최적 경사각과 방위각 찾기"""
        # 경험적 공식 사용 (빠른 계산)
        optimal_tilt = abs(lat) * 0.76 + 3.1
        optimal_azimuth = 180 if lat >= 0 else 0
        
        return round(optimal_tilt, 1), optimal_azimuth
    
    def find_optimal_angles_detailed(self, lat, lon, ghi_annual):
        """최적화 알고리즘을 사용한 상세 최적각 계산"""
        def objective_function(params):
            tilt, azimuth = params
            if not (0 <= tilt <= 90) or not (0 <= azimuth <= 360):
                return 10000
            
            result = self.calculate_pv_energy(lat, lon, tilt, azimuth, ghi_annual)
            return -result['annual_energy']
        
        # 초기값
        x0 = [abs(lat) * 0.76 + 3.1, 180 if lat >= 0 else 0]
        
        # 최적화 실행
        bounds = [(0, 90), (0, 360)]
        result = minimize(objective_function, x0, bounds=bounds, method='L-BFGS-B')
        
        if result.success:
            optimal_tilt, optimal_azimuth = result.x
            return round(optimal_tilt, 1), round(optimal_azimuth, 1)
        else:
            return self.find_optimal_angles(lat, lon, ghi_annual)
    
    def calculate_angle_matrix(self, lat, lon, ghi_annual):
        """경사각/방위각 조합별 발전량 매트릭스 계산"""
        tilt_range = range(*self.config.OPTIMIZATION_TILT_RANGE)
        azimuth_range = range(*self.config.OPTIMIZATION_AZIMUTH_RANGE)
        
        energy_matrix = np.zeros((len(tilt_range), len(azimuth_range)))
        
        for i, tilt in enumerate(tilt_range):
            for j, azimuth in enumerate(azimuth_range):
                result = self.calculate_pv_energy(lat, lon, tilt, azimuth, ghi_annual)
                energy_matrix[i, j] = result['annual_energy']
        
        return energy_matrix, tilt_range, azimuth_range