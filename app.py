# ポートフォリオ用の閲覧専用app.py
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

# --- CSVファイルからデータを読み込む ---
@st.cache_data
def load_data():
    try:
        # ファイル名を、GitHubにアップロードした実際のファイル名に正確に合わせる
        flow_df = pd.read_csv("ヘルプデスクDB - フロー定義.csv")
        steps_df = pd.read_csv("ヘルプデスクDB - ステップ定義.csv")
        tips_df = pd.read_csv("ヘルプデスクDB - Tips.csv")
        return flow_df, steps_df, tips_df
    except FileNotFoundError as e:
        st.error(f"データファイルの読み込みに失敗しました。ファイル名を確認してください。: {e}")
        return None, None, None

flow_df, steps_df, tips_df = load_data()

# --- Streamlitのメイン処理 ---
if flow_df is not None:
    st.title('ヘルプデスク ナレッジベース (Portfolio Demo)')
    st.info('これはポートフォリオ用の閲覧専用デモです。Tipsの投稿や評価など、書き込み機能は無効化されています。')

    user_input = st.text_input('質問のキーワードを入力してください（例: vpn, パスワード）')

    if user_input:
        search_term = user_input
        result = flow_df[
            (flow_df['メインキーワード'].str.contains(search_term, case=False, na=False)) |
            (flow_df['関連キーワード'].str.contains(search_term, case=False, na=False))
        ]

        if not result.empty:
            result_df = result.iloc[[0]]
            main_keyword = result_df['メインキーワード'].iloc[0]
            graphviz_code = result_df['Graphvizコード'].iloc[0]
            text_answer_raw = result_df['対応手順'].iloc[0]
            
            st.header(f"「{main_keyword}」の解決フロー")
            
            col1, col2 = st.columns([2, 1.5])

            with col1:
                if pd.notna(graphviz_code) and graphviz_code.strip() != "":
                    st.graphviz_chart(graphviz_code)
                else:
                    st.info("この項目にはフローチャート図が登録されていません。")
                
                with st.expander("テキストで手順全体を確認する"):
                    text_answer_lines = text_answer_raw.splitlines()
                    text_answer_formatted = '  \n'.join(text_answer_lines)
                    st.markdown(text_answer_formatted)

            with col2:
                st.subheader("関連する現場のTips")
                
                relevant_steps = steps_df[steps_df['フローID'] == main_keyword]
                step_options = relevant_steps.set_index('ステップID')['ステップ名'].to_dict()
                
                if not tips_df.empty and 'フローID' in tips_df.columns:
                    relevant_tips = tips_df[tips_df['フローID'] == main_keyword].sort_values(by='評価', ascending=False)
                    if not relevant_tips.empty:
                        for index, tip in relevant_tips.iterrows():
                            step_name = step_options.get(tip['ステップID'], '不明なステップ')
                            st.info(f"**ステップ: {step_name}**\n**コメント:** {tip['コメント']}\n**評価:** {tip['評価']}")
                    else:
                        st.write("このフローに関するTipsはまだありません。")
                else:
                    st.write("このフローに関するTipsはまだありません。")
        else:
            st.write(f"「{search_term}」に関する情報は見つかりませんでした。")
