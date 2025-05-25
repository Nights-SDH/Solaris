# 🔧 1. 필수 패키지 설치
# !pip install flask pyngrok pvlib pandas requests numpy matplotlib seaborn scipy dotenv -q

# 🔧 2. ngrok 인증 토큰 설정 (https://dashboard.ngrok.com/get-started)
from pyngrok import ngrok
import os
from dotenv import load_dotenv

load_dotenv()
ngrok_token = os.getenv('NGROK_AUTH_TOKEN')

ngrok.kill()
ngrok.set_auth_token(ngrok_token)  # ★ 필수!

# 🌞 3. 필요한 라이브러리 임포트
from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import json
import time
import numpy as np
import pandas as pd
import pvlib
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
from scipy.optimize import minimize
from datetime import datetime
matplotlib.use('Agg')  # 서버 환경에서 matplotlib 사용을 위한 백엔드 설정


# 🏭 4. 태양광 발전량 계산 유틸리티 함수
def get_solar_position(lat, lon, date_range):
    """특정 위치와 날짜 범위에 대한 태양 위치 계산"""
    return pvlib.solarposition.get_solarposition(date_range, lat, lon)

def decompose_ghi(ghi_values, solar_zenith, times):
    """GHI를 DNI와 DHI로 분해"""
    return pvlib.irradiance.erbs(ghi_values, solar_zenith, times)

def calculate_aoi(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth):
    """태양광선의 입사각 계산"""
    return pvlib.irradiance.aoi(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth)

def calculate_pv_energy(lat, lon, tilt, azimuth, ghi_annual, system_config=None):
    """상세한 태양광 발전량 계산"""
    # 시스템 기본 설정
    if system_config is None:
        system_config = {
            'albedo': 0.2,
            'efficiency': 0.85,
            'module_type': 'standard',
            'tracking_type': 'fixed',
            'bifacial_factor': 0,
            'inverter_efficiency': 0.96,
            'losses': 0.14,  # 직류 및 교류 손실 (케이블, 오염 등)
            'temp_model': 'sapm',
            'racking_model': 'open_rack'
        }
    
    # 1. 1년 시간 간격 생성 (매시간)
    times = pd.date_range(start='2023-01-01', end='2023-12-31 23:00:00', freq='H')
    
    # 2. 태양 위치 계산
    solpos = get_solar_position(lat, lon, times)
    
    # 3. 연간 평균 GHI를 월별 분포로 변환 (계절적 변동 시뮬레이션)
    # 한국 기준 월별 GHI 분포 비율 (1월부터 12월까지, 대략적 비율)
    monthly_ratio = np.array([0.6, 0.7, 0.9, 1.1, 1.2, 1.1, 1.0, 1.1, 1.0, 0.9, 0.7, 0.6])
    monthly_ratio = monthly_ratio / monthly_ratio.mean()  # 평균이 1이 되도록 정규화
    
    # 각 시간의 월 인덱스 추출
    month_indices = np.array([t.month-1 for t in times])
    
    # 시간별 GHI 분포 생성 (월별 비율 적용 + 일중 변동)
    daily_pattern = np.sin(np.pi * (times.hour) / 24) ** 2  # 간단한 일일 패턴
    daily_pattern[times.hour < 6] = 0  # 새벽 시간대 0으로
    daily_pattern[times.hour > 18] = 0  # 저녁 시간대 0으로
    
    # 각 시간의 GHI 값 계산
    hourly_ghi = ghi_annual / 365 / daily_pattern.sum() * 24  # 일평균으로 변환
    hourly_ghi = hourly_ghi * monthly_ratio[month_indices] * daily_pattern * 24
    
    # 4. GHI를 DNI와 DHI로 분해
    irradiance = decompose_ghi(hourly_ghi, solpos['apparent_zenith'], times)
    dni = irradiance['dni'].fillna(0)
    dhi = irradiance['dhi'].fillna(0)
    
    # 5. 트래킹 시스템인 경우 계산
    if system_config['tracking_type'] == 'single_axis':
        # 단축 트래킹 계산
        tracking = pvlib.tracking.singleaxis(
            solpos['apparent_zenith'],
            solpos['azimuth'],
            axis_tilt=0,
            axis_azimuth=180,
            max_angle=60,
            backtrack=True,
            gcr=0.4  # Ground Coverage Ratio
        )
        surface_tilt = tracking['surface_tilt']
        surface_azimuth = tracking['surface_azimuth']
    else:
        # 고정 시스템
        surface_tilt = np.full_like(solpos['apparent_zenith'], tilt)
        surface_azimuth = np.full_like(solpos['azimuth'], azimuth)
    
    # 6. 입사각 계산
    aoi_values = calculate_aoi(surface_tilt, surface_azimuth, solpos['apparent_zenith'], solpos['azimuth'])
    
    # 7. 하늘 산란일사량 계산 (Perez 모델)
    poa_sky_diffuse = pvlib.irradiance.perez(
        surface_tilt, 
        surface_azimuth, 
        dhi, 
        dni, 
        solpos['apparent_zenith'], 
        solpos['azimuth'],
        airmass=None  # 공기 질량은 자동 계산
    )
    
    # 8. 지면 반사 산란일사량 계산
    poa_ground_diffuse = pvlib.irradiance.get_ground_diffuse(surface_tilt, hourly_ghi, system_config['albedo'])
    
    # 9. 모듈 표면 일사량 계산
    poa_irrad = pvlib.irradiance.poa_components(
        aoi_values, 
        dni, 
        poa_sky_diffuse, 
        poa_ground_diffuse
    )
    
    # 10. 음수 값 제거 및 NaN 처리
    poa_global = poa_irrad['poa_global'].fillna(0).clip(min=0)
    
    # 11. 양면형 모듈 계산 (해당하는 경우)
    if system_config['bifacial_factor'] > 0:
        # 뒷면 일사량 계산 (단순화된 모델)
        poa_rear = poa_ground_diffuse * system_config['bifacial_factor']
        poa_global = poa_global + poa_rear
    
    # 12. 온도 효과 계산
    # 주변 온도 데이터가 없으므로 간단한 추정 사용
    # 한국의 월별 평균 기온 (1월-12월, °C)
    avg_monthly_temp = np.array([-2.4, 0.4, 5.7, 12.5, 17.8, 22.2, 24.9, 25.7, 21.2, 14.8, 7.2, -0.1])
    temp_data = avg_monthly_temp[month_indices]
    
    # 선택한 온도 모델에 따라 모듈 온도 및 효율 계산
    if system_config['temp_model'] == 'sapm':
        # Sandia PV Array Performance Model
        temp_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm'][system_config['racking_model']]
        temp_cell = pvlib.temperature.sapm_cell(poa_global, temp_data, 1.0, temp_params['a'], temp_params['b'], temp_params['deltaT'])
    else:
        # 간단한 모델 (표준 조건에서 1℃ 상승시 0.4% 효율 감소)
        temp_cell = temp_data + 0.035 * poa_global
    
    # NOCT에서의 효율 저하 계산
    temp_factor = 1 - 0.004 * (temp_cell - 25)  # 25℃ 기준
    temp_factor = temp_factor.clip(min=0.7, max=1.1)  # 제한
    
    # 13. 총 효율 계산
    total_efficiency = system_config['efficiency'] * system_config['inverter_efficiency'] * (1 - system_config['losses']) * temp_factor
    
    # 14. 발전량 계산
    hourly_energy = poa_global * total_efficiency / 1000  # kWh/m²
    
    # 15. 결과 집계
    annual_energy = hourly_energy.sum()  # kWh/kWp/year
    monthly_energy = hourly_energy.groupby(times.month).sum()  # kWh/kWp/month
    
    # 16. 최적 각도 계산 (간단한 검사)
    best_tilt, best_azimuth = find_optimal_angles(lat, lon, ghi_annual)
    
    return {
        'annual_energy': round(annual_energy, 1),
        'monthly_energy': monthly_energy.tolist(),
        'hourly_energy': hourly_energy.tolist(),
        'temp_effect': round((temp_factor.mean() - 1) * 100, 2),  # 온도 효과 (%)
        'optimal_tilt': best_tilt,
        'optimal_azimuth': best_azimuth
    }

def find_optimal_angles(lat, lon, ghi_annual, albedo=0.2, system_efficiency=0.85):
    """최적 경사각과 방위각 찾기 (간소화된 버전)"""
    # 위도에 따른 대략적인 최적 경사각 (간단한 경험 법칙)
    optimal_tilt = abs(lat) * 0.76 + 3.1  # 경험적 공식
    
    # 대부분의 경우 남향이 최적 (북반구), 북향이 최적 (남반구)
    optimal_azimuth = 180 if lat >= 0 else 0
    
    return round(optimal_tilt, 1), optimal_azimuth

def find_optimal_angles_detailed(lat, lon, ghi_annual):
    """최적 경사각과 방위각을 상세히 찾기 (최적화 알고리즘 사용)"""
    def objective_function(params):
        tilt, azimuth = params
        # 각도 범위 제한
        if not (0 <= tilt <= 90) or not (0 <= azimuth <= 360):
            return 10000  # 큰 페널티 값
        
        result = calculate_pv_energy(lat, lon, tilt, azimuth, ghi_annual)
        # 목표: 연간 발전량 최대화 (음수로 변환)
        return -result['annual_energy']
    
    # 초기값 (경험적 법칙 기반)
    x0 = [abs(lat) * 0.76 + 3.1, 180 if lat >= 0 else 0]
    
    # 최적화 실행
    bounds = [(0, 90), (0, 360)]
    result = minimize(objective_function, x0, bounds=bounds, method='L-BFGS-B')
    
    if result.success:
        optimal_tilt, optimal_azimuth = result.x
        return round(optimal_tilt, 1), round(optimal_azimuth, 1)
    else:
        # 최적화 실패 시 경험적 법칙 사용
        return find_optimal_angles(lat, lon, ghi_annual)

def generate_pv_chart(monthly_energy):
    """월간 발전량 차트 생성"""
    months = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(months, monthly_energy, color='#2196F3')
    
    # 값 레이블 추가
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=9)
    
    plt.title('월별 태양광 발전량 예측', fontsize=16)
    plt.ylabel('발전량 (kWh/kWp)', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    
    # 차트를 바이트 스트림으로 저장
    img_bytes = BytesIO()
    plt.tight_layout()
    plt.savefig(img_bytes, format='png', dpi=100)
    img_bytes.seek(0)
    plt.close()
    
    return img_bytes

def generate_angle_heatmap(lat, lon, ghi_annual):
    """경사각과 방위각 조합에 따른 발전량 히트맵"""
    # 각도 범위
    tilts = np.arange(0, 91, 5)  # 0도부터 90도까지 5도 간격
    azimuths = np.arange(90, 271, 10)  # 90도(동)부터 270도(서)까지 10도 간격
    
    # 결과 저장 행렬
    energy_matrix = np.zeros((len(tilts), len(azimuths)))
    
    # 각 조합에 대한 발전량 계산
    for i, tilt in enumerate(tilts):
        for j, azimuth in enumerate(azimuths):
            result = calculate_pv_energy(lat, lon, tilt, azimuth, ghi_annual)
            energy_matrix[i, j] = result['annual_energy']
    
    # 최적값 찾기
    max_idx = np.unravel_index(np.argmax(energy_matrix), energy_matrix.shape)
    optimal_tilt = tilts[max_idx[0]]
    optimal_azimuth = azimuths[max_idx[1]]
    max_energy = energy_matrix[max_idx]
    
    # 정규화 (최대값 대비 비율)
    energy_matrix_normalized = energy_matrix / max_energy
    
    # 히트맵 생성
    plt.figure(figsize=(12, 8))
    ax = sns.heatmap(energy_matrix, 
                     xticklabels=azimuths, 
                     yticklabels=tilts,
                     cmap='viridis', 
                     annot=False, 
                     fmt=".1f", 
                     cbar_kws={'label': '연간 발전량 (kWh/kWp)'},
                     vmin=max_energy*0.7, vmax=max_energy*1.0)
    
    # 최적 지점 표시
    ax.plot(max_idx[1] + 0.5, max_idx[0] + 0.5, 'ro', markersize=10)
    
    plt.title(f'경사각/방위각 조합에 따른 발전량 (최적: {optimal_tilt}°/{optimal_azimuth}°)', fontsize=14)
    plt.ylabel('경사각 (°)', fontsize=12)
    plt.xlabel('방위각 (°)', fontsize=12)
    
    # 차트를 바이트 스트림으로 저장
    img_bytes = BytesIO()
    plt.tight_layout()
    plt.savefig(img_bytes, format='png', dpi=120)
    img_bytes.seek(0)
    plt.close()
    
    return img_bytes, optimal_tilt, optimal_azimuth, max_energy

def generate_daily_profile_chart(lat, lon, ghi_annual, tilt, azimuth):
    """계절별 일일 발전량 프로필 차트"""
    # 4계절 대표 날짜
    seasonal_dates = [
        pd.date_range('2023-01-15', periods=24, freq='H'),  # 겨울
        pd.date_range('2023-04-15', periods=24, freq='H'),  # 봄
        pd.date_range('2023-07-15', periods=24, freq='H'),  # 여름
        pd.date_range('2023-10-15', periods=24, freq='H')   # 가을
    ]
    
    plt.figure(figsize=(12, 6))
    
    colors = ['#1E88E5', '#43A047', '#F9A825', '#D81B60']
    labels = ['겨울 (1월)', '봄 (4월)', '여름 (7월)', '가을 (10월)']
    
    # 계절별로 일일 프로필 계산 및 플롯
    for i, dates in enumerate(seasonal_dates):
        # 태양 위치 계산
        solpos = get_solar_position(lat, lon, dates)
        
        # 계절 가중치 (1월=0.6, 4월=1.1, 7월=1.0, 10월=0.9)
        seasonal_weight = [0.6, 1.1, 1.0, 0.9][i]
        
        # 시간별 GHI 분포 생성
        daily_pattern = np.sin(np.pi * (dates.hour) / 24) ** 2
        daily_pattern[dates.hour < 6] = 0
        daily_pattern[dates.hour > 18] = 0
        
        hourly_ghi = ghi_annual / 365 * seasonal_weight
        hourly_ghi = hourly_ghi * daily_pattern * 24
        
        # GHI를 DNI와 DHI로 분해
        irradiance = decompose_ghi(hourly_ghi, solpos['apparent_zenith'], dates)
        dni = irradiance['dni'].fillna(0)
        dhi = irradiance['dhi'].fillna(0)
        
        # 입사각 계산
        aoi_values = calculate_aoi(tilt, azimuth, solpos['apparent_zenith'], solpos['azimuth'])
        
        # 하늘 산란일사량 계산
        poa_sky_diffuse = pvlib.irradiance.haydavies(
            tilt, azimuth, dhi, dni, solpos['apparent_zenith'], solpos['azimuth']
        )
        
        # 지면 반사 산란일사량 계산
        poa_ground_diffuse = pvlib.irradiance.get_ground_diffuse(tilt, hourly_ghi, 0.2)
        
        # 모듈 표면 일사량 계산
        poa_irrad = pvlib.irradiance.poa_components(
            aoi_values, dni, poa_sky_diffuse, poa_ground_diffuse
        )
        
        # 발전량 계산
        hourly_energy = poa_irrad['poa_global'].fillna(0).clip(min=0) * 0.85 / 1000
        
        # 플롯 추가
        plt.plot(range(24), hourly_energy, 'o-', color=colors[i], label=labels[i], linewidth=2)
    
    plt.title('계절별 일일 발전량 프로필', fontsize=16)
    plt.xlabel('시간 (시)', fontsize=12)
    plt.ylabel('시간당 발전량 (kWh/kWp)', fontsize=12)
    plt.grid(linestyle='--', alpha=0.7)
    plt.legend()
    plt.xticks(range(0, 24, 2))
    
    # 차트를 바이트 스트림으로 저장
    img_bytes = BytesIO()
    plt.tight_layout()
    plt.savefig(img_bytes, format='png', dpi=100)
    img_bytes.seek(0)
    plt.close()
    
    return img_bytes

def calculate_enhanced_financial_metrics(annual_energy, system_size=3.0, install_cost_per_kw=1800000, electricity_price=220, annual_degradation=0.005, lifetime=25, smp_price=180, rec_price=40):
    """📌 향상된 태양광 발전 시스템의 재무 지표 계산 (SMP + REC 분리)"""
    # 시스템 비용 (원)
    total_cost = system_size * install_cost_per_kw
    
    # 연간 발전량 (kWh) 및 전력 판매 수익 (원)
    annual_production = system_size * annual_energy
    
    # SMP와 REC 수익 분리 계산
    annual_smp_revenue = annual_production * smp_price
    annual_rec_revenue = annual_production * rec_price
    annual_revenue = annual_smp_revenue + annual_rec_revenue
    
    # 운영 및 유지보수 비용 (설치 비용의 1.5% → 더 현실적)
    annual_maintenance_rate = 0.015
    
    # 연간 현금 흐름 계산
    cash_flows = []
    cumulative_cash_flow = -total_cost  # 초기 투자 비용은 음수
    cash_flows.append(cumulative_cash_flow)
    
    total_revenue_25years = 0
    total_maintenance_25years = 0
    
    for year in range(1, lifetime + 1):
        # 연간 성능 저하 적용
        degraded_factor = (1 - annual_degradation) ** year
        year_revenue = annual_revenue * degraded_factor
        
        # 유지보수 비용 (연차별 증가: 초기 1%, 10년 후 1.5%, 20년 후 2%)
        if year <= 10:
            maintenance_rate = 0.01
        elif year <= 20:
            maintenance_rate = 0.015
        else:
            maintenance_rate = 0.02
            
        maintenance_cost = total_cost * maintenance_rate
        
        # 연간 순이익
        net_cash_flow = year_revenue - maintenance_cost
        cumulative_cash_flow += net_cash_flow
        cash_flows.append(cumulative_cash_flow)
        
        total_revenue_25years += year_revenue
        total_maintenance_25years += maintenance_cost
    
    # 회수 기간 계산 (선형 보간)
    payback_period = None
    for i in range(1, len(cash_flows)):
        if cash_flows[i] >= 0 and cash_flows[i-1] < 0:
            payback_period = i - 1 + (-cash_flows[i-1]) / (cash_flows[i] - cash_flows[i-1])
            break
    
    if payback_period is None and cash_flows[-1] >= 0:
        payback_period = lifetime
    elif payback_period is None:
        payback_period = float('inf')
    
    # ROI 계산 (25년 기준 총 수익률)
    net_profit = total_revenue_25years - total_maintenance_25years - total_cost
    roi = (net_profit / total_cost) * 100 if total_cost > 0 else 0
    
    # 결과 반환
    return {
        'total_cost': int(total_cost),
        'annual_production': round(annual_production, 1),
        'annual_revenue': int(annual_revenue),
        'annual_smp_revenue': int(annual_smp_revenue),
        'annual_rec_revenue': int(annual_rec_revenue),
        'payback_period': round(payback_period, 1) if payback_period != float('inf') else None,
        'roi': round(roi, 1),
        'cash_flows': cash_flows,
        'life_cycle_revenue': int(total_revenue_25years - total_maintenance_25years),
        'net_profit': int(net_profit),
        'monthly_production': round(annual_production / 12, 1),
        'monthly_revenue': int(annual_revenue / 12)
    }     

def generate_roi_chart(financial_data):
    """투자 수익 차트 생성"""
    plt.figure(figsize=(12, 6))
    
    years = list(range(len(financial_data['cash_flows'])))
    cash_flows = financial_data['cash_flows']
    
    # 막대그래프 (연간 현금 흐름)
    plt.bar(years, cash_flows, color=['#D32F2F' if cf < 0 else '#388E3C' for cf in cash_flows])
    
    # 회수 지점 표시
    if financial_data['payback_period'] is not None:
        plt.axvline(x=financial_data['payback_period'], color='blue', linestyle='--', linewidth=2)
        plt.text(financial_data['payback_period'] + 0.5, min(cash_flows) * 0.8, 
                f'회수 기간: {financial_data["payback_period"]:.1f}년', 
                fontsize=12, color='blue')
    
    plt.axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    plt.title('태양광 발전 시스템 투자 수익 분석', fontsize=16)
    plt.xlabel('연도', fontsize=12)
    plt.ylabel('누적 현금 흐름 (원)', fontsize=12)
    plt.grid(linestyle='--', alpha=0.7)
    plt.xticks(range(0, len(years), 5))
    
    # y축 포맷 설정 (수백만 단위)
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, loc: f'{int(x/1000000):,}백만'))
    
    # 차트를 바이트 스트림으로 저장
    img_bytes = BytesIO()
    plt.tight_layout()
    plt.savefig(img_bytes, format='png', dpi=100)
    img_bytes.seek(0)
    plt.close()
    
    return img_bytes

# 🚀 5. Flask 앱 설정
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>고급 태양광 발전량 예측 시스템</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body, html { height: 100%; margin: 0; }
        .container-fluid { height: 100%; padding: 0; }
        .row { height: 100%; margin: 0; }
        #map { height: 100%; }
        .map-container { height: 100%; padding: 0; }
        .control-panel {
          height: 100%;
          overflow-y: auto;
          padding: 20px;
          background-color: #f8f9fa;
        }
        .chart-container {
          margin-top: 20px;
          padding: 10px;
          background-color: white;
          border-radius: 5px;
          box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .loading {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background-color: rgba(0,0,0,0.5);
          z-index: 2000;
          justify-content: center;
          align-items: center;
          color: white;
          font-size: 24px;
        }
        .loader {
          border: 16px solid #f3f3f3;
          border-top: 16px solid #3498db;
          border-radius: 50%;
          width: 120px;
          height: 120px;
          animation: spin 2s linear infinite;
          margin-bottom: 20px;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .nav-tabs {
          margin-bottom: 15px;
        }
        .financial-metrics {
          background-color: #e8f5e9;
          border-radius: 5px;
          padding: 15px;
          margin-top: 20px;
        }
        .btn-action {
          margin-top: 10px;
        }
      </style>
    </head>
    <body>
    <div class="loading" id="loadingIndicator">
      <div style="text-align: center;">
        <div class="loader"></div>
        <div>데이터 분석 중...</div>
      </div>
    </div>

    <div class="container-fluid">
      <div class="row">
        <div class="col-md-8 map-container">
          <div id="map"></div>
        </div>
        <div class="col-md-4 control-panel">
          <h2 class="mb-4">태양광 발전량 예측</h2>
          
          <ul class="nav nav-tabs" id="systemTabs" role="tablist">
            <li class="nav-item" role="presentation">
              <button class="nav-link active" id="basic-tab" data-bs-toggle="tab" data-bs-target="#basic" type="button" role="tab" aria-controls="basic" aria-selected="true">기본 설정</button>
            </li>
            <li class="nav-item" role="presentation">
              <button class="nav-link" id="advanced-tab" data-bs-toggle="tab" data-bs-target="#advanced" type="button" role="tab" aria-controls="advanced" aria-selected="false">고급 설정</button>
            </li>
            <li class="nav-item" role="presentation">
              <button class="nav-link" id="financial-tab" data-bs-toggle="tab" data-bs-target="#financial" type="button" role="tab" aria-controls="financial" aria-selected="false">경제성 분석</button>
            </li>
          </ul>
          
          <div class="tab-content" id="systemTabsContent">
            <div class="tab-pane fade show active" id="basic" role="tabpanel" aria-labelledby="basic-tab">
              <div class="mb-3">
                <label for="tiltSlider" class="form-label">모듈 경사각 (°): <span id="tiltValue">30</span></label>
                <input type="range" class="form-range" id="tiltSlider" min="0" max="90" value="30">
              </div>
              
              <div class="mb-3">
                <label for="azimuthSlider" class="form-label">모듈 방위각 (°): <span id="azimuthValue">180</span></label>
                <input type="range" class="form-range" id="azimuthSlider" min="0" max="360" value="180">
                <small class="text-muted">0°=북, 90°=동, 180°=남, 270°=서</small>
              </div>
              
              <div class="mb-3">
                <label for="efficiencyInput" class="form-label">시스템 효율 (%)</label>
                <input type="number" class="form-control" id="efficiencyInput" min="50" max="100" value="85">
                <small class="text-muted">인버터 및 시스템 손실 고려</small>
              </div>
              
              <div class="mb-3">
                <label for="albedoInput" class="form-label">지면 반사율 (알베도)</label>
                <select class="form-select" id="albedoInput">
                  <option value="0.15">도심 지역 (0.15)</option>
                  <option value="0.2" selected>일반 지역 (0.2)</option>
                  <option value="0.3">초원 지역 (0.3)</option>
                  <option value="0.6">눈 덮인 지역 (0.6)</option>
                </select>
              </div>
            </div>
            
            <div class="tab-pane fade" id="advanced" role="tabpanel" aria-labelledby="advanced-tab">
              <div class="mb-3">
                <label for="moduleTypeInput" class="form-label">모듈 유형</label>
                <select class="form-select" id="moduleTypeInput">
                  <option value="standard" selected>표준형</option>
                  <option value="premium">고효율</option>
                  <option value="thin_film">박막형</option>
                  <option value="bifacial">양면형</option>
                </select>
              </div>
              
              <div class="mb-3">
                <label for="trackingTypeInput" class="form-label">설치 방식</label>
                <select class="form-select" id="trackingTypeInput">
                  <option value="fixed" selected>고정형</option>
                  <option value="single_axis">단축 트래킹</option>
                </select>
              </div>
              
              <div class="mb-3" id="bifacialFactorContainer" style="display: none;">
                <label for="bifacialFactorInput" class="form-label">양면형 계수: <span id="bifacialFactorValue">0.7</span></label>
                <input type="range" class="form-range" id="bifacialFactorInput" min="0.6" max="0.9" step="0.05" value="0.7">
                <small class="text-muted">뒷면의 효율 비율 (보통 0.6-0.9)</small>
              </div>
              
              <div class="mb-3">
                <label for="temperatureModelInput" class="form-label">온도 모델</label>
                <select class="form-select" id="temperatureModelInput">
                  <option value="sapm" selected>SAPM (Sandia)</option>
                  <option value="simple">단순 모델</option>
                </select>
              </div>
              
              <div class="mb-3">
                <label for="rackingModelInput" class="form-label">설치 구조</label>
                <select class="form-select" id="rackingModelInput">
                  <option value="open_rack" selected>개방형 랙</option>
                  <option value="close_mount">밀착형 설치</option>
                  <option value="insulated_back">단열 후면</option>
                </select>
              </div>
            </div>
            
            <div class="tab-pane fade" id="financial" role="tabpanel" aria-labelledby="financial-tab">
              <!-- 📌 1. 면적 입력 → 설치 가능 용량 자동 계산 -->
              <div class="mb-3">
                <label for="landAreaInput" class="form-label">토지 면적 (㎡)</label>
                <input type="number" class="form-control" id="landAreaInput" min="32" max="50000" step="10" placeholder="예: 960">
                <small class="text-muted">면적 입력 시 설치 가능 용량을 자동 계산합니다 (1kW당 32㎡ 기준)</small>
              </div>
              
              <div class="mb-3">
                <label for="systemSizeInput" class="form-label">시스템 용량 (kWp)</label>
                <input type="number" class="form-control" id="systemSizeInput" min="1" max="1000" value="3">
                <small class="text-muted" id="capacityCalculation" style="display: none;"></small>
              </div>
              
              <!-- 📌 2. 설치 유형 선택 → 설치비 자동 반영 -->
              <div class="mb-3">
                <label for="installationTypeSelect" class="form-label">설치 유형</label>
                <select class="form-select" id="installationTypeSelect">
                  <option value="fixed" data-cost="1800000">고정형 (1,800,000원/kW)</option>
                  <option value="tilted" data-cost="2000000">경사형 (2,000,000원/kW)</option>
                  <option value="ess" data-cost="2500000">ESS 포함형 (2,500,000원/kW)</option>
                  <option value="tracking" data-cost="2200000">단축 트래킹 (2,200,000원/kW)</option>
                  <option value="custom" data-cost="1500000">사용자 정의</option>
                </select>
              </div>
              
              <div class="mb-3" id="customCostContainer" style="display: none;">
                <label for="installCostInput" class="form-label">설치 비용 (원/kWp)</label>
                <input type="number" class="form-control" id="installCostInput" min="500000" max="5000000" step="50000" value="1500000">
              </div>
              
              <!-- 📌 3. SMP 기반 수익 예측 -->
              <div class="mb-3">
                <label for="smpPriceInput" class="form-label">SMP 전력 판매 단가 (원/kWh)</label>
                <input type="number" class="form-control" id="smpPriceInput" min="50" max="500" value="180">
                <small class="text-muted">현재 SMP 평균: 약 180원/kWh (2024년 기준)</small>
              </div>
              
              <div class="mb-3">
                <label for="recPriceInput" class="form-label">REC 가격 (원/kWh)</label>
                <input type="number" class="form-control" id="recPriceInput" min="0" max="200" value="40">
                <small class="text-muted">신재생에너지 공급인증서 가격 (선택사항)</small>
              </div>
          </div>
          
          <div class="alert alert-info" id="instructionAlert">
            지도에서 위치를 클릭하면 해당 지점의 태양광 발전량을 계산합니다.
          </div>
          
          <div id="resultsContainer" style="display: none;">
            <h4>분석 결과</h4>
            <div class="mb-2">
              <strong>위치:</strong> <span id="locationText"></span>
            </div>
            <div class="mb-2">
              <strong>연평균 일사량:</strong> <span id="ghiText"></span> kWh/m²/년
            </div>
            <div class="mb-2">
              <strong>연간 발전량:</strong> <span id="energyText"></span> kWh/kWp/년
            </div>
            <div class="mb-2">
              <strong>온도 효과:</strong> <span id="tempEffectText"></span>% 효율 변화
            </div>
            <div class="mb-2">
              <strong>최적 설치 각도:</strong> 경사각 <span id="optimalTiltText"></span>°, 방위각 <span id="optimalAzimuthText"></span>°
            </div>
            
            <div class="d-grid gap-2 mt-3">
              <button class="btn btn-primary" id="optimizeButton">최적 각도 찾기</button>
              <button class="btn btn-outline-primary" id="resetParamsButton">매개변수 초기화</button>
            </div>
            
            <div class="financial-metrics" id="financialMetrics" style="display: none;">
              <h5>경제성 분석</h5>
              <div class="mb-2">
                <strong>총 설치 비용:</strong> <span id="totalCostText"></span>원
              </div>
              <div class="mb-2">
                <strong>연간 발전량:</strong> <span id="annualProductionText"></span> kWh
              </div>
              <div class="mb-2">
                <strong>연간 수익:</strong> <span id="annualRevenueText"></span>원
              </div>
              <div class="mb-2">
                <strong>투자 회수 기간:</strong> <span id="paybackPeriodText"></span>년
              </div>
              <div class="mb-2">
                <strong>투자 수익률 (ROI):</strong> <span id="roiText"></span>%
              </div>
              <div class="mb-2">
                <strong>생애 총 수익:</strong> <span id="lifeCycleRevenueText"></span>원
              </div>
            </div>
            
            <ul class="nav nav-tabs mt-4" id="chartTabs" role="tablist">
              <li class="nav-item" role="presentation">
                <button class="nav-link active" id="monthly-tab" data-bs-toggle="tab" data-bs-target="#monthlyChartTab" type="button" role="tab" aria-controls="monthlyChartTab" aria-selected="true">월별 발전량</button>
              </li>
              <li class="nav-item" role="presentation">
                <button class="nav-link" id="optimization-tab" data-bs-toggle="tab" data-bs-target="#optimizationChartTab" type="button" role="tab" aria-controls="optimizationChartTab" aria-selected="false">각도 최적화</button>
              </li>
              <li class="nav-item" role="presentation">
                <button class="nav-link" id="daily-tab" data-bs-toggle="tab" data-bs-target="#dailyChartTab" type="button" role="tab" aria-controls="dailyChartTab" aria-selected="false">일일 프로필</button>
              </li>
              <li class="nav-item" role="presentation">
                <button class="nav-link" id="financial-chart-tab" data-bs-toggle="tab" data-bs-target="#financialChartTab" type="button" role="tab" aria-controls="financialChartTab" aria-selected="false">투자 수익</button>
              </li>
            </ul>
            
            <div class="tab-content" id="chartTabsContent">
              <div class="tab-pane fade show active" id="monthlyChartTab" role="tabpanel" aria-labelledby="monthly-tab">
                <div class="chart-container">
                  <img id="monthlyChart" class="img-fluid" src="" alt="월별 발전량 차트">
                </div>
              </div>
              <div class="tab-pane fade" id="optimizationChartTab" role="tabpanel" aria-labelledby="optimization-tab">
                <div class="chart-container">
                  <img id="angleHeatmapChart" class="img-fluid" src="" alt="각도 최적화 히트맵">
                </div>
              </div>
              <div class="tab-pane fade" id="dailyChartTab" role="tabpanel" aria-labelledby="daily-tab">
                <div class="chart-container">
                  <img id="dailyProfileChart" class="img-fluid" src="" alt="일일 발전량 프로필">
                </div>
              </div>
              <div class="tab-pane fade" id="financialChartTab" role="tabpanel" aria-labelledby="financial-chart-tab">
                <div class="chart-container">
                  <img id="roiChart" class="img-fluid" src="" alt="투자 수익 차트">
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
      // 지도 초기화
      const map = L.map('map').setView([36.5, 127.8], 7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
      }).addTo(map);
      
      // 현재 선택된 위치 마커
      let currentMarker = null;
      let currentLatLng = null;
      
      // UI 요소
      const tiltSlider = document.getElementById('tiltSlider');
      const tiltValue = document.getElementById('tiltValue');
      const azimuthSlider = document.getElementById('azimuthSlider');
      const azimuthValue = document.getElementById('azimuthValue');
      const efficiencyInput = document.getElementById('efficiencyInput');
      const albedoInput = document.getElementById('albedoInput');
      const moduleTypeInput = document.getElementById('moduleTypeInput');
      const trackingTypeInput = document.getElementById('trackingTypeInput');
      const bifacialFactorInput = document.getElementById('bifacialFactorInput');
      const bifacialFactorValue = document.getElementById('bifacialFactorValue');
      const bifacialFactorContainer = document.getElementById('bifacialFactorContainer');
      const temperatureModelInput = document.getElementById('temperatureModelInput');
      const rackingModelInput = document.getElementById('rackingModelInput');
      const systemSizeInput = document.getElementById('systemSizeInput');
      const installCostInput = document.getElementById('installCostInput');
      const electricityPriceInput = document.getElementById('electricityPriceInput');
      const annualDegradationInput = document.getElementById('annualDegradationInput');
      const degradationValue = document.getElementById('degradationValue');
      const lifetimeInput = document.getElementById('lifetimeInput');
      const optimizeButton = document.getElementById('optimizeButton');
      const resetParamsButton = document.getElementById('resetParamsButton');
      const loadingIndicator = document.getElementById('loadingIndicator');
      const financialMetrics = document.getElementById('financialMetrics');
      
      // 슬라이더 값 표시 업데이트
      tiltSlider.addEventListener('input', () => {
        tiltValue.textContent = tiltSlider.value;
        if (currentLatLng) updateResults();
      });
      
      azimuthSlider.addEventListener('input', () => {
        azimuthValue.textContent = azimuthSlider.value;
        if (currentLatLng) updateResults();
      });
      
      bifacialFactorInput.addEventListener('input', () => {
        bifacialFactorValue.textContent = bifacialFactorInput.value;
        if (currentLatLng) updateResults();
      });
      
      annualDegradationInput.addEventListener('input', () => {
        degradationValue.textContent = annualDegradationInput.value;
        if (currentLatLng) updateResults();
      });
      
      // 양면형 모듈 선택 시 양면형 계수 표시
      moduleTypeInput.addEventListener('change', () => {
        if (moduleTypeInput.value === 'bifacial') {
          bifacialFactorContainer.style.display = 'block';
        } else {
          bifacialFactorContainer.style.display = 'none';
        }
        if (currentLatLng) updateResults();
      });
      
      // 다른 입력 변경 시 업데이트
      const inputElements = [
        efficiencyInput, albedoInput, trackingTypeInput, temperatureModelInput, 
        rackingModelInput, systemSizeInput, installCostInput, electricityPriceInput,
        lifetimeInput
      ];
      
      inputElements.forEach(element => {
        element.addEventListener('change', () => {
          if (currentLatLng) updateResults();
        });
      });
      
      // 최적 각도 적용
      optimizeButton.addEventListener('click', () => {
        const optimalTilt = document.getElementById('optimalTiltText').textContent;
        const optimalAzimuth = document.getElementById('optimalAzimuthText').textContent;
        
        tiltSlider.value = optimalTilt;
        tiltValue.textContent = optimalTilt;
        
        azimuthSlider.value = optimalAzimuth;
        azimuthValue.textContent = optimalAzimuth;
        
        updateResults();
      });
      
      // 매개변수 초기화
      resetParamsButton.addEventListener('click', () => {
        // 기본 탭 매개변수
        tiltSlider.value = 30;
        tiltValue.textContent = 30;
        
        azimuthSlider.value = 180;
        azimuthValue.textContent = 180;
        
        efficiencyInput.value = 85;
        albedoInput.value = 0.2;
        
        // 고급 탭 매개변수
        moduleTypeInput.value = 'standard';
        trackingTypeInput.value = 'fixed';
        temperatureModelInput.value = 'sapm';
        rackingModelInput.value = 'open_rack';
        bifacialFactorInput.value = 0.7;
        bifacialFactorValue.textContent = 0.7;
        bifacialFactorContainer.style.display = 'none';
        
        // 경제성 탭 매개변수
        systemSizeInput.value = 3;
        installCostInput.value = 1500000;
        electricityPriceInput.value = 120;
        annualDegradationInput.value = 0.5;
        degradationValue.textContent = 0.5;
        lifetimeInput.value = 25;
        
        updateResults();
      });
      
      // 지도 클릭 이벤트
      function onMapClick(e) {
        const lat = e.latlng.lat.toFixed(5);
        const lon = e.latlng.lng.toFixed(5);
        
        // 기존 마커 제거
        if (currentMarker) {
          map.removeLayer(currentMarker);
        }
        
        // 새 마커 추가
        currentMarker = L.marker(e.latlng).addTo(map);
        currentLatLng = e.latlng;
        
        // 결과 업데이트
        updateResults();
      }
      
      // 결과 업데이트
      function updateResults() {
        if (!currentLatLng) return;
        
        // 로딩 표시
        loadingIndicator.style.display = 'flex';
        
        // 기본 매개변수
        const lat = currentLatLng.lat.toFixed(5);
        const lon = currentLatLng.lng.toFixed(5);
        const tilt = tiltSlider.value;
        const azimuth = azimuthSlider.value;
        const efficiency = efficiencyInput.value / 100;
        const albedo = parseFloat(albedoInput.value);
        
        // 고급 매개변수
        const moduleType = moduleTypeInput.value;
        const trackingType = trackingTypeInput.value;
        const bifacialFactor = moduleType === 'bifacial' ? parseFloat(bifacialFactorInput.value) : 0;
        const temperatureModel = temperatureModelInput.value;
        const rackingModel = rackingModelInput.value;
        
        // 경제성 매개변수
        const systemSize = parseFloat(systemSizeInput.value);
        const installCost = parseFloat(installCostInput.value);
        const electricityPrice = parseFloat(electricityPriceInput.value);
        const annualDegradation = parseFloat(annualDegradationInput.value) / 100;
        const lifetime = parseInt(lifetimeInput.value);
        
        // 시스템 구성 객체
        const systemConfig = {
          albedo: albedo,
          efficiency: efficiency,
          module_type: moduleType,
          tracking_type: trackingType,
          bifacial_factor: bifacialFactor,
          inverter_efficiency: 0.96,
          losses: 0.14,
          temp_model: temperatureModel,
          racking_model: rackingModel
        };
        
        // API 요청
        fetch(`/get_advanced_pv_data?lat=${lat}&lon=${lon}&tilt=${tilt}&azimuth=${azimuth}&system_config=${JSON.stringify(systemConfig)}`)
          .then(res => res.json())
          .then(data => {
            if (data.error) {
              alert('데이터 조회 오류: ' + data.error);
              loadingIndicator.style.display = 'none';
              return;
            }
            
            // 결과 표시
            document.getElementById('resultsContainer').style.display = 'block';
            document.getElementById('locationText').textContent = `${lat}, ${lon}`;
            document.getElementById('ghiText').textContent = data.ghi;
            document.getElementById('energyText').textContent = data.energy;
            document.getElementById('tempEffectText').textContent = data.temp_effect;
            document.getElementById('optimalTiltText').textContent = data.optimal_tilt;
            document.getElementById('optimalAzimuthText').textContent = data.optimal_azimuth;
            
            // 차트 업데이트
            document.getElementById('monthlyChart').src = `/get_monthly_chart?lat=${lat}&lon=${lon}&tilt=${tilt}&azimuth=${azimuth}&system_config=${JSON.stringify(systemConfig)}`;
            document.getElementById('angleHeatmapChart').src = `/get_angle_heatmap?lat=${lat}&lon=${lon}`;
            document.getElementById('dailyProfileChart').src = `/get_daily_profile_chart?lat=${lat}&lon=${lon}&tilt=${tilt}&azimuth=${azimuth}`;
            
            // 경제성 분석
            fetch(`/get_financial_metrics?annual_energy=${data.energy}&system_size=${systemSize}&install_cost=${installCost}&electricity_price=${electricityPrice}&annual_degradation=${annualDegradation}&lifetime=${lifetime}`)
              .then(res => res.json())
              .then(financialData => {
                // 경제성 결과 표시
                financialMetrics.style.display = 'block';
                document.getElementById('totalCostText').textContent = financialData.total_cost.toLocaleString();
                document.getElementById('annualProductionText').textContent = financialData.annual_production.toLocaleString();
                document.getElementById('annualRevenueText').textContent = financialData.annual_revenue.toLocaleString();
                document.getElementById('paybackPeriodText').textContent = financialData.payback_period || '투자 회수 불가';
                document.getElementById('roiText').textContent = financialData.roi;
                document.getElementById('lifeCycleRevenueText').textContent = financialData.life_cycle_revenue.toLocaleString();
                
                // 투자 수익 차트 업데이트
                document.getElementById('roiChart').src = `/get_roi_chart?annual_energy=${data.energy}&system_size=${systemSize}&install_cost=${installCost}&electricity_price=${electricityPrice}&annual_degradation=${annualDegradation}&lifetime=${lifetime}`;
                
                // 로딩 표시 제거
                loadingIndicator.style.display = 'none';
              })
              .catch(err => {
                console.error('Error:', err);
                alert('경제성 분석 중 오류가 발생했습니다.');
                loadingIndicator.style.display = 'none';
              });
          })
          .catch(err => {
            console.error('Error:', err);
            alert('데이터 조회 중 오류가 발생했습니다.');
            loadingIndicator.style.display = 'none';
          });
      }
      
      map.on('click', onMapClick);
    </script>
    </body>
    </html>
    """)

@app.route('/get_advanced_pv_data')
def get_advanced_pv_data():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    tilt = request.args.get('tilt', default=30, type=float)
    azimuth = request.args.get('azimuth', default=180, type=float)
    
    # JSON 문자열에서 시스템 구성 파싱
    system_config_str = request.args.get('system_config', default=None)
    if system_config_str:
        try:
            system_config = json.loads(system_config_str)
        except:
            system_config = None
    else:
        system_config = None
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except Exception as e:
        return jsonify({'error': f'GHI data not found: {str(e)}'}), 500
    
    # 고급 태양광 발전량 계산
    try:
        pv_result = calculate_pv_energy(
            lat=lat, 
            lon=lon, 
            tilt=tilt, 
            azimuth=azimuth, 
            ghi_annual=ghi, 
            system_config=system_config
        )
    except Exception as e:
        return jsonify({'error': f'PV calculation error: {str(e)}'}), 500
    
    return jsonify({
        'ghi': round(ghi, 1),
        'energy': pv_result['annual_energy'],
        'monthly_energy': pv_result['monthly_energy'],
        'temp_effect': pv_result['temp_effect'],
        'optimal_tilt': pv_result['optimal_tilt'],
        'optimal_azimuth': pv_result['optimal_azimuth']
    })

@app.route('/get_monthly_chart')
def get_monthly_chart():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    tilt = request.args.get('tilt', default=30, type=float)
    azimuth = request.args.get('azimuth', default=180, type=float)
    
    # JSON 문자열에서 시스템 구성 파싱
    system_config_str = request.args.get('system_config', default=None)
    if system_config_str:
        try:
            system_config = json.loads(system_config_str)
        except:
            system_config = None
    else:
        system_config = None
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "Error: GHI data not found", 500
    
    # 발전량 계산
    pv_result = calculate_pv_energy(
        lat=lat, 
        lon=lon, 
        tilt=tilt, 
        azimuth=azimuth, 
        ghi_annual=ghi, 
        system_config=system_config
    )
    
    # 차트 생성
    img_bytes = generate_pv_chart(pv_result['monthly_energy'])
    
    return send_file(img_bytes, mimetype='image/png')

@app.route('/get_angle_heatmap')
def get_angle_heatmap():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "Error: GHI data not found", 500
    
    # 경사각/방위각 히트맵 생성
    img_bytes, optimal_tilt, optimal_azimuth, max_energy = generate_angle_heatmap(lat, lon, ghi)
    
    return send_file(img_bytes, mimetype='image/png')

@app.route('/get_daily_profile_chart')
def get_daily_profile_chart():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    tilt = request.args.get('tilt', default=30, type=float)
    azimuth = request.args.get('azimuth', default=180, type=float)
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "Error: GHI data not found", 500
    
    # 일일 프로필 차트 생성
    img_bytes = generate_daily_profile_chart(lat, lon, ghi, tilt, azimuth)
    
    return send_file(img_bytes, mimetype='image/png')

@app.route('/get_financial_metrics')
def get_financial_metrics():
    annual_energy = request.args.get('annual_energy', type=float)
    system_size = request.args.get('system_size', default=3.0, type=float)
    install_cost = request.args.get('install_cost', default=1500000, type=float)
    electricity_price = request.args.get('electricity_price', default=120, type=float)
    annual_degradation = request.args.get('annual_degradation', default=0.005, type=float)
    lifetime = request.args.get('lifetime', default=25, type=int)
    
    # 경제성 지표 계산
    financial_data = calculate_financial_metrics(
        annual_energy=annual_energy,
        system_size=system_size,
        install_cost_per_kw=install_cost,
        electricity_price=electricity_price,
        annual_degradation=annual_degradation,
        lifetime=lifetime
    )
    
    return jsonify(financial_data)

@app.route('/get_roi_chart')
def get_roi_chart():
    annual_energy = request.args.get('annual_energy', type=float)
    system_size = request.args.get('system_size', default=3.0, type=float)
    install_cost = request.args.get('install_cost', default=1500000, type=float)
    electricity_price = request.args.get('electricity_price', default=120, type=float)
    annual_degradation = request.args.get('annual_degradation', default=0.005, type=float)
    lifetime = request.args.get('lifetime', default=25, type=int)
    
    # 경제성 지표 계산
    financial_data = calculate_financial_metrics(
        annual_energy=annual_energy,
        system_size=system_size,
        install_cost_per_kw=install_cost,
        electricity_price=electricity_price,
        annual_degradation=annual_degradation,
        lifetime=lifetime
    )
    
    # ROI 차트 생성
    img_bytes = generate_roi_chart(financial_data)
    
    return send_file(img_bytes, mimetype='image/png')

# 🔥 히트맵 생성 및 시각화 코드
@app.route('/heatmap')
def heatmap():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>태양광 발전량 히트맵</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body, html { height: 100%; margin: 0; }
        #map { height: 100vh; }
        .legend {
            line-height: 18px;
            color: #555;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .legend i {
            width: 18px;
            height: 18px;
            float: left;
            margin-right: 8px;
            opacity: 0.7;
        }
        .control-container {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            max-width: 300px;
        }
      </style>
    </head>
    <body>
    <div id="map"></div>
    
    <div class="control-container">
      <h4>태양광 발전량 히트맵</h4>
      <p>한국 전역의 태양광 발전 잠재력을 시각화한 히트맵입니다.</p>
      <div class="mb-3">
        <label for="tiltInput" class="form-label">경사각 (°)</label>
        <select class="form-select" id="tiltInput" disabled>
          <option value="optimal" selected>최적 경사각 (위도 기반)</option>
        </select>
      </div>
      <div class="mb-3">
        <label for="azimuthInput" class="form-label">방위각 (°)</label>
        <select class="form-select" id="azimuthInput" disabled>
          <option value="180" selected>남향 (180°)</option>
        </select>
      </div>
      <div class="mt-3">
        <a href="/" class="btn btn-primary">상세 분석으로 이동</a>
      </div>
    </div>

    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>
    <script>
      const map = L.map('map').setView([36.5, 127.8], 7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
      }).addTo(map);

      fetch('/heat_data.json')
        .then(res => res.json())
        .then(data => {
          // 히트맵 레이어 추가
          const heatLayer = L.heatLayer(data, {
            radius: 25,
            blur: 15,
            maxZoom: 10,
            gradient: {0.4: 'blue', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}
          }).addTo(map);
          
          // 범례 추가
          const legend = L.control({position: 'bottomright'});
          legend.onAdd = function (map) {
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = `
              <h5>태양광 발전 잠재력</h5>
              <i style="background: red"></i> 매우 높음 (1300+ kWh/kWp)<br>
              <i style="background: yellow"></i> 높음 (1100-1300 kWh/kWp)<br>
              <i style="background: lime"></i> 중간 (900-1100 kWh/kWp)<br>
              <i style="background: blue"></i> 낮음 (900 kWh/kWp 이하)<br>
              <small>연간 발전량 기준</small>
            `;
            return div;
          };
          legend.addTo(map);
          
          // 클릭 이벤트 추가 (상세 페이지로 이동)
          map.on('click', function(e) {
            const lat = e.latlng.lat.toFixed(5);
            const lon = e.latlng.lng.toFixed(5);
            window.location.href = `/?lat=${lat}&lon=${lon}`;
          });
        });
    </script>
    </body>
    </html>
    """)

@app.route('/heat_data.json')
def heatmap_json():
    return send_file('heat_data.json', mimetype='application/json')

def generate_heat_data():
    """한국 지역 태양광 발전량 히트맵 데이터 생성"""
    def frange(start, stop, step):
        while start <= stop:
            yield round(start, 2)
            start += step

    lat_range = list(frange(33.0, 38.0, 0.5))
    lon_range = list(frange(126.0, 130.0, 0.5))
    
    heat_data = []
    
    for lat in lat_range:
        for lon in lon_range:
            url = (
                f'https://power.larc.nasa.gov/api/temporal/climatology/point'
                f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
            )
            try:
                res = requests.get(url).json()
                ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
                
                # 태양광 발전량 계산 (간소화된 버전)
                tilt = abs(lat) * 0.76 + 3.1  # 위도 기반 최적 경사각
                azimuth = 180  # 남향
                
                # 간소화된 발전량 계산 (정확도 향상)
                # 경사각과 방위각에 따른 보정 계수
                tilt_factor = 0.95 + 0.05 * (tilt / 35)  # 적절한 경사각 보정
                if 160 <= azimuth <= 200:  # 남향 근처
                    azimuth_factor = 1.0
                elif azimuth < 90 or azimuth > 270:  # 북쪽에 가까울수록
                    azimuth_factor = 0.7
                else:  # 동/서향
                    azimuth_factor = 0.85
                
                energy = ghi * 0.85 * tilt_factor * azimuth_factor
                
                # 히트맵 데이터 정규화 (0~1 사이 값으로)
                max_expected_energy = 1600  # 예상 최대 발전량
                intensity = round(energy / max_expected_energy, 3)
                
                heat_data.append([lat, lon, intensity])
                print(f"{lat}, {lon} → GHI: {ghi}, Energy: {round(energy, 1)}")
            except Exception as e:
                print(f"❌ 실패: {lat}, {lon} - {str(e)}")
            
            # API 속도 제한 준수
            time.sleep(1)
    
    # JSON 저장
    with open("heat_data.json", "w") as f:
        json.dump(heat_data, f)
    
    print(f"✅ 히트맵 데이터 생성 완료: {len(heat_data)}개 지점")
    return heat_data

# 히트맵 데이터가 없으면 새로 생성하는 함수
def ensure_heat_data_exists():
    import os
    if not os.path.exists('heat_data.json'):
        print("히트맵 데이터 파일이 없습니다. 새로 생성합니다...")
        generate_heat_data()
    else:
        print("기존 히트맵 데이터 사용")

# ⚡ 추가 기능: 태양광 시스템 설계 도구 페이지
@app.route('/system_designer')
def system_designer():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>태양광 시스템 설계 도구</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { padding: 20px; }
        .canvas-container {
          border: 1px solid #ddd;
          border-radius: 5px;
          margin-top: 20px;
          overflow: hidden;
        }
        #designCanvas {
          background-color: #f8f9fa;
        }
        .panel-container {
          height: 100%;
          padding: 20px;
          background-color: #f8f9fa;
          border-radius: 5px;
        }
        .result-panel {
          margin-top: 20px;
          padding: 15px;
          background-color: #e8f5e9;
          border-radius: 5px;
        }
      </style>
    </head>
    <body>
    <div class="container">
      <div class="row mb-4">
        <div class="col">
          <h1>태양광 시스템 설계 도구</h1>
          <p class="lead">설치 공간에 태양광 모듈을 배치하고 시스템을 설계해보세요.</p>
          <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
              <li class="breadcrumb-item"><a href="/">홈</a></li>
              <li class="breadcrumb-item"><a href="/heatmap">히트맵</a></li>
              <li class="breadcrumb-item active" aria-current="page">시스템 설계</li>
            </ol>
          </nav>
        </div>
      </div>
      
      <div class="row">
        <div class="col-md-8">
          <div class="canvas-container">
            <canvas id="designCanvas" width="800" height="600"></canvas>
          </div>
          <div class="d-flex justify-content-between mt-3">
            <div>
              <button class="btn btn-outline-secondary" id="clearBtn">초기화</button>
              <button class="btn btn-outline-secondary" id="undoBtn">실행 취소</button>
            </div>
            <div>
              <button class="btn btn-primary" id="calculateBtn">발전량 계산</button>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="panel-container">
            <h4>설계 매개변수</h4>
            
            <div class="mb-3">
              <label for="locationInput" class="form-label">설치 위치 (위도, 경도)</label>
              <input type="text" class="form-control" id="locationInput" placeholder="36.5, 127.8">
            </div>
            
            <div class="mb-3">
              <label for="roofTypeSelect" class="form-label">설치 면 유형</label>
              <select class="form-select" id="roofTypeSelect">
                <option value="flat">평지붕</option>
                <option value="pitched">경사지붕</option>
                <option value="ground">지면</option>
              </select>
            </div>
            
            <div class="mb-3">
              <label for="moduleTypeSelect" class="form-label">모듈 유형</label>
              <select class="form-select" id="moduleTypeSelect">
                <option value="standard" data-width="1.0" data-height="1.7" data-power="400">표준형 (400W, 1.0m x 1.7m)</option>
                <option value="high_efficiency" data-width="1.0" data-height="1.7" data-power="450">고효율 (450W, 1.0m x 1.7m)</option>
                <option value="bifacial" data-width="1.0" data-height="1.7" data-power="430">양면형 (430W, 1.0m x 1.7m)</option>
                <option value="thin_film" data-width="0.6" data-height="1.2" data-power="150">박막형 (150W, 0.6m x 1.2m)</option>
              </select>
            </div>
            
            <div class="mb-3">
              <label for="roofTiltInput" class="form-label">설치면 경사각 (°)</label>
              <input type="number" class="form-control" id="roofTiltInput" min="0" max="60" value="0">
            </div>
            
            <div class="mb-3">
              <label for="roofAzimuthInput" class="form-label">설치면 방위각 (°)</label>
              <input type="number" class="form-control" id="roofAzimuthInput" min="0" max="360" value="180">
              <small class="text-muted">0°=북, 90°=동, 180°=남, 270°=서</small>
            </div>
            
            <div class="mb-3">
              <label for="drawingModeSelect" class="form-label">그리기 모드</label>
              <select class="form-select" id="drawingModeSelect">
                <option value="area">설치 영역 그리기</option>
                <option value="module">모듈 배치하기</option>
                <option value="obstacle">장애물 추가하기</option>
              </select>
            </div>
            
            <div class="form-check mb-3">
              <input class="form-check-input" type="checkbox" id="automaticLayoutCheck" checked>
              <label class="form-check-label" for="automaticLayoutCheck">
                자동 모듈 배치
              </label>
            </div>
            
            <div id="resultPanel" class="result-panel" style="display: none;">
              <h5>시스템 결과</h5>
              <div class="mb-2">
                <strong>총 모듈 수:</strong> <span id="totalModulesText">0</span>개
              </div>
              <div class="mb-2">
                <strong>시스템 용량:</strong> <span id="systemCapacityText">0</span> kWp
              </div>
              <div class="mb-2">
                <strong>설치 면적:</strong> <span id="installAreaText">0</span> m²
              </div>
              <div class="mb-2">
                <strong>예상 연간 발전량:</strong> <span id="annualEnergyText">0</span> kWh/년
              </div>
              <div class="mb-2">
                <strong>예상 월평균 발전량:</strong> <span id="monthlyEnergyText">0</span> kWh/월
              </div>
              <div class="mb-2">
                <strong>설치 비용 예상:</strong> <span id="installCostText">0</span>원
              </div>
              <div class="mt-3">
                <button class="btn btn-sm btn-outline-primary" id="saveDesignBtn">설계 저장</button>
                <button class="btn btn-sm btn-outline-secondary" id="generateReportBtn">보고서 생성</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
      // 캔버스 및 컨텍스트 초기화
      const canvas = document.getElementById('designCanvas');
      const ctx = canvas.getContext('2d');
      
      // 변수 초기화
      let drawingMode = 'area';
      let isDrawing = false;
      let currentPath = [];
      let areas = [];
      let obstacles = [];
      let modules = [];
      let selectedModuleType = {
        width: 1.0,
        height: 1.7,
        power: 400
      };
      
      // UI 요소
      const drawingModeSelect = document.getElementById('drawingModeSelect');
      const moduleTypeSelect = document.getElementById('moduleTypeSelect');
      const clearBtn = document.getElementById('clearBtn');
      const undoBtn = document.getElementById('undoBtn');
      const calculateBtn = document.getElementById('calculateBtn');
      const automaticLayoutCheck = document.getElementById('automaticLayoutCheck');
      const resultPanel = document.getElementById('resultPanel');
      
      // 그리기 모드 변경
      drawingModeSelect.addEventListener('change', function() {
        drawingMode = this.value;
      });
      
      // 모듈 유형 변경
      moduleTypeSelect.addEventListener('change', function() {
        const option = this.options[this.selectedIndex];
        selectedModuleType = {
          width: parseFloat(option.dataset.width),
          height: parseFloat(option.dataset.height),
          power: parseFloat(option.dataset.power)
        };
      });
      
      // 캔버스 이벤트 리스너
      canvas.addEventListener('mousedown', startDrawing);
      canvas.addEventListener('mousemove', draw);
      canvas.addEventListener('mouseup', endDrawing);
      canvas.addEventListener('mouseout', endDrawing);
      
      // 버튼 이벤트 리스너
      clearBtn.addEventListener('click', clearCanvas);
      undoBtn.addEventListener('click', undoLastAction);
      calculateBtn.addEventListener('click', calculateSystem);
      
      // 그리기 시작
      function startDrawing(e) {
        isDrawing = true;
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        currentPath = [{x, y}];
        
        if (drawingMode === 'module') {
          // 모듈 배치 모드에서는 즉시 모듈 추가
          const moduleWidth = selectedModuleType.width * 50;  // 픽셀 단위로 변환
          const moduleHeight = selectedModuleType.height * 50;
          
          modules.push({
            x: x - moduleWidth / 2,
            y: y - moduleHeight / 2,
            width: moduleWidth,
            height: moduleHeight,
            power: selectedModuleType.power
          });
          
          redrawCanvas();
          isDrawing = false;
        }
      }
      
      // 그리기 중
      function draw(e) {
        if (!isDrawing) return;
        if (drawingMode === 'module') return;
        
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        currentPath.push({x, y});
        redrawCanvas();
      }
      
      // 그리기 종료
      function endDrawing() {
        if (!isDrawing) return;
        isDrawing = false;
        
        if (currentPath.length < 3) {
          // 점이 너무 적으면 무시
          currentPath = [];
          return;
        }
        
        if (drawingMode === 'area') {
          // 닫힌 영역 완성
          areas.push([...currentPath]);
          
          if (automaticLayoutCheck.checked) {
            // 자동 모듈 배치
            addModulesToArea(currentPath);
          }
        } else if (drawingMode === 'obstacle') {
          // 장애물 추가
          obstacles.push([...currentPath]);
        }
        
        currentPath = [];
        redrawCanvas();
      }
      
      // 캔버스 다시 그리기
      function redrawCanvas() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 설치 영역 그리기
        areas.forEach(area => {
          drawPath(area, '#E3F2FD', '#2196F3');
        });
        
        // 현재 그리는 경로
        if (currentPath.length > 0) {
          drawPath(currentPath, 'rgba(76, 175, 80, 0.3)', '#4CAF50');
        }
        
        // 장애물 그리기
        obstacles.forEach(obstacle => {
          drawPath(obstacle, '#FFEBEE', '#F44336');
        });
        
        // 모듈 그리기
        modules.forEach(module => {
          ctx.fillStyle = '#81C784';
          ctx.fillRect(module.x, module.y, module.width, module.height);
          ctx.strokeStyle = '#388E3C';
          ctx.strokeRect(module.x, module.y, module.width, module.height);
        });
      }
      
      // 경로 그리기
      function drawPath(path, fillStyle, strokeStyle) {
        if (path.length < 2) return;
        
        ctx.beginPath();
        ctx.moveTo(path[0].x, path[0].y);
        
        for (let i = 1; i < path.length; i++) {
          ctx.lineTo(path[i].x, path[i].y);
        }
        
        ctx.closePath();
        ctx.fillStyle = fillStyle;
        ctx.fill();
        ctx.strokeStyle = strokeStyle;
        ctx.stroke();
      }
      
      // 영역에 모듈 자동 배치
      function addModulesToArea(area) {
        // 영역의 경계 계산
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        area.forEach(point => {
          minX = Math.min(minX, point.x);
          minY = Math.min(minY, point.y);
          maxX = Math.max(maxX, point.x);
          maxY = Math.max(maxY, point.y);
        });
        
        // 모듈 크기 (픽셀)
        const moduleWidth = selectedModuleType.width * 50;
        const moduleHeight = selectedModuleType.height * 50;
        
        // 간격 (픽셀)
        const spacingX = 10;
        const spacingY = 10;
        
        // 배치 시작 좌표
        let startX = minX + 20;
        let startY = minY + 20;
        
        // 행과 열 수 계산
        const rows = Math.floor((maxY - minY - 40) / (moduleHeight + spacingY));
        const cols = Math.floor((maxX - minX - 40) / (moduleWidth + spacingX));
        
        // 모듈 배치
        for (let row = 0; row < rows; row++) {
          for (let col = 0; col < cols; col++) {
            const x = startX + col * (moduleWidth + spacingX);
            const y = startY + row * (moduleHeight + spacingY);
            
            // 모듈 중심이 영역 내에 있는지 확인
            const centerX = x + moduleWidth / 2;
            const centerY = y + moduleHeight / 2;
            
            if (isPointInPolygon(centerX, centerY, area)) {
              modules.push({
                x, y, 
                width: moduleWidth, 
                height: moduleHeight,
                power: selectedModuleType.power
              });
            }
          }
        }
      }
      
      // 점이 다각형 내부에 있는지 확인
      function isPointInPolygon(x, y, polygon) {
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
          const xi = polygon[i].x, yi = polygon[i].y;
          const xj = polygon[j].x, yj = polygon[j].y;
          
          const intersect = ((yi > y) != (yj > y)) &&
              (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
          if (intersect) inside = !inside;
        }
        return inside;
      }
      
      // 캔버스 초기화
      function clearCanvas() {
        areas = [];
        obstacles = [];
        modules = [];
        currentPath = [];
        redrawCanvas();
        resultPanel.style.display = 'none';
      }
      
      // 마지막 작업 취소
      function undoLastAction() {
        if (areas.length > 0) {
          areas.pop();
        } else if (obstacles.length > 0) {
          obstacles.pop();
        } else if (modules.length > 0) {
          modules.pop();
        }
        
        redrawCanvas();
      }
      
      // 시스템 계산
      function calculateSystem() {
        if (modules.length === 0) {
          alert('모듈이 배치되지 않았습니다. 먼저 설치 영역을 그리거나 모듈을 배치해주세요.');
          return;
        }
        
        // 총 모듈 수
        const totalModules = modules.length;
        
        // 시스템 용량 계산 (kWp)
        const systemCapacity = totalModules * selectedModuleType.power / 1000;
        
        // 설치 면적 계산 (m²)
        const installArea = totalModules * selectedModuleType.width * selectedModuleType.height;
        
        // 위치 정보 가져오기
        const locationInput = document.getElementById('locationInput').value;
        let lat = 36.5, lon = 127.8;
        
        if (locationInput) {
          const coords = locationInput.split(',').map(coord => parseFloat(coord.trim()));
          if (coords.length === 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
            lat = coords[0];
            lon = coords[1];
          }
        }
        
        // 설치면 정보
        const roofTilt = parseFloat(document.getElementById('roofTiltInput').value);
        const roofAzimuth = parseFloat(document.getElementById('roofAzimuthInput').value);
        
        // 간단한 발전량 추정
        // 한국 평균 일사량 기준 연간 발전량 추정 (kWh/kWp)
        const baseAnnualYield = 1200;  // 한국 평균 기준
        
        // 경사각 보정
        let tiltFactor = 1.0;
        if (roofTilt < 10) tiltFactor = 0.9;
        else if (roofTilt > 40) tiltFactor = 0.95;
        else if (roofTilt >= 20 && roofTilt <= 35) tiltFactor = 1.05;
        
        // 방위각 보정
        let azimuthFactor = 1.0;
        if (roofAzimuth >= 160 && roofAzimuth <= 200) azimuthFactor = 1.0;  // 남향
        else if ((roofAzimuth >= 90 && roofAzimuth < 160) || (roofAzimuth > 200 && roofAzimuth <= 270)) azimuthFactor = 0.9;  // 동향/서향
        else azimuthFactor = 0.8;  // 북향
        
        // 모듈 유형 보정
        let moduleTypeFactor = 1.0;
        switch(moduleTypeSelect.value) {
          case 'high_efficiency': 
            moduleTypeFactor = 1.1;
            break;
          case 'bifacial':
            moduleTypeFactor = 1.15;
            break;
          case 'thin_film':
            moduleTypeFactor = 0.9;
            break;
        }
        
        // 연간 발전량 계산 (kWh)
        const annualEnergy = systemCapacity * baseAnnualYield * tiltFactor * azimuthFactor * moduleTypeFactor;
        
        // 월평균 발전량
        const monthlyEnergy = annualEnergy / 12;
        
        // 설치 비용 추정 (원)
        const installCostPerKw = 1500000;  // 1kW당 150만원 기준
        const installCost = systemCapacity * installCostPerKw;
        
        // 결과 패널 표시
        resultPanel.style.display = 'block';
        document.getElementById('totalModulesText').textContent = totalModules;
        document.getElementById('systemCapacityText').textContent = systemCapacity.toFixed(2);
        document.getElementById('installAreaText').textContent = installArea.toFixed(2);
        document.getElementById('annualEnergyText').textContent = Math.round(annualEnergy).toLocaleString();
        document.getElementById('monthlyEnergyText').textContent = Math.round(monthlyEnergy).toLocaleString();
        document.getElementById('installCostText').textContent = Math.round(installCost).toLocaleString();
      }
      
      // 초기 캔버스 그리기
      redrawCanvas();
    </script>
    </body>
    </html>
    """)

# 📊 데이터 다운로드 페이지
@app.route('/download')
def download_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>태양광 발전량 데이터 다운로드</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
    <div class="container py-5">
      <h1 class="mb-4">태양광 발전량 데이터 다운로드</h1>
      
      <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
          <li class="breadcrumb-item"><a href="/">홈</a></li>
          <li class="breadcrumb-item active" aria-current="page">데이터 다운로드</li>
        </ol>
      </nav>
      
      <div class="row">
        <div class="col-md-6">
          <div class="card mb-4">
            <div class="card-header">
              데이터 요청 양식
            </div>
            <div class="card-body">
              <form id="dataRequestForm">
                <div class="mb-3">
                  <label for="locationInput" class="form-label">위치 (위도, 경도)</label>
                  <input type="text" class="form-control" id="locationInput" placeholder="36.5, 127.8" required>
                </div>
                
                <div class="mb-3">
                  <label for="dataTypeSelect" class="form-label">데이터 유형</label>
                  <select class="form-select" id="dataTypeSelect">
                    <option value="hourly">시간별 데이터</option>
                    <option value="daily">일별 데이터</option>
                    <option value="monthly">월별 데이터</option>
                    <option value="yearly">연간 데이터</option>
                  </select>
                </div>
                
                <div class="mb-3">
                  <label for="periodSelect" class="form-label">기간</label>
                  <select class="form-select" id="periodSelect">
                    <option value="1">1년</option>
                    <option value="5">5년</option>
                    <option value="10">10년</option>
                    <option value="20">20년</option>
                  </select>
                </div>
                
                <div class="mb-3">
                  <label for="formatSelect" class="form-label">파일 형식</label>
                  <select class="form-select" id="formatSelect">
                    <option value="csv">CSV</option>
                    <option value="json">JSON</option>
                    <option value="excel">Excel</option>
                  </select>
                </div>
                
                <button type="submit" class="btn btn-primary">데이터 요청</button>
              </form>
            </div>
          </div>
        </div>
        
        <div class="col-md-6">
          <div class="card">
            <div class="card-header">
              사용 가능한 데이터셋
            </div>
            <div class="card-body">
              <div class="list-group">
                <a href="/download_heatmap_data" class="list-group-item list-group-item-action">
                  <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">한국 지역 태양광 발전량 히트맵 데이터</h5>
                    <small>JSON</small>
                  </div>
                  <p class="mb-1">한국 전역(33°N~38°N, 126°E~130°E)의 태양광 발전 잠재력 데이터</p>
                  <small>위도/경도 0.5° 간격, 최적 각도 기준</small>
                </a>
                
                <a href="/download_angle_optimization_data?lat=36.5&lon=127.8" class="list-group-item list-group-item-action">
                  <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">경사각/방위각 최적화 데이터</h5>
                    <small>CSV</small>
                  </div>
                  <p class="mb-1">다양한 경사각/방위각 조합에 따른 발전량 데이터</p>
                  <small>중부지방(36.5°N, 127.8°E) 기준</small>
                </a>
                
                <a href="/download_module_comparison_data" class="list-group-item list-group-item-action">
                  <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">태양광 모듈 유형별 성능 비교 데이터</h5>
                    <small>Excel</small>
                  </div>
                  <p class="mb-1">다양한 모듈 유형과 설치 방식에 따른 발전량 비교</p>
                  <small>표준형, 고효율, 양면형, 박막형 모듈 포함</small>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="alert alert-info mt-4">
        <h4 class="alert-heading">데이터 사용 안내</h4>
        <p>이 서비스에서 제공하는 데이터는 NASA POWER API의 기상 및 일사량 데이터를 기반으로 하며, pvlib 라이브러리를 사용하여 계산되었습니다.</p>
        <p>데이터는 학습 및 비상업적 목적으로 자유롭게 사용할 수 있으나, 정확한 태양광 시스템 설계와 투자 결정에는 전문가의 검토가 필요합니다.</p>
        <hr>
        <p class="mb-0">문의: <a href="mailto:info@example.com">info@example.com</a></p>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
      document.getElementById('dataRequestForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const location = document.getElementById('locationInput').value;
        const dataType = document.getElementById('dataTypeSelect').value;
        const period = document.getElementById('periodSelect').value;
        const format = document.getElementById('formatSelect').value;
        
        // 위치 파싱
        const coords = location.split(',').map(coord => parseFloat(coord.trim()));
        if (coords.length !== 2 || isNaN(coords[0]) || isNaN(coords[1])) {
          alert('올바른 위치 형식을 입력해주세요: 위도, 경도');
          return;
        }
        
        const lat = coords[0];
        const lon = coords[1];
        
        // 다운로드 URL 생성
        const downloadUrl = `/download_data?lat=${lat}&lon=${lon}&data_type=${dataType}&period=${period}&format=${format}`;
        
        // 다운로드 페이지로 이동
        window.location.href = downloadUrl;
      });
    </script>
    </body>
    </html>
    """)

@app.route('/download_data')
def download_data():
    """요청에 따른 태양광 발전량 데이터 생성 및 다운로드"""
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    data_type = request.args.get('data_type', default='monthly')
    period = request.args.get('period', default=1, type=int)
    file_format = request.args.get('format', default='csv')
    
    if not lat or not lon:
        return "위도와 경도를 지정해주세요.", 400
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "데이터를 가져오는 중 오류가 발생했습니다.", 500
    
    # 최적 각도 계산
    optimal_tilt = abs(lat) * 0.76 + 3.1
    optimal_azimuth = 180 if lat >= 0 else 0
    
    # 시간 범위 생성
    if data_type == 'hourly':
        # 시간별 데이터 (1년치만 생성)
        times = pd.date_range(start='2023-01-01', end='2023-12-31 23:00:00', freq='H')
    elif data_type == 'daily':
        # 일별 데이터
        times = pd.date_range(start=f'2023-01-01', periods=365 * period, freq='D')
    elif data_type == 'monthly':
        # 월별 데이터
        times = pd.date_range(start=f'2023-01-01', periods=12 * period, freq='M')
    else:
        # 연간 데이터
        times = pd.date_range(start=f'2023-01-01', periods=period, freq='Y')
    
    # 태양 위치 계산 (시간별만)
    if data_type == 'hourly':
        solpos = get_solar_position(lat, lon, times)
        
        # 시간별 GHI 분포 생성
        month_indices = np.array([t.month-1 for t in times])
        monthly_ratio = np.array([0.6, 0.7, 0.9, 1.1, 1.2, 1.1, 1.0, 1.1, 1.0, 0.9, 0.7, 0.6])
        monthly_ratio = monthly_ratio / monthly_ratio.mean()
        
        daily_pattern = np.sin(np.pi * (times.hour) / 24) ** 2
        daily_pattern[times.hour < 6] = 0
        daily_pattern[times.hour > 18] = 0
        
        hourly_ghi = ghi / 365 / daily_pattern.sum() * 24
        hourly_ghi = hourly_ghi * monthly_ratio[month_indices] * daily_pattern * 24
        
        # GHI를 DNI와 DHI로 분해
        irradiance = decompose_ghi(hourly_ghi, solpos['apparent_zenith'], times)
        dni = irradiance['dni'].fillna(0)
        dhi = irradiance['dhi'].fillna(0)
        
        # 입사각 계산
        aoi_values = calculate_aoi(optimal_tilt, optimal_azimuth, solpos['apparent_zenith'], solpos['azimuth'])
        
        # 하늘 산란일사량 계산
        poa_sky_diffuse = pvlib.irradiance.haydavies(
            optimal_tilt, optimal_azimuth, dhi, dni, solpos['apparent_zenith'], solpos['azimuth']
        )
        
        # 지면 반사 산란일사량 계산
        poa_ground_diffuse = pvlib.irradiance.get_ground_diffuse(optimal_tilt, hourly_ghi, 0.2)
        
        # 모듈 표면 일사량 계산
        poa_irrad = pvlib.irradiance.poa_components(
            aoi_values, dni, poa_sky_diffuse, poa_ground_diffuse
        )
        
        # 발전량 계산
        hourly_energy = poa_irrad['poa_global'].fillna(0).clip(min=0) * 0.85 / 1000
        
        # 데이터프레임 생성
        df = pd.DataFrame({
            'datetime': times,
            'ghi': hourly_ghi,
            'dni': dni,
            'dhi': dhi,
            'poa_global': poa_irrad['poa_global'],
            'poa_direct': poa_irrad['poa_direct'],
            'poa_diffuse': poa_irrad['poa_diffuse'],
            'energy': hourly_energy
        })
    else:
        # 시간별이 아닌 데이터는 간소화된 방식으로 계산
        if data_type == 'daily':
            # 일별 데이터
            daily_energy = []
            for i in range(len(times)):
                # 월별 가중치 적용
                month = times[i].month - 1
                monthly_ratio = np.array([0.6, 0.7, 0.9, 1.1, 1.2, 1.1, 1.0, 1.1, 1.0, 0.9, 0.7, 0.6])
                monthly_ratio = monthly_ratio / monthly_ratio.mean()
                
                # 일별 변동 추가 (±10%)
                daily_variation = 1.0 + (np.sin(i * 0.7) * 0.1)
                
                daily_value = ghi / 365 * monthly_ratio[month] * daily_variation
                daily_energy.append(daily_value * 0.85)  # 시스템 효율 적용
            
            df = pd.DataFrame({
                'date': times,
                'ghi': [ghi / 365 for _ in range(len(times))],
                'energy': daily_energy
            })
        elif data_type == 'monthly':
            # 월별 데이터
            monthly_ratio = np.array([0.6, 0.7, 0.9, 1.1, 1.2, 1.1, 1.0, 1.1, 1.0, 0.9, 0.7, 0.6])
            monthly_ratio = monthly_ratio / monthly_ratio.mean()
            
            df_data = []
            for i in range(len(times)):
                month_idx = i % 12
                year_idx = i // 12
                
                # 연간 변동 추가 (±5%)
                year_variation = 1.0 + (np.sin(year_idx * 0.5) * 0.05)
                
                monthly_ghi = ghi / 12 * monthly_ratio[month_idx] * year_variation
                monthly_energy = monthly_ghi * 0.85  # 시스템 효율 적용
                
                df_data.append({
                    'date': times[i],
                    'year': times[i].year,
                    'month': times[i].month,
                    'ghi': monthly_ghi,
                    'energy': monthly_energy
                })
            
            df = pd.DataFrame(df_data)
        else:
            # 연간 데이터
            df_data = []
            for i in range(len(times)):
                # 연간 변동 추가 (±5%)
                year_variation = 1.0 + (np.sin(i * 0.5) * 0.05)
                
                annual_ghi = ghi * year_variation
                annual_energy = annual_ghi * 0.85  # 시스템 효율 적용
                
                df_data.append({
                    'year': times[i].year,
                    'ghi': annual_ghi,
                    'energy': annual_energy
                })
            
            df = pd.DataFrame(df_data)
    
    # 파일 생성
    if file_format == 'csv':
        output = BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'solar_data_{lat}_{lon}_{data_type}.csv'
        )
    elif file_format == 'json':
        output = BytesIO()
        output.write(df.to_json(orient='records').encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'solar_data_{lat}_{lon}_{data_type}.json'
        )
    else:  # Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='태양광 발전량 데이터', index=False)
            
            # 추가 정보 시트
            info_df = pd.DataFrame({
                '항목': ['위도', '경도', '연평균 일사량 (GHI)', '최적 경사각', '최적 방위각', '데이터 유형', '기간'],
                '값': [lat, lon, f'{ghi} kWh/m²/년', f'{optimal_tilt}°', f'{optimal_azimuth}°', data_type, f'{period}년']
            })
            info_df.to_excel(writer, sheet_name='정보', index=False)
            
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'solar_data_{lat}_{lon}_{data_type}.xlsx'
        )

@app.route('/download_heatmap_data')
def download_heatmap_data():
    """태양광 발전량 히트맵 데이터 다운로드"""
    # 기존 히트맵 데이터 파일 확인
    if not os.path.exists('heat_data.json'):
        return "히트맵 데이터가 없습니다.", 404
    
    return send_file(
        'heat_data.json',
        mimetype='application/json',
        as_attachment=True,
        download_name='korea_solar_heatmap_data.json'
    )

@app.route('/download_angle_optimization_data')
def download_angle_optimization_data():
    """경사각/방위각 최적화 데이터 다운로드"""
    lat = request.args.get('lat', default=36.5, type=float)
    lon = request.args.get('lon', default=127.8, type=float)
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "데이터를 가져오는 중 오류가 발생했습니다.", 500
    
    # 각도 범위
    tilts = np.arange(0, 91, 5)  # 0도부터 90도까지 5도 간격
    azimuths = np.arange(90, 271, 10)  # 90도(동)부터 270도(서)까지 10도 간격
    
    # 결과 저장 데이터
    angle_data = []
    
    # 각 조합에 대한 발전량 계산
    for tilt in tilts:
        for azimuth in azimuths:
            result = calculate_pv_energy(lat, lon, tilt, azimuth, ghi)
            angle_data.append({
                'tilt': tilt,
                'azimuth': azimuth,
                'annual_energy': result['annual_energy']
            })
    
    # 데이터프레임으로 변환
    df = pd.DataFrame(angle_data)
    
    # CSV 파일로 저장
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'angle_optimization_{lat}_{lon}.csv'
    )

@app.route('/download_module_comparison_data')
def download_module_comparison_data():
    """태양광 모듈 유형별 성능 비교 데이터 다운로드"""
    # 기본 매개변수
    lat = 36.5  # 대한민국 중부지방 기준
    lon = 127.8
    
    # NASA POWER API에서 GHI 데이터 가져오기
    url = (
        f'https://power.larc.nasa.gov/api/temporal/climatology/point'
        f'?parameters=ALLSKY_SFC_SW_DWN&community=RE&latitude={lat}&longitude={lon}&format=JSON'
    )
    
    try:
        res = requests.get(url).json()
        ghi = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "데이터를 가져오는 중 오류가 발생했습니다.", 500
    
    # 최적 각도 계산
    optimal_tilt = abs(lat) * 0.76 + 3.1
    optimal_azimuth = 180
    
    # 모듈 유형 및 설치 방식 정의
    module_types = [
        {'name': '표준형', 'config': {'module_type': 'standard', 'tracking_type': 'fixed'}},
        {'name': '고효율', 'config': {'module_type': 'premium', 'tracking_type': 'fixed'}},
        {'name': '양면형', 'config': {'module_type': 'bifacial', 'tracking_type': 'fixed', 'bifacial_factor': 0.7}},
        {'name': '박막형', 'config': {'module_type': 'thin_film', 'tracking_type': 'fixed'}},
        {'name': '단축 트래킹 (표준형)', 'config': {'module_type': 'standard', 'tracking_type': 'single_axis'}},
        {'name': '단축 트래킹 (고효율)', 'config': {'module_type': 'premium', 'tracking_type': 'single_axis'}},
        {'name': '단축 트래킹 (양면형)', 'config': {'module_type': 'bifacial', 'tracking_type': 'single_axis', 'bifacial_factor': 0.7}}
    ]
    
    # 각 유형별 성능 계산
    results = []
    
    for module in module_types:
        config = {
            'albedo': 0.2,
            'efficiency': 0.85,
            'module_type': module['config']['module_type'],
            'tracking_type': module['config']['tracking_type'],
            'bifacial_factor': module['config'].get('bifacial_factor', 0),
            'inverter_efficiency': 0.96,
            'losses': 0.14,
            'temp_model': 'sapm',
            'racking_model': 'open_rack'
        }
        
        # 발전량 계산
        result = calculate_pv_energy(lat, lon, optimal_tilt, optimal_azimuth, ghi, config)
        
        # 월별 데이터에서 계절별 데이터 추출
        winter = (result['monthly_energy'][0] + result['monthly_energy'][1] + result['monthly_energy'][11]) / 3
        spring = (result['monthly_energy'][2] + result['monthly_energy'][3] + result['monthly_energy'][4]) / 3
        summer = (result['monthly_energy'][5] + result['monthly_energy'][6] + result['monthly_energy'][7]) / 3
        fall = (result['monthly_energy'][8] + result['monthly_energy'][9] + result['monthly_energy'][10]) / 3
        
        results.append({
            '모듈 유형': module['name'],
            '연간 발전량 (kWh/kWp)': result['annual_energy'],
            '여름 평균 (kWh/kWp)': round(summer, 1),
            '겨울 평균 (kWh/kWp)': round(winter, 1),
            '봄 평균 (kWh/kWp)': round(spring, 1),
            '여름 평균 (kWh/kWp)': round(summer, 1),
            '가을 평균 (kWh/kWp)': round(fall, 1),
            '온도 효과 (%)': result['temp_effect'],
            '설치 방식': '고정형' if module['config']['tracking_type'] == 'fixed' else '트래킹형',
            '효율': '일반' if module['config']['module_type'] == 'standard' else '고효율' if module['config']['module_type'] == 'premium' else '양면형' if module['config']['module_type'] == 'bifacial' else '박막형'
        })
    
    # 데이터프레임으로 변환
    df = pd.DataFrame(results)
    
    # Excel 파일로 저장
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='모듈 비교', index=False)
        
        # 차트 추가
        workbook = writer.book
        worksheet = writer.sheets['모듈 비교']
        
        # 바 차트 생성 (연간 발전량)
        chart1 = workbook.add_chart({'type': 'column'})
        
        # 데이터 범위 추가
        for i in range(len(module_types)):
            chart1.add_series({
                'name': results[i]['모듈 유형'],
                'categories': ['모듈 비교', 0, 0],
                'values': ['모듈 비교', i+1, 1, i+1, 1],
            })
        
        chart1.set_title({'name': '모듈 유형별 연간 발전량'})
        chart1.set_y_axis({'name': '발전량 (kWh/kWp)', 'major_gridlines': {'visible': True}})
        chart1.set_style(11)
        
        worksheet.insert_chart('J2', chart1, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 계절별 발전량 비교 차트
        chart2 = workbook.add_chart({'type': 'radar'})
        
        for i in range(len(module_types)):
            chart2.add_series({
                'name': results[i]['모듈 유형'],
                'categories': ['모듈 비교', 0, 2, 0, 5],
                'values': ['모듈 비교', i+1, 2, i+1, 5],
            })
        
        chart2.set_title({'name': '계절별 발전량 비교'})
        chart2.set_style(11)
        
        worksheet.insert_chart('J20', chart2, {'x_scale': 1.5, 'y_scale': 1.5})
        
        # 안내 시트 추가
        info_data = [
            ['태양광 모듈 유형별 성능 비교 데이터'],
            [''],
            ['이 데이터는 대한민국 중부지방(위도 36.5°N, 경도 127.8°E) 기준으로 생성되었습니다.'],
            ['연평균 일사량(GHI):', f'{ghi} kWh/m²/년'],
            ['최적 경사각:', f'{optimal_tilt:.1f}°'],
            ['최적 방위각:', f'{optimal_azimuth}°'],
            [''],
            ['모듈 유형별 특징:'],
            ['표준형: 일반적인 결정질 실리콘 모듈'],
            ['고효율: 프리미엄 실리콘 모듈 (PERC, N-type 등)'],
            ['양면형: 전후면에서 발전하는 양면 모듈 (뒷면 효율 70%)'],
            ['박막형: 고온 및 저조도 상황에서 효율적인 박막 모듈'],
            ['단축 트래킹: 동-서 방향으로 태양을 추적하는 시스템'],
            [''],
            ['발전량 계산에 사용된 주요 매개변수:'],
            ['시스템 효율: 85%'],
            ['인버터 효율: 96%'],
            ['시스템 손실: 14%'],
            ['지면 반사율: 20%'],
            [''],
            ['참고: 실제 발전량은 현장 조건, 설치 품질, 기상 조건 등에 따라 달라질 수 있습니다.']
        ]
        
        info_df = pd.DataFrame(info_data)
        info_df.to_excel(writer, sheet_name='안내', header=False, index=False)
        
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='module_comparison_data.xlsx'
    )

# 🚀 6. 웹 서버 실행
if __name__ == '__main__':
    # 히트맵 데이터 확인
    ensure_heat_data_exists()
    
    # ngrok 연결 (네트워크 문제로 실패할 수 있으므로 예외 처리)
    try:
        public_url = ngrok.connect(5000, region="ap")  # 아시아 태평양 지역 서버 사용
        print(f"\n🌍 여기에 접속하세요: {public_url}\n")
        
        # 다양한 경로에 접근할 수 있도록 안내
        print(f"📊 태양광 발전량 예측: {public_url}")
        print(f"🔥 히트맵 보기: {public_url}/heatmap")
        print(f"⚡ 시스템 설계: {public_url}/system_designer")
        print(f"📥 데이터 다운로드: {public_url}/download")
    except Exception as e:
        print(f"\n⚠️ ngrok 연결 실패: {str(e)}")
        print("🌍 로컬에서 접속하세요: http://127.0.0.1:5000\n")
        print("📊 태양광 발전량 예측: http://127.0.0.1:5000")
        print("🔥 히트맵 보기: http://127.0.0.1:5000/heatmap")
        print("⚡ 시스템 설계: http://127.0.0.1:5000/system_designer")
        print("📥 데이터 다운로드: http://127.0.0.1:5000/download")
    
    # Flask 앱 실행
    app.run(port=5000)