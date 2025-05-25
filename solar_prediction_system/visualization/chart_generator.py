"""
차트 및 시각화 생성 모듈
"""
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import numpy as np
import pandas as pd
from io import BytesIO
from typing import List, Dict, Tuple

# 한글 폰트 설정
plt.rcParams['font.family'] = ['DejaVu Sans', 'Malgun Gothic', 'AppleGothic']
plt.rcParams['axes.unicode_minus'] = False

class ChartGenerator:
    """차트 생성 클래스"""
    
    def __init__(self):
        # 색상 팔레트
        self.colors = {
            'primary': '#2196F3',
            'secondary': '#4CAF50', 
            'accent': '#FF9800',
            'warning': '#F44336',
            'success': '#81C784',
            'info': '#81D4FA'
        }
        
        # 기본 스타일 설정
        sns.set_style("whitegrid")
        plt.style.use('seaborn-v0_8')
    
    def generate_monthly_chart(self, monthly_energy: List[float]) -> BytesIO:
        """월별 발전량 차트 생성"""
        months = ['1월', '2월', '3월', '4월', '5월', '6월', 
                 '7월', '8월', '9월', '10월', '11월', '12월']
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        bars = ax.bar(months, monthly_energy, color=self.colors['primary'], alpha=0.8)
        
        # 값 레이블 추가
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(monthly_energy)*0.01,
                   f'{height:.1f}', ha='center', va='bottom', fontsize=10)
        
        ax.set_title('월별 태양광 발전량 예측', fontsize=16, fontweight='bold', pad=20)
        ax.set_ylabel('발전량 (kWh/kWp)', fontsize=12)
        ax.set_xlabel('월', fontsize=12)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # y축 범위 조정
        ax.set_ylim(0, max(monthly_energy) * 1.1)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # 바이트 스트림으로 저장
        img_bytes = BytesIO()
        plt.savefig(img_bytes, format='png', dpi=150, bbox_inches='tight')
        img_bytes.seek(0)
        plt.close()
        
        return img_bytes
    
    def generate_angle_heatmap(
        self, 
        energy_matrix: np.ndarray, 
        tilt_range: range, 
        azimuth_range: range
    ) -> Tuple[BytesIO, float, float, float]:
        """경사각/방위각 최적화 히트맵 생성"""
        # 최적값 찾기
        max_idx = np.unravel_index(np.argmax(energy_matrix), energy_matrix.shape)
        optimal_tilt = list(tilt_range)[max_idx[0]]
        optimal_azimuth = list(azimuth_range)[max_idx[1]]
        max_energy = energy_matrix[max_idx]
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # 히트맵 생성
        im = ax.imshow(
            energy_matrix, 
            cmap='viridis', 
            aspect='auto',
            origin='lower',
            vmin=max_energy*0.7, 
            vmax=max_energy
        )
        
        # 최적 지점 표시
        ax.plot(max_idx[1], max_idx[0], 'ro', markersize=12, markeredgecolor='white', markeredgewidth=2)
        ax.text(max_idx[1], max_idx[0] + 2, f'최적\n{optimal_tilt}°/{optimal_azimuth}°', 
               ha='center', va='bottom', color='white', fontweight='bold', fontsize=10,
               bbox=dict(boxstyle='round,pad=0.3', facecolor='red', alpha=0.7))
        
        # 축 레이블 설정
        tilt_labels = [str(t) for t in tilt_range][::2]  # 2개씩 건너뛰어 표시
        azimuth_labels = [str(a) for a in azimuth_range][::2]
        
        ax.set_xticks(range(0, len(azimuth_range), 2))
        ax.set_xticklabels(azimuth_labels)
        ax.set_yticks(range(0, len(tilt_range), 2))
        ax.set_yticklabels(tilt_labels)
        
        ax.set_xlabel('방위각 (°)', fontsize=12)
        ax.set_ylabel('경사각 (°)', fontsize=12)
        ax.set_title(f'경사각/방위각 조합에 따른 발전량\n최적: {optimal_tilt}°/{optimal_azimuth}° ({max_energy:.1f} kWh/kWp)', 
                    fontsize=14, fontweight='bold')
        
        # 컬러바
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('연간 발전량 (kWh/kWp)', fontsize=10)
        
        plt.tight_layout()
        
        img_bytes = BytesIO()
        plt.savefig(img_bytes, format='png', dpi=150, bbox_inches='tight')
        img_bytes.seek(0)
        plt.close()
        
        return img_bytes, optimal_tilt, optimal_azimuth, max_energy
    
    def generate_daily_profile_chart(
        self, 
        seasonal_profiles: Dict[str, List[float]]
    ) -> BytesIO:
        """계절별 일일 발전량 프로필 차트"""
        fig, ax = plt.subplots(figsize=(12, 7))
        
        colors = [self.colors['info'], self.colors['success'], self.colors['accent'], self.colors['warning']]
        labels = ['겨울 (1월)', '봄 (4월)', '여름 (7월)', '가을 (10월)']
        
        hours = range(24)
        
        for i, (season, profile) in enumerate(seasonal_profiles.items()):
            ax.plot(hours, profile, 'o-', color=colors[i], label=labels[i], 
                   linewidth=2.5, markersize=4, alpha=0.8)
        
        ax.set_title('계절별 일일 발전량 프로필', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('시간 (시)', fontsize=12)
        ax.set_ylabel('시간당 발전량 (kWh/kWp)', fontsize=12)