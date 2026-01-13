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
        
        # 内部計算用カラム名（コード内では鋭利な定義を維持）
        self.feature_cols = [
            'req_ambiguity',      # 要件の曖昧さ
            'multi_vendor_layer', # 多重下請け深度
            'decision_speed',     # 意思決定の遅さ
            'user_incompetence'   # 発注者能力不足
        ]
        
        # 表示用ラベル（リスクが高いことを明確にする名称へ変更）
        self.display_labels = {
            'req_ambiguity': 'Requirement\nImmaturity',   # 要件定義の未熟度
            'multi_vendor_layer': 'Supply Chain\nDepth',  # 多重下請け深度
            'decision_speed': 'Decision\nLatency',        # 意思決定遅延
            'user_incompetence': 'Client\nImmaturity'     # 発注者未熟度(GIGOリスク)
        }
        
        print(f"[*] System Initialized: Loaded {len(self.df_cases)} historical failure cases.")

    def diagnose(self, target_params):
        """
        入力プロジェクトと過去事例のユークリッド距離を計算し、
        最も構造が近い失敗事例（Nearest Failure Neighbor）を特定する。
        """
        target_vector = np.array([target_params[col] for col in self.feature_cols])
        
        min_dist = float('inf')
        closest_case = None
        
        for _, row in self.df_cases.iterrows():
            case_vector = np.array([row[col] for col in self.feature_cols])
            dist = np.linalg.norm(target_vector - case_vector)
            
            if dist < min_dist:
                min_dist = dist
                closest_case = row

        # 類似度(%)への変換 (距離20を相関0とするヒューリスティックなロジック)
        similarity_score = max(0, (1 - (min_dist / 20.0)) * 100)

        return {
            'closest_case_name': closest_case['case_name'],
            'similarity_percent': round(similarity_score, 2),
            'estimated_loss_okuen': closest_case['est_loss_okuen'],
            'risk_description': closest_case['description'],
            'closest_case_data': closest_case
        }

    def visualize_risk(self, target_params, diagnosis_result):
        """
        診断対象と類似事例を比較するレーダーチャートを描画する。
        軸ラベルにはビジネス用語（Client Immaturity等）を使用する。
        """
        # フォント設定（環境に合わせて変更してください）
        plt.rcParams['font.family'] = 'sans-serif' 
        
        # 軸ラベルを表示用名称に変換
        categories = [self.display_labels[col] for col in self.feature_cols]
        N = len(categories)

        # データを閉じた多角形にする
        values_target = [target_params[col] for col in self.feature_cols]
        values_target += values_target[:1]
        
        case_data = diagnosis_result['closest_case_data']
        values_case = [case_data[col] for col in self.feature_cols]
        values_case += values_case[:1]

        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]

        # プロット作成
        fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True)) # サイズを少し大きく調整

        # ターゲット（診断対象）
        ax.plot(angles, values_target, linewidth=2, linestyle='solid', label='Target Project', color='#1f77b4')
        ax.fill(angles, values_target, '#1f77b4', alpha=0.2)

        # 類似事例（ニアレストネイバー）
        fail_name = case_data['case_name']
        ax.plot(angles, values_case, linewidth=2, linestyle='dashed', label=f"Ref Case: {fail_name}", color='#d62728')
        ax.fill(angles, values_case, '#d62728', alpha=0.1)

        # 軸の設定
        plt.xticks(angles[:-1], categories, size=11, weight='bold')
        ax.set_rlabel_position(0)
        plt.yticks([2, 4, 6, 8, 10], ["2", "4", "6", "8", "CRITICAL"], color="grey", size=9)
        plt.ylim(0, 10)

        # タイトル
        plt.title(f"Structural Risk Analysis\n(Similarity to {fail_name}: {diagnosis_result['similarity_percent']}%)", size=14, y=1.08)
        
        # 凡例の設定（修正箇所）
        # bbox_to_anchorでグラフ外の右上に固定配置し、切れないように調整
        plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        
        # レイアウト調整（凡例が見えるように余白を確保）
        plt.tight_layout()

        output_file = "risk_radar_chart.png"
        plt.savefig(output_file, bbox_inches='tight') # 保存時にも余白を調整
        print(f"[*] Risk Chart Saved: {output_file}")

# ---------------------------------------------------------
# Execution Demo
# ---------------------------------------------------------
if __name__ == "__main__":
    # NOTE:
    # This execution block is a demonstration for analysts.
    # In real governance use cases, this tool is embedded into 
    # the Gate Review process (e.g., Investment Committee).
    
    DATA_PATH = "data/failure_cases_dataset.csv"
    
    # ダミーCSV生成（動作確認用）
    if not os.path.exists("data"):
        os.makedirs("data")
        with open(DATA_PATH, "w") as f:
            f.write("case_name,req_ambiguity,multi_vendor_layer,decision_speed,user_incompetence,est_loss_okuen,description\n")
            f.write("Mizuho_2002,9,10,10,6,2000,Complexity Overload\n")
            f.write("SOFTIC_021_Kyushuuya,10,1,3,10,1,User Competence Failure (GIGO)\n")

    try:
        estimator = DeathMarchEstimator(DATA_PATH)
        
        # -----------------------------------------------------
        # Scenario: "Vendor is good, but Client is lost"
        # -----------------------------------------------------
        # 各変数は 1(Low Risk) - 10(Critical Risk)
        target_project = {
            'req_ambiguity': 9,      # 要件が決まらない(Immaturity)
            'multi_vendor_layer': 2, # ベンダー体制は健全
            'decision_speed': 4,     # 意思決定はそこそこ
            'user_incompetence': 9   # 【危険】発注者能力が低い(Immaturity)
        }

        print("\n--- Diagnostic Report ---")
        result = estimator.diagnose(target_project)

        print(f"Warning: Project structure resembles '{result['closest_case_name']}'")
        print(f"Similarity: {result['similarity_percent']}%")
        print(f"Root Cause: {result['risk_description']}")
        print(f"Potential Loss: {result['estimated_loss_okuen']} Oku-En")
        
        # 九州屋ケースへの特記コメント
        if 'Kyushuuya' in result['closest_case_name']:
            print("\n[Strategic Advice]")
            print("ALERT: High risk of 'Client-Side Failure'.")
            print("The vendor structure is sound, but internal requirements maturity is critical.")
            print("Action: Freeze development and conduct Business Process Re-engineering (BPR).")
            
        estimator.visualize_risk(target_project, result)

    except Exception as e:
        print(f"Error: {e}")