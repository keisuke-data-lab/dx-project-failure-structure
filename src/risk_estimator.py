import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

class DeathMarchEstimator:
    """
    DX Project Failure Structure Diagnostic
    過去の失敗事例（判例・炎上案件）との「構造的類似性」を算出し、
    潜在的なリスクと損失額を推定するガバナンス・ツール。
    """
    
    def __init__(self, data_path):
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Dataset not found: {data_path}")
            
        self.df_cases = pd.read_csv(data_path)
        
        self.feature_cols = [
            'req_ambiguity',      # 要件の曖昧さ
            'multi_vendor_layer', # 多重下請け深度
            'decision_speed',     # 意思決定の遅さ
            'user_incompetence'   # 発注者能力不足
        ]
        
        self.display_labels = {
            'req_ambiguity': 'Requirement\nImmaturity',
            'multi_vendor_layer': 'Supply Chain\nDepth',
            'decision_speed': 'Decision\nLatency',
            'user_incompetence': 'Client\nImmaturity'
        }
        
        print(f"[*] System Initialized: Loaded {len(self.df_cases)} historical failure cases.")

    def diagnose(self, target_params):
        target_vector = np.array([target_params[col] for col in self.feature_cols])
        
        min_dist = float('inf')
        closest_case = None
        
        for _, row in self.df_cases.iterrows():
            case_vector = np.array([row[col] for col in self.feature_cols])
            dist = np.linalg.norm(target_vector - case_vector)
            
            if dist < min_dist:
                min_dist = dist
                closest_case = row

        similarity_score = max(0, (1 - (min_dist / 20.0)) * 100)

        return {
            'closest_case_name': closest_case['case_name'],
            'similarity_percent': round(similarity_score, 2),
            'estimated_loss_okuen': closest_case['est_loss_okuen'],
            'risk_description': closest_case['description'],
            'closest_case_data': closest_case
        }

    def visualize_risk(self, target_params, diagnosis_result):
        plt.rcParams['font.family'] = 'sans-serif' 
        
        categories = [self.display_labels[col] for col in self.feature_cols]
        N = len(categories)

        values_target = [target_params[col] for col in self.feature_cols]
        values_target += values_target[:1]
        
        case_data = diagnosis_result['closest_case_data']
        values_case = [case_data[col] for col in self.feature_cols]
        values_case += values_case[:1]

        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]

        # FigureとAxesを定義
        fig, ax = plt.subplots(figsize=(8, 9), subplot_kw=dict(polar=True))

        # Target Project
        ax.plot(angles, values_target, linewidth=2, linestyle='solid',