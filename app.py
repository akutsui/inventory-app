import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 設定 ---
# JSONファイルの名前（ステップ2でダウンロードしたもの）
JSON_FILE = 'credentials.json' 
# スプレッドシートの名前
SPREADSHEET_NAME = 'management_db'

# --- 認証とデータ取得の関数 ---
def get_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SPREADSHEET_NAME).worksheet('data')
    data = sheet.get_all_records()
    return sheet, data

# --- アプリの画面構成 ---
st.title('📱 チーム備品管理アプリ')

try:
    # データを読み込む
    sheet, data = get_data()
    df = pd.DataFrame(data)

    # タブを作る
    tab1, tab2 = st.tabs(["一覧・検索", "新規登録・更新"])

    # === タブ1：一覧表示 ===
    with tab1:
        st.header("在庫一覧")
        
        # フィルタ機能
        category_filter = st.selectbox("カテゴリで絞り込み", ["すべて"] + list(df['カテゴリ'].unique()) if not df.empty else ["すべて"])
        
        if category_filter != "すべて":
            display_df = df[df['カテゴリ'] == category_filter]
        else:
            display_df = df
            
        st.dataframe(display_df, use_container_width=True)
        
        st.info(f"合計登録数: {len(df)} 件")

    # === タブ2：登録・更新 ===
    with tab2:
        st.header("データの登録")
        
        with st.form("entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_id = st.text_input("ID (資産番号など)")
                input_category = st.selectbox("カテゴリ", ["PC", "車両", "iPad", "携帯電話", "その他"])
                input_name = st.text_input("品名 (例: MacBook Air M1)")
            with col2:
                input_user = st.text_input("現在の利用者")
                input_status = st.selectbox("ステータス", ["利用可能", "貸出中", "故障/修理中", "廃棄"])
            
            submitted = st.form_submit_button("登録 / 更新")
            
            if submitted:
                if not input_id or not input_name:
                    st.error("IDと品名は必須です！")
                else:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_row = [input_id, input_category, input_name, input_user, input_status, current_time]
                    
                    # IDが既に存在するかチェック（簡易的な更新処理）
                    cell = sheet.find(input_id)
                    if cell:
                        # 更新処理
                        r = cell.row
                        sheet.update(f"A{r}:F{r}", [new_row])
                        st.success(f"ID: {input_id} を更新しました！")
                    else:
                        # 新規登録
                        sheet.append_row(new_row)
                        st.success(f"ID: {input_id} を新規登録しました！")
                    
                    # 画面をリロードしてデータを最新にする
                    st.rerun()

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
    st.warning("ヒント: JSONファイル名が合っているか、スプレッドシートが共有されているか確認してください。")