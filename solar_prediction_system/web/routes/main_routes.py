"""
메인 페이지 라우트
"""
from flask import Blueprint, render_template, request, redirect, url_for
from core.weather_api import WeatherAPI
from config import get_config

main_bp = Blueprint('main', __name__)
config = get_config()

@main_bp.route('/')
def index():
    """메인 페이지"""
    # URL 파라미터에서 위치 정보 가져오기 (옵션)
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    
    initial_location = None
    if lat and lon:
        weather_api = WeatherAPI()
        if weather_api.validate_coordinates(lat, lon):
            initial_location = {'lat': lat, 'lon': lon}
    
    return render_template('index.html', initial_location=initial_location)

@main_bp.route('/heatmap')
def heatmap():
    """히트맵 페이지"""
    return render_template('heatmap.html')

@main_bp.route('/about')
def about():
    """소개 페이지"""
    return render_template('about.html')

@main_bp.route('/help')
def help_page():
    """도움말 페이지"""
    return render_template('help.html')

@main_bp.errorhandler(404)
def not_found(error):
    """404 에러 페이지"""
    return render_template('error.html', 
                         error_code=404, 
                         error_message="페이지를 찾을 수 없습니다."), 404

@main_bp.errorhandler(500)
def internal_error(error):
    """500 에러 페이지"""
    return render_template('error.html',
                         error_code=500,
                         error_message="서버 내부 오류가 발생했습니다."), 500