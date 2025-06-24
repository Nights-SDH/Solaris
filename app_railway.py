# 🌾 농지 태양광 모바일 전용 UI (인스타/유튜브 광고 유입용)
import os
from flask import Flask, request, jsonify, render_template_string, send_file, send_from_directory
import requests
import json
import time
import numpy as np
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Flask 앱 설정
app = Flask(__name__)

# 🔧 농지 태양광 계산 함수
def calculate_farmland_solar(area_pyeong, lat, lon):
    """농지 태양광 수익 계산"""
    try:
        # 1. 기본 검증
        if area_pyeong < 20:
            return {
                'installable': False,
                'message': '최소 20평 이상의 면적이 필요합니다.'
            }
        
        # 2. 면적 변환 (평 → ㎡)
        area_sqm = area_pyeong * 3.3
        
        # 3. 설치 가능 용량 (1kW당 10㎡ 필요)
        install_capacity_kw = area_sqm / 10
        
        # 4. 지역별 GHI 데이터 (한국 평균 기준)
        if 33 <= lat <= 38 and 125 <= lon <= 130:
            annual_generation_per_kw = 1300  # kWh/kW/년 (한국 평균)
        else:
            annual_generation_per_kw = 1200  # 기본값
        
        # 5. 연간 발전량 계산
        annual_generation_kwh = install_capacity_kw * annual_generation_per_kw
        
        # 6. 수익 계산 (2024년 기준)
        smp_price = 113.9  # 원/kWh (계통한계가격)
        rec_price = 70000  # 원/REC
        rec_weight = 1.5   # 영농형 태양광 가중치
        
        # SMP 수익
        smp_revenue = annual_generation_kwh * smp_price
        
        # REC 수익 (1MWh당 1REC, 가중치 적용)
        rec_revenue = (annual_generation_kwh / 1000) * rec_weight * rec_price
        
        # 운영유지비 (연간)
        om_cost = install_capacity_kw * 12000  # kW당 연 1.2만원
        
        # 총 연간 수익
        total_annual_revenue = smp_revenue + rec_revenue - om_cost
        
        # 7. 설치비용 및 회수기간
        install_cost_per_kw = 20000000  # 2천만원/kW (보조금 미적용)
        total_install_cost = install_capacity_kw * install_cost_per_kw
        payback_years = total_install_cost / total_annual_revenue if total_annual_revenue > 0 else 999
        
        # 8. 농업 수익과 비교 (평당 연 50만원 가정)
        farming_revenue = area_pyeong * 500000
        solar_vs_farming_ratio = total_annual_revenue / farming_revenue if farming_revenue > 0 else 1
        
        return {
            'installable': True,
            'area_pyeong': area_pyeong,
            'area_sqm': round(area_sqm),
            'install_capacity_kw': round(install_capacity_kw, 1),
            'annual_generation_kwh': round(annual_generation_kwh),
            'annual_revenue': round(total_annual_revenue),
            'smp_revenue': round(smp_revenue),
            'rec_revenue': round(rec_revenue),
            'om_cost': round(om_cost),
            'install_cost': round(total_install_cost),
            'payback_years': round(payback_years, 1),
            'farming_revenue': round(farming_revenue),
            'solar_vs_farming_ratio': round(solar_vs_farming_ratio, 1),
            'message': '영농형 태양광 설치 가능합니다!'
        }
        
    except Exception as e:
        print(f"계산 오류: {str(e)}")
        return {
            'installable': False,
            'message': '계산 중 오류가 발생했습니다.'
        }

# 🎯 메인 라우팅
@app.route('/')
def index():
    """Step 1: 면적 입력 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>농지 태양광 수익 계산기</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">
      <style>
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          color: #333;
        }
        
        .container {
          max-width: 100%;
          margin: 0 auto;
          background: white;
          min-height: 100vh;
        }
        
        /* 🎨 헤더 */
        .header {
          background: linear-gradient(135deg, #2E8B57, #32CD32);
          color: white;
          text-align: center;
          padding: 20px 15px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header h1 {
          font-size: 20px;
          font-weight: 700;
          margin-bottom: 8px;
        }
        
        .header .subtitle {
          font-size: 14px;
          opacity: 0.9;
        }
        
        /* 📱 메인 콘텐츠 */
        .content {
          padding: 20px 15px;
        }
        
        .guide-text {
          text-align: center;
          margin-bottom: 25px;
          padding: 15px;
          background: #f8f9fa;
          border-radius: 10px;
          border-left: 4px solid #2E8B57;
        }
        
        .guide-text h2 {
          font-size: 18px;
          color: #2E8B57;
          margin-bottom: 8px;
        }
        
        .guide-text p {
          font-size: 14px;
          color: #666;
          line-height: 1.4;
        }
        
        /* 🔍 주소 검색 */
        .search-section {
          margin-bottom: 20px;
        }
        
        .search-box {
          display: flex;
          gap: 8px;
          margin-bottom: 8px;
        }
        
        .search-input {
          flex: 1;
          padding: 12px 15px;
          border: 2px solid #e9ecef;
          border-radius: 8px;
          font-size: 16px;
          outline: none;
        }
        
        .search-input:focus {
          border-color: #2E8B57;
        }
        
        .search-btn {
          padding: 12px 20px;
          background: #2E8B57;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          cursor: pointer;
          white-space: nowrap;
        }
        
        .search-btn:active {
          background: #236B43;
        }
        
        .search-help {
          font-size: 12px;
          color: #666;
          margin-left: 5px;
        }
        
        /* 🗺️ 지도 영역 */
        .map-section {
          margin-bottom: 25px;
        }
        
        .map-container {
          height: 250px;
          border-radius: 10px;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
          position: relative;
        }
        
        .location-btn {
          position: absolute;
          top: 10px;
          right: 10px;
          z-index: 1000;
          background: white;
          border: none;
          padding: 8px;
          border-radius: 6px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.2);
          cursor: pointer;
          font-size: 18px;
        }
        
        .map-guide {
          text-align: center;
          margin-top: 10px;
          font-size: 14px;
          color: #666;
        }
        
        /* 📐 면적 입력 */
        .area-section {
          margin-bottom: 30px;
        }
        
        .area-label {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 10px;
          color: #333;
        }
        
        .area-input-container {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 10px;
        }
        
        .area-input {
          flex: 1;
          padding: 15px 20px;
          border: 3px solid #e9ecef;
          border-radius: 12px;
          font-size: 24px;
          font-weight: 700;
          text-align: center;
          outline: none;
          color: #2E8B57;
        }
        
        .area-input:focus {
          border-color: #2E8B57;
          box-shadow: 0 0 0 3px rgba(46, 139, 87, 0.1);
        }
        
        .area-unit {
          font-size: 18px;
          font-weight: 600;
          color: #2E8B57;
        }
        
        .area-info {
          font-size: 12px;
          color: #666;
          text-align: center;
        }
        
        /* ⚠️ 경고 메시지 */
        .warning {
          background: #fff3cd;
          color: #856404;
          padding: 10px 15px;
          border-radius: 8px;
          font-size: 14px;
          margin-bottom: 20px;
          border-left: 4px solid #ffc107;
          display: none;
        }
        
        .warning.show {
          display: block;
        }
        
        /* 🔆 수익 확인 버튼 */
        .calculate-btn {
          width: 100%;
          padding: 18px;
          background: linear-gradient(135deg, #FFD700, #FFA500);
          color: #333;
          border: none;
          border-radius: 12px;
          font-size: 18px;
          font-weight: 700;
          cursor: pointer;
          box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
          margin-bottom: 20px;
          position: relative;
          overflow: hidden;
        }
        
        .calculate-btn:disabled {
          background: #ccc;
          color: #999;
          cursor: not-allowed;
          box-shadow: none;
        }
        
        .calculate-btn:active:not(:disabled) {
          transform: translateY(2px);
        }
        
        /* 로딩 애니메이션 */
        .loading {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.7);
          z-index: 9999;
          justify-content: center;
          align-items: center;
          flex-direction: column;
          color: white;
        }
        
        .spinner {
          width: 50px;
          height: 50px;
          border: 5px solid #ffffff33;
          border-top: 5px solid #fff;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 15px;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        .loading-text {
          font-size: 16px;
          text-align: center;
        }
        
        /* 📍 위치 정보 표시 */
        .location-info {
          background: #e8f5e9;
          color: #2e7d32;
          padding: 10px 15px;
          border-radius: 8px;
          font-size: 14px;
          margin-bottom: 15px;
          display: none;
        }
        
        .location-info.show {
          display: block;
        }
        
        /* 📱 반응형 */
        @media (max-width: 480px) {
          .content {
            padding: 15px 10px;
          }
          
          .header {
            padding: 15px 10px;
          }
          
          .area-input {
            font-size: 20px;
            padding: 12px 15px;
          }
          
          .calculate-btn {
            font-size: 16px;
            padding: 15px;
          }
        }
      </style>
    </head>
    <body>
      <!-- 로딩 오버레이 -->
      <div class="loading" id="loading">
        <div class="spinner"></div>
        <div class="loading-text">
          <div>🌾 수익 계산 중...</div>
          <div style="font-size: 14px; margin-top: 5px;">잠시만 기다려주세요</div>
        </div>
      </div>
      
      <div class="container">
        <!-- 헤더 -->
        <div class="header">
          <h1>🌾 내 농지 정보 입력하기</h1>
          <div class="subtitle">태양광으로 새로운 수익을 만들어보세요</div>
        </div>
        
        <!-- 메인 콘텐츠 -->
        <div class="content">
          <!-- 안내 문구 -->
          <div class="guide-text">
            <h2>📍 지도에서 위치를 지정하고</h2>
            <p>평 수를 입력해주세요<br><small>(예: 600평 입력)</small></p>
          </div>
          
          <!-- 주소 검색 -->
          <div class="search-section">
            <div class="search-box">
              <input type="text" class="search-input" id="addressInput" 
                     placeholder="예: 논산시 벌곡면 또는 마을명">
              <button class="search-btn" onclick="searchAddress()">🔍</button>
            </div>
            <div class="search-help">💡 읍·면·동 또는 마을명으로 검색 가능</div>
          </div>
          
          <!-- 위치 정보 표시 -->
          <div class="location-info" id="locationInfo">
            📍 <span id="locationText">위치를 선택해주세요</span>
          </div>
          
          <!-- 지도 -->
          <div class="map-section">
            <div class="map-container">
              <button class="location-btn" onclick="getCurrentLocation()" title="내 위치">📍</button>
              <div id="map" style="height: 100%; width: 100%;"></div>
            </div>
            <div class="map-guide">
              🗺️ 지도를 터치해서 농지 위치를 선택하세요
            </div>
          </div>
          
          <!-- 면적 입력 -->
          <div class="area-section">
            <div class="area-label">🏗️ 내 땅 면적을 입력해주세요</div>
            <div class="area-input-container">
              <input type="number" class="area-input" id="areaInput" 
                     placeholder="600" min="1" max="10000" 
                     inputmode="numeric" pattern="[0-9]*">
              <span class="area-unit">평</span>
            </div>
            <div class="area-info">💡 1평 = 3.3㎡로 자동 계산됩니다</div>
          </div>
          
          <!-- 경고 메시지 -->
          <div class="warning" id="warningMessage">
            ⚠️ 최소 20평 이상 입력해주세요
          </div>
          
          <!-- 수익 확인 버튼 -->
          <button class="calculate-btn" id="calculateBtn" onclick="calculateRevenue()" disabled>
            🔆 수익 확인하기
          </button>
        </div>
      </div>
      
      <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
      <script>
        // 🗺️ 지도 초기화
        const map = L.map('map', {
          zoomControl: false,
          attributionControl: false
        }).setView([36.5, 127.8], 7);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: ''
        }).addTo(map);
        
        // 줌 컨트롤 추가 (오른쪽 하단)
        L.control.zoom({
          position: 'bottomleft'
        }).addTo(map);
        
        let currentMarker = null;
        let currentLocation = { lat: null, lng: null, address: '' };
        
        // 📱 DOM 요소들
        const addressInput = document.getElementById('addressInput');
        const areaInput = document.getElementById('areaInput');
        const warningMessage = document.getElementById('warningMessage');
        const calculateBtn = document.getElementById('calculateBtn');
        const locationInfo = document.getElementById('locationInfo');
        const locationText = document.getElementById('locationText');
        const loading = document.getElementById('loading');
        
        // 🔍 주소 검색
        async function searchAddress() {
          const address = addressInput.value.trim();
          if (!address) {
            alert('주소를 입력해주세요.');
            return;
          }
          
          showLoading(true, '위치 검색 중...');
          
          try {
            const response = await fetch(`/api/search-address?query=${encodeURIComponent(address)}`);
            const data = await response.json();
            
            if (data.success && data.location) {
              const { lat, lng, display_name } = data.location;
              setMapLocation(lat, lng, display_name);
              
              // 검색창 비우기
              addressInput.value = '';
              addressInput.placeholder = '다른 위치 검색...';
            } else {
              alert('❌ 주소를 찾을 수 없습니다.\\n다른 키워드로 검색해보세요.');
            }
          } catch (error) {
            console.error('검색 오류:', error);
            alert('❌ 검색 중 오류가 발생했습니다.');
          }
          
          showLoading(false);
        }
        
        // 📍 현재 위치 가져오기
        function getCurrentLocation() {
          if (!navigator.geolocation) {
            alert('이 기기는 위치 서비스를 지원하지 않습니다.');
            return;
          }
          
          showLoading(true, '현재 위치 확인 중...');
          
          navigator.geolocation.getCurrentPosition(
            function(position) {
              const lat = position.coords.latitude;
              const lng = position.coords.longitude;
              setMapLocation(lat, lng, '현재 위치');
              showLoading(false);
            },
            function(error) {
              console.error('위치 오류:', error);
              alert('❌ 현재 위치를 가져올 수 없습니다.\\n지도에서 직접 선택해주세요.');
              showLoading(false);
            },
            {
              enableHighAccuracy: true,
              timeout: 10000,
              maximumAge: 60000
            }
          );
        }
        
        // 🗺️ 지도 위치 설정
        function setMapLocation(lat, lng, address = '') {
          if (currentMarker) {
            map.removeLayer(currentMarker);
          }
          
          const latLng = L.latLng(lat, lng);
          
          // 농지 아이콘 마커 생성
          currentMarker = L.marker(latLng, {
            icon: L.divIcon({
              html: '🌾',
              iconSize: [30, 30],
              className: 'custom-div-icon'
            })
          }).addTo(map);
          
          // 지도 이동
          map.setView(latLng, 15);
          
          // 위치 정보 저장
          currentLocation = { lat, lng, address };
          
          // 위치 정보 표시
          locationText.textContent = address || `위도: ${lat.toFixed(4)}, 경도: ${lng.toFixed(4)}`;
          locationInfo.classList.add('show');
          
          // 버튼 상태 업데이트
          updateCalculateButton();
        }
        
        // 🗺️ 지도 클릭 이벤트
        map.on('click', function(e) {
          const lat = e.latlng.lat;
          const lng = e.latlng.lng;
          setMapLocation(lat, lng, `클릭한 위치`);
        });
        
        // 📐 면적 입력 이벤트
        areaInput.addEventListener('input', function() {
          const area = parseFloat(this.value);
          
          if (area && area < 20) {
            warningMessage.classList.add('show');
          } else {
            warningMessage.classList.remove('show');
          }
          
          updateCalculateButton();
        });
        
        // 주소 검색 엔터키
        addressInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            searchAddress();
          }
        });
        
        // 🔆 계산 버튼 상태 업데이트
        function updateCalculateButton() {
          const area = parseFloat(areaInput.value);
          const hasLocation = currentLocation.lat && currentLocation.lng;
          
          if (hasLocation && area && area >= 20) {
            calculateBtn.disabled = false;
          } else {
            calculateBtn.disabled = true;
          }
        }
        
        // 💰 수익 계산
        async function calculateRevenue() {
          const area = parseFloat(areaInput.value);
          
          if (!currentLocation.lat || !currentLocation.lng) {
            alert('📍 먼저 지도에서 위치를 선택해주세요.');
            return;
          }
          
          if (!area || area < 20) {
            alert('📐 20평 이상의 면적을 입력해주세요.');
            return;
          }
          
          showLoading(true, '수익 계산 중...');
          
          try {
            const response = await fetch('/api/simulate', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({
                area_pyeong: area,
                lat: currentLocation.lat,
                lng: currentLocation.lng,
                address: currentLocation.address
              })
            });
            
            const data = await response.json();
            
            if (data.success && data.result.installable) {
              // 결과 페이지로 이동
              localStorage.setItem('solarResult', JSON.stringify(data.result));
              window.location.href = '/result';
            } else {
              alert('❌ ' + (data.result?.message || '계산 중 오류가 발생했습니다.'));
            }
          } catch (error) {
            console.error('계산 오류:', error);
            alert('❌ 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
          }
          
          showLoading(false);
        }
        
        // 로딩 표시
        function showLoading(show, text = '처리 중...') {
          if (show) {
            document.querySelector('.loading-text div').textContent = text;
            loading.style.display = 'flex';
          } else {
            loading.style.display = 'none';
          }
        }
        
        // 페이지 로드시 초기화
        window.addEventListener('load', function() {
          // 저장된 결과 데이터 삭제 (새 계산)
          localStorage.removeItem('solarResult');
          
          // 포커스 설정
          setTimeout(() => {
            addressInput.focus();
          }, 1000);
        });
      </script>
    </body>
    </html>
    """)

@app.route('/result')
def result_page():
    """Step 2: 결과 요약 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>농지 태양광 수익 결과</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
      <style>
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          color: #333;
        }
        
        .container {
          max-width: 100%;
          margin: 0 auto;
          background: white;
          min-height: 100vh;
        }
        
        /* 🎉 성공 헤더 */
        .success-header {
          background: linear-gradient(135deg, #4CAF50, #45a049);
          color: white;
          text-align: center;
          padding: 25px 15px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .success-header h1 {
          font-size: 24px;
          font-weight: 700;
          margin-bottom: 8px;
        }
        
        .success-header .subtitle {
          font-size: 16px;
          opacity: 0.9;
        }
        
        /* 💰 수익 요약 */
        .revenue-summary {
          background: linear-gradient(135deg, #FFD700, #FFA500);
          margin: 20px 15px;
          padding: 25px 20px;
          border-radius: 15px;
          text-align: center;
          box-shadow: 0 6px 20px rgba(255, 215, 0, 0.3);
        }
        
        .revenue-title {
          font-size: 18px;
          font-weight: 600;
          color: #333;
          margin-bottom: 10px;
        }
        
        .revenue-amount {
          font-size: 32px;
          font-weight: 900;
          color: #2E8B57;
          margin-bottom: 5px;
          text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        
        .revenue-period {
          font-size: 14px;
          color: #666;
        }
        
        /* ⚡ 발전량 정보 */
        .generation-info {
          background: #e3f2fd;
          margin: 0 15px 20px;
          padding: 15px 20px;
          border-radius: 10px;
          text-align: center;
          border-left: 4px solid #2196F3;
        }
        
        .generation-title {
          font-size: 16px;
          color: #1976d2;
          margin-bottom: 5px;
        }
        
        .generation-amount {
          font-size: 20px;
          font-weight: 700;
          color: #1565c0;
        }
        
        /* 📊 비교 차트 */
        .comparison-section {
          margin: 20px 15px;
          padding: 20px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .comparison-title {
          font-size: 18px;
          font-weight: 600;
          text-align: center;
          margin-bottom: 20px;
          color: #2E8B57;
        }
        
        .comparison-chart {
          display: flex;
          align-items: end;
          justify-content: space-around;
          margin-bottom: 15px;
          height: 120px;
        }
        
        .chart-bar {
          display: flex;
          flex-direction: column;
          align-items: center;
          flex: 1;
          margin: 0 10px;
        }
        
        .bar {
          width: 50px;
          border-radius: 8px 8px 0 0;
          margin-bottom: 10px;
          position: relative;
          transition: all 0.3s ease;
        }
        
        .bar.farming {
          background: linear-gradient(to top, #8bc34a, #4caf50);
        }
        
        .bar.solar {
          background: linear-gradient(to top, #ffd54f, #ff9800);
        }
        
        .bar-label {
          font-size: 14px;
          font-weight: 600;
          text-align: center;
          color: #333;
        }
        
        .bar-value {
          font-size: 12px;
          color: #666;
          margin-top: 5px;
        }
        
        .comparison-result {
          text-align: center;
          font-size: 16px;
          font-weight: 700;
          color: #ff5722;
          background: #fff3e0;
          padding: 10px;
          border-radius: 8px;
        }
        
        /* 📝 상담 신청 폼 */
        .consultation-section {
          margin: 20px 15px;
          padding: 25px 20px;
          background: #f8f9fa;
          border-radius: 12px;
          border: 2px solid #e9ecef;
        }
        
        .consultation-title {
          font-size: 20px;
          font-weight: 700;
          text-align: center;
          margin-bottom: 20px;
          color: #2E8B57;
        }
        
        .form-group {
          margin-bottom: 15px;
        }
        
        .form-label {
          display: block;
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 8px;
          color: #333;
        }
        
        .form-input {
          width: 100%;
          padding: 15px;
          border: 2px solid #e9ecef;
          border-radius: 8px;
          font-size: 16px;
          outline: none;
        }
        
        .form-input:focus {
          border-color: #2E8B57;
          box-shadow: 0 0 0 3px rgba(46, 139, 87, 0.1);
        }
        
        .consultation-btn {
          width: 100%;
          padding: 18px;
          background: linear-gradient(135deg, #2E8B57, #32CD32);
          color: white;
          border: none;
          border-radius: 12px;
          font-size: 18px;
          font-weight: 700;
          cursor: pointer;
          margin-top: 15px;
          box-shadow: 0 4px 15px rgba(46, 139, 87, 0.3);
        }
        
        .consultation-btn:active {
          transform: translateY(2px);
        }
        
        .consultation-btn:disabled {
          background: #ccc;
          cursor: not-allowed;
          box-shadow: none;
        }
        
        /* 📤 공유 및 저장 */
        .action-section {
          margin: 20px 15px;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }
        
        .action-btn {
          padding: 15px 10px;
          border: 2px solid #e9ecef;
          background: white;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s ease;
        }
        
        .action-btn:active {
          transform: scale(0.98);
        }
        
        .action-btn.save {
          color: #1976d2;
          border-color: #bbdefb;
        }
        
        .action-btn.share {
          color: #388e3c;
          border-color: #c8e6c9;
        }
        
        /* 🔙 다시 계산 */
        .recalculate-section {
          margin: 20px 15px 30px;
          text-align: center;
        }
        
        .recalculate-btn {
          padding: 12px 30px;
          background: transparent;
          color: #666;
          border: 2px solid #e9ecef;
          border-radius: 8px;
          font-size: 16px;
          cursor: pointer;
          text-decoration: none;
          display: inline-block;
        }
        
        .recalculate-btn:active {
          background: #f8f9fa;
        }
        
        /* 🎉 성공 메시지 */
        .success-message {
          position: fixed;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          background: #4caf50;
          color: white;
          padding: 20px 30px;
          border-radius: 12px;
          font-size: 16px;
          font-weight: 600;
          box-shadow: 0 6px 20px rgba(0,0,0,0.3);
          z-index: 9999;
          display: none;
          text-align: center;
        }
        
        .success-message.show {
          display: block;
          animation: successPop 0.3s ease-out;
        }
        
        @keyframes successPop {
          0% { transform: translate(-50%, -50%) scale(0.5); opacity: 0; }
          100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
        
        /* 📱 반응형 */
        @media (max-width: 480px) {
          .revenue-amount {
            font-size: 28px;
          }
          
          .consultation-section {
            margin: 15px 10px;
            padding: 20px 15px;
          }
          
          .action-section {
            margin: 15px 10px;
          }
        }
        
        /* 로딩 오버레이 */
        .loading {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.7);
          z-index: 9998;
          justify-content: center;
          align-items: center;
          flex-direction: column;
          color: white;
        }
        
        .spinner {
          width: 50px;
          height: 50px;
          border: 5px solid #ffffff33;
          border-top: 5px solid #fff;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 15px;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      </style>
    </head>
    <body>
      <!-- 로딩 오버레이 -->
      <div class="loading" id="loading">
        <div class="spinner"></div>
        <div>처리 중...</div>
      </div>
      
      <!-- 성공 메시지 -->
      <div class="success-message" id="successMessage">
        ✅ 신청이 완료되었습니다!<br>
        <small>담당자가 빠르게 연락드리겠습니다.</small>
      </div>
      
      <div class="container" id="resultContainer">
        <!-- 성공 헤더 -->
        <div class="success-header">
          <h1>🌞 설치 가능합니다!</h1>
          <div class="subtitle">농지 태양광으로 새로운 수익을 시작하세요</div>
        </div>
        
        <!-- 수익 요약 -->
        <div class="revenue-summary">
          <div class="revenue-title">💰 예상 연간 수익</div>
          <div class="revenue-amount" id="annualRevenue">계산 중...</div>
          <div class="revenue-period">매년 받으실 수 있는 금액입니다</div>
        </div>
        
        <!-- 발전량 정보 -->
        <div class="generation-info">
          <div class="generation-title">⚡ 전기 생산량</div>
          <div class="generation-amount">
            연간 <span id="annualGeneration">-</span>kWh
          </div>
        </div>
        
        <!-- 비교 차트 -->
        <div class="comparison-section">
          <div class="comparison-title">📊 기존 농사 vs 태양광 수익 비교</div>
          <div class="comparison-chart">
            <div class="chart-bar">
              <div class="bar farming" id="farmingBar" style="height: 40px;"></div>
              <div class="bar-label">기존 농사</div>
              <div class="bar-value" id="farmingValue">-</div>
            </div>
            <div class="chart-bar">
              <div class="bar solar" id="solarBar" style="height: 80px;"></div>
              <div class="bar-label">태양광</div>
              <div class="bar-value" id="solarValue">-</div>
            </div>
          </div>
          <div class="comparison-result" id="comparisonResult">
            태양광이 <span id="ratioText">2</span>배 더 수익성이 좋습니다!
          </div>
        </div>
        
        <!-- 상담 신청 폼 -->
        <div class="consultation-section">
          <div class="consultation-title">📞 무료 상담 신청하기</div>
          <form id="consultationForm">
            <div class="form-group">
              <label class="form-label">이름</label>
              <input type="text" class="form-input" id="customerName" 
                     placeholder="홍길동" required>
            </div>
            <div class="form-group">
              <label class="form-label">전화번호</label>
              <input type="tel" class="form-input" id="customerPhone" 
                     placeholder="010-1234-5678" required>
            </div>
            <button type="submit" class="consultation-btn" id="submitBtn">
              📞 상담 신청하기
            </button>
          </form>
        </div>
        
        <!-- 공유 및 저장 -->
        <div class="action-section">
          <button class="action-btn save" onclick="saveResult()">
            📸 결과 이미지 저장하기
          </button>
          <button class="action-btn share" onclick="shareKakao()">
            📤 카카오톡 공유하기
          </button>
        </div>
        
        <!-- 다시 계산 -->
        <div class="recalculate-section">
          <a href="/" class="recalculate-btn">🔙 다시 계산하기</a>
        </div>
      </div>
      
      <script>
        let resultData = null;
        
        // 페이지 로드시 결과 데이터 표시
        window.addEventListener('load', function() {
          const savedResult = localStorage.getItem('solarResult');
          
          if (!savedResult) {
            alert('❌ 계산 결과가 없습니다. 다시 계산해주세요.');
            window.location.href = '/';
            return;
          }
          
          try {
            resultData = JSON.parse(savedResult);
            displayResults(resultData);
          } catch (error) {
            console.error('데이터 오류:', error);
            alert('❌ 결과 데이터에 오류가 있습니다. 다시 계산해주세요.');
            window.location.href = '/';
          }
        });
        
        // 결과 데이터 표시
        function displayResults(data) {
          // 연간 수익 표시
          document.getElementById('annualRevenue').textContent = 
            `${Math.round(data.annual_revenue / 10000)}만원`;
          
          // 연간 발전량 표시
          document.getElementById('annualGeneration').textContent = 
            data.annual_generation_kwh.toLocaleString();
          
          // 비교 차트 업데이트
          const farmingRevenue = data.farming_revenue;
          const solarRevenue = data.annual_revenue;
          const ratio = data.solar_vs_farming_ratio;
          
          // 차트 높이 계산 (최대 100px)
          const maxRevenue = Math.max(farmingRevenue, solarRevenue);
          const farmingHeight = (farmingRevenue / maxRevenue) * 100;
          const solarHeight = (solarRevenue / maxRevenue) * 100;
          
          document.getElementById('farmingBar').style.height = farmingHeight + 'px';
          document.getElementById('solarBar').style.height = solarHeight + 'px';
          
          document.getElementById('farmingValue').textContent = 
            `${Math.round(farmingRevenue / 10000)}만원`;
          document.getElementById('solarValue').textContent = 
            `${Math.round(solarRevenue / 10000)}만원`;
          
          document.getElementById('ratioText').textContent = ratio;
          
          // 애니메이션 효과
          setTimeout(() => {
            document.getElementById('farmingBar').style.height = farmingHeight + 'px';
            document.getElementById('solarBar').style.height = solarHeight + 'px';
          }, 500);
        }
        
        // 상담 신청 폼 제출
        document.getElementById('consultationForm').addEventListener('submit', async function(e) {
          e.preventDefault();
          
          const name = document.getElementById('customerName').value.trim();
          const phone = document.getElementById('customerPhone').value.trim();
          
          if (!name || !phone) {
            alert('이름과 전화번호를 모두 입력해주세요.');
            return;
          }
          
          // 전화번호 형식 검증
          const phoneRegex = /^[0-9-+\s()]+$/;
          if (!phoneRegex.test(phone)) {
            alert('올바른 전화번호를 입력해주세요.');
            return;
          }
          
          showLoading(true);
          
          try {
            const response = await fetch('/api/consultation', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({
                name: name,
                phone: phone,
                area_pyeong: resultData.area_pyeong,
                location: `위도: ${resultData.lat || 'N/A'}, 경도: ${resultData.lng || 'N/A'}`,
                annual_revenue: resultData.annual_revenue,
                timestamp: new Date().toISOString()
              })
            });
            
            const data = await response.json();
            
            if (data.success) {
              // 성공 메시지 표시
              showSuccessMessage();
              
              // 폼 비활성화
              document.getElementById('submitBtn').disabled = true;
              document.getElementById('submitBtn').textContent = '✅ 신청 완료';
              document.getElementById('customerName').disabled = true;
              document.getElementById('customerPhone').disabled = true;
            } else {
              alert('❌ 신청 중 오류가 발생했습니다. 다시 시도해주세요.');
            }
          } catch (error) {
            console.error('신청 오류:', error);
            alert('❌ 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
          }
          
          showLoading(false);
        });
        
        // 결과 이미지 저장
        async function saveResult() {
          try {
            // html2canvas 라이브러리 동적 로드
            if (!window.html2canvas) {
              const script = document.createElement('script');
              script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
              document.head.appendChild(script);
              
              await new Promise(resolve => {
                script.onload = resolve;
              });
            }
            
            showLoading(true);
            
            const element = document.getElementById('resultContainer');
            const canvas = await html2canvas(element, {
              backgroundColor: '#ffffff',
              scale: 2,
              useCORS: true
            });
            
            // 이미지 다운로드
            const link = document.createElement('a');
            link.download = `농지태양광_수익계산결과_${new Date().getTime()}.png`;
            link.href = canvas.toDataURL();
            link.click();
            
            showLoading(false);
            alert('📸 이미지가 저장되었습니다!');
            
          } catch (error) {
            console.error('저장 오류:', error);
            showLoading(false);
            alert('❌ 이미지 저장 중 오류가 발생했습니다.');
          }
        }
        
        // 카카오톡 공유
        function shareKakao() {
          const revenue = Math.round(resultData.annual_revenue / 10000);
          const area = resultData.area_pyeong;
          
          const shareData = {
            title: '🌾 우리 농지 태양광 수익 계산 결과',
            text: `${area}평 농지에서 연간 ${revenue}만원 수익 가능!\\n\\n태양광으로 새로운 수익을 만들어보세요.`,
            url: window.location.origin
          };
          
          if (navigator.share) {
            navigator.share(shareData).catch(console.error);
          } else {
            // 클립보드 복사
            const shareText = `${shareData.title}\\n${shareData.text}\\n${shareData.url}`;
            navigator.clipboard.writeText(shareText).then(() => {
              alert('📤 공유 내용이 클립보드에 복사되었습니다!\\n카카오톡에서 붙여넣기 하세요.');
            }).catch(() => {
              alert('📤 수동으로 공유해주세요:\\n\\n' + shareText);
            });
          }
        }
        
        // 성공 메시지 표시
        function showSuccessMessage() {
          const successMessage = document.getElementById('successMessage');
          successMessage.classList.add('show');
          
          setTimeout(() => {
            successMessage.classList.remove('show');
          }, 3000);
        }
        
        // 로딩 표시
        function showLoading(show) {
          document.getElementById('loading').style.display = show ? 'flex' : 'none';
        }
      </script>
      
      <!-- html2canvas 라이브러리 -->
      <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    </body>
    </html>
    """)

# 🌐 API 엔드포인트들
@app.route('/api/search-address')
def api_search_address():
    """주소 검색 API"""
    query = request.args.get('query', '')
    if not query:
        return jsonify({'success': False, 'error': '검색어를 입력해주세요.'})
    
    try:
        # Nominatim API 사용
        nominatim_url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{query} South Korea",
            'format': 'json',
            'limit': 1,
            'countrycodes': 'kr',
            'addressdetails': 1
        }
        
        headers = {'User-Agent': 'FarmlandSolar/1.0'}
        response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            return jsonify({
                'success': True,
                'location': {
                    'lat': float(result['lat']),
                    'lng': float(result['lon']),
                    'display_name': result.get('display_name', '')
                }
            })
        else:
            return jsonify({'success': False, 'error': '주소를 찾을 수 없습니다.'})
            
    except Exception as e:
        print(f"주소 검색 오류: {str(e)}")
        return jsonify({'success': False, 'error': '검색 중 오류가 발생했습니다.'})

@app.route('/api/simulate', methods=['POST'])
def api_simulate():
    """수익 시뮬레이션 API"""
    try:
        data = request.get_json()
        area_pyeong = data.get('area_pyeong')
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address', '')
        
        if not area_pyeong or not lat or not lng:
            return jsonify({
                'success': False,
                'error': '필수 데이터가 누락되었습니다.'
            })
        
        # 농지 태양광 계산
        result = calculate_farmland_solar(area_pyeong, lat, lng)
        
        # 위치 정보 추가
        result['lat'] = lat
        result['lng'] = lng
        result['address'] = address
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        print(f"시뮬레이션 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': '계산 중 오류가 발생했습니다.'
        })

@app.route('/api/consultation', methods=['POST'])
def api_consultation():
    """상담 신청 API"""
    try:
        data = request.get_json()
        
        # 상담 신청 데이터 저장 (실제 환경에서는 데이터베이스에 저장)
        consultation_data = {
            'name': data.get('name'),
            'phone': data.get('phone'),
            'area_pyeong': data.get('area_pyeong'),
            'location': data.get('location'),
            'annual_revenue': data.get('annual_revenue'),
            'timestamp': data.get('timestamp')
        }
        
        print(f"🌾 상담 신청 접수:")
        print(f"   이름: {consultation_data['name']}")
        print(f"   전화번호: {consultation_data['phone']}")
        print(f"   면적: {consultation_data['area_pyeong']}평")
        print(f"   위치: {consultation_data['location']}")
        print(f"   예상수익: {consultation_data['annual_revenue']:,}원")
        print(f"   신청시간: {consultation_data['timestamp']}")
        
        # 실제 환경에서는 여기에 다음 기능들 구현:
        # 1. 데이터베이스 저장
        # 2. 관리자 알림 (이메일, 슬랙 등)
        # 3. 고객 SMS 발송
        # 4. CRM 시스템 연동
        
        return jsonify({
            'success': True,
            'message': '상담 신청이 완료되었습니다.'
        })
        
    except Exception as e:
        print(f"상담 신청 오류: {str(e)}")
        return jsonify({
            'success': False,
            'error': '신청 처리 중 오류가 발생했습니다.'
        })

# 정적 파일 서빙
@app.route('/static/<path:filename>')
def static_files(filename):
    """정적 파일 서빙"""
    try:
        return send_from_directory('design/logo/Solaris', filename)
    except FileNotFoundError:
        return "File not found", 404

# 🚀 웹 서버 실행
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🌾 농지 태양광 모바일 전용 UI가 시작되었습니다!")
    print(f"🌍 포트: {port}")
    print(f"\n📱 타겟 사용자: 농지 소유자 (고령층)")
    print(f"🎯 유입 경로: 인스타그램/유튜브 광고")
    print(f"🎨 UI 특징: 간단하고 직관적인 모바일 우선 디자인")
    print(f"\n🔗 페이지 구성:")
    print(f"   Step 1 (/) : 면적 입력 + 위치 선택")
    print(f"   Step 2 (/result) : 수익 결과 + 상담 신청")
    print(f"\n💰 계산 기준:")
    print(f"   - SMP: 113.9원/kWh")
    print(f"   - REC: 70,000원/REC (가중치 1.5x)")
    print(f"   - 설치비: 2,000만원/kW")
    print(f"   - 최소면적: 20평")
    print(f"\n✅ 주요 기능:")
    print(f"   - 평 단위 입력 (자동 ㎡ 변환)")
    print(f"   - 지도 위치 선택 + 주소 검색")
    print(f"   - 농업 vs 태양광 수익 비교")
    print(f"   - 상담 신청 (이름 + 전화번호)")
    print(f"   - 결과 이미지 저장 + 카톡 공유")
    
    app.run(host='0.0.0.0', port=port, debug=False)