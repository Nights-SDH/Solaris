"""
Flask 애플리케이션 팩토리
"""
from flask import Flask
import matplotlib
matplotlib.use('Agg')  # 서버 환경에서 matplotlib 사용을 위한 백엔드 설정

def create_app():
    """Flask 앱 생성 및 설정"""
    app = Flask(__name__)
    
    # 라우트 등록
    from web.routes.main_routes import main_bp
    from web.routes.api_routes import api_bp
    from web.routes.download_routes import download_bp
    from web.routes.design_routes import design_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(download_bp, url_prefix='/download')
    app.register_blueprint(design_bp, url_prefix='/design')
    
    return app