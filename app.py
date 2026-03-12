import streamlit as st
import pd as pd
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- CSS (UI調整) ---
st.markdown("""
    <style>
        .block-container { padding-top: 4rem !important; padding-bottom: 5rem; }
        div[data-testid="stVerticalBlock"] > div:has(h1) {
            position: sticky !important; top: 2.875rem !important; background-color: white !important;
            z-index: 1000 !important; padding-top: 1rem !important; padding-bottom: 0.5rem !important;
            border-bottom: 2px solid #f0f2f6; margin-bottom: 0 !important;
        }
        h1 { margin: 0 !important; padding: 0 !important; font-size: 1.8rem !important; }
        div[data-baseweb="tab-list"], div[role="tablist"] {
            position: sticky !important; top: 6.8rem !important; background-color: white !important;
            z-index: 999 !important; padding-top: 0.5rem !important; padding-bottom: 0.5rem !important;
        }
        .stButton button { height: 1.6rem !important; min-height: 1.6rem !important; font-size: 0.8rem !important; }
        p { margin-bottom: 0px !important; font-size: 0.9rem !important; line-height: 1.7rem !important; }
        hr { margin: 2px 0 !important; }
        .alert-box { padding: 0.5rem 1rem !important; margin-bottom: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# --- 設定 ---
CATEGORY_MAP = {
    "PC": "PC", "訪問車": "訪問車", "iPad": "iPad", "携帯電話": "携帯電話",
    "Office365": "Office365", "ウイルスバスター": "ウイルスバスター", "その他機器": "その他機器"
}
SHEET_NEW_EMPLOYEE = "新規入職者"
SHEET_CERTIFICATE = "電子証明書"
ONBOARDING_TASKS = ["PC", "iPad", "携帯", "駐車場", "LineworksID", "モバカルモバナーID", "MCS", "アルコールチェックID", "訪問車両", "備品", "机・椅子", "三文判", "シャチハタ"]

COLUMNS_DEF = {
    "PC": ["使用部署", "購入日", "OS", "プロダクトID(シリアルNo)", "ラベル", "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", "officeのアカウント割振", "ウィルスバスターシリアルNo", "ウィルスバスター期限", "ウィルスバスター識別ネーム", "チームビューワID", "チームビューワPW", "備考"],
    "訪問車": ["登録番号", "洗車グループ", "駐車場", "タイヤサイズ", "スタッドレス有無", "タイヤ保管場所", "リース開始日", "リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日", "使用部署", "備考"],
    "iPad": ["購入日", "ラベル", "AppleID", "AppleIDパスワード", "シリアルNo", "ストレージ", "製造番号IMEI", "端末番号", "使用部署", "キャリア", "備考"],
    "携帯電話": ["購入日", "電話番号", "SIM", "メーカー", "製造番号", "使用部署", "保管場所", "キャリア", "備考"],
    "Office365": ["アカウントID", "パスワード", "利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "備考"],
    "ウイルスバスター": ["利用者1", "利用者2", "利用者3", "期限", "備考"],
    "その他機器": ["使用部署", "使用場所", "使用開始日", "備考"]
}

# --- Google Sheets API 接続 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- セッションステート初期化 ---
if 'active_search_query' not in st.session_state: st.session_state['active_search_query'] = ""
if 'page_number' not in st.session_state: st.session_state['page_number'] = 0

# タブの強制切り替えフラグ
if 'force_switch_zaiko' not in st.session_state: st.session_state['force_switch_zaiko'] = False
if 'force_switch_newemp' not in st.session_state: st.session_state['force_switch_newemp'] = False
if 'force_switch_cert' not in st.session_state: st.session_state['force_switch_cert'] = False

# --- 関数群 ---
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

def get_new_employee_data():
    try:
        worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
        return pd.DataFrame(worksheet.get_all_records())
    except: return pd.DataFrame()

def get_certificate_data():
    try:
        worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE)
        return pd.DataFrame(worksheet.get_all_records())
    except: return pd.DataFrame()

def parse_date(date_val):
    if not date_val: return None
    try:
        date_str = str(date_val).replace('.', '/').replace('-', '/').replace('年', '/').replace('月', '/').replace('日', '')
        return pd.to_datetime(date_str).to_pydatetime()
    except: return None

def generate_auto_id(df_target, prefix):
    if df_target is None or df_target.empty or 'ID' not in df_target.columns: return f"{prefix}0001"
    ids = [int(str(x)[len(prefix):]) for x in df_target['ID'] if str(x).startswith(prefix) and str(x)[len(prefix):].isdigit()]
    return f"{prefix}{max(ids)+1:04d}" if ids else f"{prefix}0001"

def safe_text(text): return str(text).replace("@", "@\u200B")

# --- ダイアログ関数 ---
@st.dialog("📝 詳細情報の編集")
def show_detail_dialog(row_data):
    cat = row_data['カテゴリ']
    with st.form("edit_form"):
        st.write(f"ID: {row_data['ID']} / カテゴリ: {cat}")
        new_name = st.text_input("品名", value=row_data.get('品名', ''))
        new_user = st.text_input("利用者", value=row_data.get('利用者', ''))
        new_status = st.selectbox("ステータス", ["利用可能", "利用中", "貸出中", "故障/修理中", "廃棄"], index=0)
        
        custom_values = {}
        for col in COLUMNS_DEF.get(cat, []):
            custom_values[col] = st.text_input(col, value=row_data.get(col, ''))
            
        if st.form_submit_button("更新"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(CATEGORY_MAP[cat])
            cell = worksheet.find(str(row_data['ID']))
            if cell:
                update_data = [row_data['ID'], cat, new_name, new_user, new_status, datetime.now().strftime('%Y-%m-%d')]
                for col in COLUMNS_DEF.get(cat, []): update_data.append(custom_values[col])
                worksheet.update(f"A{cell.row}", [update_data])
                st.success("更新しました"); st.rerun()

@st.dialog("🔐 電子証明書の編集")
def show_cert_dialog(row_data):
    with st.form("cert_edit_form"):
        new_type = st.text_input("種類", value=row_data.get('種類', ''))
        new_device = st.text_input("端末", value=row_data.get('端末', ''))
        new_exp = st.date_input("有効期限", value=parse_date(row_data.get('有効期限')))
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("更新"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE)
            cell = worksheet.find(str(row_data['ID']))
            if cell:
                worksheet.update(f"A{cell.row}", [[row_data['ID'], new_type, new_device, str(new_exp), new_note]])
                st.success("更新しました"); st.rerun()

@st.dialog("👤 入職者タスク管理")
def show_onboarding_task_dialog(row_data):
    with st.form("onboard_form"):
        new_status = st.selectbox("全体ステータス", ["準備中", "完了"], index=0)
        task_vals = {}
        for task in ONBOARDING_TASKS:
            task_vals[task] = st.text_input(task, value=row_data.get(task, ''))
        if st.form_submit_button("更新"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
            cell = worksheet.find(str(row_data['ID']))
            if cell:
                # 簡易更新
                st.success("更新しました（デモ）"); st.rerun()

# --- メインロジック ---
st.title("📱 総務備品管理アプリ")
with st.sidebar:
    page_selection = st.radio("メニュー", ["📦 在庫管理", "👤 新規入職者管理", "🔐 電子証明書管理", "📅 5年経過リスト"])
    if st.button("🔄 データを最新にする"): get_all_data.clear(); st.rerun()

# --- ページ1: 在庫管理 ---
if page_selection == "📦 在庫管理":
    if st.session_state.force_switch_zaiko:
        st.session_state.tab_zaiko_key = "🔍 一覧・検索"; st.session_state.force_switch_zaiko = False
    
    tab_select = st.radio("機能", ["🔍 一覧・検索", "📝 新規登録"], horizontal=True, key="tab_zaiko_key")
    df = get_all_data()
    
    if tab_select == "🔍 一覧・検索":
        query = st.text_input("フリーワード検索", key="main_search")
        if query: df = df[df.astype(str).apply(lambda row: row.str.contains(query, case=False).any(), axis=1)]
        st.dataframe(df)

# --- ページ2: 新規入職者管理 ---
elif page_selection == "👤 新規入職者管理":
    if st.session_state.force_switch_newemp:
        st.session_state.tab_emp_key = "📋 一覧"; st.session_state.force_switch_newemp = False
    st.radio("機能", ["📋 一覧", "➕ 新規登録"], horizontal=True, key="tab_emp_key")

# --- ページ3: 電子証明書管理 ---
elif page_selection == "🔐 電子証明書管理":
    # 安全なタブ切り替え処理
    if st.session_state.force_switch_cert:
        st.session_state.tab_cert_key = "📋 一覧・検索"
        st.session_state.force_switch_cert = False

    tab_cert = st.radio("機能", ["📋 一覧・検索", "➕ 新規登録"], horizontal=True, key="tab_cert_key")
    df_cert = get_certificate_data()

    if tab_cert == "📋 一覧・検索":
        if not df_cert.empty:
            # アラート判定
            today = datetime.now().date()
            alert_items = []
            for _, row in df_cert.iterrows():
                dt = parse_date(row.get('有効期限'))
                if dt:
                    diff = (dt.date() - today).days
                    if diff <= 75:
                        msg = f"あと{diff}日" if diff >= 0 else "超過"
                        alert_items.append({"row": row, "text": f"**{row.get('種類', '不明')} : 有効期限 {msg} ({dt.strftime('%Y-%m-%d')})**"})
            
            if alert_items:
                st.markdown('<div class="alert-box" style="background-color:#ffcccc; border:1px solid red; border-radius:5px; padding:10px;">⚠️ 電子証明書 期日アラート</div>', unsafe_allow_html=True)
                for item in alert_items:
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(item['text'])
                    if c2.button("詳細", key=f"btn_cert_{item['row']['ID']}"): show_cert_dialog(item['row'])
            
            st.write("---")
            st.write("### 証明書一覧")
            st.dataframe(df_cert)

    elif tab_cert == "➕ 新規登録":
        with st.form("new_cert"):
            new_id = generate_auto_id(df_cert, "I")
            c_type = st.text_input("種類")
            c_dev = st.text_input("端末")
            c_exp = st.date_input("有効期限")
            if st.form_submit_button("登録"):
                worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE)
                worksheet.append_row([new_id, c_type, c_dev, str(c_exp), ""])
                st.success("登録完了"); st.session_state.force_switch_cert = True; st.rerun()

# --- ページ4: 5年経過リスト ---
elif page_selection == "📅 5年経過リスト":
    st.write("購入から5年以上経過したPC/iPadを表示します。")
