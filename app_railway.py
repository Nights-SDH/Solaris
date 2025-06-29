# 🌞 디바이스 감지 및 분리 라우팅 태양광 시스템 (수정된 버전)
import os
from flask import Flask, request, jsonify, render_template_string, send_file, send_from_directory, redirect, url_for
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

# 🔧 디바이스 감지 함수
def detect_device():
    """User-Agent 기반 디바이스 감지"""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    device_info = {
        'user_agent': user_agent,
        'is_mobile': False,
        'is_tablet': False,
        'is_desktop': True,
        'device_type': 'desktop',
        'os': 'unknown',
        'browser': 'unknown'
    }
    
    # 모바일 감지
    mobile_indicators = [
        'mobile', 'android', 'iphone', 'ipod', 'blackberry',
        'windows phone', 'opera mini', 'iemobile', 'webos'
    ]
    
    if any(indicator in user_agent for indicator in mobile_indicators):
        device_info['is_mobile'] = True
        device_info['is_desktop'] = False
        device_info['device_type'] = 'mobile'
    
    # 태블릿 감지 (iPad는 특별 처리)
    tablet_indicators = ['tablet', 'ipad']
    if any(indicator in user_agent for indicator in tablet_indicators):
        device_info['is_tablet'] = True
        device_info['is_mobile'] = False
        device_info['is_desktop'] = False
        device_info['device_type'] = 'tablet'
    
    # OS 감지
    if 'android' in user_agent:
        device_info['os'] = 'android'
    elif any(ios in user_agent for ios in ['iphone', 'ipad', 'ipod']):
        device_info['os'] = 'ios'
    elif 'windows' in user_agent:
        device_info['os'] = 'windows'
    elif 'mac' in user_agent:
        device_info['os'] = 'macos'
    elif 'linux' in user_agent:
        device_info['os'] = 'linux'
    
    # 브라우저 감지
    if 'chrome' in user_agent:
        device_info['browser'] = 'chrome'
    elif 'firefox' in user_agent:
        device_info['browser'] = 'firefox'
    elif 'safari' in user_agent and 'chrome' not in user_agent:
        device_info['browser'] = 'safari'
    elif 'edge' in user_agent:
        device_info['browser'] = 'edge'
    
    return device_info

# 🌞 태양광 계산 함수 (공통)
def calculate_farmland_solar(area_pyeong, lat, lon):
    """농지 태양광 수익 계산 (모바일/데스크톱 공통)"""
    try:
        if area_pyeong < 20:
            return {
                'installable': False,
                'message': '최소 20평 이상의 면적이 필요합니다.'
            }
        
        # 면적 변환
        area_sqm = area_pyeong * 3.3
        install_capacity_kw = area_pyeong * 0.14
        
        # 지역별 GHI 데이터
        if 33 <= lat <= 38 and 125 <= lon <= 130:
            annual_generation_per_kw = 1300
        else:
            annual_generation_per_kw = 1200
        
        annual_generation_kwh = install_capacity_kw * annual_generation_per_kw
        
        # 수익 계산
        smp_price = 128.39
        rec_price = 70000
        rec_weight = 1.2
        
        smp_revenue = annual_generation_kwh * smp_price
        rec_revenue = (annual_generation_kwh / 1000) * rec_weight * rec_price
        
        # 설치비용 및 회수기간
        install_cost_per_kw = 1800000
        total_install_cost = install_capacity_kw * install_cost_per_kw
        
        # 연간 운영비 상세 계산
        maintenance_cost = install_capacity_kw * 15000    # 유지보수비
        insurance_cost = total_install_cost * 0.003      # 보험료 0.3%
        management_cost = 500000                          # 기타 관리비
        total_om_cost = maintenance_cost + insurance_cost + management_cost
        
        total_annual_revenue = smp_revenue + rec_revenue - total_om_cost
        
        payback_years = total_install_cost / total_annual_revenue if total_annual_revenue > 0 else 999
        
        # 농업 수익 비교
        farming_revenue = area_pyeong * 3571
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
            'om_cost': round(total_om_cost),
            'install_cost': round(total_install_cost),
            'payback_years': round(payback_years, 1),
            'farming_revenue': round(farming_revenue),
            'solar_vs_farming_ratio': round(solar_vs_farming_ratio, 1),
            'message': '영농형 태양광 설치 가능합니다!'
        }
        
    except Exception as e:
        print(f"calculate_farmland_solar 오류: {str(e)}")
        return {
            'installable': False,
            'message': '계산 중 오류가 발생했습니다.'
        }

def calculate_desktop_solar(lat, lng, system_size, tilt=30, azimuth=180, smp_price=128.39, rec_price=70000):
    """데스크톱/태블릿용 고급 계산 (수정된 버전)"""
    try:
        print(f"🔧 calculate_desktop_solar 호출: lat={lat}, lng={lng}, size={system_size}, tilt={tilt}, azimuth={azimuth}")
        
        # 입력값 검증 및 기본값 설정
        if not lat or not lng:
            print("❌ 위치 정보가 없음")
            return {'success': False, 'error': '위치 정보가 필요합니다.'}
        
        # 기본값 설정 및 타입 변환
        try:
            system_size = float(system_size) if system_size else 30.0
            tilt = float(tilt) if tilt else 30.0
            azimuth = float(azimuth) if azimuth else 180.0
            smp_price = float(smp_price) if smp_price else 128.39
            rec_price = float(rec_price) if rec_price else 70000.0
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError) as e:
            print(f"❌ 타입 변환 오류: {e}")
            return {'success': False, 'error': '입력값 형식이 올바르지 않습니다.'}
        
        # 유효성 검사
        if system_size <= 0 or system_size > 10000:
            system_size = 30.0
        if tilt < 0 or tilt > 90:
            tilt = 30.0
        if azimuth < 0 or azimuth > 360:
            azimuth = 180.0
        
        print(f"📊 정규화된 파라미터: size={system_size}, tilt={tilt}, azimuth={azimuth}")
        
        # 기본 발전량 계산
        annual_generation_per_kw = 1300  # kWh/kW/년
        base_annual_generation = system_size * annual_generation_per_kw
        
        # 최적 각도 계산
        optimal_tilt = abs(lat) * 0.76 + 3.1
        optimal_azimuth = 180 if lat >= 0 else 0
        
        # 효율 계산
        tilt_efficiency = max(0.8, min(1.1, 1.0 - abs(tilt - optimal_tilt) * 0.008))
        
        azimuth_diff = min(abs(azimuth - optimal_azimuth), 360 - abs(azimuth - optimal_azimuth))
        azimuth_efficiency = max(0.7, min(1.0, 1.0 - azimuth_diff * 0.002))
        
        # 최종 발전량
        adjusted_generation = base_annual_generation * tilt_efficiency * azimuth_efficiency
        
        # 수익 계산
        smp_revenue = adjusted_generation * smp_price
        rec_revenue = (adjusted_generation / 1000) * 1.5 * rec_price
        om_cost = system_size * 12000
        
        annual_revenue = smp_revenue + rec_revenue - om_cost
        
        # 투자 회수
        install_cost = system_size * 2000000  # 2백만원/kWp로 수정
        payback_years = install_cost / annual_revenue if annual_revenue > 0 else 999
        
        result = {
            'success': True,
            'annual_generation': round(adjusted_generation),
            'annual_revenue': round(annual_revenue),
            'smp_revenue': round(smp_revenue),
            'rec_revenue': round(rec_revenue),
            'om_cost': round(om_cost),
            'install_cost': round(install_cost),
            'payback_years': round(payback_years, 1) if payback_years < 50 else 99.9,
            'optimal_tilt': round(optimal_tilt, 1),
            'optimal_azimuth': round(optimal_azimuth),
            'tilt_efficiency': round(tilt_efficiency * 100, 1),
            'azimuth_efficiency': round(azimuth_efficiency * 100, 1),
            'system_size': system_size,
            'location': f"{lat:.4f}, {lng:.4f}"
        }
        
        print(f"✅ 계산 완료: {result}")
        return result
        
    except Exception as e:
        print(f"❌ calculate_desktop_solar 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': f'계산 중 오류: {str(e)}'}

# 🎯 메인 라우팅 (자동 디바이스 감지)
@app.route('/')
def index():
    """자동 디바이스 감지 후 적절한 버전으로 라우팅"""
    device = detect_device()
    
    # URL 파라미터로 강제 지정 확인
    force_version = request.args.get('version')
    if force_version in ['mobile', 'desktop', 'tablet']:
        if force_version == 'mobile':
            return mobile_index()
        elif force_version == 'desktop':
            return desktop_index()
        elif force_version == 'tablet':
            return tablet_index()
    
    # 자동 감지에 따른 라우팅
    if device['is_mobile']:
        return mobile_index()
    elif device['is_tablet']:
        return tablet_index()
    else:
        return desktop_index()

# 📱 모바일 전용 라우트
@app.route('/mobile')
def mobile_route():
    return mobile_index()

@app.route('/mobile/result')
def mobile_result_route():
    return mobile_result_page()

# 🖥️ 데스크톱 전용 라우트
@app.route('/desktop')
def desktop_route():
    return desktop_index()

# 📟 태블릿 전용 라우트
@app.route('/tablet')
def tablet_route():
    return tablet_index()

# 🔄 결과 페이지 자동 라우팅
@app.route('/result')
def result_route():
    device = detect_device()
    
    if device['is_mobile']:
        return mobile_result_page()
    elif device['is_tablet']:
        return tablet_result_page()
    else:
        return desktop_result_page()

# 📱 모바일 UI 함수들
def mobile_index():
    """모바일 전용 메인 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>농지 태양광 수익 계산기 📱</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          color: #333;
        }
        
        .device-indicator {
          position: fixed;
          top: 5px;
          left: 5px;
          background: rgba(255,255,255,0.9);
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 10px;
          z-index: 9999;
          color: #666;
        }
        
        .version-switcher {
          position: fixed;
          top: 5px;
          right: 5px;
          z-index: 9999;
        }
        
        .version-btn {
          background: rgba(255,255,255,0.9);
          border: 1px solid #ddd;
          padding: 4px 8px;
          font-size: 10px;
          margin-left: 2px;
          border-radius: 3px;
          text-decoration: none;
          color: #666;
        }
        
        .container {
          max-width: 100%;
          margin: 0 auto;
          background: white;
          min-height: 100vh;
          padding-top: 25px;
        }
        
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
        
        .map-container {
          height: 250px;
          border-radius: 10px;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
          position: relative;
          margin-bottom: 20px;
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
        
        .area-unit {
          font-size: 18px;
          font-weight: 600;
          color: #2E8B57;
        }
        
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
        }
        
        .calculate-btn:disabled {
          background: #ccc;
          color: #999;
          cursor: not-allowed;
          box-shadow: none;
        }
        
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
      </style>
    </head>
    <body>
      <div class="device-indicator">📱 Mobile</div>
      
      <div class="version-switcher">
        <a href="/desktop" class="version-btn">🖥️ PC</a>
        <a href="/tablet" class="version-btn">📟 Tab</a>
      </div>
      
      <div class="loading" id="loading">
        <div class="spinner"></div>
        <div>🌾 수익 계산 중...</div>
      </div>
      
      <div class="container">
        <div class="header">
          <h1>🌾 내 농지 정보 입력하기</h1>
          <div class="subtitle">태양광으로 새로운 수익을 만들어보세요</div>
        </div>
        
        <div class="content">
          <div class="guide-text">
            <h2>📍 지도에서 위치를 지정하고</h2>
            <p>평 수를 입력해주세요<br><small>(예: 600평 입력)</small></p>
          </div>
          
          <div class="search-section">
            <div class="search-box">
              <input type="text" class="search-input" id="addressInput" 
                     placeholder="예: 논산시 벌곡면">
              <button class="search-btn" onclick="searchAddress()">🔍</button>
            </div>
          </div>
          
          <div class="location-info" id="locationInfo">
            📍 <span id="locationText">위치를 선택해주세요</span>
          </div>
          
          <div class="map-container">
            <button class="location-btn" onclick="getCurrentLocation()">📍</button>
            <div id="map" style="height: 100%; width: 100%;"></div>
          </div>
          
          <div class="area-section">
            <div class="area-label">🏗️ 내 땅 면적을 입력해주세요</div>
            <div class="area-input-container">
              <input type="number" class="area-input" id="areaInput" 
                     placeholder="600" min="1" max="10000">
              <span class="area-unit">평</span>
            </div>
          </div>
          
          <div class="warning" id="warningMessage">
            ⚠️ 최소 20평 이상 입력해주세요
          </div>
          
          <button class="calculate-btn" id="calculateBtn" onclick="calculateRevenue()" disabled>
            🔆 수익 확인하기
          </button>
        </div>
      </div>
      
      <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
      <script>
        const map = L.map('map', {
          zoomControl: false,
          attributionControl: false
        }).setView([36.5, 127.8], 7);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        L.control.zoom({ position: 'bottomleft' }).addTo(map);
        
        let currentMarker = null;
        let currentLocation = { lat: null, lng: null, address: '' };
        
        const addressInput = document.getElementById('addressInput');
        const areaInput = document.getElementById('areaInput');
        const warningMessage = document.getElementById('warningMessage');
        const calculateBtn = document.getElementById('calculateBtn');
        const locationInfo = document.getElementById('locationInfo');
        const locationText = document.getElementById('locationText');
        const loading = document.getElementById('loading');
        
        async function searchAddress() {
          const address = addressInput.value.trim();
          if (!address) {
            alert('주소를 입력해주세요.');
            return;
          }
          
          showLoading(true);
          
          try {
            const response = await fetch(`/api/search-address?query=${encodeURIComponent(address)}`);
            const data = await response.json();
            
            if (data.success && data.location) {
              const { lat, lng, display_name } = data.location;
              setMapLocation(lat, lng, display_name);
              addressInput.value = '';
            } else {
              alert('❌ 주소를 찾을 수 없습니다.');
            }
          } catch (error) {
            alert('❌ 검색 중 오류가 발생했습니다.');
          }
          
          showLoading(false);
        }
        
        function getCurrentLocation() {
          if (!navigator.geolocation) {
            alert('위치 서비스를 지원하지 않습니다.');
            return;
          }
          
          showLoading(true);
          
          navigator.geolocation.getCurrentPosition(
            function(position) {
              const lat = position.coords.latitude;
              const lng = position.coords.longitude;
              setMapLocation(lat, lng, '현재 위치');
              showLoading(false);
            },
            function(error) {
              alert('❌ 현재 위치를 가져올 수 없습니다.');
              showLoading(false);
            }
          );
        }
        
        function setMapLocation(lat, lng, address = '') {
          if (currentMarker) {
            map.removeLayer(currentMarker);
          }
          
          currentMarker = L.marker([lat, lng], {
            icon: L.divIcon({
              html: '🌾',
              iconSize: [30, 30],
              className: 'custom-div-icon'
            })
          }).addTo(map);
          
          map.setView([lat, lng], 15);
          
          currentLocation = { lat, lng, address };
          locationText.textContent = address || `위도: ${lat.toFixed(4)}, 경도: ${lng.toFixed(4)}`;
          locationInfo.classList.add('show');
          
          updateCalculateButton();
        }
        
        map.on('click', function(e) {
          setMapLocation(e.latlng.lat, e.latlng.lng, '클릭한 위치');
        });
        
        areaInput.addEventListener('input', function() {
          const area = parseFloat(this.value);
          
          if (area && area < 20) {
            warningMessage.classList.add('show');
          } else {
            warningMessage.classList.remove('show');
          }
          
          updateCalculateButton();
        });
        
        addressInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            searchAddress();
          }
        });
        
        function updateCalculateButton() {
          const area = parseFloat(areaInput.value);
          const hasLocation = currentLocation.lat && currentLocation.lng;
          
          calculateBtn.disabled = !(hasLocation && area && area >= 20);
        }
        
        async function calculateRevenue() {
          const area = parseFloat(areaInput.value);
          
          if (!currentLocation.lat || !currentLocation.lng) {
            alert('📍 먼저 위치를 선택해주세요.');
            return;
          }
          
          if (!area || area < 20) {
            alert('📐 20평 이상의 면적을 입력해주세요.');
            return;
          }
          
          showLoading(true);
          
          try {
            const response = await fetch('/api/simulate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                area_pyeong: area,
                lat: currentLocation.lat,
                lng: currentLocation.lng,
                address: currentLocation.address
              })
            });
            
            const data = await response.json();
            
            if (data.success && data.result.installable) {
              localStorage.setItem('solarResult', JSON.stringify(data.result));
              window.location.href = '/mobile/result';
            } else {
              alert('❌ ' + (data.result?.message || '계산 중 오류가 발생했습니다.'));
            }
          } catch (error) {
            alert('❌ 서버 오류가 발생했습니다.');
          }
          
          showLoading(false);
        }
        
        function showLoading(show) {
          loading.style.display = show ? 'flex' : 'none';
        }
        
        window.addEventListener('load', function() {
          localStorage.removeItem('solarResult');
          setTimeout(() => addressInput.focus(), 1000);
        });
      </script>
    </body>
    </html>
    """)

def mobile_result_page():
    """모바일 전용 결과 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>농지 태양광 수익 결과 📱</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          color: #333;
        }
        
        .device-indicator {
          position: fixed;
          top: 5px;
          left: 5px;
          background: rgba(255,255,255,0.9);
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 10px;
          z-index: 9999;
          color: #666;
        }
        
        .container {
          max-width: 100%;
          margin: 0 auto;
          background: white;
          min-height: 100vh;
          padding-top: 25px;
        }
        
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
        }
        
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
        
        .form-input {
          width: 100%;
          padding: 15px;
          border: 2px solid #e9ecef;
          border-radius: 8px;
          font-size: 16px;
          margin-bottom: 15px;
          outline: none;
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
        }
        
        .recalculate-btn {
          display: block;
          text-align: center;
          padding: 12px 30px;
          margin: 20px auto;
          background: transparent;
          color: #666;
          border: 2px solid #e9ecef;
          border-radius: 8px;
          text-decoration: none;
        }
        
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
        
        /* 개인정보 처리 동의 스타일 */
        .privacy-section {
          background: #f8f9fa;
          border: 1px solid #e9ecef;
          border-radius: 8px;
          padding: 15px;
          margin-bottom: 15px;
        }
        
        .privacy-notice {
          font-size: 14px;
          color: #495057;
          margin-bottom: 12px;
          text-align: center;
          line-height: 1.4;
        }
        
        .privacy-consent {
          display: flex;
          align-items: center;
          justify-content: center;
        }
        
        .consent-checkbox {
          display: flex;
          align-items: center;
          cursor: pointer;
          font-size: 14px;
          color: #495057;
          position: relative;
        }
        
        .consent-checkbox input[type="checkbox"] {
          width: 18px;
          height: 18px;
          margin-right: 8px;
          cursor: pointer;
        }
        
        .privacy-detail-btn {
          background: #007bff;
          color: white;
          border: none;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          margin-left: 8px;
          cursor: pointer;
        }
        
        .privacy-detail-btn:hover {
          background: #0056b3;
        }
        
        /* 팝업 스타일 */
        .privacy-popup {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.6);
          z-index: 10000;
          justify-content: center;
          align-items: center;
        }
        
        .privacy-popup-content {
          background: white;
          border-radius: 12px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
          max-width: 90%;
          width: 400px;
          max-height: 80vh;
          overflow-y: auto;
        }
        
        .privacy-popup-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 20px 0;
          border-bottom: 1px solid #e9ecef;
        }
        
        .privacy-popup-header h3 {
          margin: 0;
          color: #2E8B57;
          font-size: 18px;
        }
        
        .close-popup {
          background: none;
          border: none;
          font-size: 20px;
          cursor: pointer;
          color: #666;
          padding: 5px;
        }
        
        .close-popup:hover {
          color: #000;
        }
        
        .privacy-popup-body {
          padding: 20px;
        }
        
        .privacy-item {
          margin-bottom: 15px;
          padding: 12px;
          background: #f8f9fa;
          border-radius: 6px;
          border-left: 4px solid #2E8B57;
        }
        
        .privacy-item strong {
          color: #2E8B57;
          display: block;
          margin-bottom: 5px;
        }
        
        .privacy-popup-footer {
          padding: 0 20px 20px;
          display: flex;
          gap: 10px;
          justify-content: center;
        }
        
        .privacy-agree-btn {
          background: #2E8B57;
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
        }
        
        .privacy-close-btn {
          background: #6c757d;
          color: white;
          border: none;
          padding: 10px 20px;
          border-radius: 6px;
          cursor: pointer;
        }
        
        .consultation-btn:disabled {
          background: #ccc !important;
          cursor: not-allowed;
        }
      </style>
    </head>
    <body>
      <div class="device-indicator">📱 Mobile Result</div>
      
      <div class="container" id="resultContainer">
        <div class="success-header">
          <h1>🌞 설치 가능합니다!</h1>
          <div class="subtitle">농지 태양광으로 새로운 수익을 시작하세요</div>
        </div>
        
        <div class="revenue-summary">
          <div class="revenue-title">💰 예상 연간 수익</div>
          <div class="revenue-amount" id="annualRevenue">계산 중...</div>
          <div class="revenue-period">매년 받으실 수 있는 금액입니다</div>
        </div>
        
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
        
        <div class="consultation-section">
          <div class="consultation-title">📞 무료 상담 신청하기</div>
          <form id="consultationForm">
            <input type="text" class="form-input" id="customerName" placeholder="이름" required>
            <input type="tel" class="form-input" id="customerPhone" placeholder="전화번호" required>
            
            <!-- 개인정보 처리 동의 -->
            <div class="privacy-section">
              <div class="privacy-notice">
                📋 입력하신 정보는 영농형 태양광 설치 상담 목적으로 사용됩니다.
              </div>
              
              <div class="privacy-consent">
                <label class="consent-checkbox">
                  <input type="checkbox" id="privacyConsent" required>
                  <span class="checkmark"></span>
                  개인정보 수집 및 이용에 동의합니다
                  <button type="button" class="privacy-detail-btn" onclick="showPrivacyDetails()">보기</button>
                </label>
              </div>
            </div>
            
            <button type="submit" class="consultation-btn" id="submitConsultationBtn" disabled>📞 상담 신청하기</button>
          </form>
        </div>
        
        <!-- 개인정보 처리방침 팝업 -->
        <div class="privacy-popup" id="privacyPopup">
          <div class="privacy-popup-content">
            <div class="privacy-popup-header">
              <h3>📋 개인정보 수집·이용 동의 안내</h3>
              <button class="close-popup" onclick="closePrivacyPopup()">✕</button>
            </div>
            <div class="privacy-popup-body">
              <div class="privacy-item">
                <strong>1. 수집 항목:</strong> 이름, 전화번호
              </div>
              <div class="privacy-item">
                <strong>2. 수집 목적:</strong> 설치 상담 및 예상 수익 안내
              </div>
              <div class="privacy-item">
                <strong>3. 보관 기간:</strong> 상담 완료 후 1년, 고객 요청 시 즉시 삭제
              </div>
              <div class="privacy-item">
                <strong>4. 동의 거부 시:</strong> 상담 신청이 제한될 수 있습니다
              </div>
            </div>
            <div class="privacy-popup-footer">
              <button class="privacy-agree-btn" onclick="agreeAndClosePopup()">동의하고 닫기</button>
              <button class="privacy-close-btn" onclick="closePrivacyPopup()">닫기</button>
            </div>
          </div>
        </div>
        
        <a href="/mobile" class="recalculate-btn">🔙 다시 계산하기</a>
      </div>
      
      <script>
        let resultData = null;
        
        window.addEventListener('load', function() {
          const savedResult = localStorage.getItem('solarResult');
          if (!savedResult) {
            alert('❌ 계산 결과가 없습니다.');
            window.location.href = '/mobile';
            return;
          }
          
          resultData = JSON.parse(savedResult);
          displayResults(resultData);
        });
        
        function displayResults(data) {
          document.getElementById('annualRevenue').textContent = 
            `${Math.round(data.annual_revenue / 10000)}만원`;
          
          const farmingRevenue = data.farming_revenue;
          const solarRevenue = data.annual_revenue;
          const ratio = data.solar_vs_farming_ratio;
          
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
        }
        
        // 개인정보 동의 체크박스 이벤트
        document.getElementById('privacyConsent').addEventListener('change', function() {
          const submitBtn = document.getElementById('submitConsultationBtn');
          submitBtn.disabled = !this.checked;
        });
        
        // 개인정보 처리방침 팝업 함수들
        function showPrivacyDetails() {
          document.getElementById('privacyPopup').style.display = 'flex';
        }
        
        function closePrivacyPopup() {
          document.getElementById('privacyPopup').style.display = 'none';
        }
        
        function agreeAndClosePopup() {
          document.getElementById('privacyConsent').checked = true;
          document.getElementById('submitConsultationBtn').disabled = false;
          closePrivacyPopup();
        }
        
        // 팝업 외부 클릭 시 닫기
        document.getElementById('privacyPopup').addEventListener('click', function(e) {
          if (e.target === this) {
            closePrivacyPopup();
          }
        });
        
        document.getElementById('consultationForm').addEventListener('submit', async function(e) {
          e.preventDefault();
          
          const name = document.getElementById('customerName').value.trim();
          const phone = document.getElementById('customerPhone').value.trim();
          const privacyConsent = document.getElementById('privacyConsent').checked;
          
          if (!name || !phone) {
            alert('이름과 전화번호를 모두 입력해주세요.');
            return;
          }
          
          if (!privacyConsent) {
            alert('개인정보 수집 및 이용에 동의해주세요.');
            return;
          }
          
          // 전화번호 형식 검증
          const phoneRegex = /^[0-9-+\s()]+$/;
          if (!phoneRegex.test(phone)) {
            alert('올바른 전화번호를 입력해주세요.');
            return;
          }
          
          try {
            const response = await fetch('/api/consultation', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                name, 
                phone,
                privacy_consent: true,
                result_data: resultData
              })
            });
            
            const data = await response.json();
            
            if (data.success) {
              alert('✅ 신청이 완료되었습니다!\\n담당자가 빠르게 연락드리겠습니다.\\n\\n개인정보는 상담 목적으로만 사용되며, 상담 완료 후 1년간 보관됩니다.');
              this.reset();
              document.getElementById('submitConsultationBtn').disabled = true;
            } else {
              alert('❌ 신청 중 오류가 발생했습니다. 다시 시도해주세요.');
            }
          } catch (error) {
            console.error('상담 신청 오류:', error);
            alert('❌ 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
          }
        });
      </script>
    </body>
    </html>
    """)

# 🖥️ 데스크톱 UI 함수들
def desktop_index():
    """데스크톱 전용 메인 페이지 (수정된 버전)"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>Solaris Desktop - 태양광 발전량 예측 시스템 🖥️</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body, html { height: 100%; margin: 0; }
        .container-fluid { height: 100%; padding: 0; }
        .row { height: 100%; margin: 0; }
        #map { height: 100%; }
        .map-container { height: 100%; padding: 0; }
        
        .device-indicator {
          position: fixed;
          bottom: 10px;
          left: 10px;
          background: rgba(0,0,0,0.7);
          color: white;
          padding: 5px 10px;
          border-radius: 5px;
          font-size: 12px;
          z-index: 1000;
        }
        
        .version-switcher {
          position: fixed;
          top: 10px;
          right: 10px;
          z-index: 1000;
        }
        
        .version-btn {
          background: rgba(255,255,255,0.9);
          border: 1px solid #ddd;
          padding: 5px 10px;
          font-size: 12px;
          margin-left: 5px;
          border-radius: 4px;
          text-decoration: none;
          color: #666;
        }
        
        .control-panel {
          height: 100%;
          overflow-y: auto;
          padding: 20px;
          background-color: #f8f9fa;
          border-right: 2px solid #dee2e6;
        }
        
        .logo-container {
          display: flex;
          align-items: center;
          margin-bottom: 20px;
          padding: 15px;
          background: linear-gradient(135deg, #ffd700, #ff8c00);
          border-radius: 10px;
          box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .logo-container img {
          height: 40px;
          width: auto;
          margin-right: 12px;
        }
        
        .logo-text {
          color: #fff;
          font-weight: 700;
          font-size: 1.5rem;
          margin: 0;
        }
        
        .logo-subtitle {
          color: #fff;
          font-size: 0.8rem;
          opacity: 0.9;
          margin: 0;
        }
        
        .form-control:focus {
          border-color: #ffd700;
          box-shadow: 0 0 0 0.2rem rgba(255, 215, 0, 0.25);
        }
        
        .btn-primary {
          background: linear-gradient(135deg, #ffd700, #ff8c00);
          border-color: #ffd700;
          color: #333;
          font-weight: 600;
        }
        
        .btn-primary:hover {
          background: linear-gradient(135deg, #ffed4e, #ffb84d);
          border-color: #ffed4e;
          color: #333;
        }
        
        .results-container {
          display: none;
          margin-top: 20px;
          padding: 20px;
          background: white;
          border-radius: 10px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .loading {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0,0,0,0.5);
          z-index: 9999;
          justify-content: center;
          align-items: center;
          color: white;
          font-size: 18px;
        }
        
        .spinner {
          width: 60px;
          height: 60px;
          border: 6px solid #ffffff33;
          border-top: 6px solid #fff;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 20px;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        .alert-danger {
          background-color: #f8d7da;
          border-color: #f5c6cb;
          color: #721c24;
        }
      </style>
    </head>
    <body>
      <div class="device-indicator">🖥️ Desktop Version</div>
      
      <div class="version-switcher">
        <a href="/mobile" class="version-btn">📱 Mobile</a>
        <a href="/tablet" class="version-btn">📟 Tablet</a>
      </div>
      
      <div class="loading" id="loading">
        <div style="text-align: center;">
          <div class="spinner"></div>
          <div>데이터 분석 중...</div>
        </div>
      </div>
      
      <div class="container-fluid">
        <div class="row">
          <div class="col-lg-3 col-md-4 control-panel">
            <div class="logo-container">
              <img src="/static/png" alt="Solaris Logo" onerror="this.style.display='none'">
              <div>
                <h2 class="logo-text">Solaris</h2>
                <p class="logo-subtitle">태양광 발전량 예측 시스템</p>
              </div>
            </div>
            
            <div class="mb-4 p-3 bg-primary-subtle rounded">
              <h5 class="mb-3">📍 위치 검색</h5>
              <div class="mb-3">
                <label for="addressInput" class="form-label">주소 입력</label>
                <div class="input-group">
                  <input type="text" class="form-control" id="addressInput" 
                         placeholder="예: 서울시 강남구 테헤란로">
                  <button class="btn btn-primary" type="button" onclick="searchAddress()">🔍 검색</button>
                </div>
              </div>
            </div>
            
            <div class="mb-3">
              <label for="systemSizeInput" class="form-label">⚡ 시스템 용량 (kWp)</label>
              <div class="input-group">
                <input type="number" class="form-control" id="systemSizeInput" 
                       min="0.1" max="1000" value="30" step="0.1">
                <span class="input-group-text">kWp</span>
              </div>
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
              <input type="number" class="form-control" id="smpPriceInput" 
                     min="50" max="500" value="128.39" step="0.1">
            </div>
            
            <div class="mb-3">
              <label for="recPriceInput" class="form-label">🌿 REC 가격 (원/REC)</label>
              <input type="number" class="form-control" id="recPriceInput" 
                     min="0" max="200000" value="70000" step="1000">
            </div>
            
            <div class="alert alert-info" id="instructionAlert">
              📍 <strong>위치 설정 방법:</strong><br>
              1️⃣ 위의 주소 검색 기능 사용<br>
              2️⃣ 지도에서 직접 클릭<br>
              <small class="text-muted">위치 설정 후 해당 지점의 태양광 발전량을 자동 계산합니다.</small>
            </div>
            
            <div class="alert alert-danger" id="errorAlert" style="display: none;">
              <strong>⚠️ 오류:</strong> <span id="errorMessage"></span>
            </div>
            
            <div class="results-container" id="resultsContainer">
              <h4>📊 분석 결과</h4>
              
              <div class="mb-2">
                <strong>📍 위치:</strong> <span id="locationText">-</span>
              </div>
              <div class="mb-2">
                <strong>⚡ 연간 발전량:</strong> <span id="energyText">-</span> kWh/년
              </div>
              <div class="mb-2">
                <strong>💰 연간 수익:</strong> <span id="revenueText">-</span>원/년
              </div>
              <div class="mb-2">
                <strong>⏰ 투자 회수기간:</strong> <span id="paybackText">-</span>년
              </div>
              <div class="mb-2">
                <strong>🎯 경사각 효율:</strong> <span id="tiltEffText">-</span>%
              </div>
              <div class="mb-2">
                <strong>🧭 방위각 효율:</strong> <span id="azimuthEffText">-</span>%
              </div>
              
              <div class="d-grid gap-2 mt-3">
                <button class="btn btn-success" onclick="optimizeAngles()">🎯 최적 각도 적용</button>
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
        const map = L.map('map').setView([36.5, 127.8], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        let currentMarker = null;
        let currentLatLng = null;
        let optimalTilt = 30;
        let optimalAzimuth = 180;
        
        const addressInput = document.getElementById('addressInput');
        const systemSizeInput = document.getElementById('systemSizeInput');
        const tiltSlider = document.getElementById('tiltSlider');
        const tiltValue = document.getElementById('tiltValue');
        const azimuthSlider = document.getElementById('azimuthSlider');
        const azimuthValue = document.getElementById('azimuthValue');
        const smpPriceInput = document.getElementById('smpPriceInput');
        const recPriceInput = document.getElementById('recPriceInput');
        const loading = document.getElementById('loading');
        const resultsContainer = document.getElementById('resultsContainer');
        const errorAlert = document.getElementById('errorAlert');
        const errorMessage = document.getElementById('errorMessage');
        
        function showError(message) {
          errorMessage.textContent = message;
          errorAlert.style.display = 'block';
          setTimeout(() => {
            errorAlert.style.display = 'none';
          }, 5000);
        }
        
        async function searchAddress() {
          const address = addressInput.value.trim();
          if (!address) {
            showError('주소를 입력해주세요.');
            return;
          }
          
          showLoading(true);
          
          try {
            const response = await fetch(`/api/search-address?query=${encodeURIComponent(address)}`);
            const data = await response.json();
            
            if (data.success && data.location) {
              const { lat, lng, display_name } = data.location;
              setMapLocation(lat, lng, display_name);
              addressInput.value = '';
            } else {
              showError('주소를 찾을 수 없습니다.');
            }
          } catch (error) {
            console.error('주소 검색 오류:', error);
            showError('검색 중 오류가 발생했습니다.');
          }
          
          showLoading(false);
        }
        
        function setMapLocation(lat, lng, address = '') {
          console.log(`🗺️ 위치 설정: ${lat}, ${lng}, ${address}`);
          
          if (currentMarker) {
            map.removeLayer(currentMarker);
          }
          
          currentMarker = L.marker([lat, lng]).addTo(map);
          currentLatLng = { lat, lng, address };
          map.setView([lat, lng], 12);
          
          // 자동으로 계산 실행
          updateResults();
        }
        
        map.on('click', function(e) {
          setMapLocation(e.latlng.lat, e.latlng.lng, '클릭한 위치');
        });
        
        tiltSlider.addEventListener('input', function() {
          tiltValue.textContent = this.value;
          if (currentLatLng) updateResults();
        });
        
        azimuthSlider.addEventListener('input', function() {
          azimuthValue.textContent = this.value;
          if (currentLatLng) updateResults();
        });
        
        [systemSizeInput, smpPriceInput, recPriceInput].forEach(input => {
          input.addEventListener('change', () => {
            if (currentLatLng) updateResults();
          });
        });
        
        addressInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            searchAddress();
          }
        });
        
        async function updateResults() {
          if (!currentLatLng) {
            console.log('❌ 위치 정보가 없어 계산을 건너뜁니다.');
            return;
          }
          
          console.log('🔄 결과 업데이트 시작...');
          showLoading(true);
          
          const params = {
            lat: currentLatLng.lat,
            lng: currentLatLng.lng,
            system_size: parseFloat(systemSizeInput.value) || 30,
            tilt: parseFloat(tiltSlider.value) || 30,
            azimuth: parseFloat(azimuthSlider.value) || 180,
            smp_price: parseFloat(smpPriceInput.value) || 128.39,
            rec_price: parseFloat(recPriceInput.value) || 70000
          };
          
          console.log('📊 계산 파라미터:', params);
          
          try {
            const response = await fetch('/api/desktop-calculate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(params)
            });
            
            console.log('📡 서버 응답 상태:', response.status);
            const data = await response.json();
            console.log('📥 서버 응답 데이터:', data);
            
            if (data.success && data.annual_generation !== undefined) {
              displayResults(data);
              optimalTilt = data.optimal_tilt || 30;
              optimalAzimuth = data.optimal_azimuth || 180;
              console.log('✅ 계산 성공');
            } else {
              console.error('❌ 계산 실패:', data.error || '알 수 없는 오류');
              showError(data.error || '계산 중 오류가 발생했습니다.');
            }
          } catch (error) {
            console.error('❌ 네트워크 오류:', error);
            showError('서버와의 통신 중 오류가 발생했습니다.');
          }
          
          showLoading(false);
        }
        
        function displayResults(result) {
          console.log('🖼️ 결과 표시:', result);
          
          // 안전한 값 표시를 위한 헬퍼 함수
          const safeValue = (value, fallback = '-') => {
            return (value !== undefined && value !== null) ? value : fallback;
          };
          
          const safeNumber = (value, fallback = 0) => {
            const num = parseFloat(value);
            return isNaN(num) ? fallback : num;
          };
          
          document.getElementById('locationText').textContent = 
            currentLatLng.address || `${currentLatLng.lat.toFixed(4)}, ${currentLatLng.lng.toFixed(4)}`;
          
          document.getElementById('energyText').textContent = 
            safeNumber(result.annual_generation).toLocaleString();
          
          document.getElementById('revenueText').textContent = 
            safeNumber(result.annual_revenue).toLocaleString();
          
          document.getElementById('paybackText').textContent = 
            safeValue(result.payback_years);
          
          document.getElementById('tiltEffText').textContent = 
            safeValue(result.tilt_efficiency);
          
          document.getElementById('azimuthEffText').textContent = 
            safeValue(result.azimuth_efficiency);
          
          resultsContainer.style.display = 'block';
          console.log('✅ 결과 표시 완료');
        }
        
        function optimizeAngles() {
          console.log(`🎯 최적 각도 적용: 경사각=${optimalTilt}°, 방위각=${optimalAzimuth}°`);
          
          tiltSlider.value = optimalTilt;
          tiltValue.textContent = optimalTilt;
          azimuthSlider.value = optimalAzimuth;
          azimuthValue.textContent = optimalAzimuth;
          
          updateResults();
          alert(`🎯 최적 각도가 적용되었습니다!\\n경사각: ${optimalTilt}°, 방위각: ${optimalAzimuth}°`);
        }
        
        function showLoading(show) {
          loading.style.display = show ? 'flex' : 'none';
        }
        
        // 페이지 로드 시 초기화
        window.addEventListener('load', function() {
          console.log('🖥️ Desktop version loaded');
          
          // 기본값 확인
          console.log('📊 기본 설정값:');
          console.log(`   시스템 용량: ${systemSizeInput.value}kWp`);
          console.log(`   경사각: ${tiltSlider.value}°`);
          console.log(`   방위각: ${azimuthSlider.value}°`);
          console.log(`   SMP 가격: ${smpPriceInput.value}원/kWh`);
          console.log(`   REC 가격: ${recPriceInput.value}원/REC`);
        });
      </script>
    </body>
    </html>
    """)

def desktop_result_page():
    """데스크톱 전용 결과 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>Solaris Desktop - 분석 결과 🖥️</title>
      <style>
        body { 
          font-family: Arial, sans-serif; 
          padding: 40px;
          background: #f5f5f5;
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          background: white;
          padding: 40px;
          border-radius: 12px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .device-indicator {
          position: fixed;
          bottom: 20px;
          left: 20px;
          background: rgba(0,0,0,0.8);
          color: white;
          padding: 8px 15px;
          border-radius: 6px;
          font-size: 14px;
        }
        h1 { color: #2E8B57; text-align: center; margin-bottom: 30px; }
        .results-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 30px;
          margin-bottom: 30px;
        }
        .result-card {
          padding: 20px;
          border: 2px solid #e9ecef;
          border-radius: 10px;
          text-align: center;
        }
        .result-value {
          font-size: 28px;
          font-weight: bold;
          color: #2E8B57;
          margin: 10px 0;
        }
        .back-btn {
          display: block;
          width: 200px;
          margin: 20px auto;
          padding: 12px;
          background: #007bff;
          color: white;
          text-decoration: none;
          text-align: center;
          border-radius: 6px;
        }
      </style>
    </head>
    <body>
      <div class="device-indicator">🖥️ Desktop Result</div>
      
      <div class="container">
        <h1>🌞 태양광 발전량 분석 결과</h1>
        
        <div class="results-grid">
          <div class="result-card">
            <h3>💰 연간 수익</h3>
            <div class="result-value" id="annualRevenue">8,500만원</div>
            <p>예상 연간 수익 금액</p>
          </div>
          
          <div class="result-card">
            <h3>⚡ 연간 발전량</h3>
            <div class="result-value" id="annualGeneration">45,000kWh</div>
            <p>연간 전력 생산량</p>
          </div>
          
          <div class="result-card">
            <h3>⏰ 투자 회수기간</h3>
            <div class="result-value" id="paybackPeriod">7.2년</div>
            <p>초기 투자 회수 예상 기간</p>
          </div>
          
          <div class="result-card">
            <h3>📊 설치 용량</h3>
            <div class="result-value" id="installCapacity">30kWp</div>
            <p>권장 시스템 용량</p>
          </div>
        </div>
        
        <a href="/desktop" class="back-btn">🔙 다시 계산하기</a>
      </div>
    </body>
    </html>
    """)

# 📟 태블릿 UI 함수들
def tablet_index():
    """태블릿 전용 메인 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>Solaris Tablet - 태양광 시스템 📟</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
        }
        
        .device-indicator {
          position: fixed;
          top: 10px;
          left: 10px;
          background: rgba(255,255,255,0.9);
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 12px;
          z-index: 9999;
          color: #666;
        }
        
        .version-switcher {
          position: fixed;
          top: 10px;
          right: 10px;
          z-index: 9999;
        }
        
        .version-btn {
          background: rgba(255,255,255,0.9);
          border: 1px solid #ddd;
          padding: 6px 12px;
          font-size: 12px;
          margin-left: 5px;
          border-radius: 4px;
          text-decoration: none;
          color: #666;
        }
        
        .container {
          max-width: 1024px;
          margin: 0 auto;
          background: white;
          min-height: 100vh;
          padding-top: 40px;
          display: grid;
          grid-template-columns: 400px 1fr;
          gap: 0;
        }
        
        .control-panel {
          padding: 30px 25px;
          background: #f8f9fa;
          overflow-y: auto;
          max-height: 100vh;
        }
        
        .map-section {
          position: relative;
        }
        
        .header {
          background: linear-gradient(135deg, #2E8B57, #32CD32);
          color: white;
          text-align: center;
          padding: 20px;
          margin-bottom: 25px;
          border-radius: 10px;
        }
        
        .header h1 {
          font-size: 22px;
          font-weight: 700;
          margin-bottom: 5px;
        }
        
        .input-group {
          margin-bottom: 20px;
        }
        
        .input-label {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 8px;
          color: #333;
          display: block;
        }
        
        .input-field {
          width: 100%;
          padding: 12px 15px;
          border: 2px solid #e9ecef;
          border-radius: 8px;
          font-size: 16px;
          outline: none;
        }
        
        .input-field:focus {
          border-color: #2E8B57;
          box-shadow: 0 0 0 3px rgba(46, 139, 87, 0.1);
        }
        
        .search-btn {
          width: 100%;
          padding: 12px;
          background: #2E8B57;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          cursor: pointer;
          margin-top: 8px;
        }
        
        .map-container {
          height: 100vh;
          position: relative;
        }
        
        #map {
          height: 100%;
          width: 100%;
        }
        
        .location-btn {
          position: absolute;
          top: 15px;
          right: 15px;
          z-index: 1000;
          background: white;
          border: none;
          padding: 10px;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.2);
          cursor: pointer;
          font-size: 20px;
        }
        
        .calculate-btn {
          width: 100%;
          padding: 16px;
          background: linear-gradient(135deg, #FFD700, #FFA500);
          color: #333;
          border: none;
          border-radius: 10px;
          font-size: 18px;
          font-weight: 700;
          cursor: pointer;
          margin-top: 20px;
        }
        
        .calculate-btn:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        
        .results-panel {
          background: white;
          padding: 20px;
          margin-top: 20px;
          border-radius: 10px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          display: none;
        }
        
        .result-item {
          display: flex;
          justify-content: space-between;
          padding: 10px 0;
          border-bottom: 1px solid #eee;
        }
        
        .result-label {
          font-weight: 600;
          color: #666;
        }
        
        .result-value {
          font-weight: 700;
          color: #2E8B57;
        }
        
        @media (max-width: 768px) {
          .container {
            grid-template-columns: 1fr;
            grid-template-rows: auto 1fr;
          }
          .map-container {
            height: 60vh;
          }
        }
      </style>
    </head>
    <body>
      <div class="device-indicator">📟 Tablet Version</div>
      
      <div class="version-switcher">
        <a href="/mobile" class="version-btn">📱 Mobile</a>
        <a href="/desktop" class="version-btn">🖥️ Desktop</a>
      </div>
      
      <div class="container">
        <div class="control-panel">
          <div class="header">
            <h1>📟 Solaris Tablet</h1>
            <div class="subtitle">태블릿 최적화 버전</div>
          </div>
          
          <div class="input-group">
            <label class="input-label">📍 주소 검색</label>
            <input type="text" class="input-field" id="tabletAddressInput" placeholder="주소를 입력하세요">
            <button class="search-btn" onclick="tabletSearchAddress()">🔍 검색</button>
          </div>
          
          <div class="input-group">
            <label class="input-label">🏗️ 시스템 용량 (kWp)</label>
            <input type="number" class="input-field" id="tabletSystemSize" value="30" min="1" max="1000">
          </div>
          
          <div class="input-group">
            <label class="input-label">📐 경사각: <span id="tabletTiltValue">30</span>°</label>
            <input type="range" class="input-field" id="tabletTiltSlider" min="0" max="90" value="30" 
                   style="height: 8px; background: #ddd;">
          </div>
          
          <div class="input-group">
            <label class="input-label">🧭 방위각: <span id="tabletAzimuthValue">180</span>°</label>
            <input type="range" class="input-field" id="tabletAzimuthSlider" min="0" max="360" value="180"
                   style="height: 8px; background: #ddd;">
          </div>
          
          <button class="calculate-btn" id="tabletCalculateBtn" onclick="tabletCalculate()" disabled>
            🔆 발전량 계산하기
          </button>
          
          <div class="results-panel" id="tabletResults">
            <h4 style="margin-bottom: 15px; color: #2E8B57;">📊 계산 결과</h4>
            
            <div class="result-item">
              <span class="result-label">📍 위치</span>
              <span class="result-value" id="tabletLocation">-</span>
            </div>
            
            <div class="result-item">
              <span class="result-label">⚡ 연간 발전량</span>
              <span class="result-value" id="tabletGeneration">-</span>
            </div>
            
            <div class="result-item">
              <span class="result-label">💰 연간 수익</span>
              <span class="result-value" id="tabletRevenue">-</span>
            </div>
            
            <div class="result-item">
              <span class="result-label">⏰ 회수기간</span>
              <span class="result-value" id="tabletPayback">-</span>
            </div>
          </div>
        </div>
        
        <div class="map-section">
          <div class="map-container">
            <button class="location-btn" onclick="tabletGetLocation()">📍</button>
            <div id="map"></div>
          </div>
        </div>
      </div>
      
      <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
      <script>
        const tabletMap = L.map('map').setView([36.5, 127.8], 7);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(tabletMap);
        
        let tabletMarker = null;
        let tabletCurrentLocation = null;
        
        const tabletAddressInput = document.getElementById('tabletAddressInput');
        const tabletSystemSize = document.getElementById('tabletSystemSize');
        const tabletTiltSlider = document.getElementById('tabletTiltSlider');
        const tabletTiltValue = document.getElementById('tabletTiltValue');
        const tabletAzimuthSlider = document.getElementById('tabletAzimuthSlider');
        const tabletAzimuthValue = document.getElementById('tabletAzimuthValue');
        const tabletCalculateBtn = document.getElementById('tabletCalculateBtn');
        const tabletResults = document.getElementById('tabletResults');
        
        tabletTiltSlider.addEventListener('input', function() {
          tabletTiltValue.textContent = this.value;
        });
        
        tabletAzimuthSlider.addEventListener('input', function() {
          tabletAzimuthValue.textContent = this.value;
        });
        
        async function tabletSearchAddress() {
          const address = tabletAddressInput.value.trim();
          if (!address) {
            alert('주소를 입력해주세요.');
            return;
          }
          
          try {
            const response = await fetch(`/api/search-address?query=${encodeURIComponent(address)}`);
            const data = await response.json();
            
            if (data.success && data.location) {
              const { lat, lng, display_name } = data.location;
              tabletSetLocation(lat, lng, display_name);
              tabletAddressInput.value = '';
            } else {
              alert('❌ 주소를 찾을 수 없습니다.');
            }
          } catch (error) {
            alert('❌ 검색 중 오류가 발생했습니다.');
          }
        }
        
        function tabletGetLocation() {
          if (!navigator.geolocation) {
            alert('위치 서비스를 지원하지 않습니다.');
            return;
          }
          
          navigator.geolocation.getCurrentPosition(
            function(position) {
              const lat = position.coords.latitude;
              const lng = position.coords.longitude;
              tabletSetLocation(lat, lng, '현재 위치');
            },
            function(error) {
              alert('❌ 현재 위치를 가져올 수 없습니다.');
            }
          );
        }
        
        function tabletSetLocation(lat, lng, address = '') {
          if (tabletMarker) {
            tabletMap.removeLayer(tabletMarker);
          }
          
          tabletMarker = L.marker([lat, lng]).addTo(tabletMap);
          tabletMap.setView([lat, lng], 12);
          
          tabletCurrentLocation = { lat, lng, address };
          tabletCalculateBtn.disabled = false;
        }
        
        tabletMap.on('click', function(e) {
          tabletSetLocation(e.latlng.lat, e.latlng.lng, '클릭한 위치');
        });
        
        tabletAddressInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') {
            tabletSearchAddress();
          }
        });
        
        async function tabletCalculate() {
          if (!tabletCurrentLocation) {
            alert('📍 먼저 위치를 선택해주세요.');
            return;
          }
          
          const systemSize = parseFloat(tabletSystemSize.value);
          if (!systemSize || systemSize <= 0) {
            alert('⚡ 올바른 시스템 용량을 입력해주세요.');
            return;
          }
          
          try {
            const response = await fetch('/api/desktop-calculate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                lat: tabletCurrentLocation.lat,
                lng: tabletCurrentLocation.lng,
                system_size: systemSize,
                tilt: parseFloat(tabletTiltSlider.value),
                azimuth: parseFloat(tabletAzimuthSlider.value),
                smp_price: 128.39,
                rec_price: 70000
              })
            });
            
            const data = await response.json();
            
            if (data.success) {
              tabletDisplayResults(data);
            } else {
              alert('❌ 계산 중 오류가 발생했습니다.');
            }
          } catch (error) {
            alert('❌ 서버 오류가 발생했습니다.');
          }
        }
        
        function tabletDisplayResults(result) {
          document.getElementById('tabletLocation').textContent = 
            tabletCurrentLocation.address || `${tabletCurrentLocation.lat.toFixed(3)}, ${tabletCurrentLocation.lng.toFixed(3)}`;
          document.getElementById('tabletGeneration').textContent = 
            `${result.annual_generation?.toLocaleString() || '-'} kWh`;
          document.getElementById('tabletRevenue').textContent = 
            `${result.annual_revenue?.toLocaleString() || '-'} 원`;
          document.getElementById('tabletPayback').textContent = 
            `${result.payback_years || '-'} 년`;
          
          tabletResults.style.display = 'block';
        }
        
        console.log('📟 Tablet version loaded');
      </script>
    </body>
    </html>
    """)

def tablet_result_page():
    """태블릿 전용 결과 페이지"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="utf-8">
      <title>Solaris Tablet - 결과 📟</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          margin: 0;
          padding: 20px;
        }
        .device-indicator {
          position: fixed;
          top: 10px;
          left: 10px;
          background: rgba(255,255,255,0.9);
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 12px;
          z-index: 9999;
        }
        .container {
          max-width: 800px;
          margin: 0 auto;
          background: white;
          padding: 30px;
          border-radius: 15px;
          box-shadow: 0 6px 25px rgba(0,0,0,0.15);
        }
        h1 {
          text-align: center;
          color: #2E8B57;
          margin-bottom: 30px;
          font-size: 28px;
        }
        .results-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          margin-bottom: 30px;
        }
        .result-card {
          background: #f8f9fa;
          padding: 25px;
          border-radius: 12px;
          text-align: center;
          border-left: 4px solid #2E8B57;
        }
        .result-title {
          font-size: 18px;
          color: #666;
          margin-bottom: 10px;
        }
        .result-value {
          font-size: 24px;
          font-weight: bold;
          color: #2E8B57;
        }
        .back-btn {
          display: block;
          width: 250px;
          margin: 20px auto;
          padding: 15px;
          background: linear-gradient(135deg, #2E8B57, #32CD32);
          color: white;
          text-decoration: none;
          text-align: center;
          border-radius: 10px;
          font-size: 16px;
          font-weight: 600;
        }
      </style>
    </head>
    <body>
      <div class="device-indicator">📟 Tablet Result</div>
      
      <div class="container">
        <h1>🌞 태양광 시뮬레이션 결과</h1>
        
        <div class="results-grid">
          <div class="result-card">
            <div class="result-title">💰 연간 예상 수익</div>
            <div class="result-value">6,800만원</div>
          </div>
          
          <div class="result-card">
            <div class="result-title">⚡ 연간 발전량</div>
            <div class="result-value">39,000kWh</div>
          </div>
          
          <div class="result-card">
            <div class="result-title">⏰ 투자 회수기간</div>
            <div class="result-value">8.5년</div>
          </div>
          
          <div class="result-card">
            <div class="result-title">🎯 투자 수익률</div>
            <div class="result-value">185%</div>
          </div>
        </div>
        
        <a href="/tablet" class="back-btn">🔙 다시 계산하기</a>
      </div>
    </body>
    </html>
    """)

# 🌐 API 엔드포인트들
@app.route('/api/device-info')
def api_device_info():
    """디바이스 정보 API"""
    device = detect_device()
    return jsonify({
        'success': True,
        'device': device,
        'recommended_version': device['device_type']
    })

@app.route('/api/search-address')
def api_search_address():
    """주소 검색 API (공통)"""
    query = request.args.get('query', '')
    if not query:
        return jsonify({'success': False, 'error': '검색어를 입력해주세요.'})
    
    try:
        nominatim_url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{query} South Korea",
            'format': 'json',
            'limit': 1,
            'countrycodes': 'kr',
            'addressdetails': 1
        }
        
        headers = {'User-Agent': 'SolarSystem/1.0'}
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
    """모바일용 수익 시뮬레이션 API"""
    try:
        data = request.get_json()
        area_pyeong = data.get('area_pyeong')
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address', '')
        
        if not area_pyeong or not lat or not lng:
            return jsonify({'success': False, 'error': '필수 데이터가 누락되었습니다.'})
        
        result = calculate_farmland_solar(area_pyeong, lat, lng)
        result['lat'] = lat
        result['lng'] = lng
        result['address'] = address
        
        return jsonify({'success': True, 'result': result})
        
    except Exception as e:
        print(f"모바일 시뮬레이션 오류: {str(e)}")
        return jsonify({'success': False, 'error': '계산 중 오류가 발생했습니다.'})

@app.route('/api/desktop-calculate', methods=['POST'])
def api_desktop_calculate():
    """데스크톱/태블릿용 고급 계산 API (수정된 버전)"""
    try:
        data = request.get_json()
        print(f"🔧 API 호출 받음: {data}")
        
        lat = data.get('lat')
        lng = data.get('lng')
        system_size = data.get('system_size', 30)
        tilt = data.get('tilt', 30)
        azimuth = data.get('azimuth', 180)
        smp_price = data.get('smp_price', 128.39)
        rec_price = data.get('rec_price', 70000)
        
        if not lat or not lng:
            print("❌ 위치 정보 누락")
            return jsonify({'success': False, 'error': '위치 정보가 필요합니다.'})
        
        print(f"📍 계산 요청: lat={lat}, lng={lng}, size={system_size}")
        
        result = calculate_desktop_solar(lat, lng, system_size, tilt, azimuth, smp_price, rec_price)
        
        print(f"📊 계산 결과: {result}")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ API 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'서버 오류: {str(e)}'})

@app.route('/api/consultation', methods=['POST'])
def api_consultation():
    """상담 신청 API (개인정보 처리 동의 포함)"""
    try:
        data = request.get_json()
        device = detect_device()
        
        # 개인정보 처리 동의 확인
        privacy_consent = data.get('privacy_consent', False)
        if not privacy_consent:
            return jsonify({
                'success': False, 
                'error': '개인정보 수집 및 이용에 동의해주세요.'
            })
        
        consultation_data = {
            'name': data.get('name'),
            'phone': data.get('phone'),
            'privacy_consent': privacy_consent,
            'device_type': device['device_type'],
            'os': device['os'],
            'browser': device['browser'],
            'user_agent': device['user_agent'],
            'result_data': data.get('result_data'),  # 계산 결과 데이터
            'ip_address': request.remote_addr,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'consent_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"\n📞 상담 신청 접수 ({device['device_type']}):")
        print(f"   이름: {consultation_data['name']}")
        print(f"   전화번호: {consultation_data['phone']}")
        print(f"   개인정보 동의: {consultation_data['privacy_consent']}")
        print(f"   디바이스: {consultation_data['device_type']} ({consultation_data['os']}/{consultation_data['browser']})")
        print(f"   IP 주소: {consultation_data['ip_address']}")
        print(f"   신청시간: {consultation_data['timestamp']}")
        print(f"   동의시간: {consultation_data['consent_timestamp']}")
        
        # 결과 데이터가 있는 경우 추가 로깅
        if consultation_data['result_data']:
            result = consultation_data['result_data']
            print(f"   📊 계산 결과:")
            print(f"      - 면적: {result.get('area_pyeong', 'N/A')}평")
            print(f"      - 예상 연간 수익: {result.get('annual_revenue', 'N/A'):,}원")
            print(f"      - 설치 용량: {result.get('install_capacity_kw', 'N/A')}kW")
        
        return jsonify({
            'success': True,
            'message': '상담 신청이 완료되었습니다.',
            'privacy_notice': '개인정보는 상담 목적으로만 사용되며, 상담 완료 후 1년간 보관됩니다.'
        })
        
    except Exception as e:
        print(f"❌ 상담 신청 처리 오류: {str(e)}")
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
    print(f"\n🌞 수정된 디바이스 감지 및 분리 라우팅 태양광 시스템이 시작되었습니다!")
    print(f"🌍 포트: {port}")
    print(f"\n🔧 주요 수정사항:")
    print(f"   ✅ calculate_desktop_solar 함수 오류 처리 개선")
    print(f"   ✅ 프론트엔드 오류 처리 및 로깅 강화")
    print(f"   ✅ 데이터 타입 검증 및 기본값 설정")
    print(f"   ✅ API 응답 구조 일관성 확보")
    print(f"   ✅ 사용자 친화적 오류 메시지")
    print(f"\n🔄 자동 디바이스 감지 및 라우팅:")
    print(f"   📱 모바일 감지 → 농지 태양광 UI (간단)")
    print(f"   📟 태블릿 감지 → 중간 복잡도 UI")
    print(f"   🖥️ 데스크톱 감지 → 전문가용 UI (상세)")
    print(f"\n🔗 접속 방법:")
    print(f"   자동 감지: http://localhost:{port}/")
    print(f"   강제 모바일: http://localhost:{port}/mobile")
    print(f"   강제 데스크톱: http://localhost:{port}/desktop")
    print(f"   강제 태블릿: http://localhost:{port}/tablet")
    print(f"   URL 파라미터: http://localhost:{port}/?version=mobile")
    print(f"\n📊 API 엔드포인트:")
    print(f"   GET  /api/device-info - 디바이스 정보 확인")
    print(f"   GET  /api/search-address - 주소 검색")
    print(f"   POST /api/simulate - 모바일용 계산")
    print(f"   POST /api/desktop-calculate - 데스크톱/태블릿용 계산 (수정됨)")
    print(f"   POST /api/consultation - 상담 신청")
    print(f"\n🛠️ 오류 해결:")
    print(f"   - TypeError: Cannot read properties of undefined → 해결")
    print(f"   - 데이터 타입 안전성 강화")
    print(f"   - 프론트엔드-백엔드 데이터 구조 일치")
    print(f"   - 상세한 로깅 및 디버깅 정보 추가")
    
    app.run(host='0.0.0.0', port=port, debug=True)