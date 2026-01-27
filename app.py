import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="centered")

# --- 設定: カテゴリとシート名の対応表 ---
CATEGORY_MAP = {
    "PC": "PC",
    "訪問車": "訪問車",
    "iPad": "iPad",
    "ガラケー": "ガラケー",
    "その他": "その他"
}

# --- 設定: クラウドの金庫(Secrets)から情報を取得 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- データ取得関数 ---
def get_all_data():
    all_data = []
    for cat_name, sheet_name in CATEGORY_MAP.items():
        try:
            worksheet = client.open(SPREADSHEET_NAME).worksheet(sheet_name)
            records = worksheet.get_all_records()
            for record in records:
                record['カテゴリ'] = cat_name
            all_data.extend(records)
        except gspread.WorksheetNotFound:
            pass
    return pd.DataFrame(all_data)

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

try:
    df = get_all_data()

    main_tab1, main_tab2 = st.tabs(["🔍 一覧・検索", "📝 新規登録・更新"])

    # ==========================================
    # タブ1：一覧・検索
    # ==========================================
    with main_tab1:
        st.header("在庫データの検索")
        search_query = st.text_input("フリーワード検索", placeholder="品名、ID、利用者名など...")

        if search_query and not df.empty:
            filtered_df = df[df.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)]
            st.success(f"検索結果: {len(filtered_df)} 件")
        else:
            filtered_df = df

        st.markdown("---")

        categories = ["すべて"] + list(CATEGORY_MAP.keys())
        cat_tabs = st.tabs(categories)

        for i, category in enumerate(categories):
            with cat_tabs[i]:
                if df.empty:
                    st.info("データがありません")
                else:
                    # 1. データを絞り込む
                    if category == "すべて":
                        display_df = filtered_df.copy()
                    else:
                        display_df = filtered_df[filtered_df['カテゴリ'] == category].copy()

                    # 2. 不要な列を削除 (エラー回避の try-except 的な処理)
                    if category == "訪問車":
                        display_df = display_df.drop(columns=['OS・詳細'], errors='ignore')
                    elif category in ["PC", "iPad", "ガラケー"]:
                        display_df = display_df.drop(columns=['車検期限'], errors='ignore')
                    elif category == "その他":
                        display_df = display_df.drop(columns=['車検期限', 'OS・詳細'], errors='ignore')

                    # 3. 表示
                    st.dataframe(display_df, use_container_width=True)

    # ==========================================
    # タブ2：登録・更新
    # ==========================================
    with main_tab2:
        st.header("データの登録")
        
        st.subheader("① カテゴリを選択")
        selected_category_key = st.radio("登録するカテゴリ", list(CATEGORY_MAP.keys()), horizontal=True)
        target_sheet_name = CATEGORY_MAP[selected_category_key]

        st.subheader("② 詳細情報の入力")
        with st.form("entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_id = st.text_input("ID (資産番号など)")
                input_name = st.text_input("品名")
            with col2:
                input_user = st.text_input("利用者")
                input_status = st.selectbox("ステータス", ["利用可能", "貸出中", "故障/修理中", "廃棄"])

            input_syaken = ""
            input_os_detail = ""

            # 入力項目の表示制御
            if selected_category_key == "訪問車":
                st.markdown("---")
                st.markdown("**🚗 訪問車 専用項目**")
                d = st.date_input("車検満了日", value=None)
                if d: input_syaken = d.strftime('%Y-%m-%d')
            
            elif selected_category_key in ["PC", "iPad", "ガラケー"]:
                st.markdown("---")
                label_text = "OS・スペック" if selected_category_key == "PC" else "電話番号・契約詳細"
                st.markdown(f"**📱 {selected_category_key} 専用項目**")
                input_os_detail = st.text_input(label_text)

            st.markdown("---")
            submitted = st.form_submit_button(f"「{selected_category_key}」として登録")
            
            if submitted:
                if not input_id or not input_name:
                    st.error("IDと品名は必須です！")
                else:
                    try:
                        worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                        
                        # 日付のみのフォーマットに変更しました
                        current_time = datetime.now().strftime('%Y-%m-%d')
                        
                        new_row = [
                            input_id, selected_category_key, input_name, input_user, input_status, current_time,
                            input_syaken, input_os_detail
                        ]
                        
                        cell = worksheet.find(input_id)
                        if cell:
                            r = cell.row
                            worksheet.update(f"A{r}:H{r}", [new_row])
                            st.success(f"【{selected_category_key}】ID: {input_id} を更新しました！")
                        else:
                            worksheet.append_row(new_row)
                            st.success(f"【{selected_category_key}】ID: {input_id} を新規登録しました！")
                        
                        st.rerun()

                    except gspread.WorksheetNotFound:
                        st.error(f"エラー: シート「{target_sheet_name}」が見つかりません。")
                    except Exception as e:
                        st.error(f"書き込みエラー: {e}")

except Exception as e:
    st.error(f"全体エラー: {e}")
