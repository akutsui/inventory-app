import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="centered")

# --- 設定: カテゴリとシート名の対応表 ---
# ここを「携帯電話」に変更しました
CATEGORY_MAP = {
    "PC": "PC",
    "訪問車": "訪問車",
    "iPad": "iPad",
    "携帯電話": "携帯電話",
    "その他": "その他"
}

# --- 設定: クラウドの金庫(Secrets)から情報を取得 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- セッションステートの初期化 ---
if 'form_data' not in st.session_state:
    st.session_state['form_data'] = {}

# --- データ取得関数（キャッシュ機能付き） ---
@st.cache_data(ttl=600)
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
        except Exception:
            pass
    return pd.DataFrame(all_data)

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

# 手動更新ボタン
if st.sidebar.button("🔄 データを最新にする"):
    get_all_data.clear()
    st.rerun()

try:
    df = get_all_data()

    main_tab1, main_tab2 = st.tabs(["🔍 一覧・検索", "📝 新規登録・編集"])

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
                    if category == "すべて":
                        display_df = filtered_df.copy()
                    else:
                        display_df = filtered_df[filtered_df['カテゴリ'] == category].copy()

                    # 不要な列を削除（ここも携帯電話に対応）
                    if category == "訪問車":
                        display_df = display_df.drop(columns=['OS・詳細'], errors='ignore')
                    elif category in ["PC", "iPad", "携帯電話"]:
                        display_df = display_df.drop(columns=['車検期限'], errors='ignore')
                    elif category == "その他":
                        display_df = display_df.drop(columns=['車検期限', 'OS・詳細'], errors='ignore')

                    st.dataframe(display_df, use_container_width=True)

    # ==========================================
    # タブ2：登録・更新
    # ==========================================
    with main_tab2:
        st.header("データの登録・編集")
        
        st.subheader("① カテゴリとIDを指定")
        selected_category_key = st.radio("カテゴリ", list(CATEGORY_MAP.keys()), horizontal=True)
        target_sheet_name = CATEGORY_MAP[selected_category_key]

        col_load1, col_load2 = st.columns([3, 1])
        with col_load1:
            input_search_id = st.text_input("編集する場合はIDを入力して「呼び出す」を押してください", key="search_id_input")
        with col_load2:
            st.write("") 
            st.write("") 
            load_btn = st.button("📥 データを呼び出す")

        # 呼び出し処理
        if load_btn and input_search_id:
            try:
                worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                cell = worksheet.find(input_search_id)
                if cell:
                    row_data = worksheet.get_all_records()[cell.row - 2]
                    st.session_state['form_data'] = {
                        'ID': row_data['ID'],
                        '品名': row_data['品名'],
                        '利用者': row_data['利用者'],
                        'ステータス': row_data['ステータス'],
                        '車検期限': row_data.get('車検期限', ''),
                        'OS・詳細': row_data.get('OS・詳細', '')
                    }
                    st.success(f"ID: {input_search_id} を読み込みました。")
                else:
                    st.error("指定されたIDは見つかりませんでした。")
                    st.session_state['form_data'] = {}
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

        # 入力フォーム
        st.subheader("② 詳細情報の入力")
        current_data = st.session_state.get('form_data', {})
        default_id = current_data.get('ID', '') if current_data.get('ID') == input_search_id else input_search_id
        
        with st.form("entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_id = st.text_input("ID (資産番号など)", value=default_id)
                input_name = st.text_input("品名", value=current_data.get('品名', ''))
            with col2:
                input_user = st.text_input("利用者", value=current_data.get('利用者', ''))
                status_options = ["利用可能", "貸出中", "故障/修理中", "廃棄"]
                current_status = current_data.get('ステータス', '利用可能')
                index_status = status_options.index(current_status) if current_status in status_options else 0
                input_status = st.selectbox("ステータス", status_options, index=index_status)

            input_syaken = ""
            input_os_detail = ""

            # カテゴリ別入力欄（ここも携帯電話に対応）
            if selected_category_key == "訪問車":
                st.markdown("---")
                st.markdown("**🚗 訪問車 専用項目**")
                saved_date = current_data.get('車検期限', '')
                default_date = None
                if saved_date:
                    try:
                        default_date = datetime.strptime(saved_date, '%Y-%m-%d')
                    except:
                        default_date = None
                d = st.date_input("車検満了日", value=default_date)
                if d: input_syaken = d.strftime('%Y-%m-%d')
            
            elif selected_category_key in ["PC", "iPad", "携帯電話"]:
                st.markdown("---")
                label_text = "OS・スペック" if selected_category_key == "PC" else "電話番号・契約詳細"
                st.markdown(f"**📱 {selected_category_key} 専用項目**")
                input_os_detail = st.text_input(label_text, value=current_data.get('OS・詳細', ''))

            st.markdown("---")
            submitted = st.form_submit_button(f"「{selected_category_key}」として登録 / 更新")
            
            if submitted:
                if not input_id or not input_name:
                    st.error("IDと品名は必須です！")
                else:
                    try:
                        worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                        current_time = datetime.now().strftime('%Y-%m-%d')
                        
                        new_row = [
                            input_id, selected_category_key, input_name, input_user, input_status, current_time,
                            input_syaken, input_os_detail
                        ]
                        
                        cell = worksheet.find(input_id)
                        if cell:
                            r = cell.row
                            worksheet.update(f"A{r}:H{r}", [new_row])
                            st.success(f"更新完了！")
                        else:
                            worksheet.append_row(new_row)
                            st.success(f"新規登録完了！")
                        
                        get_all_data.clear()
                        st.session_state['form_data'] = {}
                        st.rerun()

                    except Exception as e:
                        st.error(f"書き込みエラー: {e}")

except Exception as e:
    st.error(f"エラー: {e}")
