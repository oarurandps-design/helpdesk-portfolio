import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import google.generativeai as genai

# ------------------- アプリの基本設定と認証情報 -------------------
st.set_page_config(layout="wide")

# Googleドライブ内のファイルパスを指定
JSON_FILE_PATH = "/content/drive/MyDrive/HelpdeskApp/helpdesk-tool-project-7c8c8f2bbdc0.json"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/13z7a4EKuFcLJxePVkPZMdWQq-ZGDqWrPuI88aMpYNEY/edit?usp=sharing"

# --- st.session_stateの初期化 ---
if 'last_search' not in st.session_state: st.session_state.last_search = ""
if 'generated_data' not in st.session_state: st.session_state.generated_data = None
if 'gemini_api_key' not in st.session_state: st.session_state.gemini_api_key = None

# ------------------- 認証とクライアント接続 -------------------
@st.cache_resource
def authorize_gspread():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(JSON_FILE_PATH, scopes=scopes)
    client = gspread.authorize(creds)
    return client

client = authorize_gspread()
spreadsheet = client.open_by_url(SPREADSHEET_URL)
flow_sheet = spreadsheet.worksheet("フロー定義")
tips_sheet = spreadsheet.worksheet("Tips")
steps_sheet = spreadsheet.worksheet("ステップ定義")

# ------------------- ページを分割するためのサイドバー -------------------
page = st.sidebar.radio("ページを選択", ["ヘルプデスク検索", "ナレッジ自動登録・更新"])

# ===================================================================
# =================== ヘルプデスク検索ページ ========================
# ===================================================================
if page == "ヘルプデスク検索":
    st.title('ヘルプデスク ナレッジベース')
    user_input = st.text_input('質問のキーワードを入力してください（例: vpn, パスワード）', st.session_state.last_search)
    if st.button('検索する'):
        st.session_state.last_search = user_input

    if st.session_state.last_search:
        search_term = st.session_state.last_search
        flow_data = flow_sheet.get_all_records()
        flow_df = pd.DataFrame(flow_data)
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
            st.graphviz_chart(graphviz_code)
            
            text_answer_lines = text_answer_raw.splitlines()
            text_answer_formatted = '  \n'.join(text_answer_lines)
            with st.expander("テキストで手順を確認する"):
                st.markdown(text_answer_formatted)
            
            st.markdown("---")
            st.header("現場のTips（経験談）")

            steps_data = steps_sheet.get_all_records()
            steps_df = pd.DataFrame(steps_data)
            relevant_steps = steps_df[steps_df['フローID'] == main_keyword]
            
            st.subheader("新しいTipsを投稿する")
            step_options = relevant_steps.set_index('ステップID')['ステップ名'].to_dict()

            if not step_options:
                st.warning("このフローのステップが「ステップ定義」シートに登録されていません。")
            else:
                selected_step_id = st.selectbox(
                    "Tipsを投稿するステップを選択してください",
                    options=list(step_options.keys()),
                    format_func=lambda x: step_options.get(x, "不明なステップ")
                )
                with st.form(key="new_tip_form"):
                    new_comment = st.text_area("新しいTips（経験談）を共有")
                    submit_button = st.form_submit_button("このステップにTipsを追加する")
                    if submit_button and new_comment:
                        new_row = [main_keyword, selected_step_id, new_comment, 0]
                        tips_sheet.append_row(new_row)
                        st.success("新しいTipsを共有しました！")
                        st.rerun()

            st.subheader("投稿されたTips一覧")
            tips_data = tips_sheet.get_all_records()
            tips_df = pd.DataFrame(tips_data) if tips_data else pd.DataFrame()

            if not tips_df.empty:
                relevant_tips = tips_df[tips_df['フローID'] == main_keyword].sort_values(by='評価', ascending=False)
                if not relevant_tips.empty:
                    for index, tip in relevant_tips.iterrows():
                        step_name = step_options.get(tip['ステップID'], '不明なステップ')
                        st.info(f"**ステップ: {step_name}**\n**コメント:** {tip['コメント']}")
                        if st.button(f"👍 参考になった ({tip['評価']})", key=f"tip_{index}"):
                            tip_row_index = index + 2
                            tips_cols = tips_sheet.row_values(1)
                            tip_col_index = tips_cols.index('評価') + 1
                            new_rating = int(tip['評価']) + 1
                            tips_sheet.update_cell(tip_row_index, tip_col_index, new_rating)
                            st.success("評価を更新しました！")
                            st.rerun()
                else:
                    st.write("このフローに関するTipsはまだありません。")
            else:
                st.write("このフローに関するTipsはまだありません。")
        else:
            st.write(f"「{search_term}」に関する情報は見つかりませんでした。")

# ===================================================================
# =================== ナレッジ自動登録・更新ページ ==================
# ===================================================================
elif page == "ナレッジ自動登録・更新":
    st.title("ナレッジ自動登録・更新システム")
    if not st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = st.text_input("Gemini APIキーを入力してください", type="password")
        st.warning("APIキーを入力してEnterキーを押すと、下のフォームが表示されます。")

    if st.session_state.gemini_api_key:
        genai.configure(api_key=st.session_state.gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        with st.form(key='generation_form'):
            st.subheader("1. 基本情報を入力")
            main_keyword = st.text_input("メインキーワード *", help="例: PC動作不良")
            related_keywords = st.text_input("関連キーワード（カンマ区切り）", help="例: 遅い, 重い, フリーズ")
            st.subheader("2. 対応手順（テキスト版）を入力")
            procedure_text = st.text_area("対応手順テキスト *", height=200)
            generate_button = st.form_submit_button("GraphvizコードをAIで生成 ＆ 内容確認")
        
        if generate_button and procedure_text:
            prompt_1 = f"""
            あなたは、テキストをGraphvizのDOT言語に変換する機械です。
            指示されたルールと以下の具体例に厳密に従って、与えられたテキストを変換してください。
            # (プロンプト内容は省略)...
            # 変換対象の対応手順テキスト:
            {procedure_text}
            """
            
            with st.spinner("AIが翻訳中です... (1回目)"):
                response_1 = model.generate_content(prompt_1)
                graphviz_code = None
                try:
                    graphviz_code = response_1.text.split("```dot")[1].split("```")[0].strip()
                except IndexError:
                    st.warning("AIが指示を誤解したため、再指示を出します...")
                    prompt_2 = f"""
                    あなたの前回の回答は、指示された形式に違反していました。
                    前回の回答: "{response_1.text}"
                    これはGraphvizコードではありません。フィードバックや改善提案は不要です。
                    もう一度、以下のテキストを、```dot ... ```で囲まれたGraphvizコードのみで回答してください。
                    # 変換対象テキスト:
                    {procedure_text}
                    """
                    with st.spinner("AIを再教育中です... (2回目)"):
                        response_2 = model.generate_content(prompt_2)
                        try:
                            graphviz_code = response_2.text.split("```dot")[1].split("```")[0].strip()
                        except IndexError:
                            st.error("AIの再教育に失敗しました。AIが頑固なようです。")
                            st.text(response_2.text)
            
            if graphviz_code:
                nodes = re.findall(r'^\s*(\w+)\s*\[.*label="([^"]+)".*\];$', graphviz_code, re.MULTILINE)
                steps_data = [[main_keyword, sid, sl.replace('\\n', ' ')] for sid, sl in nodes]
                steps_df = pd.DataFrame(steps_data, columns=["フローID", "ステップID", "ステップ名"])
                st.session_state.generated_data = {
                    "main_keyword": main_keyword,
                    "related_keywords": related_keywords,
                    "procedure_text": procedure_text,
                    "graphviz_code": graphviz_code,
                    "steps_df": steps_df
                }

        if 'generated_data' in st.session_state and st.session_state.generated_data:
            st.markdown("---")
            st.subheader("3. 生成内容の確認と登録・更新")
            gen_data = st.session_state.generated_data
            
            st.write(f"**メインキーワード:** {gen_data['main_keyword']}")
            st.write(f"**関連キーワード:** {gen_data['related_keywords']}")
            st.write("**生成されたGraphvizコード:**")
            st.code(gen_data['graphviz_code'], language='dot')
            st.write("**抽出されたステップ定義:**")
            st.table(gen_data['steps_df'])

            if st.button("この内容でデータベースに登録・更新する"):
                flow_data = flow_sheet.get_all_records()
                flow_df = pd.DataFrame(flow_data)
                existing_row = flow_df[flow_df['メインキーワード'] == gen_data['main_keyword']]
                
                with st.spinner("データベースに登録・更新中..."):
                    if not existing_row.empty:
                        # 更新処理
                        row_index = existing_row.index[0] + 2
                        if gen_data['related_keywords']: flow_sheet.update_cell(row_index, 2, gen_data['related_keywords'])
                        if gen_data['procedure_text']: flow_sheet.update_cell(row_index, 3, gen_data['procedure_text'])
                        if gen_data['graphviz_code']:
                            flow_sheet.update_cell(row_index, 4, gen_data['graphviz_code'])
                            # 古いステップ定義を削除
                            steps_to_delete_df = pd.DataFrame(steps_sheet.get_all_records())
                            if not steps_to_delete_df.empty:
                                indices_to_delete = steps_to_delete_df[steps_to_delete_df['フローID'] == gen_data['main_keyword']].index
                                for i in sorted(indices_to_delete, reverse=True):
                                    steps_sheet.delete_rows(int(i) + 2)
                            
                            # 新しいステップ定義を追加
                            steps_to_append = gen_data['steps_df'].values.tolist()
                            if steps_to_append:
                                steps_sheet.append_rows(steps_to_append)
                        st.success(f"既存ナレッジ「{gen_data['main_keyword']}」を更新しました！")
                    else:
                        # 新規登録処理
                        new_flow_row = [gen_data['main_keyword'], gen_data['related_keywords'], gen_data['procedure_text'], gen_data['graphviz_code'], 0]
                        flow_sheet.append_row(new_flow_row)
                        steps_to_append = gen_data['steps_df'].values.tolist()
                        if steps_to_append:
                            steps_sheet.append_rows(steps_to_append)
                        st.success(f"新しいナレッジ「{gen_data['main_keyword']}」を完全登録しました！")
                    
                    st.session_state.generated_data = None
                    st.rerun()