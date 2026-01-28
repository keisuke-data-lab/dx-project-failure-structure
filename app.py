import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. System Dynamics Logic (Core Physics)
# -----------------------------------------------------------------------------

class ProjectSimulator:
    """
    プロジェクトの進行、人員追加、バグ発生、仕様変更、手戻りをシミュレートするクラス
    """
    def __init__(self, 
                 total_scope: int, 
                 initial_staff: int, 
                 add_staff_num: int, 
                 add_staff_trigger_day: int,
                 tech_debt_level: str,
                 scope_creep_level: float):
        
        self.total_scope_initial = total_scope
        self.current_scope = total_scope
        self.completed_work = 0
        self.staff = initial_staff
        self.add_staff_num = add_staff_num
        self.add_staff_trigger_day = add_staff_trigger_day
        self.scope_creep_prob = scope_creep_level
        
        # fix_complexity: 1つのバグを直すのに必要な工数係数
        self.debt_params = {
            "Low":    (0.02, 1.2), # 新規開発・綺麗
            "Medium": (0.05, 1.5), # 普通
            "High":   (0.10, 2.5)  # スパゲッティ
        }
        self.bug_rate, self.fix_complexity = self.debt_params[tech_debt_level]
        
        self.day = 0
        self.bugs_active = 0
        self.bugs_total_count = 0
        self.cost_accumulated = 0 # 人日ベース
        self.is_staff_added = False
        self.onboarding_days_remaining = 0
        self.history = []

    def _calculate_gross_productivity(self):
        n = self.staff
        if n <= 0: return 0
        base_productivity = n * 1.0
        
        # コミュニケーションコスト (Brooks' Law)
        comm_paths = (n * (n - 1)) / 2
        comm_penalty_factor = 0.012 * comm_paths
        efficiency = max(0.1, 1.0 - (comm_penalty_factor / n))
        
        # 教育コスト
        onboarding_penalty = 0.0
        if self.onboarding_days_remaining > 0:
            new_members = self.add_staff_num
            old_members = max(0, self.staff - new_members)
            mentoring_cost = min(old_members * 0.4, new_members * 1.0)
            onboarding_penalty = mentoring_cost
            self.onboarding_days_remaining -= 1

        gross_productivity = (base_productivity * efficiency) - onboarding_penalty
        return max(0, gross_productivity)

    def step(self):
        self.day += 1
        
        # A. 人員追加
        if not self.is_staff_added and self.day >= self.add_staff_trigger_day and self.add_staff_num > 0:
            self.staff += self.add_staff_num
            self.is_staff_added = True
            self.onboarding_days_remaining = self.add_staff_num * 3 
        
        # B. 総生産力
        gross_productivity = self._calculate_gross_productivity()
        
        # C. リソース配分 (手戻り優先)
        fix_attempt_count = self.bugs_active * 0.2
        required_rework_effort = fix_attempt_count * self.fix_complexity
        
        effort_spent_on_rework = min(gross_productivity, required_rework_effort)
        effort_spent_on_features = gross_productivity - effort_spent_on_rework
        
        bugs_fixed = effort_spent_on_rework / self.fix_complexity
        self.bugs_active = max(0, self.bugs_active - bugs_fixed)
        
        # D. 新規進捗
        progress = 0
        if self.completed_work < self.current_scope:
            progress = min(effort_spent_on_features, self.current_scope - self.completed_work)
            self.completed_work += progress
            
        # E. 新規バグ発生
        pressure_factor = 1.0 + (self.day / 150.0)
        new_bugs = progress * self.bug_rate * pressure_factor
        self.bugs_active += new_bugs
        self.bugs_total_count += new_bugs
        
        # F. 仕様変更 (Scope Creep)
        if np.random.rand() < self.scope_creep_prob:
            added_scope = self.total_scope_initial * 0.01
            self.current_scope += added_scope
            
        # G. コスト (人日)
        self.cost_accumulated += self.staff
        
        # H. 履歴
        self.history.append({
            "day": self.day,
            "staff": self.staff,
            "gross_productivity": gross_productivity,
            "effort_rework": effort_spent_on_rework,
            "effort_feature": effort_spent_on_features,
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
# 2. UI/UX Implementation (Business & Money)
# -----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="DX Project Simulator (Biz Ver)", layout="wide")
    
    st.title("💸 DX Project Budget Simulator")
    st.markdown("""
    **「その仕様変更と増員で、いくら赤字が出るのか？」**
    
    現場の「工数」を経営の「金額」にリアルタイム換算します。
    安易な意思決定がプロジェクトの採算をどう悪化させるかを確認してください。
    """)
    st.markdown("---")

    # --- Sidebar: Definitions ---
    with st.sidebar.expander("📝 設定の前提条件 (定義)", expanded=False):
        st.markdown("""
        * **1 Story Point (SP)**: エンジニア1名が1日(ベストエフォート)でこなせる作業量と仮定します。
        * **人月単価**: エンジニア1名あたりの月額費用。ここでは1ヶ月=20営業日で計算します。
        * **初期予算**: `総SP × (人月単価 ÷ 20)` で自動算出される「理想的な見積もり額」です。
        """)

    st.sidebar.header("💰 予算・単価設定 (Business)")
    
    unit_price_man_month = st.sidebar.number_input(
        "エンジニア人月単価 (万円/月)", 
        min_value=40, max_value=300, value=100, step=10,
        help="エンジニア1名を1ヶ月雇うのにかかる費用（給与+販管費、または外注費）。"
    )
    # 人日単価に変換 (1ヶ月 = 20日稼働とする)
    unit_price_man_day = (unit_price_man_month * 10000) / 20

    st.sidebar.markdown("---")
    st.sidebar.header("🛠 プロジェクトパラメータ")

    total_scope = st.sidebar.slider(
        "開発総規模 (Story Points)", 500, 5000, 1000, step=100,
        help="仕事の総量。これが1000なら、理想的には1000人日分の作業です。"
    )
    
    initial_staff = st.sidebar.slider("初期メンバー数 (名)", 1, 20, 5)
    
    st.sidebar.subheader("🚨 クライシス対応")
    add_staff_trigger = st.sidebar.slider("増員投入日 (日目)", 10, 200, 60)
    add_staff_num = st.sidebar.slider("追加人数 (名)", 0, 20, 0)
    
    st.sidebar.subheader("💀 リスク要因")
    tech_debt = st.sidebar.select_slider(
        "技術的負債 (バグ修正難易度)",
        options=["Low", "Medium", "High"],
        value="Medium",
        help="Highの場合、バグ修正に通常の2.5倍のコストがかかり、その分赤字が拡大します。"
    )
    scope_creep = st.sidebar.slider(
        "仕様変更頻度", 0.0, 0.2, 0.03, 0.01,
        help="0.03=毎日3%の確率で仕様が増える。期間が延びるほど累積で効いてきます。"
    )

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
    
    # --- Financial Calculation ---
    last_row = df.iloc[-1]
    is_finished = last_row["completed_work"] >= last_row["current_scope"] - 1.0
    
    # 予算計算
    initial_budget = total_scope * unit_price_man_day
    actual_cost = last_row['cost'] * unit_price_man_day
    profit_loss = initial_budget - actual_cost
    
    # --- Metrics Section ---
    st.subheader("📊 経営サマリー (Financial Impact)")
    
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.metric(
            "初期予算 (見積)",
            f"¥{initial_budget/1000000:,.1f} M",
            help=f"総規模 {total_scope} SP × 単価 @{int(unit_price_man_day):,}円 で算出した理想予算"
        )
    
    with m2:
        st.metric(
            "実績コスト (見込)",
            f"¥{actual_cost/1000000:,.1f} M",
            delta=f"¥{profit_loss/1000000:,.1f} M ({'黒字' if profit_loss >=0 else '赤字'})",
            delta_color="normal" if profit_loss >= 0 else "inverse",
            help="実際に投入された人件費の総額"
        )

    with m3:
        roi_ratio = actual_cost / initial_budget
        st.metric(
            "コスト超過率",
            f"{roi_ratio*100:.1f} %",
            delta=f"予算比 {roi_ratio:.2f}倍",
            delta_color="inverse",
            help="100%を超えると予算オーバー。200%なら予算の倍かかっている状態。"
        )

    with m4:
        st.metric(
            "完了ステータス",
            "Completed" if is_finished else "Failed",
            f"{int(last_row['day'])} Days",
            delta_color="off"
        )

    # --- Visualizations ---
    tab1, tab2 = st.tabs(["💸 コスト構造と赤字要因", "📉 デスマーチの推移"])
    
    with tab1:
        st.markdown("#### なぜ予算を超過したのか？ (工数内訳)")
        
        # 工数を金額に換算
        total_feature_cost = df["effort_feature"].sum() * unit_price_man_day
        total_rework_cost = df["effort_rework"].sum() * unit_price_man_day
        
        # 1. 予算対比のウォーターフォールチャート（あるいはバーチャート）
        fig_cost = go.Figure()
        
        fig_cost.add_trace(go.Bar(
            y=['コスト内訳'],
            x=[initial_budget],
            name='初期予算',
            orientation='h',
            marker_color='lightgray'
        ))
        
        fig_cost.add_trace(go.Bar(
            y=['コスト内訳'],
            x=[total_feature_cost],
            name='有効な開発コスト(価値創造)',
            orientation='h',
            marker_color='royalblue'
        ))
        
        fig_cost.add_trace(go.Bar(
            y=['コスト内訳'],
            x=[total_rework_cost],
            name='手戻り/バグ修正コスト(損失)',
            orientation='h',
            marker_color='firebrick'
        ))
        
        fig_cost.update_layout(
            barmode='stack',
            title="予算 vs 実績コストの内訳 (赤色は品質負債による損失)",
            xaxis_title="金額 (円)",
            height=300
        )
        st.plotly_chart(fig_cost, use_container_width=True)
        
        st.info(f"""
        **分析結果:**
        総コストのうち、**約 {total_rework_cost/actual_cost*100:.1f}%** が「バグ修正・手戻り」などの非生産的な活動に費やされました。
        この {total_rework_cost/1000000:,.1f} 万円 は、品質管理が適切であれば削減できた可能性があります。
        """)

    with tab2:
        st.markdown("#### プロジェクト進行と累積赤字")
        
        # 2軸グラフ: 進捗(左) と 累積コスト(右)
        fig_trend = go.Figure()
        
        # 進捗
        fig_trend.add_trace(go.Scatter(
            x=df['day'], y=df['completed_work'],
            name='進捗 (SP)',
            line=dict(color='blue')
        ))
        
        # スコープライン
        fig_trend.add_trace(go.Scatter(
            x=df['day'], y=df['current_scope'],
            name='要求スコープ',
            line=dict(color='red', dash='dot')
        ))
        
        # 増員ライン
        if add_staff_num > 0:
            fig_trend.add_vline(x=add_staff_trigger, line_dash="dash", line_color="orange", annotation_text="増員")

        # コスト推移 (右軸)
        fig_trend.add_trace(go.Scatter(
            x=df['day'], y=df['cost'] * unit_price_man_day,
            name='累積コスト(円)',
            line=dict(color='green'),
            yaxis='y2'
        ))
        
        fig_trend.update_layout(
            title="進捗とコストの同時推移",
            yaxis=dict(title="スコープ (SP)"),
            yaxis2=dict(title="累積コスト (円)", overlaying='y', side='right'),
            height=450
        )
        st.plotly_chart(fig_trend, use_container_width=True)

if __name__ == "__main__":
    main()