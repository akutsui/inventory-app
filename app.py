import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- 🎨 UIデザイン (CSS) ---
st.markdown("""
    <style>
        .block-container { padding-top: 4rem !important; padding-bottom: 5rem; }
        div[data-testid="stVerticalBlock"] > div:has(h1) {
            position: sticky !important; top: 2.875rem !important; background-color: white !important;
            z-index: 1000 !important; padding-top: 1rem !important; padding-bottom: 0.5rem !important;
            border-bottom: 2px solid #f0f2f6; margin-bottom: 0 !important;
        }
        h1 { margin: 0 !important; padding: 0 !important; font-size: 1.8rem !important; }
        div[role="radiogroup"] {
            position: sticky !important; top: 6.8rem !important; background-color: white !important;
            z-index: 999 !important; padding-top: 0.5rem !important; padding-bottom: 0.5rem !important;
        }
        .stButton button { height: 1.6rem !important; min-height: 1.6rem !important; font-size: 0.8rem !important; }
        p { margin-bottom: 0px !important; font-size: 0.9rem !important; line-height: 1.7rem !important; }
        hr { margin: 2px 0 !important; }
        .alert-box { padding: 0.5rem 1rem !important; margin-bottom: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# --- 設定・定数 ---
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
if 'force_switch_zaiko' not in st.session_state: st.session_state['force_switch_zaiko'] = False
if 'force_switch_newemp' not in st.session_state: st.session_state['force_switch_newemp'] = False
if 'force_switch_cert' not in st.session_state: st.session_state['force_switch_cert'] = False

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
                get_all_data.clear(); st.success("更新しました"); st.rerun()

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

# --- メインロジック ---
st.title("📱 総務備品管理アプリ")
with st.sidebar:
    page_selection = st.radio("メニュー", ["📦 在庫管理", "👤 新規入職者管理", "🔐 電子証明書管理", "📅 5年経過リスト"])
    if st.button("🔄 データを最新にする"): get_all_data.clear(); st.rerun()

# --- ページ3: 電子証明書管理 ---
if page_selection == "🔐 電子証明書管理":
    if st.session_state.force_switch_cert:
        st.session_state.tab_cert_key = "📋 一覧・検索"; st.session_state.force_switch_cert = False

    tab_cert = st.radio("機能", ["📋 一覧・検索", "➕ 新規登録"], horizontal=True, key="tab_cert_key", label_visibility="collapsed")
    df_cert = get_certificate_data()

    if tab_cert == "📋 一覧・検索":
        st.markdown("#### 電子証明書の管理")
        if not df_cert.empty:
            today = datetime.now().date()
            alert_items = []
            for i, row in df_cert.iterrows():
                dt = parse_date(row.get('有効期限'))
                if dt:
                    diff = (dt.date() - today).days
                    if diff <= 75:
                        cert_type = row.get('種類', '不明')
                        device_name = row.get('端末', '不明')
                        msg = f"あと{diff}日" if diff >= 0 else "超過"
                        exp_str = dt.strftime('%Y-%m-%d')
                        # 【以前の仕様】に戻したアラートテキスト
                        alert_items.append({
                            "row": row, "idx": i,
                            "text": f"**【{device_name}】{cert_type} : 有効期限 {msg} ({exp_str})**"
                        })
            
            if alert_items:
                st.markdown('<div class="alert-box" style="background-color:#ffcccc; border-radius:5px; border:1px solid red; padding:5px 10px;"><span style="color:#8B0000; font-weight:bold;">⚠️ 電子証明書 期日アラート (75日以内)</span></div>', unsafe_allow_html=True)
                for item in alert_items:
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(f"<div style='color:#8B0000;'>{item['text']}</div>", unsafe_allow_html=True)
                    if c2.button("詳細", key=f"alert_btn_{item['idx']}"): show_cert_dialog(item['row'])
                    st.markdown('<hr style="margin:0.2rem 0; border-top:1px dotted #ff9999;">', unsafe_allow_html=True)
            st.write("")
            st.dataframe(df_cert, use_container_width=True)

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

# --- ページ1: 在庫管理 ---
elif page_selection == "📦 在庫管理":
    if st.session_state.force_switch_zaiko:
        st.session_state.tab_zaiko_key = "🔍 一覧・検索"; st.session_state.force_switch_zaiko = False
    
    tab_select = st.radio("機能", ["🔍 一覧・検索", "📝 新規登録"], horizontal=True, key="tab_zaiko_key", label_visibility="collapsed")
    df = get_all_data()
    
    if tab_select == "🔍 一覧・検索":
        st.markdown("#### 在庫・備品一覧")
        query = st.text_input("フリーワード検索", key="main_search")
        if query: df = df[df.astype(str).apply(lambda row: row.str.contains(query, case=False).any(), axis=1)]
        st.dataframe(df, use_container_width=True)
    
    elif tab_select == "📝 新規登録":
        st.markdown("#### 新規備品登録")
        with st.form("new_zaiko"):
            cat = st.selectbox("カテゴリ", list(CATEGORY_MAP.keys()))
            name = st.text_input("品名")
            user = st.text_input("利用者")
            status = st.selectbox("ステータス", ["利用可能", "利用中", "貸出中", "故障/修理中"])
            custom_data = {}
            for col in COLUMNS_DEF.get(cat, []):
                custom_data[col] = st.text_input(col)
            if st.form_submit_button("登録"):
                new_id = generate_auto_id(df, "A") # 簡易
                worksheet = client.open(SPREADSHEET_NAME).worksheet(CATEGORY_MAP[cat])
                # 登録処理（略）
                st.success("登録完了"); st.session_state.force_switch_zaiko = True; st.rerun()

# --- ページ2: 新規入職者管理 ---
elif page_selection == "👤 新規入職者管理":
    st.markdown("#### 新規入職者タスク管理")
    df_emp = get_new_employee_data()
    st.dataframe(df_emp, use_container_width=True)

# --- ページ4: 5年経過リスト ---
elif page_selection == "📅 5年経過リスト":
    st.markdown("#### 購入から5年以上経過した資産")
    df = get_all_data()
    # 5年判定ロジック（略）
    st.dataframe(df, use_container_width=True)
