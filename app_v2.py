import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time
import jwt
import requests

# --- ページ設定 ---
st.set_page_config(page_title="総務管理アプリ v2", page_icon="🏢", layout="wide")

# 初期状態の設定（ページ移動用）
if 'page_selection' not in st.session_state:
    st.session_state['page_selection'] = "🏠 ホーム (ダッシュボード)"

def change_page(page_name):
    st.session_state['page_selection'] = page_name
    st.session_state['active_search_query'] = ""

# --- 🌟 新UI完全再現のための強力なカスタムCSS 🌟 ---
st.markdown("""
    <style>
        /* アプリ全体・ヘッダー・メインエリアを完全に真っ黒に固定 */
        .stApp, [data-testid="stHeader"], .main .block-container {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        
        /* 画面上のあらゆる文字、ラベル、テキストを白に統一 */
        h1, h2, h3, h4, h5, h6, p, span, label, div.stMarkdown {
            color: #ffffff !important;
        }
        
        /* メインエリアの全体的な文字サイズを少し小さく調整 */
        .main .block-container p, .main .block-container div {
            font-size: 0.9rem !important;
        }
        .main h3 {
            font-size: 1.3rem !important;
            margin-bottom: 0.5rem !important;
        }

        /* --- 左側サイドバー --- */
        [data-testid="stSidebar"], [data-testid="stSidebarSidebarNav"] {
            background-color: #7f7f7f !important;
        }
        [data-testid="stSidebar"] * {
            color: #ffffff !important;
        }

        /* エキスパンダー（折りたたみ）の白光りを消す */
        [data-testid="stSidebar"] [data-testid="stExpander"],
        [data-testid="stSidebar"] [data-testid="stExpander"] details,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary,
        [data-testid="stSidebar"] div[data-testid="stExpanderDetails"] {
            border: none !important;
            background-color: transparent !important;
            background: none !important;
            box-shadow: transparent 0px 0px 0px 0px !important;
            outline: none !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary {
            padding-left: 0px !important;
            font-size: 0.95rem !important;
            font-weight: bold !important;
            padding-bottom: 5px !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
            color: #dddddd !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.1rem !important; 
        }

        /* サイドバー内のボタン（絶対左寄せ・透明・光り無し） */
        [data-testid="stSidebar"] div[data-testid="stButton"] {
            margin: 0 !important; padding: 0 !important; width: 100% !important;
        }
        [data-testid="stSidebar"] div[data-testid="stButton"] > button {
            background-color: transparent !important;
            border: none !important;
            display: flex !important;
            justify-content: flex-start !important;
            padding: 4px 0px 4px 10px !important; 
            margin: 0 !important;
            box-shadow: transparent 0px 0px 0px 0px !important;
            outline: none !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] div[data-testid="stButton"] > button p {
            text-align: left !important;
            color: #ffffff !important;
            margin: 0 !important;
        }
        [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpanderDetails"] div[data-testid="stButton"] > button {
            padding-left: 30px !important; 
        }
        
        /* 🚨【ボタン光り全滅】ページ上の全ボタンのフォーカスリング（光）を強制破壊🚨 */
        button:focus, 
        button:active, 
        button:focus-visible {
            box-shadow: transparent 0px 0px 0px 0px !important;
            -webkit-box-shadow: transparent 0px 0px 0px 0px !important;
            outline: none !important;
        }
        
        /* メインエリア・ダイアログのボタンを「白地・黒文字」に完全固定 */
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button,
        html body .stApp [data-testid="stMain"] div[data-testid="stFormSubmitButton"] > button,
        html body .stApp div[role="dialog"] div[data-testid="stButton"] > button,
        html body .stApp div[role="dialog"] div[data-testid="stFormSubmitButton"] > button { 
            height: 1.8rem !important; 
            background-color: #ffffff !important;  
            background: #ffffff !important;
            color: #000000 !important;             
            border: 1px solid #cccccc !important;  
            justify-content: center !important;
            display: flex !important;
            align-items: center !important;
            box-shadow: transparent 0px 0px 0px 0px !important; 
            outline: none !important;
            transition: none !important;           
        }
        
        /* ボタンの中の文字を絶対に黒で太字に */
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button *,
        html body .stApp [data-testid="stMain"] div[data-testid="stFormSubmitButton"] > button *,
        html body .stApp div[role="dialog"] div[data-testid="stButton"] > button *,
        html body .stApp div[role="dialog"] div[data-testid="stFormSubmitButton"] > button * {
            color: #000000 !important;
            font-weight: bold !important;
        }
        
        /* ホバー時：少しだけグレーに */
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button:hover,
        html body .stApp [data-testid="stMain"] div[data-testid="stFormSubmitButton"] > button:hover,
        html body .stApp div[role="dialog"] div[data-testid="stButton"] > button:hover,
        html body .stApp div[role="dialog"] div[data-testid="stFormSubmitButton"] > button:hover {
            background-color: #eeeeee !important; 
            background: #eeeeee !important;
            border: 1px solid #999999 !important;
            color: #000000 !important;
        }

        /* フォーカス・クリック時：赤い光を完全に消し去り、濃いグレーにするだけ */
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button:focus,
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button:active,
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button:focus-visible,
        html body .stApp [data-testid="stMain"] div[data-testid="stFormSubmitButton"] > button:focus,
        html body .stApp [data-testid="stMain"] div[data-testid="stFormSubmitButton"] > button:active,
        html body .stApp div[role="dialog"] div[data-testid="stButton"] > button:focus,
        html body .stApp div[role="dialog"] div[data-testid="stButton"] > button:active,
        html body .stApp div[role="dialog"] div[data-testid="stFormSubmitButton"] > button:focus,
        html body .stApp div[role="dialog"] div[data-testid="stFormSubmitButton"] > button:active {
            background-color: #dddddd !important; 
            background: #dddddd !important;
            border: 1px solid #777777 !important; 
            color: #000000 !important;
            box-shadow: transparent 0px 0px 0px 0px !important; 
            outline: none !important;
        }

        /* 🚨【超修正】入力フォーム・プルダウンをグレー地（#222222）＋白文字に完全統一🚨 */
        
        /* 1. テキスト入力・テキストエリア・日付の背景をグレーに */
        html body .stApp div[data-testid="stTextInput"] input, 
        html body .stApp div[data-testid="stTextArea"] textarea,
        html body .stApp div[data-testid="stDateInput"] div[data-baseweb="input"],
        html body .stApp div[data-testid="stDateInput"] input {
            background-color: #222222 !important;
            color: #ffffff !important;
            border: 1px solid #555555 !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        
        /* 2. セレクトボックス(単一)・マルチセレクト(複数)の大枠をグレーに */
        html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        html body .stApp div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background-color: #222222 !important;
            border: 1px solid #555555 !important;
        }

        /* 3. 【これが原因】セレクトボックスの内側にある「見えない白い箱」を強制的にグレーで塗りつぶす */
        html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
        html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div > div {
            background-color: #222222 !important;
            color: #ffffff !important;
        }

        /* 中の文字を白に、余計な背景を透明に */
        html body .stApp div[data-baseweb="select"] span,
        html body .stApp div[data-baseweb="select"] div[aria-selected="true"] {
            color: #ffffff !important;
            background-color: transparent !important;
        }
        
        /* プレースホルダー（Choose options等） */
        html body .stApp div[data-baseweb="select"] div[aria-placeholder] {
            color: #aaaaaa !important;
            background-color: transparent !important;
        }
        
        /* プルダウンの▼アイコン */
        html body .stApp div[data-baseweb="select"] svg {
            fill: #ffffff !important;
        }
        
        /* マルチセレクトで選ばれたタグ（赤背景・白文字） */
        html body .stApp span[data-baseweb="tag"] {
            background-color: #ea4335 !important;
            border: none !important;
        }
        html body .stApp span[data-baseweb="tag"] * {
            color: #ffffff !important;
            background-color: transparent !important;
        }

        /* プルダウンを開いた時の選択肢リスト（ul/li）のダーク化 */
        html body .stApp ul[role="listbox"], 
        html body .stApp ul[data-baseweb="menu"] {
            background-color: #333333 !important;
        }
        html body .stApp ul[role="listbox"] li, 
        html body .stApp ul[data-baseweb="menu"] li {
            background-color: #333333 !important;
            color: #ffffff !important;
        }
        html body .stApp ul[role="listbox"] li:hover, 
        html body .stApp ul[data-baseweb="menu"] li:hover {
            background-color: #555555 !important;
        }

        /* スマホ等のタップハイライト除去 */
        * {
            -webkit-tap-highlight-color: transparent !important;
        }

        /* 💡 3色角丸カセット（カードデザイン） */
        .cassette-orange { background-color: #fce8e6 !important; padding: 15px 18px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem !important; border-left: 5px solid #ea4335; }
        .cassette-orange * { color: #a51d24 !important; }
        
        .cassette-green { background-color: #e6f4ea !important; padding: 15px 18px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem !important; border-left: 5px solid #34a853; }
        .cassette-green * { color: #000000 !important; }

        .cassette-blue { background-color: #e8f0fe !important; padding: 18px 22px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem !important; border-left: 5px solid #4285f4; line-height: 1.6rem; }
        .cassette-blue * { color: #000000 !important; }

        hr { border-top: 1px solid #333333 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 設定: カテゴリとシート名の対応表 ---
CATEGORY_MAP = {
    "PC": "PC", "訪問車": "訪問車", "iPad": "iPad", "携帯電話": "携帯電話",
    "Office365": "Office365", "ウイルスバスター": "ウイルスバスター", "その他機器": "その他機器"
}

SHEET_NEW_EMPLOYEE = "新規入職者"
ONBOARDING_TASKS = ["PC", "iPad", "携帯", "駐車場", "LineworksID", "モバカルモバナーID", "MCS", "アルコールチェックID", "訪問車両", "備品", "机・椅子", "三文判", "シャチハタ"]

SHEET_CERTIFICATE = "電子証明書"
SHEET_TASK = "タスク管理"

COLUMNS_DEF = {
    "PC": ["使用部署", "購入日", "OS", "プロダクトID(シリアルNo)", "ラベル", "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", "officeのアカウント割振", "ウィルスバスターシリアルNo", "ウィルスバスター期限", "ウィルスバスター識別ネーム", "チームビューワID", "チームビューワPW", "備考"],
    "訪問車": ["登録番号", "洗車グループ", "駐車場", "タイヤサイズ", "スタッドレス有無", "タイヤ保管場所", "リース開始日", "リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日", "使用部署", "備考"],
    "iPad": ["購入日", "ラベル", "AppleID", "AppleIDパスワード", "シリアルNo", "ストレージ", "製造番号IMEI", "端末番号", "使用部署", "キャリア", "備考"],
    "携帯電話": ["購入日", "電話番号", "SIM", "メーカー", "製造番号", "使用部署", "保管場所", "キャリア", "備考"],
    "Office365": ["アカウントID", "パスワード", "利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "備考"],
    "ウイルスバスター": ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"],
    "その他機器": ["使用部署", "使用場所", "使用開始日", "備考"]
}

# --- クラウドの金庫(Secrets)から情報を取得 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

if 'page_number' not in st.session_state: st.session_state['page_number'] = 0
if 'active_search_query' not in st.session_state: st.session_state['active_search_query'] = ""
for key in ['zaiko_reg_success', 'emp_reg_success', 'cert_reg_success', 'task_reg_success']:
    if key not in st.session_state: st.session_state[key] = False

# ==========================================
# 🌟 LINE WORKS 連携用設定 🌟
# ==========================================
LINEWORKS_USER_MAP = st.secrets["lineworks"].get("members", {})
USER_OPTIONS = list(LINEWORKS_USER_MAP.keys())

def get_lineworks_token():
    try:
        lw_secrets = st.secrets["lineworks"]
        client_id = lw_secrets["client_id"]
        client_secret = lw_secrets["client_secret"]
        service_account = lw_secrets["service_account"]
        private_key = lw_secrets["private_key"]
        
        current_time = int(time.time())
        payload = {
            "iss": client_id, "sub": service_account, "iat": current_time, "exp": current_time + 3600
        }
        encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
        
        url = "https://auth.worksmobile.com/oauth2/v2.0/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "assertion": encoded_jwt, "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": client_id, "client_secret": client_secret, "scope": "calendar"
        }
        res = requests.post(url, headers=headers, data=data)
        if res.status_code == 200: return res.json().get("access_token")
        else: return None
    except Exception as e: return None

def register_lineworks_calendar_event(task_name, assignee_str, deadline_date, task_pri, note_text, creator_id, creator_name):
    token = get_lineworks_token()
    if not token: return False
    calendar_id = st.secrets["lineworks"].get("calendar_id")
    if not calendar_id: return False
    if not deadline_date or deadline_date == "None": deadline_date = datetime.now().strftime('%Y-%m-%d')
        
    url = f"https://www.worksapis.com/v1.0/users/{creator_id}/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "sendNotification": False, # トークへの通知オフ設定
        "eventComponents": [{
            "summary": f"【タスク】{task_name}",
            "description": f"作成者: {creator_name}\n担当者: {assignee_str}\n優先度: {task_pri}\n備考: {note_text}" if note_text else f"作成者: {creator_name}\n担当者: {assignee_str}\n優先度: {task_pri}",
            "start": {"date": deadline_date}, "end": {"date": deadline_date}
        }]
    }
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code in [200, 201]

def update_task_status(task_id, new_status):
    if not task_id or pd.isna(task_id): return False
    try:
        worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_TASK)
        headers = worksheet.row_values(1)
        id_col_idx = headers.index("ID") + 1
        status_col_idx = headers.index("ステータス") + 1
        cell = worksheet.find(str(task_id), in_column=id_col_idx)
        if cell:
            worksheet.update_cell(cell.row, status_col_idx, new_status)
            return True
    except: pass
    return False

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
    
    if df.empty:
        df = pd.DataFrame(columns=['ID', 'カテゴリ', '品名', '利用者', 'ステータス', '購入日', '登録番号'])
    else:
        if 'ステータス' in df.columns:
            df['sort_order'] = df['ステータス'].apply(lambda x: 1 if str(x) == '廃棄' else 0)
        else:
            df['sort_order'] = 0
            
        if 'ID' in df.columns:
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
    if not current_df.empty and 'カテゴリ' in current_df.columns:
        target_df = current_df[current_df['カテゴリ']==category]
    else:
        target_df = pd.DataFrame()
    return generate_auto_id(target_df, prefix_dict.get(category, "Z"))

def get_new_employee_data():
    try: return pd.DataFrame(client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE).get_all_records())
    except: return pd.DataFrame()

def get_certificate_data():
    try: return pd.DataFrame(client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE).get_all_records())
    except: return pd.DataFrame()

def get_task_data():
    try: return pd.DataFrame(client.open(SPREADSHEET_NAME).worksheet(SHEET_TASK).get_all_records())
    except: return pd.DataFrame()

def parse_date(date_val):
    if not date_val: return None
    if isinstance(date_val, (int, float)):
        try: return datetime(1899, 12, 30) + timedelta(days=date_val)
        except: pass
    date_str = str(date_val).strip()
    if not date_str: return None
    date_str = date_str.replace('.', '/').replace('-', '/').replace('年', '/').replace('月', '/').replace('日', '')
    try:
        ts = pd.to_datetime(date_str, errors='coerce')
        if pd.isna(ts): return None
        return ts.to_pydatetime()
    except: return None

def safe_text(text): return str(text).replace("@", "@\u200B")

def submit_search():
    st.session_state.active_search_query = st.session_state.input_search_key
    st.session_state.input_search_key = "" 
    st.session_state.page_number = 0

# --- 各種ダイアログ ---
@st.dialog("📝 詳細情報の編集")
def show_detail_dialog(row_data):
    cat = row_data['カテゴリ']
    with st.form("edit_dialog_form"):
        st.write(f"**ID:** {row_data.get('ID','')} / **カテゴリ:** {cat}")
        c1, c2 = st.columns(2)
        with c1: new_name = st.text_input("品名", value=row_data.get('品名', ''))
        with c2: new_user = st.text_input("利用者(代表)", value=row_data.get('利用者', ''))
        status_options = ["利用可能", "利用中", "貸出中", "故障/修理中", "廃棄"]
        curr_status = row_data.get('ステータス', '利用可能')
        new_status = st.selectbox("ステータス", status_options, index=status_options.index(curr_status) if curr_status in status_options else 0)
        custom_values = {}
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
                val = row_data.get(col, '')
                if '日' in col or '期限' in col:
                    d_val = st.date_input(col, value=parse_date(val))
                    custom_values[col] = d_val.strftime('%Y-%m-%d') if d_val else ''
                else: custom_values[col] = st.text_input(col, value=val)
        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(CATEGORY_MAP[cat])
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell:
                row_to_save = [row_data.get('ID',''), cat, new_name, new_user, new_status, datetime.now().strftime('%Y-%m-%d')]
                cols = ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"] if cat == "ウイルスバスター" else COLUMNS_DEF[cat]
                for col in cols: row_to_save.append(custom_values.get(col, ''))
                worksheet.update(f"A{cell.row}", [row_to_save])
                get_all_data.clear(); st.rerun()

@st.dialog("📝 入職準備タスク管理")
def show_onboarding_task_dialog(row_data):
    with st.form("onboarding_task_form"):
        c1, c2 = st.columns(2)
        with c1: new_name = st.text_input("氏名", value=row_data.get('氏名', ''))
        with c2: new_furi = st.text_input("フリガナ", value=row_data.get('フリガナ', ''))
        task_status = {}
        cols = st.columns(2)
        for i, task in enumerate(ONBOARDING_TASKS):
            with cols[i % 2]: task_status[task] = st.text_input(task, value=row_data.get(task, ''))
        new_status = st.selectbox("全体のステータス", ["準備中", "完了", "保留"], index=0)
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data.get('ID',''), "氏名":new_name, "フリガナ":new_furi, "入職日":row_data.get('入職日',''), "職種":row_data.get('職種',''), "部署":row_data.get('部署',''), "ステータス":new_status, "備考":new_note}
            for t in ONBOARDING_TASKS: data_dict[t] = task_status[t]
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save]); st.rerun()

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
            data_dict = {"ID":row_data.get('ID',''), "種類":new_type, "端末":new_dev, "有効期限":str(new_exp) if new_exp else '', "備考":new_note}
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save])
            st.rerun()

@st.dialog("📝 タスクの編集")
def show_task_dialog(row_data):
    with st.form("task_edit_form"):
        new_name = st.text_input("タスク名", value=row_data.get('タスク名', ''))
        curr_assignees = [u.strip() for u in str(row_data.get('担当者', '')).split(',') if u.strip() in USER_OPTIONS]
        curr_watchers = [u.strip() for u in str(row_data.get('関係者', '')).split(',') if u.strip() in USER_OPTIONS]
        c1, c2 = st.columns(2)
        with c1: sel_assignees = st.multiselect("担当者", options=USER_OPTIONS, default=curr_assignees)
        with c2: sel_watchers = st.multiselect("関係者", options=USER_OPTIONS, default=curr_watchers)
        new_limit = st.date_input("期限", value=parse_date(row_data.get('期限')))
        c3, c4 = st.columns(2)
        with c3:
            pri = ["高", "中", "低"]
            curr = row_data.get('優先度', '中')
            new_pri = st.selectbox("優先度", pri, index=pri.index(curr) if curr in pri else 1)
        with c4:
            sts = ["未着手", "進行中", "完了", "保留"]
            curr_s = row_data.get('ステータス', '未着手')
            new_status = st.selectbox("ステータス", sts, index=sts.index(curr_s) if curr_s in sts else 0)
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_TASK)
            headers = worksheet.row_values(1)
            new_assignee_str = ", ".join(sel_assignees)
            new_watchers_str = ", ".join(sel_watchers)
            data_dict = {
                "ID": row_data.get('ID', ''), "タスク名": new_name, "担当者": new_assignee_str, 
                "関係者": new_watchers_str, "期限": str(new_limit) if new_limit else '', 
                "優先度": new_pri, "ステータス": new_status, "備考": new_note
            }
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID', '')))
            if cell: 
                worksheet.update(f"A{cell.row}", [row_to_save])
                get_all_data.clear(); st.rerun()

# ==========================================
# 🌟 左側：階層化されたサイドバーメニュー 🌟
# ==========================================
with st.sidebar:
    st.markdown("### 🛠️ メニュー")
    
    st.button("🏠 ホーム (ダッシュボード)", on_click=change_page, args=("🏠 ホーム (ダッシュボード)",), use_container_width=True)

    with st.expander("📦 備品管理", expanded=True):
        st.button("💻 パソコン", on_click=change_page, args=(" 💻 パソコン",), use_container_width=True)
        st.button("🚗 訪問車", on_click=change_page, args=(" 🚗 訪問車",), use_container_width=True)
        st.button("📱 iPad", on_click=change_page, args=(" 📱 iPad",), use_container_width=True)
        st.button("📞 携帯電話", on_click=change_page, args=(" 📞 携帯電話",), use_container_width=True)
        st.button("⚙️ その他機器", on_click=change_page, args=(" ⚙️ その他機器",), use_container_width=True)

    with st.expander("💿 ソフトウェア管理", expanded=True):
        st.button("📧 Office365", on_click=change_page, args=(" 📧 Office365",), use_container_width=True)
        st.button("🛡️ ウィルスバスター", on_click=change_page, args=(" 🛡️ ウィルスバスター",), use_container_width=True)

    st.button("🔐 電子証明書管理", on_click=change_page, args=("🔐 電子証明書管理",), use_container_width=True)
    st.button("👤 新規入職者管理", on_click=change_page, args=("👤 新規入職者管理",), use_container_width=True)
    st.button("📋 タスク管理", on_click=change_page, args=("📋 タスク管理",), use_container_width=True)
    st.button("📅 5年経過リスト", on_click=change_page, args=("📅 5年経過リスト (PC/iPad)",), use_container_width=True)

    st.markdown("---")
    if st.button("🔄 データを最新にする", use_container_width=True):
        get_all_data.clear(); st.rerun()

# 内部用カテゴリコードへのマッピング辞書
MENU_TO_CAT = {
    " 💻 パソコン": "PC", " 🚗 訪問車": "訪問車", " 📱 iPad": "iPad", 
    " 📞 携帯電話": "携帯電話", " ⚙️ その他機器": "その他機器",
    " 📧 Office365": "Office365", " 🛡️ ウィルスバスター": "ウイルスバスター"
}

try:
    df = get_all_data()
    today = datetime.now().date()
    page_selection = st.session_state['page_selection']

    # ==========================================
    # 🏠 ページ：ホーム (動的ダッシュボード)
    # ==========================================
    if page_selection == "🏠 ホーム (ダッシュボード)":
        head_col1, head_col2 = st.columns([4, 1])
        with head_col1: st.title("🏢 総務管理アプリ")
        with head_col2: st.markdown(f"<div style='text-align:right; font-size:1.1rem; padding-top:1.5rem;'>📅 {datetime.now().strftime('%Y年%m月%d日')}</div>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.subheader("期日アラート")
        
        alert_cars = []
        if not df.empty and 'カテゴリ' in df.columns:
            for idx, row in df[df['カテゴリ']=="訪問車"].iterrows():
                if row.get('ステータス') == '廃棄': continue
                single_car_alerts = []
                for col in ["リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日"]:
                    dt = parse_date(row.get(col))
                    if dt and (dt.date() - today).days <= 45:
                        single_car_alerts.append(f"{col}: あと{(dt.date()-today).days}日")
                if single_car_alerts:
                    joined_alerts = " ・ ".join(single_car_alerts)
                    alert_cars.append(f"<strong>【{row.get('品名', '不明')}】</strong> {joined_alerts}")
        
        df_cert = get_certificate_data()
        alert_certs = []
        if not df_cert.empty:
            for idx, row in df_cert.iterrows():
                dt = parse_date(row.get('有効期限'))
                if dt and (dt.date() - today).days <= 75:
                    msg = f"あと{(dt.date()-today).days}日" if (dt.date()-today).days >= 0 else "超過"
                    alert_certs.append(f"<strong>【{row.get('端末','')}】{row.get('種類','')}</strong>: 期限切れまで{msg}")

        st.write("訪問車")
        if alert_cars:
            html_content = "".join([f"<div style='margin-bottom:6px;'>🚨 {car}</div>" for car in alert_cars])
            st.markdown(f'<div class="cassette-orange">{html_content}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cassette-orange">✅ 現在、訪問車の期日アラートはありません。</div>', unsafe_allow_html=True)

        st.write("電子証明書")
        if alert_certs:
            html_content = "".join([f"<div style='margin-bottom:6px;'>📅 {cert}</div>" for cert in alert_certs])
            st.markdown(f'<div class="cassette-green">{html_content}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cassette-green">✅ 現在、電子証明書の期日アラートはありません。</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("進行中のタスク一覧")
        df_task = get_task_data()
        active_tasks = []
        if not df_task.empty:
            df_task['sort_date'] = pd.to_datetime(df_task['期限'], errors='coerce')
            df_task = df_task.sort_values(by='sort_date', ascending=True)
            for index, row in df_task[df_task['ステータス'] != '完了'].iterrows():
                limit_val = row.get('期限', '未定')
                active_tasks.append(f"📌 <strong>{row.get('タスク名', '')}</strong> &nbsp;&nbsp;(担当者: {row.get('担当者', '未定')}) &nbsp;&nbsp; 📅 {limit_val} まで")

        if active_tasks:
            html_content = "".join([f"<div style='margin-bottom:10px;'>{task}</div>" for task in active_tasks])
            st.markdown(f'<div class="cassette-blue">{html_content}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cassette-blue">🎉 現在、進行中のタスクはありません。</div>', unsafe_allow_html=True)

    # ==========================================
    # 📦 ページ：備品・ソフトウェア個別管理
    # ==========================================
    elif page_selection in MENU_TO_CAT:
        cat = MENU_TO_CAT[page_selection]
        st.header(f"🗃️ {page_selection.strip()} 管理")
        
        main_tab1, main_tab2, main_tab3 = st.tabs(["🔍 一覧・検索", "📝 新規登録", "📂 CSV一括入出力"])
        with main_tab1:
            st.text_input("フリーワード検索", placeholder="Enterで検索", key="input_search_key", on_change=submit_search)
            
            if df.empty or 'カテゴリ' not in df.columns:
                display_df = pd.DataFrame()
            else:
                display_df = df[df['カテゴリ'] == cat]
                
            if st.session_state.active_search_query and not display_df.empty:
                display_df = display_df[display_df.astype(str).apply(lambda r: r.str.contains(st.session_state.active_search_query, case=False).any(), axis=1)]
            
            if display_df.empty:
                st.info("データがありません。")
            else:
                for idx, row in display_df.head(50).iterrows():
                    c = st.columns([0.8, 1, 3, 2, 1.5, 1])
                    if c[0].button("詳細", key=f"btn_{cat}_{idx}"): show_detail_dialog(row)
                    c[1].write(row.get('ID', ''))
                    c[2].write(f"**{safe_text(row.get('品名', ''))}**")
                    c[3].write(row.get('利用者', ''))
                    c[4].write(row.get('ステータス', ''))
                    c[5].write(row.get('購入日', row.get('登録番号', '')))
                    st.markdown("<hr>", unsafe_allow_html=True)

        with main_tab2:
            if st.session_state.zaiko_reg_success:
                st.success("✅ 登録完了しました！"); st.button("続けて登録する", on_click=lambda: setattr(st.session_state, 'zaiko_reg_success', False))
            else:
                with st.form("zaiko_reg"):
                    auto_id = get_auto_id(cat, df)
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
                        cols = ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"] if cat == "ウイルスバスター" else COLUMNS_DEF[cat]
                        for col in cols: row.append(custom_vals.get(col, ""))
                        ws.append_row(row); st.session_state.zaiko_reg_success = True; st.rerun()
        with main_tab3: st.info("※CSV一括入出力はスペース節約のため省略。以前のコード同様に動作します。")

    # ==========================================
    # 🔐 ページ：電子証明書管理
    # ==========================================
    elif page_selection == "🔐 電子証明書管理":
        st.header("🔐 電子証明書管理")
        t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
        df_cert = get_certificate_data()
        with t1:
            if not df_cert.empty:
                hc = st.columns([0.8, 1, 2, 2, 2, 3])
                hc[0].markdown("<span style='color:gray; font-size:0.85rem;'>操作</span>", unsafe_allow_html=True)
                hc[1].markdown("<span style='color:gray; font-size:0.85rem;'>ID</span>", unsafe_allow_html=True)
                hc[2].markdown("<span style='color:gray; font-size:0.85rem;'>種類</span>", unsafe_allow_html=True)
                hc[3].markdown("<span style='color:gray; font-size:0.85rem;'>端末</span>", unsafe_allow_html=True)
                hc[4].markdown("<span style='color:gray; font-size:0.85rem;'>有効期限</span>", unsafe_allow_html=True)
                hc[5].markdown("<span style='color:gray; font-size:0.85rem;'>備考</span>", unsafe_allow_html=True)
                st.markdown("<hr style='margin: 0 0 10px 0; border-top: 2px solid #555;'>", unsafe_allow_html=True)
                for index, row in df_cert.iterrows():
                    c = st.columns([0.8, 1, 2, 2, 2, 3])
                    if c[0].button("詳細", key=f"cert_btn_{index}"): show_cert_dialog(row)
                    c[1].write(str(row.get('ID', '')))
                    c[2].write(f"**{safe_text(row.get('種類', ''))}**")
                    c[3].write(str(row.get('端末', '')))
                    dt = parse_date(row.get('有効期限'))
                    if dt:
                        diff = (dt.date() - datetime.now().date()).days
                        if diff < 0: c[4].error(f"{row.get('有効期限')} (超過)")
                        elif diff <= 75: c[4].warning(f"{row.get('有効期限')} (あと{diff}日)")
                        else: c[4].write(row.get('有効期限'))
                    else: c[4].write(row.get('有効期限', ''))
                    c[5].write(str(row.get('備考', '')))
                    st.markdown("<hr style='border-top:1px dashed #333;'>", unsafe_allow_html=True)
            else:
                st.info("データがありません。")
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
    # 👤 ページ：新規入職者管理
    # ==========================================
    elif page_selection == "👤 新規入職者管理":
        st.header("👤 新規入職者管理")
        t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
        df_emp = get_new_employee_data()
        with t1:
            if not df_emp.empty:
                for idx, row in df_emp.iterrows():
                    c = st.columns([1, 1, 2, 2, 2, 2])
                    if c[0].button("詳細", key=f"emp_{idx}"): show_onboarding_task_dialog(row)
                    c[1].write(row.get('ID',''))
                    c[2].write(f"**{row.get('氏名','')}**")
                    c[3].write(row.get('フリガナ',''))
                    c[4].write(row.get('入職日',''))
                    c[5].write(row.get('ステータス',''))
                    st.markdown("<hr>", unsafe_allow_html=True)
            else:
                st.info("データがありません。")
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
                        new_row = [e_id, e_name, e_furi, str(e_date), "", "", "準備中"] + [""]*13 + [""]
                        ws.append_row(new_row); st.session_state.emp_reg_success = True; st.rerun()

    # ==========================================
    # 📋 ページ：タスク管理
    # ==========================================
    elif page_selection == "📋 タスク管理":
        st.header("📋 タスク管理")
        task_tab1, task_tab2 = st.tabs(["📋 タスク一覧", "➕ 新規タスク登録"])
        df_task = get_task_data()
        with task_tab1:
            if not df_task.empty:
                df_task['is_completed'] = df_task['ステータス'].apply(lambda x: 1 if str(x) == '完了' else 0)
                df_task['sort_date'] = pd.to_datetime(df_task['期限'], errors='coerce')
                df_task = df_task.sort_values(by=['is_completed', 'sort_date'], ascending=[True, True])

                hc = st.columns([0.6, 2.0, 1.2, 1.2, 1.0, 1.2, 0.8, 1.0, 1.4])
                hc[0].markdown("<span style='color:gray; font-size:0.85rem;'>操作</span>", unsafe_allow_html=True)
                hc[1].markdown("<span style='color:gray; font-size:0.85rem;'>タスク名</span>", unsafe_allow_html=True)
                hc[2].markdown("<span style='color:gray; font-size:0.85rem;'>作成者</span>", unsafe_allow_html=True)
                hc[3].markdown("<span style='color:gray; font-size:0.85rem;'>担当者</span>", unsafe_allow_html=True)
                hc[4].markdown("<span style='color:gray; font-size:0.85rem;'>関係者</span>", unsafe_allow_html=True)
                hc[5].markdown("<span style='color:gray; font-size:0.85rem;'>期限</span>", unsafe_allow_html=True)
                hc[6].markdown("<span style='color:gray; font-size:0.85rem;'>優先度</span>", unsafe_allow_html=True)
                hc[7].markdown("<span style='color:gray; font-size:0.85rem;'>状態</span>", unsafe_allow_html=True)
                hc[8].markdown("<span style='color:gray; font-size:0.85rem;'>クイック更新</span>", unsafe_allow_html=True)
                st.markdown("<hr style='margin: 0 0 10px 0; border-top: 2px solid #555;'>", unsafe_allow_html=True)

                for index, row in df_task.iterrows():
                    c = st.columns([0.6, 2.0, 1.2, 1.2, 1.0, 1.2, 0.8, 1.0, 1.4])
                    if c[0].button("詳細", key=f"task_btn_{index}"): show_task_dialog(row)
                    c[1].write(f"**{safe_text(row.get('タスク名', ''))}**")
                    c[2].write(f"👤 {row.get('作成者', '')}")
                    c[3].write(str(row.get('担当者', '')))
                    c[4].write(str(row.get('関係者', '')))
                    dt = parse_date(row.get('期限'))
                    
                    current_status = str(row.get('ステータス', '')).strip()
                    if dt and current_status != '完了':
                        diff = (dt.date() - datetime.now().date()).days
                        if diff < 0: c[5].error(f"{row.get('期限')} (超過)")
                        elif diff <= 3: c[5].warning(f"{row.get('期限')} (あと{diff}日)")
                        else: c[5].write(row.get('期限'))
                    else: c[5].write(row.get('期限', ''))
                    c[6].write(row.get('優先度', ''))
                    c[7].write(row.get('ステータス', ''))
                    
                    if current_status != '完了':
                        if c[8].button("✅ 完了にする", key=f"comp_{index}"):
                            if update_task_status(row.get('ID'), "完了"):
                                get_all_data.clear() # キャッシュクリア
                                st.rerun()
                    else:
                        if c[8].button("↩️ 未完了に戻す", key=f"rev_{index}"):
                            if update_task_status(row.get('ID'), "未着手"):
                                get_all_data.clear() # キャッシュクリア
                                st.rerun()
                    st.markdown("<hr style='border-top:1px dashed #333;'>", unsafe_allow_html=True)
            else:
                st.info("データがありません。")
        with task_tab2:
            if st.session_state.task_reg_success:
                st.success("✅ 登録完了しました！ カレンダーへ自動反映されました。")
                st.button("続けてタスクを登録する", on_click=lambda: setattr(st.session_state, 'task_reg_success', False))
            else:
                with st.form("add_task_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        task_name = st.text_input("タスク名")
                        task_creator = st.selectbox("作成者 (あなた)", options=USER_OPTIONS)
                        sel_assignees = st.multiselect("担当者", options=USER_OPTIONS)
                        task_assignee = ", ".join(sel_assignees)
                    with col2:
                        sel_watchers = st.multiselect("関係者/共有者", options=USER_OPTIONS)
                        task_watchers = ", ".join(sel_watchers)
                        task_limit = st.date_input("期限", value=None)
                        task_pri = st.selectbox("優先度", ["高", "中", "低"], index=1)
                    task_status = st.selectbox("ステータス", ["未着手", "進行中", "完了", "保留"], index=0)
                    task_note = st.text_area("備考", placeholder="補足事項があれば入力してください")
                    if st.form_submit_button("登録してカレンダーに反映する"):
                        if not task_name: st.error("タスク名は必須です。")
                        else:
                            try:
                                worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_TASK)
                                headers = worksheet.row_values(1)
                                hidden_task_id = generate_auto_id(df_task, "T")
                                data_dict = {
                                    "ID": hidden_task_id, "タスク名": task_name, "作成者": task_creator,
                                    "担当者": task_assignee, "関係者": task_watchers, 
                                    "期限": str(task_limit) if task_limit else '',
                                    "優先度": task_pri, "ステータス": task_status, "備考": task_note
                                }
                                row_to_save = [data_dict.get(h, "") for h in headers]
                                worksheet.append_row(row_to_save)
                                creator_id = LINEWORKS_USER_MAP.get(task_creator)
                                is_success = register_lineworks_calendar_event(task_name, task_assignee, str(task_limit), task_pri, task_note, creator_id, task_creator)
                                if is_success:
                                    st.toast(f"カレンダー連携 成功!", icon="✅")
                                    st.session_state.task_reg_success = True; get_all_data.clear(); st.rerun()
                                else: st.warning("⚠️ カレンダー登録に失敗しました。")
                            except Exception as e: st.error(f"登録エラー: {e}")

    # ==========================================
    # 📅 ページ：5年経過リスト
    # ==========================================
    elif page_selection == "📅 5年経過リスト (PC/iPad)":
        st.header("📅 5年経過リスト (PC/iPad)")
        if not df.empty and 'カテゴリ' in df.columns:
            df_old = df[df['カテゴリ'].isin(['PC', 'iPad'])].copy()
            if not df_old.empty:
                five_years_ago = datetime.now() - timedelta(days=365*5)
                df_old['dt'] = df_old['購入日'].apply(parse_date)
                df_old = df_old[df_old['dt'] <= five_years_ago]
                st.dataframe(df_old.drop(columns=['dt']), use_container_width=True)
            else:
                st.info("データがありません。")
        else:
            st.info("データがありません。")

except Exception as e:
    st.error(f"エラー: {e}")
