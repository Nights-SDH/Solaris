"""
web 모듈 - Flask 웹 애플리케이션

이 모듈은 다음 컴포넌트들을 포함합니다:
- app: Flask 애플리케이션 팩토리
- routes: URL 라우팅 모듈들
- templates: HTML 템플릿 파일들
- static: 정적 파일들 (CSS, JS, 이미지)
"""

from .app import create_app

__version__ = "1.0.0"
__author__ = "Solar Prediction Team"

# Flask 앱 생성 편의 함수
def create_development_app():
    """개발용 Flask 앱 생성"""
    import os
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = 'true'
    return create_app()

def create_production_app():
    """운영용 Flask 앱 생성"""
    import os
    os.environ['FLASK_ENV'] = 'production'
    os.environ['FLASK_DEBUG'] = 'false'
    return create_app()

__all__ = [
    'create_app',
    'create_development_app',
    'create_production_app'
]