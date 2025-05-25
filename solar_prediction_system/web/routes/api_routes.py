"""
API 엔드포인트 라우트
"""
import json
from flask import Blueprint, request, jsonify, send_file
from core.solar_calculator import SolarCalculator
from core.weather_api import WeatherAPI
from core.financial_analysis import FinancialAnalyzer
from core.optimization import AngleOptimizer
from visualization.chart_generator import ChartGenerator

api_bp = Blueprint('api', __name__)

# 전역 인스턴스 생성
solar_calc = SolarCalculator()
weather_api = WeatherAPI()
financial_analyzer = FinancialAnalyzer()
angle_optimizer = AngleOptimizer(solar_calc)
chart_gen = ChartGenerator()

@api_bp.route('/pv_data')
def get_pv_data():
    """태양광 발전량 데이터 조회"""
    try:
        # 파라미터 가져오기
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        tilt = request.args.get('tilt', default=30, type=float)
        azimuth = request.args.get('azimuth', default=180, type=float)
        
        # 시스템 구성 파라미터
        system_config_str = request.args.get('system_config')
        if system_config_str:
            try:
                system_config = json.loads(system_config_str)
            except:
                system_config = None
        else:
            system_config = None
        
        # 입력 검증
        if not lat or not lon:
            return jsonify({'error': '위도와 경도를 입력해주세요.'}), 400
        
        if not weather_api.validate_coordinates(lat, lon):
            return jsonify({'error': '유효하지 않은 좌표입니다.'}), 400
        
        # GHI 데이터 조회
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            # 대체값 사용
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        # 태양광 발전량 계산
        pv_result = solar_calc.calculate_pv_energy(
            lat=lat,
            lon=lon,
            tilt=tilt,
            azimuth=azimuth,
            ghi_annual=ghi,
            system_config=system_config
        )
        
        return jsonify({
            'success': True,
            'ghi': round(ghi, 1),
            'energy': pv_result['annual_energy'],
            'monthly_energy': pv_result['monthly_energy'],
            'temp_effect': pv_result['temp_effect'],
            'optimal_tilt': pv_result['optimal_tilt'],
            'optimal_azimuth': pv_result['optimal_azimuth']
        })
        
    except Exception as e:
        return jsonify({'error': f'계산 중 오류가 발생했습니다: {str(e)}'}), 500

@api_bp.route('/optimize_angles')
def optimize_angles():
    """각도 최적화"""
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        method = request.args.get('method', 'simple')  # simple or detailed
        
        if not lat or not lon:
            return jsonify({'error': '위도와 경도를 입력해주세요.'}), 400
        
        # GHI 데이터 조회
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        if method == 'detailed':
            optimal_tilt, optimal_azimuth, max_energy = angle_optimizer.find_optimal_angles_detailed(
                lat, lon, ghi
            )
        else:
            optimal_tilt, optimal_azimuth = angle_optimizer.find_optimal_angles_simple(
                lat, lon, ghi
            )
            # 최대 발전량 계산
            result = solar_calc.calculate_pv_energy(lat, lon, optimal_tilt, optimal_azimuth, ghi)
            max_energy = result['annual_energy']
        
        return jsonify({
            'success': True,
            'optimal_tilt': optimal_tilt,
            'optimal_azimuth': optimal_azimuth,
            'max_energy': max_energy
        })
        
    except Exception as e:
        return jsonify({'error': f'최적화 중 오류가 발생했습니다: {str(e)}'}), 500

@api_bp.route('/financial_analysis')
def financial_analysis():
    """경제성 분석"""
    try:
        # 파라미터 가져오기
        annual_energy = request.args.get('annual_energy', type=float)
        system_size = request.args.get('system_size', default=3.0, type=float)
        install_cost = request.args.get('install_cost', type=float)
        electricity_price = request.args.get('electricity_price', type=float)
        annual_degradation = request.args.get('annual_degradation', type=float)
        lifetime = request.args.get('lifetime', type=int)
        
        if not annual_energy:
            return jsonify({'error': '연간 발전량을 입력해주세요.'}), 400
        
        # 경제성 분석 수행
        financial_result = financial_analyzer.calculate_financial_metrics(
            annual_energy=annual_energy,
            system_size=system_size,
            install_cost_per_kw=install_cost,
            electricity_price=electricity_price,
            annual_degradation=annual_degradation,
            lifetime=lifetime
        )
        
        return jsonify({
            'success': True,
            **financial_result
        })
        
    except Exception as e:
        return jsonify({'error': f'경제성 분석 중 오류가 발생했습니다: {str(e)}'}), 500

@api_bp.route('/sensitivity_analysis')
def sensitivity_analysis():
    """민감도 분석"""
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        optimal_tilt = request.args.get('optimal_tilt', type=float)
        optimal_azimuth = request.args.get('optimal_azimuth', type=float)
        
        if not all([lat, lon, optimal_tilt is not None, optimal_azimuth is not None]):
            return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400
        
        # GHI 데이터 조회
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        # 민감도 분석 수행
        sensitivity_result = angle_optimizer.calculate_angle_sensitivity(
            lat, lon, ghi, optimal_tilt, optimal_azimuth
        )
        
        return jsonify({
            'success': True,
            **sensitivity_result
        })
        
    except Exception as e:
        return jsonify({'error': f'민감도 분석 중 오류가 발생했습니다: {str(e)}'}), 500

@api_bp.route('/charts/monthly')
def get_monthly_chart():
    """월별 발전량 차트"""
    try:
        # 발전량 데이터 (URL 파라미터 또는 세션에서)
        monthly_energy_str = request.args.get('monthly_energy')
        if not monthly_energy_str:
            return "월별 발전량 데이터가 필요합니다.", 400
        
        monthly_energy = json.loads(monthly_energy_str)
        
        # 차트 생성
        img_bytes = chart_gen.generate_monthly_chart(monthly_energy)
        
        return send_file(img_bytes, mimetype='image/png')
        
    except Exception as e:
        return f"차트 생성 오류: {str(e)}", 500

@api_bp.route('/charts/angle_heatmap')
def get_angle_heatmap_chart():
    """각도 최적화 히트맵 차트"""
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        
        if not lat or not lon:
            return "위도와 경도가 필요합니다.", 400
        
        # GHI 데이터 조회
        ghi = weather_api.get_ghi_data(lat, lon)
        if ghi is None:
            ghi = weather_api.get_fallback_ghi(lat, lon)
        
        # 각도 매트릭스 계산
        energy_matrix, tilt_range, azimuth_range = solar_calc.calculate_angle_matrix(lat, lon, ghi)
        
        # 히트맵 생성
        img_bytes, _, _, _ = chart_gen.generate_angle_heatmap(energy_matrix, tilt_range, azimuth_range)
        
        return send_file(img_bytes, mimetype='image/png')
        
    except Exception as e:
        return f"히트맵 생성 오류: {str(e)}", 500

@api_bp.route('/charts/roi')
def get_roi_chart():
    """ROI 차트"""
    try:
        # 경제성 데이터 가져오기
        financial_data_str = request.args.get('financial_data')
        if not financial_data_str:
            return "경제성 데이터가 필요합니다.", 400
        
        financial_data = json.loads(financial_data_str)
        
        # 차트 생성
        img_bytes = chart_gen.generate_roi_chart(financial_data)
        
        return send_file(img_bytes, mimetype='image/png')
        
    except Exception as e:
        return f"ROI 차트 생성 오류: {str(e)}", 500

@api_bp.route('/validate_location')
def validate_location():
    """위치 좌표 검증"""
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        
        if lat is None or lon is None:
            return jsonify({'valid': False, 'message': '위도와 경도를 입력해주세요.'})
        
        # 좌표 유효성 검증
        is_valid = weather_api.validate_coordinates(lat, lon)
        is_korea = weather_api.is_korea_region(lat, lon)
        
        return jsonify({
            'valid': is_valid,
            'korea_region': is_korea,
            'message': '유효한 좌표입니다.' if is_valid else '유효하지 않은 좌표입니다.',
            'warning': '한국 지역 밖의 좌표입니다. 데이터 정확도가 떨어질 수 있습니다.' if is_valid and not is_korea else None
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'message': f'검증 중 오류: {str(e)}'})

@api_bp.route('/system_presets')
def get_system_presets():
    """시스템 프리셋 목록"""
    presets = {
        'residential_small': {
            'name': '소형 주택용 (3kWp)',
            'system_size': 3.0,
            'module_type': 'standard',
            'tracking_type': 'fixed',
            'install_cost_per_kw': 1500000,
            'description': '일반 가정용 소형 시스템'
        },
        'residential_medium': {
            'name': '중형 주택용 (5kWp)',
            'system_size': 5.0,
            'module_type': 'premium',
            'tracking_type': 'fixed',
            'install_cost_per_kw': 1400000,
            'description': '넓은 지붕을 가진 주택용'
        },
        'commercial_small': {
            'name': '소형 상업용 (10kWp)',
            'system_size': 10.0,
            'module_type': 'standard',
            'tracking_type': 'fixed',
            'install_cost_per_kw': 1300000,
            'description': '소규모 상업 시설용'
        },
        'commercial_large': {
            'name': '대형 상업용 (100kWp)',
            'system_size': 100.0,
            'module_type': 'bifacial',
            'tracking_type': 'single_axis',
            'install_cost_per_kw': 1200000,
            'description': '대규모 상업/산업 시설용'
        }
    }
    
    return jsonify({'success': True, 'presets': presets})