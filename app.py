import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="centered")

# --- 設定: クラウドの金庫(Secrets)から情報を取得 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- データ取得関数 ---
def get_data():
    sheet = client.open(SPREADSHEET_NAME).worksheet('data')
    data = sheet.get_all_records()
    return sheet, data

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

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

    # === タブ2：登録・更新（ここが大きく変わりました） ===
    with tab2:
        st.header("データの登録")
        
        # カテゴリ選択をフォームの外に出す（これを選ぶと画面が再描画され、下の項目が変わる）
        st.subheader("① カテゴリを選択")
        selected_category = st.radio("登録するカテゴリを選んでください", ["PC", "車両", "iPad/携帯", "その他"], horizontal=True)

        st.subheader("② 詳細情報の入力")
        with st.form("entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_id = st.text_input("ID (資産番号など)")
                input_name = st.text_input("品名 (例: プリウス / MacBook)")
            with col2:
                input_user = st.text_input("現在の利用者")
                input_status = st.selectbox("ステータス", ["利用可能", "貸出中", "故障/修理中", "廃棄"])

            # === カテゴリごとの特別入力欄 ===
            input_syaken = ""
            input_os_detail = ""

            if selected_category == "車両":
                st.markdown("---")
                st.markdown("**🚗 車両専用項目**")
                # 日付入力（空欄許容のために入力なければNone）
                d = st.date_input("車検満了日", value=None)
                if d:
                    input_syaken = d.strftime('%Y-%m-%d')
            
            elif selected_category == "PC" or selected_category == "iPad/携帯":
                st.markdown("---")
                st.markdown("**💻 IT機器専用項目**")
                input_os_detail = st.text_input("OS・スペック・電話番号など")

            # === 登録ボタン ===
            st.markdown("---")
            submitted = st.form_submit_button("登録 / 更新")
            
            if submitted:
                if not input_id or not input_name:
                    st.error("IDと品名は必須です！")
                else:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # データの並び順: [ID, カテゴリ, 品名, 利用者, ステータス, 更新日, 車検期限, OS詳細]
                    # ※選んでいないカテゴリの項目は自動的に「空欄」になります
                    new_row = [
                        input_id, 
                        selected_category, 
                        input_name, 
                        input_user, 
                        input_status, 
                        current_time,
                        input_syaken,   # G列
                        input_os_detail # H列
                    ]
                    
                    cell = sheet.find(input_id)
                    if cell:
                        # 更新処理
                        r = cell.row
                        sheet.update(f"A{r}:H{r}", [new_row]) # AからHまで書き換え
                        st.success(f"ID: {input_id} を更新しました！")
                    else:
                        # 新規登録
                        sheet.append_row(new_row)
                        st.success(f"ID: {input_id} を新規登録しました！")
                    
                    st.rerun()

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
