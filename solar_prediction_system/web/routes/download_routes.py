"""
데이터 다운로드 라우트
"""
import os
import json
import pandas as pd
import numpy as np
from io import BytesIO
from flask import Blueprint, render_template, request, send_file, jsonify
from core.solar_calculator import SolarCalculator
from core.weather_api import WeatherAPI
from core.financial_analysis import FinancialAnalyzer
from config import get_config

download_bp = Blueprint('download', __name__)
config = get_config()

# 인스턴스 생성
solar_calc = SolarCalculator()
weather_api = WeatherAPI()
financial_analyzer = FinancialAnalyzer()

@download_bp.route('/')
def download_page():
    """다운로드 메인 페이지"""
    return render_template('download.html')

@download_bp.route('/data')
def download_data():
    """요청에 따른 태양광 발전량 데이터 생성 및 다운로드"""
    try:
        # 파라미터 가져오기
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        data_type = request.args.get('data_type', default='monthly')
        period = request.args.get('period', default=1, type=int)
        file_format = request.args.get('format', default='csv')
        
        if not lat or not lon:
            return "위도와 경도를 지정해주세요.", 400
        
        # GHI 데이터 가져오기
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        # 최적 각도 계산
        optimal_tilt = abs(lat) * 0.76 + 3.1
        optimal_azimuth = 180 if lat >= 0 else 0
        
        # 데이터 생성
        df = _generate_data_by_type(data_type, period, lat, lon, ghi, optimal_tilt, optimal_azimuth)
        
        # 파일 형식에 따른 다운로드
        if file_format == 'csv':
            return _download_csv(df, lat, lon, data_type)
        elif file_format == 'json':
            return _download_json(df, lat, lon, data_type)
        elif file_format == 'excel':
            return _download_excel(df, lat, lon, data_type, ghi, optimal_tilt, optimal_azimuth)
        else:
            return "지원하지 않는 파일 형식입니다.", 400
            
    except Exception as e:
        return f"데이터 생성 중 오류가 발생했습니다: {str(e)}", 500

@download_bp.route('/heatmap_data')
def download_heatmap_data():
    """태양광 발전량 히트맵 데이터 다운로드"""
    try:
        heatmap_path = config.HEATMAP_DATA_PATH
        
        if not os.path.exists(heatmap_path):
            return "히트맵 데이터가 없습니다. 먼저 데이터를 생성해주세요.", 404
        
        return send_file(
            heatmap_path,
            mimetype='application/json',
            as_attachment=True,
            download_name='korea_solar_heatmap_data.json'
        )
        
    except Exception as e:
        return f"히트맵 데이터 다운로드 오류: {str(e)}", 500

@download_bp.route('/angle_optimization_data')
def download_angle_optimization_data():
    """경사각/방위각 최적화 데이터 다운로드"""
    try:
        lat = request.args.get('lat', default=36.5, type=float)
        lon = request.args.get('lon', default=127.8, type=float)
        
        # GHI 데이터 가져오기
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        # 각도 매트릭스 계산
        energy_matrix, tilt_range, azimuth_range = solar_calc.calculate_angle_matrix(lat, lon, ghi)
        
        # 데이터프레임 생성
        angle_data = []
        for i, tilt in enumerate(tilt_range):
            for j, azimuth in enumerate(azimuth_range):
                angle_data.append({
                    'tilt': tilt,
                    'azimuth': azimuth,
                    'annual_energy': energy_matrix[i, j]
                })
        
        df = pd.DataFrame(angle_data)
        
        # CSV 파일로 다운로드
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'angle_optimization_{lat}_{lon}.csv'
        )
        
    except Exception as e:
        return f"각도 최적화 데이터 생성 오류: {str(e)}", 500

@download_bp.route('/module_comparison_data')
def download_module_comparison_data():
    """태양광 모듈 유형별 성능 비교 데이터 다운로드"""
    try:
        # 기본 위치 (대한민국 중부)
        lat, lon = 36.5, 127.8
        
        # GHI 데이터 가져오기
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        # 최적 각도
        optimal_tilt = abs(lat) * 0.76 + 3.1
        optimal_azimuth = 180
        
        # 모듈 유형 정의
        module_types = [
            {'name': '표준형', 'config': {'module_type': 'standard', 'tracking_type': 'fixed'}},
            {'name': '고효율', 'config': {'module_type': 'premium', 'tracking_type': 'fixed'}},
            {'name': '양면형', 'config': {'module_type': 'bifacial', 'tracking_type': 'fixed', 'bifacial_factor': 0.7}},
            {'name': '박막형', 'config': {'module_type': 'thin_film', 'tracking_type': 'fixed'}},
            {'name': '단축 트래킹 (표준형)', 'config': {'module_type': 'standard', 'tracking_type': 'single_axis'}},
            {'name': '단축 트래킹 (양면형)', 'config': {'module_type': 'bifacial', 'tracking_type': 'single_axis', 'bifacial_factor': 0.7}}
        ]
        
        # 각 유형별 성능 계산
        results = []
        for module in module_types:
            config_data = {
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
            
            result = solar_calc.calculate_pv_energy(lat, lon, optimal_tilt, optimal_azimuth, ghi, config_data)
            
            # 계절별 데이터 계산
            monthly = result['monthly_energy']
            winter = (monthly[0] + monthly[1] + monthly[11]) / 3
            spring = (monthly[2] + monthly[3] + monthly[4]) / 3
            summer = (monthly[5] + monthly[6] + monthly[7]) / 3
            fall = (monthly[8] + monthly[9] + monthly[10]) / 3
            
            results.append({
                '모듈 유형': module['name'],
                '연간 발전량 (kWh/kWp)': result['annual_energy'],
                '겨울 평균 (kWh/kWp)': round(winter, 1),
                '봄 평균 (kWh/kWp)': round(spring, 1),
                '여름 평균 (kWh/kWp)': round(summer, 1),
                '가을 평균 (kWh/kWp)': round(fall, 1),
                '온도 효과 (%)': result['temp_effect'],
                '설치 방식': '고정형' if module['config']['tracking_type'] == 'fixed' else '트래킹형'
            })
        
        df = pd.DataFrame(results)
        
        # Excel 파일로 다운로드
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='모듈 비교', index=False)
            
            # 정보 시트 추가
            info_data = [
                ['태양광 모듈 유형별 성능 비교 데이터'],
                [''],
                ['기준 위치:', f'위도 {lat}°N, 경도 {lon}°E (대한민국 중부지방)'],
                ['연평균 일사량(GHI):', f'{ghi} kWh/m²/년'],
                ['최적 경사각:', f'{optimal_tilt:.1f}°'],
                ['최적 방위각:', f'{optimal_azimuth}°'],
                [''],
                ['계산 조건:'],
                ['- 시스템 효율: 85%'],
                ['- 인버터 효율: 96%'],
                ['- 시스템 손실: 14%'],
                ['- 지면 반사율: 20%'],
                [''],
                ['주의사항:'],
                ['실제 발전량은 현장 조건에 따라 달라질 수 있습니다.']
            ]
            
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, sheet_name='정보', header=False, index=False)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='module_comparison_data.xlsx'
        )
        
    except Exception as e:
        return f"모듈 비교 데이터 생성 오류: {str(e)}", 500

@download_bp.route('/financial_template')
def download_financial_template():
    """경제성 분석 템플릿 다운로드"""
    try:
        # 기본 시나리오들
        scenarios = [
            {
                'scenario': '소형 주택용 (3kWp)',
                'system_size': 3.0,
                'install_cost_per_kw': 1500000,
                'electricity_price': 120,
                'annual_energy': 1200
            },
            {
                'scenario': '중형 주택용 (5kWp)',
                'system_size': 5.0,
                'install_cost_per_kw': 1400000,
                'electricity_price': 120,
                'annual_energy': 1200
            },
            {
                'scenario': '상업용 (10kWp)',
                'system_size': 10.0,
                'install_cost_per_kw': 1300000,
                'electricity_price': 100,
                'annual_energy': 1250
            }
        ]
        
        # 각 시나리오별 경제성 분석
        results = []
        for scenario in scenarios:
            financial_result = financial_analyzer.calculate_financial_metrics(
                annual_energy=scenario['annual_energy'],
                system_size=scenario['system_size'],
                install_cost_per_kw=scenario['install_cost_per_kw'],
                electricity_price=scenario['electricity_price']
            )
            
            results.append({
                '시나리오': scenario['scenario'],
                '시스템 용량 (kWp)': scenario['system_size'],
                '설치 비용 (원/kWp)': scenario['install_cost_per_kw'],
                '전력 단가 (원/kWh)': scenario['electricity_price'],
                '연간 발전량 (kWh/kWp)': scenario['annual_energy'],
                '총 설치 비용 (원)': financial_result['total_cost'],
                '연간 수익 (원)': financial_result['annual_revenue'],
                '투자 회수 기간 (년)': financial_result['payback_period'],
                'ROI (%)': financial_result['roi'],
                '생애 총 수익 (원)': financial_result['life_cycle_revenue']
            })
        
        df = pd.DataFrame(results)
        
        # Excel 파일로 저장
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='경제성 분석', index=False)
            
            # 사용자 입력 템플릿 시트
            template_data = [
                ['항목', '값', '단위', '설명'],
                ['시스템 용량', '', 'kWp', '설치할 태양광 시스템 용량'],
                ['설치 비용', '', '원/kWp', 'kW당 설치 비용'],
                ['전력 판매 단가', '', '원/kWh', 'kWh당 전력 판매 가격'],
                ['연간 발전량', '', 'kWh/kWp', 'kWp당 연간 예상 발전량'],
                ['연간 성능 저하율', '0.5', '%', '매년 성능 저하 비율'],
                ['시스템 수명', '25', '년', '태양광 시스템 설계 수명']
            ]
            
            template_df = pd.DataFrame(template_data[1:], columns=template_data[0])
            template_df.to_excel(writer, sheet_name='입력 템플릿', index=False)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='financial_analysis_template.xlsx'
        )
        
    except Exception as e:
        return f"경제성 분석 템플릿 생성 오류: {str(e)}", 500

def _generate_data_by_type(data_type, period, lat, lon, ghi, optimal_tilt, optimal_azimuth):
    """데이터 타입에 따른 데이터 생성"""
    if data_type == 'hourly':
        # 시간별 데이터 (1년치)
        result = solar_calc.calculate_pv_energy(lat, lon, optimal_tilt, optimal_azimuth, ghi)
        times = pd.date_range(start='2023-01-01', end='2023-12-31 23:00:00', freq='H')
        
        df = pd.DataFrame({
            'datetime': times,
            'energy': result['hourly_energy']
        })
        
    elif data_type == 'daily':
        # 일별 데이터
        days = period * 365
        dates = pd.date_range(start='2023-01-01', periods=days, freq='D')
        
        # 간소화된 일별 변동 생성
        daily_energy = []
        for i, date in enumerate(dates):
            month = date.month - 1
            monthly_ratio = np.array(config.MONTHLY_GHI_RATIO)
            monthly_ratio = monthly_ratio / monthly_ratio.mean()
            
            daily_variation = 1.0 + (np.sin(i * 0.7) * 0.1)
            daily_value = ghi / 365 * monthly_ratio[month] * daily_variation * 0.85
            daily_energy.append(daily_value)
        
        df = pd.DataFrame({
            'date': dates,
            'energy': daily_energy
        })
        
    elif data_type == 'monthly':
        # 월별 데이터
        result = solar_calc.calculate_pv_energy(lat, lon, optimal_tilt, optimal_azimuth, ghi)
        months = period * 12
        dates = pd.date_range(start='2023-01-01', periods=months, freq='M')
        
        # 월별 에너지 반복
        monthly_pattern = result['monthly_energy']
        monthly_energy = []
        
        for i in range(months):
            month_idx = i % 12
            year_variation = 1.0 + (np.sin(i * 0.5) * 0.05)
            monthly_energy.append(monthly_pattern[month_idx] * year_variation)
        
        df = pd.DataFrame({
            'date': dates,
            'year': [d.year for d in dates],
            'month': [d.month for d in dates],
            'energy': monthly_energy
        })
        
    else:  # yearly
        # 연간 데이터
        result = solar_calc.calculate_pv_energy(lat, lon, optimal_tilt, optimal_azimuth, ghi)
        years = range(2023, 2023 + period)
        
        annual_energies = []
        for i, year in enumerate(years):
            year_variation = 1.0 + (np.sin(i * 0.5) * 0.05)
            annual_energies.append(result['annual_energy'] * year_variation)
        
        df = pd.DataFrame({
            'year': years,
            'energy': annual_energies
        })
    
    return df

def _download_csv(df, lat, lon, data_type):
    """CSV 파일 다운로드"""
    output = BytesIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'solar_data_{lat}_{lon}_{data_type}.csv'
    )

def _download_json(df, lat, lon, data_type):
    """JSON 파일 다운로드"""
    output = BytesIO()
    output.write(df.to_json(orient='records', date_format='iso').encode('utf-8'))
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/json',
        as_attachment=True,
        download_name=f'solar_data_{lat}_{lon}_{data_type}.json'
    )

def _download_excel(df, lat, lon, data_type, ghi, optimal_tilt, optimal_azimuth):
    """Excel 파일 다운로드"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='태양광 발전량 데이터', index=False)
        
        # 정보 시트 추가
        info_df = pd.DataFrame({
            '항목': ['위도', '경도', '연평균 일사량 (GHI)', '최적 경사각', '최적 방위각', '데이터 유형'],
            '값': [lat, lon, f'{ghi} kWh/m²/년', f'{optimal_tilt}°', f'{optimal_azimuth}°', data_type]
        })
        info_df.to_excel(writer, sheet_name='정보', index=False)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'solar_data_{lat}_{lon}_{data_type}.xlsx'
    )