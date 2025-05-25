"""
web.routes 모듈 - Flask 라우트 모음

이 모듈은 다음 라우트들을 포함합니다:
- main_routes: 메인 페이지 및 기본 페이지들
- api_routes: REST API 엔드포인트들
- download_routes: 데이터 다운로드 관련 라우트들
- design_routes: 시스템 설계 도구 관련 라우트들
"""

from .main_routes import main_bp
from .api_routes import api_bp
from .download_routes import download_bp

__version__ = "1.0.0"
__author__ = "Solar Prediction Team"

# 모든 블루프린트 목록
all_blueprints = [
    (main_bp, {}),  # (blueprint, url_prefix)
    (api_bp, {'url_prefix': '/api'}),
    (download_bp, {'url_prefix': '/download'})
]

def register_all_blueprints(app):
    """모든 블루프린트를 Flask 앱에 등록"""
    for blueprint, options in all_blueprints:
        app.register_blueprint(blueprint, **options)
    
    print(f"✅ {len(all_blueprints)}개 블루프린트 등록 완료")

__all__ = [
    'main_bp',
    'api_bp', 
    'download_bp',
    'all_blueprints',
    'register_all_blueprints'
]