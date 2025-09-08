import streamlit as st
import pandas as pd
from utils import get_sheets
import time
import gspread

# --- データ読み込みと自己修復機能 ---
@st.cache_data(ttl=600)
def load_all_data():
    flow_sheet, tips_sheet, steps_sheet = get_sheets()
    
    def verify_and_heal_sheet(sheet, expected_header, sheet_name):
        try:
            header = sheet.row_values(1)
        except Exception: header = []
        if header != expected_header:
            sheet.update('A1', [expected_header])
            time.sleep(1)
            st.toast(f"「{sheet_name}」シートのヘッダーを自動修復しました。", icon='🛠️')

    verify_and_heal_sheet(flow_sheet, ['メインキーワード', '関連キーワード', '対応手順', 'Graphvizコード', '評価'], "フロー定義")
    verify_and_heal_sheet(steps_sheet, ['フローID', 'ステップID', 'ステップ名'], "ステップ定義")
    verify_and_heal_sheet(tips_sheet, ['フローID', 'ステップID', 'コメント', '評価'], "Tips")

    flow_data = flow_sheet.get_all_records()
    steps_data = steps_sheet.get_all_records()
    tips_data = tips_sheet.get_all_records()

    flow_df = pd.DataFrame(flow_data)
    steps_df = pd.DataFrame(steps_data)
    tips_df = pd.DataFrame(tips_data) if tips_data else pd.DataFrame(columns=['フローID', 'ステップID', 'コメント', '評価'])
    
    return flow_df, steps_df, tips_df

# ------------------- Streamlit App Main Body -------------------
st.title('ヘルプデスク ナレッジベース')

# --- 状態管理 ---
if 'last_search' not in st.session_state: st.session_state.last_search = ""

# --- メイン処理 ---
try:
    flow_df, steps_df, tips_df = load_all_data()
except Exception as e:
    st.error(f"データベースの読み込み中にエラーが発生しました。エラー詳細: {e}")
    st.stop()

# --- 検索フォーム ---
with st.form(key='search_form'):
    user_input = st.text_input('質問のキーワードを入力してください', value=st.session_state.last_search)
    search_button = st.form_submit_button('検索する')

if search_button:
    st.session_state.last_search = user_input

if st.session_state.last_search:
    search_term = st.session_state.last_search
    
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
                        
                        # 投稿されたTips一覧
                        if '評価' in tips_df.columns:
                            tips_df['評価'] = pd.to_numeric(tips_df['評価'], errors='coerce').fillna(0)
                        
                        relevant_tips = tips_df[(tips_df['フローID'] == main_keyword) & (tips_df['ステップID'] == selected_id)].sort_values(by='評価', ascending=False)
                        
                        if not relevant_tips.empty:
                            for i, tip in relevant_tips.iterrows():
                                st.info(f"**コメント:** {tip['コメント']}")
                                if st.button(f"👍 参考になった ({tip['評価']})", key=f"tip_{i}"):
                                    _, tips_sheet_writer, _ = get_sheets()
                                    tip_row_index = i + 2
                                    tips_cols = tips_sheet_writer.row_values(1)
                                    tip_col_index = tips_cols.index('評価') + 1
                                    new_rating = int(tip['評価']) + 1
                                    tips_sheet_writer.update_cell(tip_row_index, tip_col_index, new_rating)
                                    st.cache_data.clear()
                                    st.rerun()
                        else:
                            st.write("このステップに関するTipsはまだありません。")

                        # 新しいTipsを投稿するフォーム
                        with st.form(key=f"form_{selected_id}"):
                            new_comment = st.text_area("新しいTips（経験談）を共有", key=f"area_{selected_id}")
                            submit_button = st.form_submit_button("このステップにTipsを追加する")
                            if submit_button and new_comment:
                                _, tips_sheet_writer, _ = get_sheets()
                                new_row = [main_keyword, selected_id, new_comment, 0]
                                tips_sheet_writer.append_row(new_row)
                                st.cache_data.clear()
                                st.success("新しいTipsを共有しました！")
                                st.rerun()
    else:
        if st.session_state.last_search != "":
            st.write(f"「{st.session_state.last_search}」に関する情報は見つかりませんでした。")
