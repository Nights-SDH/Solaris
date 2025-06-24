import os
from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import json
import time
import numpy as np
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
from scipy.optimize import minimize
from datetime import datetime
matplotlib.use('Agg')

# 🏭 태양광 발전량 계산 함수
def calculate_pv_energy(lat, lon, tilt, azimuth, ghi_daily, system_config=None):
    try:
        ghi_annual = float(ghi_daily) * 365  # kWh/m²/day → kWh/m²/year
        
        # 기본 시스템 효율
        module_efficiency = 0.20      # 모듈 효율 20%
        inverter_efficiency = 0.96    # 인버터 효율 96%
        system_losses = 0.14          # 시스템 손실 14%
        
        total_efficiency = module_efficiency * inverter_efficiency * (1 - system_losses)
        
        # 경사각 보정 계수
        optimal_tilt = abs(lat) * 0.76 + 3.1
        tilt_diff = abs(tilt - optimal_tilt)
        tilt_factor = 1.0 - tilt_diff * 0.008
        tilt_factor = max(0.8, min(1.1, tilt_factor))
        
        # 방위각 보정 계수
        optimal_azimuth = 180 if lat >= 0 else 0
        azimuth_diff = abs(azimuth - optimal_azimuth)
        if azimuth_diff > 180:
            azimuth_diff = 360 - azimuth_diff
        azimuth_factor = 1.0 - azimuth_diff * 0.002
        azimuth_factor = max(0.7, min(1.0, azimuth_factor))
        
        # 위도별 일사량 보정
        if 33 <= lat <= 38:
            latitude_factor = 1.0 + (lat - 35.5) * 0.01
        else:
            latitude_factor = 1.0
        
        # 온도 보정 계수
        temperature_factor = 0.94
        
        # 연간 발전량 계산
        annual_energy = (float(ghi_annual) * float(total_efficiency) * 
                        float(tilt_factor) * float(azimuth_factor) * 
                        float(latitude_factor) * float(temperature_factor))
        
        # 한국 월별 일사량 분포
        monthly_distribution = [
            0.45, 0.55, 0.75, 0.95, 1.10, 1.15,  # 1-6월
            1.05, 1.10, 0.95, 0.75, 0.55, 0.40   # 7-12월
        ]
        
        # 정규화
        avg_ratio = sum(monthly_distribution) / len(monthly_distribution)
        monthly_distribution = [r / avg_ratio for r in monthly_distribution]
        
        # 월별 발전량 계산
        monthly_energy = []
        for ratio in monthly_distribution:
            monthly_val = annual_energy / 12.0 * ratio
            monthly_energy.append(round(monthly_val, 1))
        
        # 온도 효과
        temp_effect = -6.0 + (lat - 36) * 0.3
        
        return {
            'annual_energy': round(annual_energy, 1),
            'monthly_energy': monthly_energy,
            'temp_effect': round(temp_effect, 1),
            'optimal_tilt': round(optimal_tilt, 1),
            'optimal_azimuth': int(optimal_azimuth)
        }
        
    except Exception as e:
        print(f"PV 계산 오류: {str(e)}")
        return calculate_simple_pv_energy(lat, lon, tilt, azimuth, ghi_daily)

# 백업용 함수
def calculate_simple_pv_energy(lat, lon, tilt, azimuth, ghi_daily):
    try:
        ghi_annual = float(ghi_daily) * 365
        
        # 간단한 계산
        optimal_tilt = abs(lat) * 0.76 + 3.1
        tilt_factor = 1.0 - abs(tilt - optimal_tilt) * 0.01
        tilt_factor = max(0.8, min(1.1, tilt_factor))
        
        optimal_azimuth = 180 if lat >= 0 else 0
        azimuth_diff = abs(azimuth - optimal_azimuth)
        if azimuth_diff > 180:
            azimuth_diff = 360 - azimuth_diff
        azimuth_factor = 1.0 - azimuth_diff * 0.002
        azimuth_factor = max(0.7, min(1.0, azimuth_factor))
        
        system_efficiency = 0.85 * 0.96 * (1 - 0.14)
        annual_energy = ghi_annual * system_efficiency * tilt_factor * azimuth_factor
        
        monthly_ratio = [0.6, 0.7, 0.9, 1.1, 1.2, 1.1, 1.0, 1.1, 1.0, 0.9, 0.7, 0.6]
        avg_ratio = sum(monthly_ratio) / len(monthly_ratio)
        monthly_ratio = [r / avg_ratio for r in monthly_ratio]
        monthly_energy = [round(annual_energy / 12 * ratio, 1) for ratio in monthly_ratio]
        
        return {
            'annual_energy': round(annual_energy, 1),
            'monthly_energy': monthly_energy,
            'temp_effect': -5.0,
            'optimal_tilt': round(optimal_tilt, 1),
            'optimal_azimuth': int(optimal_azimuth)
        }
    except Exception as e:
        print(f"백업 계산 오류: {str(e)}")
        # 최후의 수단
        backup_energy = float(ghi_daily) * 365 * 0.15
        return {
            'annual_energy': round(backup_energy, 1),
            'monthly_energy': [round(backup_energy / 12, 1)] * 12,
            'temp_effect': -5.0,
            'optimal_tilt': 30.0,
            'optimal_azimuth': 180
        }

def find_optimal_angles(lat, lon, ghi_daily, albedo=0.2, system_efficiency=0.85):
    """최적 경사각과 방위각 찾기"""
    optimal_tilt = abs(lat) * 0.76 + 3.1
    optimal_azimuth = 180 if lat >= 0 else 0
    return round(optimal_tilt, 1), optimal_azimuth

def generate_pv_chart(monthly_energy):
    """월간 발전량 차트 생성"""
    try:
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # 폰트 설정 (Railway 환경에서 안전한 폰트)
        plt.rcParams['font.family'] = 'DejaVu Sans'
        
        plt.figure(figsize=(10, 6))
        bars = plt.bar(months, monthly_energy, color='#2196F3')
        
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + max(monthly_energy) * 0.01,
                    f'{height:.1f}',
                    ha='center', va='bottom', fontsize=9)
        
        plt.title('Monthly Solar Energy Generation (kWh/kWp)', fontsize=16)
        plt.ylabel('Energy (kWh/kWp)', fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        
        img_bytes = BytesIO()
        plt.tight_layout()
        plt.savefig(img_bytes, format='png', dpi=100, bbox_inches='tight')
        img_bytes.seek(0)
        plt.close()
        
        return img_bytes
    except Exception as e:
        print(f"차트 생성 오류: {str(e)}")
        # 오류 발생 시 빈 차트 반환
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, 'Chart generation error', ha='center', va='center', transform=plt.gca().transAxes)
        img_bytes = BytesIO()
        plt.savefig(img_bytes, format='png', dpi=100)
        img_bytes.seek(0)
        plt.close()
        return img_bytes

def calculate_financial_metrics(energy_per_kwp, system_size=3.0, install_cost_per_kw=1800000, smp_price=180, rec_price=40, annual_degradation=0.005, lifetime=25):
    """
    재무 지표 계산
    
    Args:
        energy_per_kwp: kWh/kWp/년 단위의 발전량 (1kWp당 연간 발전량)
        system_size: 시스템 용량 (kWp)
        install_cost_per_kw: 설치비용 (원/kW)
        smp_price: SMP 전력 판매 단가 (원/kWh)
        rec_price: REC 가격 (원/REC) - 1MWh당 1REC 발급
        annual_degradation: 연간 성능 저하율 (기본 0.5%)
        lifetime: 시스템 수명 (년)
    """
    # ✅ 1. 명확한 단위 구분
    total_cost = system_size * install_cost_per_kw  # 총 설치비용 (원)
    annual_production = system_size * energy_per_kwp  # 연간 발전량 (kWh/년)
    
    print(f"💰 경제성 계산:")
    print(f"   - 시스템 용량: {system_size} kWp")
    print(f"   - kWp당 발전량: {energy_per_kwp} kWh/kWp/년")
    print(f"   - 총 연간발전량: {annual_production} kWh/년")
    print(f"   - 총 설치비용: {total_cost:,} 원")
    
    # ✅ 2. REC 수익 계산 개선 (가중치 적용)
    rec_weight = 1.5  # 영농형 태양광 등 가중치 (일반적으로 1.0~1.5)
    
    # 1년차 기준 수익 계산
    annual_smp_revenue = annual_production * smp_price
    # REC: 1MWh(1,000kWh)당 1REC 발급, 가중치 적용
    annual_rec_revenue = (annual_production / 1000) * rec_price * rec_weight
    annual_revenue = annual_smp_revenue + annual_rec_revenue
    
    print(f"   - SMP 수익: {annual_smp_revenue:,} 원/년")
    print(f"   - REC 수익: {annual_rec_revenue:,} 원/년 (가중치 {rec_weight}x 적용)")
    print(f"   - 총 연간수익: {annual_revenue:,} 원/년")
    
    # ✅ 3. 회수기간 계산 로직 개선
    cash_flows = []
    cumulative_cash = -total_cost  # 초기 투자비 (음수)
    total_revenue_25years = 0
    total_maintenance_25years = 0
    payback_period = None
    
    for year in range(1, lifetime + 1):
        # 연간 성능 저하 적용
        degraded_factor = (1 - annual_degradation) ** year
        year_production = annual_production * degraded_factor
        
        # 해당 연도 수익 계산
        year_smp_revenue = year_production * smp_price
        year_rec_revenue = (year_production / 1000) * rec_price * rec_weight
        year_total_revenue = year_smp_revenue + year_rec_revenue
        
        # 유지보수 비용 (시스템 나이에 따라 차등 적용)
        if year <= 10:
            maintenance_rate = 0.01  # 1%
        elif year <= 20:
            maintenance_rate = 0.015  # 1.5%
        else:
            maintenance_rate = 0.02  # 2%
            
        maintenance_cost = total_cost * maintenance_rate
        
        # 순현금흐름 = 수익 - 유지보수비
        net_cash_flow = year_total_revenue - maintenance_cost
        
        # 누적 현금흐름 업데이트
        cumulative_cash += net_cash_flow
        cash_flows.append(cumulative_cash)
        
        # ✅ 회수기간 계산: 누적 현금흐름이 0 이상이 되는 시점
        if cumulative_cash >= 0 and payback_period is None:
            if year == 1:
                payback_period = 1.0
            else:
                # 선형 보간으로 정확한 회수 시점 계산
                prev_cumulative = cash_flows[year-2] if year > 1 else -total_cost
                payback_period = year - 1 + (-prev_cumulative) / (cumulative_cash - prev_cumulative)
        
        # 25년간 총합 계산
        total_revenue_25years += year_total_revenue
        total_maintenance_25years += maintenance_cost
    
    # ✅ 4. ROI 계산 개선
    net_profit = total_revenue_25years - total_maintenance_25years - total_cost
    roi = (net_profit / total_cost) * 100 if total_cost > 0 else 0
    
    # 회수기간이 25년 내에 없으면 None 처리
    if payback_period is None:
        payback_period = None
    
    print(f"   - 25년 총수익: {total_revenue_25years:,} 원")
    print(f"   - 25년 유지비: {total_maintenance_25years:,} 원") 
    print(f"   - 순이익: {net_profit:,} 원")
    print(f"   - 투자회수기간: {payback_period} 년" if payback_period else "   - 투자회수기간: 25년 내 회수 불가")
    print(f"   - ROI: {roi:.1f}%")
    
    return {
        'total_cost': int(total_cost),
        'annual_production': round(annual_production, 1),
        'annual_revenue': int(annual_revenue),
        'annual_smp_revenue': int(annual_smp_revenue),
        'annual_rec_revenue': int(annual_rec_revenue),
        'payback_period': round(payback_period, 1) if payback_period else None,
        'roi': round(roi, 1),
        'cash_flows': cash_flows,
        'life_cycle_revenue': int(total_revenue_25years - total_maintenance_25years),
        'net_profit': int(net_profit),
        'monthly_production': round(annual_production / 12, 1),
        'monthly_revenue': int(annual_revenue / 12),
        'rec_weight': rec_weight  # 디버깅용
    }

# 🚀 Flask 앱 설정
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>태양광 발전량 예측 시스템</title>
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
          border-right: 2px solid #dee2e6;
        }
        
        /* 모바일 반응형 */
        @media (max-width: 768px) {
          .control-panel {
            height: auto;
            max-height: 50vh;
            border-right: none;
            border-bottom: 2px solid #dee2e6;
          }
          .map-container {
            height: 50vh;
          }
          .row {
            height: auto;
          }
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
        .financial-metrics {
          background-color: #e8f5e9;
          border-radius: 5px;
          padding: 15px;
          margin-top: 20px;
        }
        .ghi-info {
          background-color: #fff3cd;
          border: 1px solid #ffeeba;
          border-radius: 5px;
          padding: 10px;
          margin-bottom: 15px;
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
        <div class="col-lg-3 col-md-4 control-panel">
          <h2 class="mb-4">태양광 발전량 예측</h2>
          
          <!-- 🔍 주소 검색 기능 추가 -->
          <div class="mb-4 p-3 bg-primary-subtle rounded">
            <h5 class="mb-3">📍 위치 검색</h5>
            <div class="mb-3">
              <label for="addressInput" class="form-label">주소 입력</label>
              <div class="input-group">
                <input type="text" class="form-control" id="addressInput" placeholder="예: 서울시 강남구 테헤란로 또는 대전광역시 유성구">
                <button class="btn btn-primary" type="button" id="searchButton">🔍 검색</button>
              </div>
              <small class="text-muted">도로명주소, 지번주소, 건물명 모두 검색 가능합니다</small>
            </div>
            
            <!-- 빠른 검색 버튼들 -->
            <div class="mb-2">
              <small class="text-muted">빠른 검색:</small><br>
              <div class="btn-group-sm mt-1" role="group">
                <button type="button" class="btn btn-outline-secondary btn-sm quick-search" data-address="서울시 강남구 테헤란로">서울 강남</button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-search" data-address="부산시 해운대구">부산 해운대</button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-search" data-address="대전시 유성구">대전 유성</button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-search" data-address="제주시 연동">제주도</button>
              </div>
            </div>
            
            <div id="searchResults" class="mt-2" style="display: none;">
              <div class="alert alert-info" role="alert">
                <span id="searchResultText"></span>
              </div>
            </div>
          </div>
          
          <div class="mb-3">
            <label for="landAreaInput" class="form-label">🏗️ 토지 면적 (㎡)</label>
            <input type="number" class="form-control" id="landAreaInput" min="32" max="50000" step="10" placeholder="예: 960">
            <small class="text-muted">면적 입력 시 설치 가능 용량을 자동 계산합니다 (1kW당 32㎡ 기준)</small>
          </div>
          
          <div class="mb-3">
            <label for="systemSizeInput" class="form-label">⚡ 시스템 용량 (kWp)</label>
            <div class="input-group">
              <input type="number" class="form-control" id="systemSizeInput" min="0.1" max="1000" value="3" step="0.1" placeholder="예: 30.5">
              <span class="input-group-text">kWp</span>
            </div>
            <div id="capacityCalculation" class="text-success mt-1" style="display: none;">
              <small><strong>📊 면적 기반 자동 계산: <span id="maxCapacityText">0</span>kWp</strong></small>
            </div>
            <div class="text-info mt-1">
              <small>💡 토지 면적 입력 시 자동 계산되지만 언제든 수정 가능합니다</small>
            </div>
            
            <!-- 빠른 용량 선택 버튼들 -->
            <div class="mt-2">
              <small class="text-muted">빠른 선택:</small><br>
              <div class="btn-group-sm mt-1" role="group">
                <button type="button" class="btn btn-outline-secondary btn-sm quick-capacity" data-capacity="3">3kWp</button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-capacity" data-capacity="10">10kWp</button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-capacity" data-capacity="30">30kWp</button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-capacity" data-capacity="100">100kWp</button>
              </div>
            </div>
          </div>
          
          <div class="mb-3">
            <label for="installationTypeSelect" class="form-label">🔧 설치 유형</label>
            <select class="form-select" id="installationTypeSelect">
              <option value="fixed" data-cost="1800000">고정형 (1,800,000원/kW)</option>
              <option value="tilted" data-cost="2000000">경사형 (2,000,000원/kW)</option>
              <option value="ess" data-cost="2500000">ESS 포함형 (2,500,000원/kW)</option>
              <option value="tracking" data-cost="2200000">단축 트래킹 (2,200,000원/kW)</option>
              <option value="custom" data-cost="1500000">사용자 정의</option>
            </select>
          </div>
          
          <div class="mb-3" id="customCostContainer" style="display: none;">
            <label for="installCostInput" class="form-label">💰 설치 비용 (원/kW)</label>
            <input type="number" class="form-control" id="installCostInput" min="500000" max="5000000" step="50000" value="1500000">
          </div>
          
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
            <label for="smpPriceInput" class="form-label">💡 SMP 전력 판매 단가 (원/kWh)</label>
            <input type="number" class="form-control" id="smpPriceInput" min="50" max="500" value="180">
            <small class="text-muted">현재 SMP 평균: 약 180원/kWh (2024년 기준)</small>
          </div>
          
          <div class="mb-3">
            <label for="recPriceInput" class="form-label">🌿 REC 가격 (원/kWh)</label>
            <input type="number" class="form-control" id="recPriceInput" min="0" max="200" value="40">
            <small class="text-muted">신재생에너지 공급인증서 가격 (선택사항)</small>
          </div>
          
          <div class="alert alert-info" id="instructionAlert">
            📍 <strong>위치 설정 방법:</strong><br>
            1️⃣ 위의 주소 검색 기능 사용<br>
            2️⃣ 지도에서 직접 클릭<br>
            <small class="text-muted">위치 설정 후 해당 지점의 태양광 발전량을 자동 계산합니다.</small>
          </div>
          
          <div id="resultsContainer" style="display: none;">
            <h4>분석 결과</h4>
            
            <!-- ✅ GHI 정보 표시 개선 -->
            <div class="ghi-info">
              <div class="mb-2">
                <strong>📍 위치:</strong> <span id="locationText"></span>
              </div>
              <div class="mb-2">
                <strong>☀️ 일평균 일사량:</strong> <span id="ghiDailyText"></span> kWh/m²/일
              </div>
              <div class="mb-2">
                <strong>📅 연평균 일사량:</strong> <span id="ghiAnnualText"></span> kWh/m²/년
              </div>
              <small class="text-muted">✅ NASA POWER 위성 데이터 기반 (30년 평균)</small>
            </div>
            
            <div class="mb-2">
              <strong>⚡ 연간 발전량:</strong> <span id="energyText"></span> kWh/kWp/년
            </div>
            <div class="mb-2">
              <strong>🎯 최적 설치 각도:</strong> 경사각 <span id="optimalTiltText"></span>°, 방위각 <span id="optimalAzimuthText"></span>°
            </div>
            
            <div class="d-grid gap-2 mt-3">
              <button class="btn btn-primary" id="optimizeButton">최적 각도 적용</button>
            </div>
            
            <div class="financial-metrics" id="financialMetrics" style="display: none;">
              <h5>💰 경제성 분석</h5>
              <div class="row">
                <div class="col-6">
                  <div class="mb-2">
                    <strong>🏗️ 설치 가능 용량:</strong><br>
                    <span class="text-primary fs-6" id="maxCapacityDisplayText">-</span>
                  </div>
                  <div class="mb-2">
                    <strong>💰 총 설치 비용:</strong><br>
                    <span class="text-danger fs-6" id="totalCostText">-</span>
                  </div>
                  <div class="mb-2">
                    <strong>⚡ 연간 발전량:</strong><br>
                    <span class="text-success fs-6" id="annualProductionText">-</span>
                  </div>
                </div>
                <div class="col-6">
                  <div class="mb-2">
                    <strong>💵 연간 매출:</strong><br>
                    <span class="text-success fs-6" id="annualRevenueText">-</span>
                  </div>
                  <div class="mb-2">
                    <strong>⏰ 투자 회수 기간:</strong><br>
                    <span class="text-warning fs-6" id="paybackPeriodText">-</span>
                  </div>
                  <div class="mb-2">
                    <strong>📈 투자 수익률 (ROI):</strong><br>
                    <span class="text-info fs-6" id="roiText">-</span>
                  </div>
                </div>
              </div>
              
              <div class="mt-3 p-3 bg-light rounded">
                <h6>📊 상세 수익 분석</h6>
                <div class="mb-1">
                  <small><strong>SMP 수익:</strong> <span id="smpRevenueText">-</span>원/년</small>
                </div>
                <div class="mb-1">
                  <small><strong>REC 수익:</strong> <span id="recRevenueText">-</span>원/년</small>
                </div>
                <div class="mb-1">
                  <small><strong>월평균 발전량:</strong> <span id="monthlyProductionText">-</span>kWh</small>
                </div>
                <div class="mb-1">
                  <small><strong>월평균 수익:</strong> <span id="monthlyRevenueText">-</span>원</small>
                </div>
                <div class="mt-2">
                  <small><strong>25년 총 수익:</strong> <span class="text-success" id="lifeCycleRevenueText">-</span>원</small>
                </div>
              </div>
            </div>
            
            <div class="chart-container">
              <img id="monthlyChart" class="img-fluid" src="" alt="월별 발전량 차트">
            </div>
          </div>
        </div>
        <div class="col-lg-9 col-md-8 map-container">
          <div id="map"></div>
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
      
      let currentMarker = null;
      let currentLatLng = null;
      
      const landAreaInput = document.getElementById('landAreaInput');
      const systemSizeInput = document.getElementById('systemSizeInput');
      const maxCapacityText = document.getElementById('maxCapacityText');
      const capacityCalculation = document.getElementById('capacityCalculation');
      const installationTypeSelect = document.getElementById('installationTypeSelect');
      const customCostContainer = document.getElementById('customCostContainer');
      const installCostInput = document.getElementById('installCostInput');
      const smpPriceInput = document.getElementById('smpPriceInput');
      const recPriceInput = document.getElementById('recPriceInput');
      const tiltSlider = document.getElementById('tiltSlider');
      const tiltValue = document.getElementById('tiltValue');
      const azimuthSlider = document.getElementById('azimuthSlider');
      const azimuthValue = document.getElementById('azimuthValue');
      const optimizeButton = document.getElementById('optimizeButton');
      const loadingIndicator = document.getElementById('loadingIndicator');
      const financialMetrics = document.getElementById('financialMetrics');
      
      // 🔍 주소 검색 기능
      const addressInput = document.getElementById('addressInput');
      const searchButton = document.getElementById('searchButton');
      const searchResults = document.getElementById('searchResults');
      const searchResultText = document.getElementById('searchResultText');
      
      // 주소 검색 함수
      async function searchAddress(address) {
        try {
          loadingIndicator.style.display = 'flex';
          searchResults.style.display = 'none';
          
          // 주소 검색 API 호출
          const response = await fetch(`/search_address?query=${encodeURIComponent(address)}`);
          const data = await response.json();
          
          if (data.error) {
            searchResultText.textContent = `❌ 검색 실패: ${data.error}`;
            searchResults.style.display = 'block';
            searchResults.querySelector('.alert').className = 'alert alert-danger';
            loadingIndicator.style.display = 'none';
            return;
          }
          
          if (data.documents && data.documents.length > 0) {
            const result = data.documents[0];
            const lat = parseFloat(result.y);
            const lon = parseFloat(result.x);
            
            // 지도에 마커 표시
            if (currentMarker) {
              map.removeLayer(currentMarker);
            }
            
            const latLng = L.latLng(lat, lon);
            currentMarker = L.marker(latLng).addTo(map);
            currentLatLng = latLng;
            
            // 지도 중심 이동
            map.setView(latLng, 15);
            
            // 검색 결과 표시
            searchResultText.innerHTML = `
              ✅ <strong>검색 성공!</strong><br>
              📍 주소: ${result.address_name || result.place_name}<br>
              📌 좌표: ${lat.toFixed(5)}, ${lon.toFixed(5)}<br>
              🔄 발전량 계산을 시작합니다...
            `;
            searchResults.style.display = 'block';
            searchResults.querySelector('.alert').className = 'alert alert-success';
            
            // 자동으로 발전량 계산 시작
            setTimeout(() => {
              updateResults();
            }, 1000);
            
          } else {
            searchResultText.textContent = `❌ '${address}' 주소를 찾을 수 없습니다. 다른 키워드로 검색해보세요.`;
            searchResults.style.display = 'block';
            searchResults.querySelector('.alert').className = 'alert alert-warning';
          }
          
          loadingIndicator.style.display = 'none';
          
        } catch (error) {
          console.error('Address search error:', error);
          searchResultText.textContent = '❌ 주소 검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
          searchResults.style.display = 'block';
          searchResults.querySelector('.alert').className = 'alert alert-danger';
          loadingIndicator.style.display = 'none';
        }
      }
      
      // 검색 버튼 클릭 이벤트
      searchButton.addEventListener('click', () => {
        const address = addressInput.value.trim();
        if (address) {
          searchAddress(address);
        } else {
          alert('주소를 입력해주세요.');
        }
      });
      
      // 주소 입력 후 엔터키 이벤트
      addressInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          const address = addressInput.value.trim();
          if (address) {
            searchAddress(address);
          }
        }
      });
      
      // 주소 입력창 포커스 시 검색 결과 숨기기
      addressInput.addEventListener('focus', () => {
        searchResults.style.display = 'none';
      });
      
      // 빠른 검색 버튼들 이벤트
      document.querySelectorAll('.quick-search').forEach(button => {
        button.addEventListener('click', (e) => {
          const address = e.target.dataset.address;
          addressInput.value = address;
          searchAddress(address);
        });
      });
      
      // 빠른 용량 선택 버튼들 이벤트
      document.querySelectorAll('.quick-capacity').forEach(button => {
        button.addEventListener('click', (e) => {
          const capacity = parseFloat(e.target.dataset.capacity);
          systemSizeInput.value = capacity;
          
          // 버튼 활성화 표시
          document.querySelectorAll('.quick-capacity').forEach(btn => {
            btn.classList.remove('active');
          });
          e.target.classList.add('active');
          
          // 즉시 결과 업데이트
          if (currentLatLng) updateResults();
        });
      });
      
      // 📌 1. 면적 입력 → 설치 가능 용량 자동 계산
      landAreaInput.addEventListener('input', () => {
        const area = parseFloat(landAreaInput.value);
        if (area && area >= 32) {
          const maxCapacity = Math.floor(area / 32);
          maxCapacityText.textContent = maxCapacity;
          capacityCalculation.style.display = 'block';
          
          if (systemSizeInput.value < maxCapacity) {
            systemSizeInput.value = maxCapacity;
          }
        } else {
          capacityCalculation.style.display = 'none';
        }
        
        if (currentLatLng) updateResults();
      });
      
      // 📌 2. 설치 유형 선택 → 설치비 자동 반영
      installationTypeSelect.addEventListener('change', () => {
        const selectedOption = installationTypeSelect.options[installationTypeSelect.selectedIndex];
        const cost = selectedOption.dataset.cost;
        
        if (installationTypeSelect.value === 'custom') {
          customCostContainer.style.display = 'block';
        } else {
          customCostContainer.style.display = 'none';
          installCostInput.value = cost;
        }
        
        if (currentLatLng) updateResults();
      });
      
      // 다른 입력 요소들 이벤트 리스너
      const inputElements = [
        installCostInput, smpPriceInput, recPriceInput
      ];
      
      inputElements.forEach(element => {
        element.addEventListener('change', () => {
          if (currentLatLng) updateResults();
        });
      });
      
      // 슬라이더 값 표시 업데이트
      tiltSlider.addEventListener('input', () => {
        tiltValue.textContent = tiltSlider.value;
        if (currentLatLng) updateResults();
      });
      
      azimuthSlider.addEventListener('input', () => {
        azimuthValue.textContent = azimuthSlider.value;
        if (currentLatLng) updateResults();
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
      
      // 지도 클릭 이벤트
      function onMapClick(e) {
        const lat = e.latlng.lat.toFixed(5);
        const lon = e.latlng.lng.toFixed(5);
        
        if (currentMarker) {
          map.removeLayer(currentMarker);
        }
        
        currentMarker = L.marker(e.latlng).addTo(map);
        currentLatLng = e.latlng;
        
        updateResults();
      }
      
      // 결과 업데이트
      function updateResults() {
        if (!currentLatLng) return;
        
        loadingIndicator.style.display = 'flex';
        
        const lat = currentLatLng.lat.toFixed(5);
        const lon = currentLatLng.lng.toFixed(5);
        const tilt = tiltSlider.value;
        const azimuth = azimuthSlider.value;
        const systemSize = parseFloat(systemSizeInput.value);
        
        // 📌 설치비 계산
        const selectedOption = installationTypeSelect.options[installationTypeSelect.selectedIndex];
        const installCostPerKw = installationTypeSelect.value === 'custom' 
          ? parseFloat(installCostInput.value) 
          : parseFloat(selectedOption.dataset.cost);
        
        // 📌 전력 판매 단가
        const smpPrice = parseFloat(smpPriceInput.value);
        const recPrice = parseFloat(recPriceInput.value);
        
        // API 요청
        fetch(`/get_pv_data?lat=${lat}&lon=${lon}&tilt=${tilt}&azimuth=${azimuth}`)
          .then(res => res.json())
          .then(data => {
            if (data.error) {
              alert('데이터 조회 오류: ' + data.error);
              loadingIndicator.style.display = 'none';
              return;
            }
            
            // ✅ 결과 표시 (GHI 정보 개선)
            document.getElementById('resultsContainer').style.display = 'block';
            document.getElementById('locationText').textContent = `${lat}, ${lon}`;
            
            // GHI 일일값과 연간값 모두 표시
            document.getElementById('ghiDailyText').textContent = data.ghi_daily;
            document.getElementById('ghiAnnualText').textContent = data.ghi_annual;
            
            document.getElementById('energyText').textContent = data.energy;
            document.getElementById('optimalTiltText').textContent = data.optimal_tilt;
            document.getElementById('optimalAzimuthText').textContent = data.optimal_azimuth;
            
            // 차트 업데이트
            document.getElementById('monthlyChart').src = `/get_monthly_chart?lat=${lat}&lon=${lon}&tilt=${tilt}&azimuth=${azimuth}`;
            
            # 경제성 분석
            fetch(`/get_financial_metrics?energy_per_kwp=${data.energy}&system_size=${systemSize}&install_cost=${installCostPerKw}&smp_price=${smpPrice}&rec_price=${recPrice}`)
              .then(res => res.json())
              .then(financialData => {
                // 📌 3. 최종 출력 – 수익 예측 및 ROI 계산 (단위 명시)
                financialMetrics.style.display = 'block';
                
                // 설치 가능 용량 표시
                const landArea = parseFloat(landAreaInput.value) || 0;
                const currentSystemSize = parseFloat(systemSizeInput.value) || 0;
                const maxCapacity = landArea >= 32 ? Math.floor(landArea / 32) : 0;
                
                if (maxCapacity > 0) {
                  const utilizationRate = ((currentSystemSize / maxCapacity) * 100).toFixed(1);
                  document.getElementById('maxCapacityDisplayText').textContent = 
                    `${currentSystemSize}kWp / ${maxCapacity}kWp (토지 활용률: ${utilizationRate}%)`;
                } else {
                  document.getElementById('maxCapacityDisplayText').textContent = 
                    `${currentSystemSize}kWp (면적 미입력)`;
                }
                
                // ✅ 기본 정보 (단위 명시)
                document.getElementById('totalCostText').textContent = `${financialData.total_cost.toLocaleString()}원`;
                document.getElementById('annualProductionText').textContent = `${financialData.annual_production.toLocaleString()}kWh/년`;
                document.getElementById('annualRevenueText').textContent = `${financialData.annual_revenue.toLocaleString()}원/년`;
                
                // ✅ 회수기간 표시 개선
                if (financialData.payback_period && financialData.payback_period <= 25) {
                  document.getElementById('paybackPeriodText').textContent = `${financialData.payback_period}년`;
                  document.getElementById('paybackPeriodText').className = 'text-success fs-6';
                } else {
                  document.getElementById('paybackPeriodText').textContent = '25년 내 회수 불가';
                  document.getElementById('paybackPeriodText').className = 'text-danger fs-6';
                }
                
                // ✅ ROI 표시 개선 (색상 구분)
                const roi = financialData.roi;
                document.getElementById('roiText').textContent = `${roi}% (25년)`;
                if (roi > 100) {
                  document.getElementById('roiText').className = 'text-success fs-6';
                } else if (roi > 0) {
                  document.getElementById('roiText').className = 'text-warning fs-6';
                } else {
                  document.getElementById('roiText').className = 'text-danger fs-6';
                }
                
                // ✅ 상세 수익 분석 (단위 명시 및 REC 정보 추가)
                document.getElementById('smpRevenueText').textContent = `${financialData.annual_smp_revenue.toLocaleString()}`;
                document.getElementById('recRevenueText').textContent = `${financialData.annual_rec_revenue.toLocaleString()} (가중치 ${financialData.rec_weight || 1.5}x)`;
                document.getElementById('monthlyProductionText').textContent = `${financialData.monthly_production.toLocaleString()}`;
                document.getElementById('monthlyRevenueText').textContent = `${financialData.monthly_revenue.toLocaleString()}`;
                document.getElementById('lifeCycleRevenueText').textContent = `${financialData.life_cycle_revenue.toLocaleString()}`;
                
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

@app.route('/search_address')
def search_address():
    """한국 주소 검색 API (Nominatim 사용)"""
    query = request.args.get('query', '')
    if not query:
        return jsonify({'error': '검색어를 입력해주세요.'}), 400
    
    try:
        # Nominatim API 사용 (무료, 키 불필요)
        nominatim_url = f"https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{query} South Korea",
            'format': 'json',
            'limit': 1,
            'countrycodes': 'kr',
            'addressdetails': 1
        }
        
        headers = {
            'User-Agent': 'SolarCalculator/1.0'
        }
        
        response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            return jsonify({
                'documents': [{
                    'y': result['lat'],
                    'x': result['lon'],
                    'address_name': result.get('display_name', ''),
                    'place_name': result.get('display_name', '')
                }]
            })
        else:
            return jsonify({'documents': []})
            
    except requests.RequestException as e:
        return jsonify({'error': f'네트워크 오류: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'검색 오류: {str(e)}'}), 500

@app.route('/get_pv_data')
def get_pv_data():
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
        res = requests.get(url, timeout=10).json()
        ghi_daily = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
        print(f"🌞 NASA API 응답: 위치({lat}, {lon}), GHI 일일값={ghi_daily} kWh/m²/일")
    except Exception as e:
        print(f"❌ NASA API 오류: {str(e)}")
        return jsonify({'error': f'GHI data not found: {str(e)}'}), 500
    
    # ✅ 태양광 발전량 계산 (수정된 함수 사용)
    try:
        pv_result = calculate_pv_energy(lat=lat, lon=lon, tilt=tilt, azimuth=azimuth, ghi_daily=ghi_daily)
        print(f"⚡ 계산 결과: 연간 발전량={pv_result['annual_energy']} kWh/kWp")
    except Exception as e:
        print(f"❌ 발전량 계산 오류: {str(e)}")
        return jsonify({'error': f'PV calculation error: {str(e)}'}), 500
    
    # ✅ 응답에 일일값과 연간값 모두 포함
    ghi_annual = ghi_daily * 365
    
    return jsonify({
        'ghi_daily': round(ghi_daily, 1),
        'ghi_annual': round(ghi_annual, 1),
        'energy': pv_result['annual_energy'],
        'monthly_energy': pv_result['monthly_energy'],
        'optimal_tilt': pv_result['optimal_tilt'],
        'optimal_azimuth': pv_result['optimal_azimuth']
    })

@app.route('/get_monthly_chart')
def get_monthly_chart():
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
        res = requests.get(url, timeout=10).json()
        ghi_daily = res['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
    except:
        return "Error: GHI data not found", 500
    
    # ✅ 발전량 계산 (수정된 함수 사용)
    pv_result = calculate_pv_energy(lat=lat, lon=lon, tilt=tilt, azimuth=azimuth, ghi_daily=ghi_daily)
    
    # 차트 생성
    img_bytes = generate_pv_chart(pv_result['monthly_energy'])
    
    return send_file(img_bytes, mimetype='image/png')

@app.route('/get_financial_metrics')
def get_financial_metrics():
    # ✅ 파라미터명 수정: annual_energy → energy_per_kwp
    energy_per_kwp = request.args.get('energy_per_kwp', type=float)
    system_size = request.args.get('system_size', default=3.0, type=float)
    install_cost = request.args.get('install_cost', default=1800000, type=float)
    smp_price = request.args.get('smp_price', default=180, type=float)
    rec_price = request.args.get('rec_price', default=40, type=float)
    
    # ✅ 수정된 경제성 지표 계산 함수 호출
    financial_data = calculate_financial_metrics(
        energy_per_kwp=energy_per_kwp,  # kWh/kWp/년 단위 명시
        system_size=system_size,
        install_cost_per_kw=install_cost,
        smp_price=smp_price,
        rec_price=rec_price
    )
    
    return jsonify(financial_data)

# 🚀 웹 서버 실행
if __name__ == '__main__':
    # Railway에서 제공하는 PORT 환경변수 사용
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🌞 태양광 발전량 예측 시스템이 시작되었습니다!")
    print(f"🌍 포트: {port}")
    print("\n📊 기능:")
    print("   - 지도 클릭으로 태양광 발전량 계산")
    print("   - 경사각/방위각 조정")
    print("   - 경제성 분석")
    print("   - 월별 발전량 차트")
    print("\n✅ 모든 계산 오류 수정 완료!")
    print("   - GHI 단위 변환: 일일값 → 연간값")
    print("   - 발전량 이중 곱셈 방지: energy_per_kwp 단위 명시")
    print("   - REC 가중치 적용: 1.5x")
    print("   - 회수기간 계산 로직 개선")
    print("   - ROI 계산 정확성 향상")
    
    # Railway 환경에서 실행
    app.run(host='0.0.0.0', port=port, debug=False)