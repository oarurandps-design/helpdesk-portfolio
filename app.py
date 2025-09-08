# ポートフォリオ用の閲覧専用app.py
import streamlit as st
import pandas as pd

# ------------------- アプリの基本設定 -------------------
st.set_page_config(layout="wide")

# --- CSVファイルからデータを読み込む ---
@st.cache_data # ファイル読み込みの結果をキャッシュする
def load_data():
    # --- ここが修正点！実際のファイル名に合わせる ---
    flow_df = pd.read_csv("ヘルプデスクDB - フロー定義.csv")
    steps_df = pd.read_csv("ヘルプデスクDB - ステップ定義.csv")
    tips_df = pd.read_csv("ヘルプデスクDB - Tips.csv")
    return flow_df, steps_df, tips_df

flow_df, steps_df, tips_df = load_data()

# ------------------- Streamlitのメイン処理 -------------------
st.title('ヘルプデスク ナレッジベース (Portfolio Demo)')
st.info('これはポートフォリオ用の閲覧専用デモです。データの追加や評価はできません。')

user_input = st.text_input('質問のキーワードを入力してください（例: vpn, パスワード）')

if user_input: # ボタンを押さなくても、入力されたら即座に検索
    search_term = user_input
    result = flow_df[
        flow_df['メインキーワード'].str.contains(search_term, case=False, na=False) |
        flow_df['関連キーワード'].str.contains(search_term, case=False, na=False)
    ]

    if not result.empty:
        result_df = result.iloc[[0]]
        main_keyword = result_df['メインキーワード'].iloc[0]
        graphviz_code = result_df['Graphvizコード'].iloc[0]
        text_answer_raw = result_df['対応手順'].iloc[0]
        
        st.header(f"「{main_keyword}」の解決フロー")
        if pd.notna(graphviz_code):
            st.graphviz_chart(graphviz_code)
        
        text_answer_lines = text_answer_raw.splitlines()
        # 見えない特殊な空白文字を修正
        text_answer_formatted = '  \n'.join(text_answer_lines)
        with st.expander("テキストで手順を確認する"):
            st.markdown(text_answer_formatted)
        
        st.markdown("---")
        st.header("現場のTips（経験談）")

        relevant_steps = steps_df[steps_df['フローID'] == main_keyword]
        step_options = relevant_steps.set_index('ステップID')['ステップ名'].to_dict()
        
        relevant_tips = tips_df[tips_df['フローID'] == main_keyword].sort_values(by='評価', ascending=False)
        if not relevant_tips.empty:
            for index, tip in relevant_tips.iterrows():
                step_name = step_options.get(tip['ステップID'], '不明なステップ')
                st.info(f"**ステップ: {step_name}**\n**コメント:** {tip['コメント']}\n**評価:** {tip['評価']}")
        else:
            st.write("このフローに関するTipsはまだありません。")
    else:
        st.write(f"「{search_term}」に関する情報は見つかりませんでした。")
