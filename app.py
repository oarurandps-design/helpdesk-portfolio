# ポートフォリオ用の閲覧専用app.py (UIデモ機能つき)
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

# --- CSVファイルからデータを読み込む ---
@st.cache_data
def load_data():
    try:
        flow_df = pd.read_csv("ヘルプデスクDB - フロー定義.csv")
        steps_df = pd.read_csv("ヘルプデスクDB - ステップ定義.csv")
        tips_df = pd.read_csv("ヘルプデスクDB - Tips.csv")
        return flow_df, steps_df, tips_df
    except FileNotFoundError as e:
        st.error(f"データファイルの読み込みに失敗しました。ファイル名を再確認してください: {e}")
        return None, None, None

flow_df, steps_df, tips_df = load_data()

# --- Streamlitのメイン処理 ---
if flow_df is not None:
    st.title('ヘルプデスク ナレッジベース (Portfolio Demo)')
    st.info('これはポートフォリオ用の閲覧専用デモです。実際のデータ追加や評価はできません。')

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
                st.subheader("現場のTips")
                st.info("下の各ステップをクリックすると、詳細の閲覧・投稿ができます。")

                relevant_steps = steps_df[steps_df['フローID'] == main_keyword]
                
                if relevant_steps.empty:
                    st.warning("このフローのステップが「ステップ定義」シートに登録されていません。")
                else:
                    # --- ここからが新UI！アコーディオン形式 ---
                    for index, step in relevant_steps.iterrows():
                        with st.expander(f"ステップ： {step['ステップID']}: {step['ステップ名']}"):
                            
                            selected_id = step['ステップID']
                            
                            st.write("**投稿されたTips一覧**")
                            if not tips_df.empty and 'フローID' in tips_df.columns:
                                relevant_tips = tips_df[(tips_df['フローID'] == main_keyword) & (tips_df['ステップID'] == selected_id)].sort_values(by='評価', ascending=False)
                                if not relevant_tips.empty:
                                    for i, tip in relevant_tips.iterrows():
                                        st.info(f"**コメント:** {tip['コメント']}\n**評価:** {tip['評価']}")
                                else:
                                    st.write("このステップに関するTipsはまだありません。")
                            else:
                                st.write("このステップに関するTipsはまだありません。")

                            # --- ここからが新機能！入力欄のデモ ---
                            st.markdown("---")
                            st.write("**新しいTipsを投稿する（デモ）**")
                            st.text_area(
                                "新しいTips（経験談）を共有", 
                                value="ここに新しい経験談を入力して、下のボタンでデータベースに追加できます。（※このデモ版では入力できません）", 
                                disabled=True, 
                                key=f"area_{selected_id}"
                            )
                            st.button("このステップにTipsを追加する", key=f"form_{selected_id}", disabled=True)
                            # --- ここまでが新機能 ---

        else:
            st.write(f"「{search_term}」に関する情報は見つかりませんでした。")
