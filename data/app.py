import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. System Dynamics Logic (Class Definition)
# -----------------------------------------------------------------------------

class ProjectSimulator:
    """
    プロジェクトの進行、人員追加、バグ発生、仕様変更、
    そして「手戻り（Rework）」によるリソース枯渇をシミュレートするクラス
    """
    def __init__(self, 
                 total_scope: int, 
                 initial_staff: int, 
                 add_staff_num: int, 
                 add_staff_trigger_day: int,
                 tech_debt_level: str,
                 scope_creep_level: float):
        
        # --- 初期設定 ---
        self.total_scope_initial = total_scope
        self.current_scope = total_scope
        self.completed_work = 0
        self.staff = initial_staff
        self.add_staff_num = add_staff_num
        self.add_staff_trigger_day = add_staff_trigger_day
        self.scope_creep_prob = scope_creep_level
        
        # --- 技術的負債パラメータ ---
        # fix_complexity: 1つのバグを直すのに必要な工数係数（負債が高いほど直しにくい）
        # bug_rate: 進捗単位あたりのバグ混入率
        self.debt_params = {
            "Low":    (0.02, 1.2), # バグ少、修正容易
            "Medium": (0.05, 1.5), # 標準
            "High":   (0.10, 2.5)  # バグ多、スパゲッティコードで修正困難
        }
        self.bug_rate, self.fix_complexity = self.debt_params[tech_debt_level]
        
        # --- 状態変数 ---
        self.day = 0
        self.bugs_active = 0      # 現在残っている未修正バグ
        self.bugs_total_count = 0 # 発生したバグの累計
        self.cost_accumulated = 0 # 人日
        self.is_staff_added = False
        self.onboarding_days_remaining = 0
        
        # 履歴記録用
        self.history = []

    def _calculate_gross_productivity(self):
        """
        チーム全体の「総生産力」を計算する。
        （まだバグ修正と新規開発への配分は考慮しない、純粋な労働力）
        """
        n = self.staff
        if n <= 0: return 0
        
        # 1. 基本生産力
        base_productivity = n * 1.0
        
        # 2. コミュニケーションコスト (Brooks' Law)
        # 人数が増えるほど指数関数的に調整コストが増える
        comm_paths = (n * (n - 1)) / 2
        # 係数を調整し、人数過多で「逆に遅くなる」現象まで表現可能にする
        comm_penalty_factor = 0.012 * comm_paths
        
        # 効率係数（下限はある程度残す）
        efficiency = max(0.1, 1.0 - (comm_penalty_factor / n))
        
        # 3. 教育コスト (Onboarding Penalty)
        onboarding_penalty = 0.0
        if self.onboarding_days_remaining > 0:
            new_members = self.add_staff_num
            old_members = max(0, self.staff - new_members)
            # 既存メンバーが教育に時間を取られる
            mentoring_cost = min(old_members * 0.4, new_members * 1.0)
            onboarding_penalty = mentoring_cost
            self.onboarding_days_remaining -= 1

        gross_productivity = (base_productivity * efficiency) - onboarding_penalty
        return max(0, gross_productivity)

    def step(self):
        """
        1日分のシミュレーション（手戻り優先ロジック適用）
        """
        self.day += 1
        
        # --- A. 人員追加イベント ---
        if not self.is_staff_added and self.day >= self.add_staff_trigger_day and self.add_staff_num > 0:
            self.staff += self.add_staff_num
            self.is_staff_added = True
            # 人が増えれば教育期間も長引くと仮定
            self.onboarding_days_remaining = self.add_staff_num * 3 
        
        # --- B. 総生産力の算出 ---
        gross_productivity = self._calculate_gross_productivity()
        
        # --- C. リソース配分（ここがデスマーチの核） ---
        # 「バグ修正」は「新規開発」より優先される（または現場が足止めを食らう）
        
        # 1. 修正に必要な工数の見積もり
        # 溜まっているバグの20%を今日解決しようとする、あるいは緊急対応するイメージ
        # 技術的負債が高いと(fix_complexity)、1つのバグ修正に多くのパワーが必要
        fix_attempt_count = self.bugs_active * 0.2  # 1日に着手するバグの割合
        required_rework_effort = fix_attempt_count * self.fix_complexity
        
        # 2. 実作業の割り当て
        effort_spent_on_rework = min(gross_productivity, required_rework_effort)
        effort_spent_on_features = gross_productivity - effort_spent_on_rework
        
        # 3. バグの減少処理
        # 投入した工数分だけバグが減る
        bugs_fixed = effort_spent_on_rework / self.fix_complexity
        self.bugs_active = max(0, self.bugs_active - bugs_fixed)
        
        # --- D. 新規進捗の更新 ---
        progress = 0
        if self.completed_work < self.current_scope:
            progress = min(effort_spent_on_features, self.current_scope - self.completed_work)
            self.completed_work += progress
            
        # --- E. 新たなバグの発生 ---
        # 新規開発した分だけバグが混入する
        # プロジェクト後半（プレッシャー増）はバグ率上昇
        pressure_factor = 1.0 + (self.day / 150.0)
        new_bugs = progress * self.bug_rate * pressure_factor
        self.bugs_active += new_bugs
        self.bugs_total_count += new_bugs
        
        # --- F. 仕様変更 (Scope Creep) ---
        if np.random.rand() < self.scope_creep_prob:
            added_scope = self.total_scope_initial * 0.01
            self.current_scope += added_scope
            
        # --- G. コスト集計 ---
        self.cost_accumulated += self.staff
        
        # --- H. 履歴保存 ---
        self.history.append({
            "day": self.day,
            "staff": self.staff,
            "gross_productivity": gross_productivity, # 総労働力
            "effort_rework": effort_spent_on_rework,  # 手戻りに消えた力
            "effort_feature": effort_spent_on_features, # 本質的な進捗に使えた力
            "completed_work": self.completed_work,
            "current_scope": self.current_scope,
            "bugs_active": self.bugs_active,
            "cost": self.cost_accumulated
        })

    def run_simulation(self, max_days=365):
        while self.completed_work < self.current_scope and self.day < max_days:
            self.step()
        return pd.DataFrame(self.history)

# -----------------------------------------------------------------------------
# 2. UI/UX Implementation (Streamlit)
# -----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="DX Project Failure Simulator v2", layout="wide")
    
    st.title("📉 DX Project Failure Simulator (Realism Mode)")
    st.markdown("""
    **「なぜ、バグ対応に追われて開発が止まるのか？」**
    
    前回のモデルを改良し、**「手戻り工数（Rework Cost）」**を導入しました。
    バグ（技術的負債）が蓄積すると、エンジニアのリソースが修正作業に奪われ、
    **人員を追加しても進捗線がピクリとも動かなくなる「デスマーチの真の姿」**を体験できます。
    """)
    st.markdown("---")

    # --- Sidebar ---
    st.sidebar.header("🛠 Project Settings")
    total_scope = st.sidebar.slider("開発総規模 (Story Points)", 500, 5000, 1000, step=100)
    initial_staff = st.sidebar.slider("初期メンバー数", 1, 20, 5)
    
    st.sidebar.subheader("🚨 Crisis Action")
    add_staff_trigger = st.sidebar.slider("増員投入日", 10, 200, 60)
    add_staff_num = st.sidebar.slider("追加人数", 0, 20, 0)
    
    st.sidebar.subheader("💀 Risk Factors")
    tech_debt = st.sidebar.select_slider(
        "技術的負債レベル (修正難易度)",
        options=["Low", "Medium", "High"],
        value="Medium"
    )
    scope_creep = st.sidebar.slider("仕様変更発生率", 0.0, 0.2, 0.05, 0.01)

    # --- Simulation ---
    simulator = ProjectSimulator(
        total_scope=total_scope,
        initial_staff=initial_staff,
        add_staff_num=add_staff_num,
        add_staff_trigger_day=add_staff_trigger,
        tech_debt_level=tech_debt,
        scope_creep_level=scope_creep
    )
    df = simulator.run_simulation()
    
    # --- Metrics ---
    last_row = df.iloc[-1]
    is_finished = last_row["completed_work"] >= last_row["current_scope"] - 1.0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("経過日数", f"{int(last_row['day'])} 日", 
                  "Project Finished" if is_finished else "Failed (Timeover)")
    with col2:
        st.metric("残存バグ数", f"{int(last_row['bugs_active'])} 件",
                  delta_color="inverse", delta=f"Total Generated: {int(simulator.bugs_total_count)}")
    with col3:
        # 効率性指標: 全投入工数のうち、何%が機能開発に使われたか
        total_effort = df["gross_productivity"].sum()
        feature_effort = df["effort_feature"].sum()
        efficiency = (feature_effort / total_effort * 100) if total_effort > 0 else 0
        st.metric("開発効率 (Feature/Total)", f"{efficiency:.1f} %", 
                  help="100%に近いほど健全。低いほどバグ修正や調整に時間を浪費している。")
    with col4:
        st.metric("総コスト", f"{int(last_row['cost'])} 人日")

    # --- Main Charts ---
    st.markdown("### 3. デスマーチの構造的可視化")
    
    tab1, tab2, tab3 = st.tabs(["📊 労力配分 (Feature vs Rework)", "📈 進捗曲線 (Ideal vs Real)", "🕸 リスク分析"])

    # Tab 1: 積み上げ面グラフ (Effort Allocation)
    with tab1:
        st.markdown("**「チームは一体何に時間を使っているのか？」**")
        fig_alloc = go.Figure()
        
        # Rework (手戻り)
        fig_alloc.add_trace(go.Scatter(
            x=df["day"], y=df["effort_rework"],
            mode='lines',
            stackgroup='one', # 積み上げ
            name='手戻り/バグ修正 (Rework)',
            line=dict(width=0, color='firebrick'),
            fillcolor='firebrick'
        ))
        
        # Feature (有効作業)
        fig_alloc.add_trace(go.Scatter(
            x=df["day"], y=df["effort_feature"],
            mode='lines',
            stackgroup='one',
            name='新規機能開発 (Feature Work)',
            line=dict(width=0, color='royalblue'),
            fillcolor='royalblue'
        ))

        # 注釈: 増員ライン
        if add_staff_num > 0:
            fig_alloc.add_vline(x=add_staff_trigger, line_dash="dash", annotation_text="増員")

        fig_alloc.update_layout(
            title="日次の工数配分推移 (赤が増えるほど開発が停止する)",
            yaxis_title="投入工数 (人日相当)",
            height=400
        )
        st.plotly_chart(fig_alloc, use_container_width=True)
        st.warning("⚠️ **赤色（Rework）** が支配的になると、人員を追加しても新規開発（青色）の面積が増えず、コストだけが積み上がる状態になります。")

    # Tab 2: 従来の進捗曲線
    with tab2:
        fig_prog = go.Figure()
        fig_prog.add_trace(go.Scatter(x=df["day"], y=df["completed_work"], name="現実の進捗", line=dict(color='blue', width=3)))
        fig_prog.add_trace(go.Scatter(x=df["day"], y=df["current_scope"], name="要求スコープ", line=dict(color='red', dash='dot')))
        
        ideal_pace = total_scope / initial_staff
        fig_prog.add_trace(go.Scatter(x=df["day"], y=df["day"] * initial_staff, name="初期想定ペース", line=dict(color='green', dash='dot', width=1)))
        
        if add_staff_num > 0:
            fig_prog.add_vline(x=add_staff_trigger, line_dash="dash", line_color="orange")
        
        st.plotly_chart(fig_prog, use_container_width=True)

    # Tab 3: リスクレーダー
    with tab3:
        # リスク計算ロジック
        risk_org = min(100, (initial_staff + add_staff_num) * 5)
        # 修正難易度によるリスク
        debt_risk_map = {"Low": 20, "Medium": 50, "High": 90}
        risk_quality = debt_risk_map[tech_debt]
        
        categories = ['体制リスク', 'スケジュール', '品質(負債)', '仕様変更', 'コスト']
        r_values = [
            risk_org, 
            min(100, (add_staff_trigger/(total_scope/initial_staff))*100) if add_staff_num>0 else 10,
            risk_quality,
            min(100, scope_creep * 500),
            min(100, risk_org*0.5 + risk_quality*0.5)
        ]
        
        fig_radar = go.Figure(data=go.Scatterpolar(r=r_values, theta=categories, fill='toself'))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=350)
        st.plotly_chart(fig_radar, use_container_width=True)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.info("Created by Keisuke Nakamura | Refined Logic v2")

if __name__ == "__main__":
    main()