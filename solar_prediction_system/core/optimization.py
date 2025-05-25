"""
태양광 모듈 설치 각도 최적화 모듈
"""
import numpy as np
from scipy.optimize import minimize, differential_evolution
from typing import Tuple, Dict, List
from config import get_config

config = get_config()

class AngleOptimizer:
    """태양광 모듈 각도 최적화 클래스"""
    
    def __init__(self, solar_calculator):
        self.solar_calculator = solar_calculator
        self.config = config
    
    def find_optimal_angles_simple(self, lat: float, lon: float, ghi_annual: float) -> Tuple[float, float]:
        """
        경험적 공식을 사용한 빠른 최적 각도 계산
        
        Args:
            lat: 위도
            lon: 경도  
            ghi_annual: 연간 GHI
            
        Returns:
            (최적 경사각, 최적 방위각)
        """
        # 위도 기반 최적 경사각 (경험적 공식)
        optimal_tilt = abs(lat) * 0.76 + 3.1
        
        # 위도에 따른 최적 방위각
        optimal_azimuth = 180 if lat >= 0 else 0
        
        return round(optimal_tilt, 1), optimal_azimuth
    
    def find_optimal_angles_detailed(
        self, 
        lat: float, 
        lon: float, 
        ghi_annual: float,
        method: str = 'L-BFGS-B'
    ) -> Tuple[float, float, float]:
        """
        최적화 알고리즘을 사용한 상세 최적각 계산
        
        Args:
            lat: 위도
            lon: 경도
            ghi_annual: 연간 GHI
            method: 최적화 방법
            
        Returns:
            (최적 경사각, 최적 방위각, 최대 발전량)
        """
        def objective_function(params):
            tilt, azimuth = params
            
            # 각도 범위 제한
            if not (0 <= tilt <= 90) or not (0 <= azimuth <= 360):
                return 10000
            
            try:
                result = self.solar_calculator.calculate_pv_energy(
                    lat, lon, tilt, azimuth, ghi_annual
                )
                return -result['annual_energy']  # 최대화를 위해 음수 반환
            except:
                return 10000
        
        # 초기값 (경험적 법칙 기반)
        initial_tilt, initial_azimuth = self.find_optimal_angles_simple(lat, lon, ghi_annual)
        x0 = [initial_tilt, initial_azimuth]
        
        # 경계 조건
        bounds = [(0, 90), (0, 360)]
        
        try:
            if method == 'differential_evolution':
                # 전역 최적화
                result = differential_evolution(
                    objective_function, 
                    bounds, 
                    seed=42,
                    maxiter=50
                )
            else:
                # 지역 최적화
                result = minimize(
                    objective_function, 
                    x0, 
                    bounds=bounds, 
                    method=method
                )
            
            if result.success:
                optimal_tilt, optimal_azimuth = result.x
                max_energy = -result.fun
                return round(optimal_tilt, 1), round(optimal_azimuth, 1), round(max_energy, 1)
            else:
                # 최적화 실패시 경험적 법칙 사용
                tilt, azimuth = self.find_optimal_angles_simple(lat, lon, ghi_annual)
                energy_result = self.solar_calculator.calculate_pv_energy(
                    lat, lon, tilt, azimuth, ghi_annual
                )
                return tilt, azimuth, energy_result['annual_energy']
                
        except Exception as e:
            print(f"최적화 오류: {e}")
            tilt, azimuth = self.find_optimal_angles_simple(lat, lon, ghi_annual)
            energy_result = self.solar_calculator.calculate_pv_energy(
                lat, lon, tilt, azimuth, ghi_annual
            )
            return tilt, azimuth, energy_result['annual_energy']
    
    def calculate_angle_sensitivity(
        self, 
        lat: float, 
        lon: float, 
        ghi_annual: float,
        optimal_tilt: float,
        optimal_azimuth: float
    ) -> Dict:
        """
        최적 각도 주변의 민감도 분석
        
        Args:
            lat: 위도
            lon: 경도
            ghi_annual: 연간 GHI
            optimal_tilt: 최적 경사각
            optimal_azimuth: 최적 방위각
            
        Returns:
            민감도 분석 결과
        """
        # 경사각 민감도 (±10도)
        tilt_variations = np.arange(
            max(0, optimal_tilt - 10), 
            min(90, optimal_tilt + 11), 
            2
        )
        
        tilt_sensitivity = []
        for tilt in tilt_variations:
            result = self.solar_calculator.calculate_pv_energy(
                lat, lon, tilt, optimal_azimuth, ghi_annual
            )
            loss_percent = (1 - result['annual_energy'] / 
                          self.solar_calculator.calculate_pv_energy(
                              lat, lon, optimal_tilt, optimal_azimuth, ghi_annual
                          )['annual_energy']) * 100
            
            tilt_sensitivity.append({
                'angle': tilt,
                'energy': result['annual_energy'],
                'loss_percent': round(loss_percent, 2)
            })
        
        # 방위각 민감도 (±30도)
        azimuth_variations = np.arange(
            max(0, optimal_azimuth - 30),
            min(360, optimal_azimuth + 31),
            5
        )
        
        azimuth_sensitivity = []
        for azimuth in azimuth_variations:
            result = self.solar_calculator.calculate_pv_energy(
                lat, lon, optimal_tilt, azimuth, ghi_annual
            )
            loss_percent = (1 - result['annual_energy'] / 
                          self.solar_calculator.calculate_pv_energy(
                              lat, lon, optimal_tilt, optimal_azimuth, ghi_annual
                          )['annual_energy']) * 100
            
            azimuth_sensitivity.append({
                'angle': azimuth,
                'energy': result['annual_energy'],
                'loss_percent': round(loss_percent, 2)
            })
        
        return {
            'tilt_sensitivity': tilt_sensitivity,
            'azimuth_sensitivity': azimuth_sensitivity
        }
    
    def multi_objective_optimization(
        self, 
        lat: float, 
        lon: float, 
        ghi_annual: float,
        objectives: List[str] = ['energy', 'cost', 'aesthetic']
    ) -> Dict:
        """
        다목적 최적화 (에너지, 비용, 미관 등 고려)
        
        Args:
            lat: 위도
            lon: 경도
            ghi_annual: 연간 GHI
            objectives: 최적화 목표 리스트
            
        Returns:
            파레토 최적해 집합
        """
        def multi_objective_function(params, weights):
            tilt, azimuth = params
            
            if not (0 <= tilt <= 90) or not (0 <= azimuth <= 360):
                return [10000] * len(objectives)
            
            try:
                result = self.solar_calculator.calculate_pv_energy(
                    lat, lon, tilt, azimuth, ghi_annual
                )
                
                objectives_values = []
                
                for obj in objectives:
                    if obj == 'energy':
                        # 에너지 최대화 (음수로 변환)
                        objectives_values.append(-result['annual_energy'])
                    elif obj == 'cost':
                        # 설치 비용 최소화 (경사각이 클수록 비용 증가)
                        cost_factor = 1 + (tilt / 90) * 0.2  # 최대 20% 증가
                        objectives_values.append(cost_factor)
                    elif obj == 'aesthetic':
                        # 미관 고려 (낮은 경사각 선호)
                        aesthetic_score = abs(tilt - 15) / 75  # 15도가 최적
                        objectives_values.append(aesthetic_score)
                
                # 가중합 반환
                return sum(w * obj for w, obj in zip(weights, objectives_values))
                
            except:
                return 10000
        
        # 여러 가중치 조합으로 파레토 프론트 생성
        pareto_solutions = []
        
        # 가중치 조합 생성
        if len(objectives) == 2:
            weight_combinations = [(1-w, w) for w in np.linspace(0, 1, 11)]
        elif len(objectives) == 3:
            weight_combinations = []
            for w1 in np.linspace(0, 1, 6):
                for w2 in np.linspace(0, 1-w1, 6):
                    w3 = 1 - w1 - w2
                    if w3 >= 0:
                        weight_combinations.append((w1, w2, w3))
        else:
            # 기본 균등 가중치
            weight_combinations = [tuple([1/len(objectives)] * len(objectives))]
        
        for weights in weight_combinations:
            try:
                result = minimize(
                    lambda params: multi_objective_function(params, weights),
                    [30, 180],  # 초기값
                    bounds=[(0, 90), (0, 360)],
                    method='L-BFGS-B'
                )
                
                if result.success:
                    tilt, azimuth = result.x
                    energy_result = self.solar_calculator.calculate_pv_energy(
                        lat, lon, tilt, azimuth, ghi_annual
                    )
                    
                    pareto_solutions.append({
                        'tilt': round(tilt, 1),
                        'azimuth': round(azimuth, 1),
                        'energy': energy_result['annual_energy'],
                        'weights': weights
                    })
            except:
                continue
        
        return {
            'pareto_solutions': pareto_solutions,
            'objectives': objectives
        }
    
    def seasonal_optimization(
        self, 
        lat: float, 
        lon: float, 
        ghi_annual: float
    ) -> Dict:
        """
        계절별 최적 각도 계산
        
        Args:
            lat: 위도
            lon: 경도
            ghi_annual: 연간 GHI
            
        Returns:
            계절별 최적 각도
        """
        seasons = {
            'winter': (lat + 15, 180),  # 겨울: 경사각 높게
            'spring': (lat, 180),       # 봄: 위도와 비슷
            'summer': (lat - 15, 180),  # 여름: 경사각 낮게  
            'fall': (lat, 180)          # 가을: 위도와 비슷
        }
        
        seasonal_results = {}
        
        for season, (tilt, azimuth) in seasons.items():
            # 각도 범위 제한
            tilt = max(0, min(90, tilt))
            
            result = self.solar_calculator.calculate_pv_energy(
                lat, lon, tilt, azimuth, ghi_annual
            )
            
            seasonal_results[season] = {
                'tilt': tilt,
                'azimuth': azimuth,
                'energy': result['annual_energy']
            }
        
        return seasonal_results