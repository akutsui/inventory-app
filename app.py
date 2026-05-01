import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- CSS (UI調整: 極限までコンパクト化) ---
st.markdown("""
    <style>
        /* メインエリアの上部余白 */
        .block-container {
            padding-top: 4rem !important;
            padding-bottom: 5rem;
        }

        /* タイトルの固定 */
        div[data-testid="stVerticalBlock"] > div:has(h1) {
            position: sticky !important;
            top: 2.875rem !important;
            background-color: white !important;
            z-index: 1000 !important;
            padding-top: 1rem !important;
            padding-bottom: 0.5rem !important;
            border-bottom: 2px solid #f0f2f6;
            margin-bottom: 0 !important;
        }
        
        h1 {
            margin: 0 !important;
            padding: 0 !important;
            font-size: 1.8rem !important;
        }

        /* タブバーの固定 */
        div[data-baseweb="tab-list"],
        div[role="tablist"],
        div[data-testid="stTabs"] > div:first-child {
            position: sticky !important;
            top: 6.8rem !important;
            background-color: white !important;
            z-index: 999 !important;
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        div[data-testid="stTabs"] button {
            background-color: white !important;
        }

        /* === 行間短縮のための設定 === */
        
        /* ボタンを小さく薄く */
        .stButton button {
            height: 1.6rem !important;
            min-height: 1.6rem !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 2px !important;
            font-size: 0.8rem !important;
        }
        
        /* テキストの行間・余白を削除 */
        p {
            margin-bottom: 0px !important;
            padding-bottom: 0px !important;
            font-size: 0.9rem !important;
            line-height: 1.7rem !important;
        }
        
        /* 区切り線(hr)の余白を極小に */
        hr {
            margin: 2px 0 !important;
            padding: 0 !important;
        }
        
        /* 列(カラム)内の余白削除 */
        div[data-testid="column"] {
            padding: 0px !important;
        }
        
        /* 要素間の垂直ギャップを詰める */
        div.stMarkdown {
            margin-bottom: 0px !important;
        }
        
        /* アラート外枠のパディング調整 */
        div.alert-box {
            padding: 0.5rem 1rem !important;
        }
        
        /* トグルスイッチの位置調整 */
        div[data-testid="stToggle"] {
            margin-top: 0px;
            padding-top: 5px;
        }
        div[data-testid="stToggle"] label {
            font-size: 0.9rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- 設定: カテゴリとシート名の対応表 ---
CATEGORY_MAP = {
    "PC": "PC",
    "訪問車": "訪問車",
    "iPad": "iPad",
    "携帯電話": "携帯電話",
    "Office365": "Office365",
    "ウイルスバスター": "ウイルスバスター",
    "その他機器": "その他機器"
}

# --- 設定: 各ページ用定数 ---
SHEET_NEW_EMPLOYEE = "新規入職者"
SHEET_CERTIFICATE = "電子証明書"
ONBOARDING_TASKS = ["PC", "iPad", "携帯", "駐車場", "LineworksID", "モバカルモバナーID", "MCS", "アルコールチェックID", "訪問車両", "備品", "机・椅子", "三文判", "シャチハタ"]

# --- 設定: 各シートの列定義 (ウイルスバスターに利用者4〜6を追加) ---
COLUMNS_DEF = {
    "PC": ["使用部署", "購入日", "OS", "プロダクトID(シリアルNo)", "ラベル", "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", "officeのアカウント割振", "ウィルスバスターシリアルNo", "ウィルスバスター期限", "ウィルスバスター識別ネーム", "チームビューワID", "チームビューワPW", "備考"],
    "訪問車": ["登録番号", "洗車グループ", "駐車場", "タイヤサイズ", "スタッドレス有無", "タイヤ保管場所", "リース開始日", "リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日", "使用部署", "備考"],
    "iPad": ["購入日", "ラベル", "AppleID", "AppleIDパスワード", "シリアルNo", "ストレージ", "製造番号IMEI", "端末番号", "使用部署", "キャリア", "備考"],
    "携帯電話": ["購入日", "電話番号", "SIM", "メーカー", "製造番号", "使用部署", "保管場所", "キャリア", "備考"],
    "Office365": ["アカウントID", "パスワード", "利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "備考"],
    "ウイルスバスター": ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"],
    "その他機器": ["使用部署", "使用場所", "使用開始日", "備考"]
}

# --- Google Sheets API 接続 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- セッションステート初期化 ---
if 'page_number' not in st.session_state: st.session_state['page_number'] = 0
if 'active_search_query' not in st.session_state: st.session_state['active_search_query'] = ""
if 'zaiko_reg_success' not in st.session_state: st.session_state.zaiko_reg_success = False
if 'emp_reg_success' not in st.session_state: st.session_state.emp_reg_success = False
if 'cert_reg_success' not in st.session_state: st.session_state.cert_reg_success = False

# --- データ取得・補助関数 ---
@st.cache_data(ttl=600)
def get_all_data():
    all_data = []
    for cat_name, sheet_name in CATEGORY_MAP.items():
        try:
            worksheet = client.open(SPREADSHEET_NAME).worksheet(sheet_name)
            records = worksheet.get_all_records(value_render_option='FORMATTED_VALUE')
            for record in records: record['カテゴリ'] = cat_name
            all_data.extend(records)
        except: pass
    df = pd.DataFrame(all_data)
    if not df.empty:
        df['sort_order'] = df['ステータス'].apply(lambda x: 1 if x == '廃棄' else 0)
        df = df.sort_values(by=['sort_order', 'ID'], ascending=[True, True])
    return df

def generate_auto_id(df_target, prefix, id_col='ID'):
    if df_target is None or df_target.empty: return f"{prefix}0001"
    max_num = 0
    if id_col in df_target.columns:
        for val in df_target[id_col].astype(str):
            val = val.strip()
            if val.startswith(prefix):
                try:
                    num = int(val[len(prefix):])
                    if num > max_num: max_num = num
                except: pass
    return f"{prefix}{max_num + 1:04d}"

def get_auto_id(category, current_df):
    prefix_dict = {"PC":"A","訪問車":"B","iPad":"C","携帯電話":"D","Office365":"E","ウイルスバスター":"F","その他機器":"G"}
    return generate_auto_id(current_df[current_df['カテゴリ']==category] if not current_df.empty else None, prefix_dict.get(category, "Z"))

def get_new_employee_data():
    try: return pd.DataFrame(client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE).get_all_records())
    except: return pd.DataFrame()

def get_certificate_data():
    try: return pd.DataFrame(client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE).get_all_records())
    except: return pd.DataFrame()

def parse_date(date_val):
    if not date_val: return None
    try:
        date_str = str(date_val).replace('.', '/').replace('-', '/').replace('年', '/').replace('月', '/').replace('日', '')
        return pd.to_datetime(date_str).to_pydatetime()
    except: return None

def safe_text(text): return str(text).replace("@", "@\u200B")

def submit_search():
    st.session_state.active_search_query = st.session_state.input_search_key
    st.session_state.input_search_key = "" 
    st.session_state.page_number = 0

# --- ダイアログ関数 ---
@st.dialog("📝 詳細情報の編集")
def show_detail_dialog(row_data):
    cat = row_data['カテゴリ']
    with st.form("edit_dialog_form"):
        st.write(f"**ID:** {row_data['ID']} / **カテゴリ:** {cat}")
        c1, c2 = st.columns(2)
        with c1: new_name = st.text_input("品名", value=row_data.get('品名', ''))
        with c2: new_user = st.text_input("利用者(代表)", value=row_data.get('利用者', ''))
        
        status_options = ["利用可能", "利用中", "貸出中", "故障/修理中", "廃棄"]
        new_status = st.selectbox("ステータス", status_options, index=status_options.index(row_data['ステータス']) if row_data['ステータス'] in status_options else 0)
        
        st.markdown("---")
        custom_values = {}
        
        # ウイルスバスター用の2列レイアウト
        if cat == "ウイルスバスター":
            v1, v2 = st.columns(2)
            with v1:
                custom_values['利用者1'] = st.text_input("利用者1", value=row_data.get('利用者1', ''))
                custom_values['利用者2'] = st.text_input("利用者2", value=row_data.get('利用者2', ''))
                custom_values['利用者3'] = st.text_input("利用者3", value=row_data.get('利用者3', ''))
            with v2:
                custom_values['利用者4'] = st.text_input("利用者4", value=row_data.get('利用者4', ''))
                custom_values['利用者5'] = st.text_input("利用者5", value=row_data.get('利用者5', ''))
                custom_values['利用者6'] = st.text_input("利用者6", value=row_data.get('利用者6', ''))
            d_exp = st.date_input("期限", value=parse_date(row_data.get('期限')))
            custom_values['期限'] = d_exp.strftime('%Y-%m-%d') if d_exp else ''
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))
        else:
            for col in COLUMNS_DEF.get(cat, []):
                custom_values[col] = st.text_input(col, value=row_data.get(col, ''))

        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(CATEGORY_MAP[cat])
            cell = worksheet.find(str(row_data['ID']))
            if cell:
                row_to_save = [row_data['ID'], cat, new_name, new_user, new_status, datetime.now().strftime('%Y-%m-%d')]
                for col in COLUMNS_DEF[cat]: row_to_save.append(custom_values.get(col, ''))
                worksheet.update(f"A{cell.row}", [row_to_save])
                get_all_data.clear(); st.success("更新しました！"); st.rerun()

@st.dialog("📝 入職準備タスク管理")
def show_onboarding_task_dialog(row_data):
    with st.form("onboarding_task_form"):
        c1, c2 = st.columns(2)
        with c1: new_name = st.text_input("氏名", value=row_data.get('氏名', ''))
        with c2: new_furi = st.text_input("フリガナ", value=row_data.get('フリガナ', ''))
        st.markdown("---")
        task_status = {}
        cols = st.columns(2)
        for i, task in enumerate(ONBOARDING_TASKS):
            with cols[i % 2]: task_status[task] = st.text_input(task, value=row_data.get(task, ''))
        st.markdown("---")
        new_status = st.selectbox("全体のステータス", ["準備中", "完了", "保留"], index=0)
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data['ID'], "氏名":new_name, "フリガナ":new_furi, "入職日":row_data['入職日'], "職種":row_data['職種'], "部署":row_data['部署'], "ステータス":new_status, "備考":new_note}
            for t in ONBOARDING_TASKS: data_dict[t] = task_status[t]
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data['ID']))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save]); st.success("更新しました！"); st.rerun()

@st.dialog("📝 電子証明書の編集")
def show_cert_dialog(row_data):
    with st.form("cert_edit_form"):
        new_type = st.text_input("種類", value=row_data.get('種類', ''))
        new_dev = st.text_input("端末", value=row_data.get('端末', ''))
        new_exp = st.date_input("有効期限", value=parse_date(row_data.get('有効期限')))
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data['ID'], "種類":new_type, "端末":new_dev, "有効期限":str(new_exp), "備考":new_note}
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data['ID']))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save]); st.success("更新しました！"); st.rerun()

# --- メイン画面構成 ---
st.title('📱 総務備品管理アプリ')

with st.sidebar:
    page_selection = st.radio("メニュー切替", ["📦 在庫管理 (メイン)", "👤 新規入職者管理", "🔐 電子証明書管理", "📅 5年経過リスト (PC/iPad)"])
    if st.button("🔄 データを最新にする"): get_all_data.clear(); st.rerun()

# ==========================================
# ページ1：在庫管理 (メイン)
# ==========================================
if page_selection == "📦 在庫管理 (メイン)":
    main_tab1, main_tab2, main_tab3 = st.tabs(["🔍 一覧・検索", "📝 新規登録", "📂 CSV一括入出力"])

    with main_tab1:
        df = get_all_data()
        # 訪問車アラート
        today = datetime.now().date()
        alert_items = []
        if not df.empty:
            for _, row in df[df['カテゴリ']=="訪問車"].iterrows():
                if row['ステータス'] == '廃棄': continue
                check_cols = ["リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日"]
                for col in check_cols:
                    dt = parse_date(row.get(col))
                    if dt and (dt.date() - today).days <= 45:
                        alert_items.append(f"【{row['品名']}】{col}: あと{(dt.date()-today).days}日")
        
        if alert_items:
            st.error("⚠️ 訪問車期日アラート (45日以内)\n\n" + "\n".join(alert_items))

        st.text_input("フリーワード検索", placeholder="Enterで検索", key="input_search_key", on_change=submit_search)
        
        # カテゴリ別タブ
        cat_tabs = st.tabs(["すべて"] + list(CATEGORY_MAP.keys()))
        for i, category in enumerate(["すべて"] + list(CATEGORY_MAP.keys())):
            with cat_tabs[i]:
                display_df = df if category == "すべて" else df[df['カテゴリ']==category]
                if st.session_state.active_search_query:
                    display_df = display_df[display_df.astype(str).apply(lambda row: row.str.contains(st.session_state.active_search_query, case=False).any(), axis=1)]
                
                for idx, row in display_df.head(50).iterrows():
                    c = st.columns([0.8, 1, 3, 2, 1.5, 1])
                    if c[0].button("詳細", key=f"btn_{idx}"): show_detail_dialog(row)
                    c[1].write(row['ID'])
                    c[2].write(f"**{safe_text(row['品名'])}**")
                    c[3].write(row['利用者'])
                    c[4].write(row['ステータス'])
                    c[5].write(row.get('購入日', row.get('登録番号', '')))
                    st.markdown("<hr>", unsafe_allow_html=True)

    with main_tab2:
        if st.session_state.zaiko_reg_success:
            st.success("✅ 登録完了しました！"); st.button("続けて登録する", on_click=lambda: setattr(st.session_state, 'zaiko_reg_success', False))
        else:
            with st.form("zaiko_reg"):
                cat = st.radio("カテゴリ", list(CATEGORY_MAP.keys()), horizontal=True)
                auto_id = get_auto_id(cat, get_all_data())
                i_id = st.text_input("ID ※自動採番", value=auto_id)
                i_name = st.text_input("品名")
                i_user = st.text_input("利用者")
                custom_vals = {}
                if cat == "ウイルスバスター":
                    v1, v2 = st.columns(2)
                    with v1: 
                        custom_vals['利用者1'] = st.text_input("利用者1")
                        custom_vals['利用者2'] = st.text_input("利用者2")
                        custom_vals['利用者3'] = st.text_input("利用者3")
                    with v2:
                        custom_vals['利用者4'] = st.text_input("利用者4")
                        custom_vals['利用者5'] = st.text_input("利用者5")
                        custom_vals['利用者6'] = st.text_input("利用者6")
                    custom_vals['期限'] = str(st.date_input("期限"))
                else:
                    for col in COLUMNS_DEF[cat]: custom_vals[col] = st.text_input(col)
                
                if st.form_submit_button("登録"):
                    ws = client.open(SPREADSHEET_NAME).worksheet(CATEGORY_MAP[cat])
                    row = [i_id, cat, i_name, i_user, "利用可能", datetime.now().strftime('%Y-%m-%d')]
                    for col in COLUMNS_DEF[cat]: row.append(custom_vals.get(col, ""))
                    ws.append_row(row); st.session_state.zaiko_reg_success = True; st.rerun()

# ==========================================
# ページ2：新規入職者管理
# ==========================================
elif page_selection == "👤 新規入職者管理":
    t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
    df_emp = get_new_employee_data()
    with t1:
        if not df_emp.empty:
            for idx, row in df_emp.iterrows():
                c = st.columns([1, 1, 2, 2, 2, 2])
                if c[0].button("詳細", key=f"emp_{idx}"): show_onboarding_task_dialog(row)
                c[1].write(row['ID'])
                c[2].write(f"**{row['氏名']}**")
                c[3].write(row['フリガナ'])
                c[4].write(row['入職日'])
                c[5].write(row['ステータス'])
                st.markdown("<hr>", unsafe_allow_html=True)
    with t2:
        if st.session_state.emp_reg_success:
            st.success("✅ 登録しました"); st.button("次を登録", on_click=lambda: setattr(st.session_state, 'emp_reg_success', False))
        else:
            with st.form("emp_reg"):
                e_id = st.text_input("ID", value=generate_auto_id(df_emp, "H"))
                e_name = st.text_input("氏名")
                e_furi = st.text_input("フリガナ")
                e_date = st.date_input("入職日")
                if st.form_submit_button("登録"):
                    ws = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
                    # 全列分の空データを作成(21項目)
                    new_row = [e_id, e_name, e_furi, str(e_date), "", "", "準備中"] + [""]*13 + [""]
                    ws.append_row(new_row); st.session_state.emp_reg_success = True; st.rerun()

# ==========================================
# ページ3：電子証明書管理
# ==========================================
elif page_selection == "🔐 電子証明書管理":
    t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
    df_cert = get_certificate_data()
    with t1:
        today = datetime.now().date()
        for idx, row in df_cert.iterrows():
            dt = parse_date(row.get('有効期限'))
            if dt and (dt.date() - today).days <= 75:
                msg = f"あと{(dt.date()-today).days}日" if (dt.date()-today).days >= 0 else "超過"
                st.warning(f"**【{row['端末']}】{row['種類']} : 有効期限 {msg} ({dt.strftime('%Y-%m-%d')})**")
        st.dataframe(df_cert, use_container_width=True)
    with t2:
        with st.form("cert_reg"):
            c_id = st.text_input("ID", value=generate_auto_id(df_cert, "I"))
            c_type = st.text_input("種類")
            c_dev = st.text_input("端末")
            c_exp = st.date_input("有効期限")
            if st.form_submit_button("登録"):
                ws = client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE)
                ws.append_row([c_id, c_type, c_dev, str(c_exp), ""]); st.success("登録しました"); st.rerun()

# ==========================================
# ページ4：5年経過リスト
# ==========================================
elif page_selection == "📅 5年経過リスト (PC/iPad)":
    st.info("購入から5年以上経過したPCおよびiPadを表示します。")
    df = get_all_data()
    if not df.empty:
        df_old = df[df['カテゴリ'].isin(['PC', 'iPad'])]
        five_years_ago = datetime.now() - timedelta(days=365*5)
        df_old['dt'] = df_old['購入日'].apply(parse_date)
        df_old = df_old[df_old['dt'] <= five_years_ago]
        st.dataframe(df_old.drop(columns=['dt']), use_container_width=True)
