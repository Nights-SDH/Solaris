"""
태양광 발전 시스템의 경제성 분석 모듈
"""
from typing import Dict, List
from config import get_config

config = get_config()

class FinancialAnalyzer:
    """경제성 분석 클래스"""
    
    def __init__(self):
        self.config = config
    
    def calculate_financial_metrics(
        self, 
        annual_energy: float, 
        system_size: float = 3.0,
        install_cost_per_kw: float = None,
        electricity_price: float = None,
        annual_degradation: float = None,
        lifetime: int = None
    ) -> Dict:
        """
        태양광 발전 시스템의 재무 지표 계산
        
        Args:
            annual_energy: 연간 발전량 (kWh/kWp)
            system_size: 시스템 용량 (kWp)
            install_cost_per_kw: kW당 설치 비용 (원)
            electricity_price: 전력 판매 단가 (원/kWh)
            annual_degradation: 연간 성능 저하율
            lifetime: 시스템 수명 (년)
        
        Returns:
            재무 지표 딕셔너리
        """
        # 기본값 설정
        if install_cost_per_kw is None:
            install_cost_per_kw = self.config.DEFAULT_INSTALL_COST_PER_KW
        if electricity_price is None:
            electricity_price = self.config.DEFAULT_ELECTRICITY_PRICE
        if annual_degradation is None:
            annual_degradation = self.config.DEFAULT_ANNUAL_DEGRADATION
        if lifetime is None:
            lifetime = self.config.DEFAULT_LIFETIME
        
        # 시스템 총 비용
        total_cost = system_size * install_cost_per_kw
        
        # 연간 발전량 및 수익
        annual_production = system_size * annual_energy
        annual_revenue = annual_production * electricity_price
        
        # 연간 현금 흐름 계산
        cash_flows = self._calculate_cash_flows(
            total_cost, annual_revenue, annual_degradation, lifetime
        )
        
        # 회수 기간 계산
        payback_period = self._calculate_payback_period(cash_flows)
        
        # ROI 계산
        roi = self._calculate_roi(cash_flows, total_cost)
        
        # 생애 총 수익
        life_cycle_revenue = self._calculate_life_cycle_revenue(
            annual_revenue, annual_degradation, lifetime, total_cost
        )
        
        return {
            'total_cost': int(total_cost),
            'annual_production': round(annual_production, 1),
            'annual_revenue': int(annual_revenue),
            'payback_period': payback_period,
            'roi': round(roi, 1),
            'cash_flows': cash_flows,
            'life_cycle_revenue': int(life_cycle_revenue),
            'npv': self._calculate_npv(cash_flows, 0.03),  # 3% 할인율
            'irr': self._calculate_irr(cash_flows)
        }
    
    def _calculate_cash_flows(
        self, 
        total_cost: float, 
        annual_revenue: float, 
        annual_degradation: float, 
        lifetime: int
    ) -> List[float]:
        """연간 현금 흐름 계산"""
        cash_flows = [-total_cost]  # 초기 투자 비용
        cumulative_cash_flow = -total_cost
        
        for year in range(1, lifetime + 1):
            # 성능 저하 적용
            degraded_factor = (1 - annual_degradation) ** year
            year_revenue = annual_revenue * degraded_factor
            
            # 유지보수 비용 (설치 비용의 1%)
            maintenance_cost = total_cost * 0.01
            
            # 연간 순이익
            net_cash_flow = year_revenue - maintenance_cost
            cumulative_cash_flow += net_cash_flow
            cash_flows.append(cumulative_cash_flow)
        
        return cash_flows
    
    def _calculate_payback_period(self, cash_flows: List[float]) -> float:
        """투자 회수 기간 계산"""
        for i in range(1, len(cash_flows)):
            if cash_flows[i] >= 0 and cash_flows[i-1] < 0:
                # 선형 보간으로 정확한 회수 기간 계산
                return i - 1 + (-cash_flows[i-1]) / (cash_flows[i] - cash_flows[i-1])
        
        # 회수되지 않는 경우
        return None if cash_flows[-1] < 0 else len(cash_flows) - 1
    
    def _calculate_roi(self, cash_flows: List[float], total_cost: float) -> float:
        """투자 수익률 계산"""
        if total_cost == 0:
            return 0
        
        total_return = cash_flows[-1] + total_cost  # 누적 현금흐름 + 초기투자
        return (total_return / total_cost) * 100
    
    def _calculate_life_cycle_revenue(
        self, 
        annual_revenue: float, 
        annual_degradation: float, 
        lifetime: int, 
        total_cost: float
    ) -> float:
        """생애 총 수익 계산"""
        total_revenue = 0
        for year in range(1, lifetime + 1):
            degraded_factor = (1 - annual_degradation) ** year
            total_revenue += annual_revenue * degraded_factor
        
        # 유지보수 비용 차감
        total_maintenance = total_cost * 0.01 * lifetime
        return total_revenue - total_maintenance
    
    def _calculate_npv(self, cash_flows: List[float], discount_rate: float) -> float:
        """순현재가치 계산"""
        npv = cash_flows[0]  # 초기 투자
        
        for year in range(1, len(cash_flows)):
            # 연간 현금흐름을 누적이 아닌 연간 순 현금흐름으로 변환
            annual_cash_flow = cash_flows[year] - cash_flows[year-1]
            npv += annual_cash_flow / ((1 + discount_rate) ** year)
        
        return npv
    
    def _calculate_irr(self, cash_flows: List[float]) -> float:
        """내부수익률 계산 (근사치)"""
        # 간단한 이분법으로 IRR 근사 계산
        def npv_at_rate(rate):
            npv = cash_flows[0]
            for year in range(1, len(cash_flows)):
                annual_cash_flow = cash_flows[year] - cash_flows[year-1]
                npv += annual_cash_flow / ((1 + rate) ** year)
            return npv
        
        # 이분법으로 IRR 찾기
        low, high = 0.0, 1.0
        for _ in range(100):  # 최대 100회 반복
            mid = (low + high) / 2
            npv = npv_at_rate(mid)
            
            if abs(npv) < 1000:  # 충분히 가까우면 종료
                return mid * 100  # 백분율로 반환
            
            if npv > 0:
                low = mid
            else:
                high = mid
        
        return mid * 100 if mid * 100 < 100 else None
    
    def compare_scenarios(self, scenarios: List[Dict]) -> Dict:
        """여러 시나리오 비교 분석"""
        results = []
        
        for i, scenario in enumerate(scenarios):
            result = self.calculate_financial_metrics(**scenario)
            result['scenario_name'] = scenario.get('name', f'시나리오 {i+1}')
            results.append(result)
        
        # 최적 시나리오 찾기
        best_roi = max(results, key=lambda x: x['roi'] if x['roi'] else -999)
        best_payback = min(
            [r for r in results if r['payback_period'] is not None], 
            key=lambda x: x['payback_period'],
            default=None
        )
        
        return {
            'scenarios': results,
            'best_roi': best_roi,
            'best_payback': best_payback
        }
    
    def sensitivity_analysis(
        self, 
        base_scenario: Dict, 
        variable: str, 
        variation_range: tuple
    ) -> List[Dict]:
        """민감도 분석"""
        results = []
        start, end, step = variation_range
        
        current = start
        while current <= end:
            scenario = base_scenario.copy()
            scenario[variable] = current
            
            result = self.calculate_financial_metrics(**scenario)
            result[variable] = current
            results.append(result)
            
            current += step
        
        return results