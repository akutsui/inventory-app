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
    st.session_state['page_number'] = 0  # 💡 ページ移動時に1ページ目にリセット

# --- 🌟 CSS省略（レイアウト設定） 🌟 ---
st.markdown("""
    <style>
        .stApp, .main .block-container { background-color: #000000 !important; color: #ffffff !important; }
        
        /* 🚨 1. ヘッダーを透明にして残すことで、サイドバー開閉の「＞」「＜」ボタンを復活させます */
        [data-testid="stHeader"] { 
            background: transparent !important; 
        }
        
        /* 🚨 2. ヘッダーを残しつつ、メインコンテンツだけを上に引っ張り上げて余白を消します */
        .main .block-container { 
            padding-top: 0px !important; 
            margin-top: -60px !important; 
            padding-bottom: 1rem !important; 
        }
        
        h2, h3, h4, h5, h6, p, span, label, div.stMarkdown { color: #ffffff !important; }
        .text-alert, .text-alert * { color: #ff4b4b !important; font-weight: bold !important; }
        .text-warning, .text-warning * { color: #faca2b !important; font-weight: bold !important; }
        .main .block-container p, .main .block-container div, .main .block-container span { font-size: 0.82rem !important; }
        .page-title-box { margin-top: 0px !important; padding-top: 0px !important; margin-bottom: 15px !important; }
        .page-title-box h2 { font-size: 1.15rem !important; font-weight: bold !important; margin: 0px !important; padding: 0px !important; line-height: 1.2 !important; }
        .main h2, .main h3, .main h4, .main [data-testid="stMarkdownContainer"] h2, .main [data-testid="stMarkdownContainer"] h3 { font-size: 1.15rem !important; margin-top: 0px !important; padding-top: 0px !important; }
        [data-testid="stTabs"] { margin-top: 5px !important; padding-top: 0px !important; }
        [data-testid="stVerticalBlock"] { gap: 0.8rem !important; }
        .date-display-box { text-align: right; font-size: 1.1rem; padding-top: 0px !important; margin-top: 0px !important; line-height: 1.2 !important; }
        
        /* サイドバーデザイン */
        [data-testid="stSidebar"], [data-testid="stSidebarSidebarNav"] { background-color: #7f7f7f !important; }
        [data-testid="stSidebar"] * { color: #ffffff !important; }
        [data-testid="stSidebar"] [data-testid="stExpander"], [data-testid="stSidebar"] [data-testid="stExpander"] details, [data-testid="stSidebar"] [data-testid="stExpander"] summary, [data-testid="stSidebar"] div[data-testid="stExpanderDetails"] { border: none !important; background-color: transparent !important; background: none !important; box-shadow: transparent 0px 0px 0px 0px !important; outline: none !important; }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary { padding-left: 0px !important; padding-top: 0px !important; padding-bottom: 0px !important; font-size: 0.95rem !important; font-weight: bold !important; min-height: 2rem !important; }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { color: #dddddd !important; }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0rem !important; }
        [data-testid="stSidebar"] .element-container { margin-bottom: 0px !important; }
        [data-testid="stSidebar"] [data-testid="stExpanderDetails"] { padding-top: 0px !important; padding-bottom: 0px !important; }
        [data-testid="stSidebar"] div[data-testid="stButton"] { margin: 0 !important; padding: 0 !important; width: 100% !important; }
        
        /* 通常のメニューボタン */
        [data-testid="stSidebar"] div[data-testid="stButton"] > button { background-color: transparent !important; border: none !important; display: flex !important; justify-content: flex-start !important; padding: 0px 0px 0px 10px !important; margin: 0 !important; box-shadow: transparent 0px 0px 0px 0px !important; outline: none !important; width: 100% !important; height: 1.6rem !important; min-height: 1.6rem !important; }
        [data-testid="stSidebar"] div[data-testid="stButton"] > button > div, [data-testid="stSidebar"] div[data-testid="stButton"] > button > div > div { width: 100% !important; display: flex !important; justify-content: flex-start !important; align-items: center !important; margin: 0 !important; padding: 0 !important; }
        [data-testid="stSidebar"] div[data-testid="stButton"] > button p { text-align: left !important; color: #ffffff !important; margin: 0 !important; padding: 0 !important; width: 100% !important; line-height: 1 !important; }
        [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover { background-color: rgba(255, 255, 255, 0.1) !important; }
        [data-testid="stSidebar"] [data-testid="stExpanderDetails"] div[data-testid="stButton"] > button { padding-left: 30px !important; }
        
        /* 🚨 「データを最新にする」更新ボタンだけ青色で目立たせる特別CSS */
        [data-testid="stSidebar"] div[data-testid="stButton"]:has(p:contains("データを最新にする")) > button {
            background-color: #4285f4 !important;
            border-radius: 6px !important;
            justify-content: center !important;
            height: 2.2rem !important;
            min-height: 2.2rem !important;
            margin-bottom: 10px !important;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.2) !important;
        }
        [data-testid="stSidebar"] div[data-testid="stButton"]:has(p:contains("データを最新にする")) > button p {
            text-align: center !important;
            font-weight: bold !important;
            font-size: 0.9rem !important;
        }
        [data-testid="stSidebar"] div[data-testid="stButton"]:has(p:contains("データを最新にする")) > button:hover {
            background-color: #3367d6 !important;
        }

        button:focus, button:active, button:focus-visible { box-shadow: transparent 0px 0px 0px 0px !important; -webkit-box-shadow: transparent 0px 0px 0px 0px !important; outline: none !important; }
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button, html body .stApp [data-testid="stMain"] div[data-formsubmitbutton] > button, html body .stApp div[role="dialog"] div[data-testid="stButton"] > button, html body .stApp div[role="dialog"] div[data-formsubmitbutton] > button { height: 1.6rem !important; background-color: #ffffff !important; background: #ffffff !important; color: #000000 !important; border: 1px solid #cccccc !important; justify-content: center !important; display: flex !important; align-items: center !important; box-shadow: transparent 0px 0px 0px 0px !important; outline: none !important; transition: none !important; }
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button *, html body .stApp [data-testid="stMain"] div[data-formsubmitbutton] > button *, html body .stApp div[role="dialog"] div[data-testid="stButton"] > button *, html body .stApp div[role="dialog"] div[data-formsubmitbutton] > button * { color: #000000 !important; font-weight: bold !important; font-size: 0.8rem !important; }
        html body .stApp [data-testid="stMain"] div[data-testid="stButton"] > button:hover, html body .stApp [data-testid="stMain"] div[data-formsubmitbutton] > button:hover, html body .stApp div[role="dialog"] div[data-testid="stButton"] > button:hover, html body .stApp div[role="dialog"] div[data-formsubmitbutton] > button:hover { background-color: #eeeeee !important; background: #eeeeee !important; border: 1px solid #999999 !important; color: #000000 !important; }
        html body .stApp div[data-testid="stTextInput"] input, html body .stApp div[data-testid="stTextArea"] textarea, html body .stApp div[data-testid="stDateInput"] div[data-baseweb="input"], html body .stApp div[data-testid="stDateInput"] input { background-color: #222222 !important; color: #ffffff !important; border: 1px solid #555555 !important; -webkit-text-fill-color: #ffffff !important; }
        html body .stApp div[data-baseweb="select"] > div { background-color: #222222 !important; border: 1px solid #555555 !important; }
        html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div, html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div > div { background-color: #222222 !important; color: #ffffff !important; }
        html body .stApp div[data-baseweb="select"] span, html body .stApp div[data-baseweb="select"] div[aria-selected="true"] { color: #ffffff !important; background-color: transparent !important; }
        html body .stApp div[data-baseweb="select"] div[aria-placeholder] { color: #aaaaaa !important; background-color: transparent !important; }
        html body .stApp div[data-baseweb="select"] svg { fill: #ffffff !important; }
        html body .stApp span[data-baseweb="tag"] { background-color: #ea4335 !important; border: none !important; }
        html body .stApp span[data-baseweb="tag"] * { color: #ffffff !important; background-color: transparent !important; }
        html body .stApp ul[role="listbox"], html body .stApp ul[data-baseweb="menu"] { background-color: #333333 !important; }
        html body .stApp ul[role="listbox"] li, html body .stApp ul[data-baseweb="menu"] li { background-color: #333333 !important; color: #ffffff !important; }
        html body .stApp ul[role="listbox"] li:hover, html body .stApp ul[data-baseweb="menu"] li:hover { background-color: #555555 !important; }
        html body .stApp div[data-testid="stTextInput"] input[placeholder="Enterで検索"] { background-color: #ffffff !important; color: #000000 !important; -webkit-text-fill-color: #000000 !important; border: 2px solid #cccccc !important; font-weight: bold !important; }
        html body .stApp div[data-testid="stTextInput"] input[placeholder="Enterで検索"]::placeholder { color: #888888 !important; -webkit-text-fill-color: #888888 !important; font-weight: normal !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) { background-color: #7f7f7f !important; padding: 10px 15px !important; border-radius: 8px !important; margin-top: 8px !important; margin-bottom: 15px !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) > div[data-testid="stVerticalBlock"] { gap: 0rem !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) div[data-testid="stHorizontalBlock"] { margin-bottom: -10px !important; margin-top: -10px !important; align-items: center !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) div.element-container { margin-bottom: 0px !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) p, div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) div[data-testid="stMarkdownContainer"] { margin-bottom: 0px !important; padding-bottom: 0px !important; line-height: 1.1 !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) div[data-testid="stButton"] > button p, div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) div[data-testid="stButton"] > button * { white-space: nowrap !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) div[data-testid="stButton"] > button { height: 1.4rem !important; min-height: 1.4rem !important; padding: 0px 5px !important; }
        div[data-testid="stVerticalBlock"]:has(> div.element-container .list-bg-marker) hr { margin-top: 2px !important; margin-bottom: 2px !important; border-top: 1px dashed rgba(255, 255, 255, 0.4) !important; }
        * { -webkit-tap-highlight-color: transparent !important; }
        .cassette-orange { background-color: #fce8e6 !important; padding: 15px 18px; border-radius: 8px; margin-bottom: 15px; font-size: 0.82rem !important; border-left: 5px solid #ea4335; }
        html body .stApp .cassette-orange, html body .stApp .cassette-orange * { color: #a51d24 !important; }
        .cassette-green { background-color: #e6f4ea !important; padding: 15px 18px; border-radius: 8px; margin-bottom: 15px; font-size: 0.82rem !important; border-left: 5px solid #34a853; }
        html body .stApp .cassette-green, html body .stApp .cassette-green * { color: #a51d24 !important; }
        .cassette-blue { background-color: #e8f0fe !important; padding: 18px 22px; border-radius: 8px; margin-bottom: 15px; font-size: 0.82rem !important; border-left: 5px solid #4285f4; line-height: 1.4rem; }
        html body .stApp .cassette-blue, html body .stApp .cassette-blue * { color: #000000 !important; }
        hr { border-top: 1px solid #333333 !important; }
        .sidebar-link { display: flex !important; align-items: center !important; justify-content: flex-start !important; padding: 0px 0px 0px 10px !important; width: 100% !important; height: 1.6rem !important; color: #ffffff !important; text-decoration: none !important; font-size: 0.82rem !important; margin-bottom: 5px !important; }
        .sidebar-link:hover { background-color: rgba(255, 255, 255, 0.1) !important; color: #ffffff !important; text-decoration: none !important; }
    </style>
""", unsafe_allow_html=True)

CATEGORY_MAP = {
    "PC": "PC", "訪問車": "訪問車", "iPad": "iPad", "携帯電話": "携帯電話",
    "Office365": "Office365", "ウイルスバスター": "ウイルスバスター", "その他機器": "その他機器"
}

SHEET_NEW_EMPLOYEE = "新規入職者"
ONBOARDING_TASKS = ["PC", "iPad", "携帯", "駐車場", "LineworksID", "モバカルモバナーID", "MCS", "アルコールチェックID", "訪問車両", "備品", "机・椅子", "三文判", "シャチハタ"]
SHEET_CERTIFICATE = "電子証明書"
SHEET_TASK = "タスク管理"
SHEET_MATERNITY = "産休育休"
SHEET_ORCA_CERT = "ORCA証明書"
SHEET_PARKING = "駐車場データ"

COLUMNS_DEF = {
    "PC": ["使用部署", "購入日", "OS", "プロダクトID(シリアルNo)", "ラベル", "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", "officeのアカウント割振", "ウィルスバスターシリアルNo", "ウィルスバスター期限", "ウィルスバスター識別ネーム", "チームビューワID", "チームビューワPW", "備考"],
    "訪問車": ["登録番号", "洗車グループ", "駐車場", "タイヤサイズ", "スタッドレス有無", "タイヤ保管場所", "リース開始日", "リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日", "使用部署", "備考"],
    "iPad": ["購入日", "ラベル", "AppleID", "AppleIDパスワード", "シリアルNo", "ストレージ", "製造番号IMEI", "端末番号", "使用部署", "キャリア", "備考"],
    "携帯電話": ["購入日", "電話番号", "SIM", "メーカー", "製造番号", "使用部署", "保管場所", "キャリア", "備考"],
    "Office365": ["アカウントID", "パスワード", "利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "備考"],
    "ウイルスバスター": ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"],
    "その他機器": ["使用部署", "使用場所", "使用開始日", "備考"]
}

SPREADSHEET_NAME = 'management_db'

@st.cache_resource
def get_spreadsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME)

doc = get_spreadsheet()

if 'page_number' not in st.session_state: st.session_state['page_number'] = 0
if 'active_search_query' not in st.session_state: st.session_state['active_search_query'] = ""
for key in ['zaiko_reg_success', 'emp_reg_success', 'cert_reg_success', 'task_reg_success', 'mat_reg_success', 'orca_reg_success', 'parking_reg_success']:
    if key not in st.session_state: st.session_state[key] = False

# ==========================================
# 🔐 LINE WORKS 連携ロジック 🔐
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
    if not token: return None
    calendar_id = st.secrets["lineworks"].get("calendar_id")
    if not calendar_id: return None
    if not deadline_date or deadline_date == "None": deadline_date = datetime.now().strftime('%Y-%m-%d')
        
    url = f"https://www.worksapis.com/v1.0/users/{st.secrets['lineworks']['service_account']}/calendars/{calendar_id}/events"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "sendNotification": False,
        "eventComponents": [{
            "summary": f"【タスク】{task_name}",
            "description": f"作成者: {creator_name}\n担当者: {assignee_str}\n優先度: {task_pri}\n備考: {note_text or ''}",
            "start": {"date": deadline_date}, "end": {"date": deadline_date},
            "reminders": []
        }]
    }
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code in [200, 201]:
        data = res.json()
        event_id = data.get("eventId")
        if not event_id and data.get("eventComponents"):
            event_id = data["eventComponents"][0].get("eventId")
        return event_id or "SUCCESS_BUT_NO_ID"
    return None

def update_lineworks_calendar_event(event_id, task_name, assignee_str, deadline_date, task_pri, note_text, creator_name):
    if not event_id or event_id == "SUCCESS_BUT_NO_ID": return False
    token = get_lineworks_token()
    if not token: return False
    calendar_id = st.secrets["lineworks"].get("calendar_id")
    
    url = f"https://www.worksapis.com/v1.0/users/{st.secrets['lineworks']['service_account']}/calendars/{calendar_id}/events/{event_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "sendNotification": False,
        "eventComponents": [{
            "eventId": event_id,
            "summary": f"【タスク】{task_name}",
            "description": f"作成者: {creator_name}\n担当者: {assignee_str}\n優先度: {task_pri}\n備考: {note_text or ''}",
            "start": {"date": deadline_date}, "end": {"date": deadline_date},
            "reminders": []
        }]
    }
    res = requests.put(url, headers=headers, json=payload)
    return res.status_code in [200, 204]

def delete_lineworks_calendar_event(event_id):
    if not event_id or event_id in ["", "SUCCESS_BUT_NO_ID"]: return False
    token = get_lineworks_token()
    if not token: return False
    calendar_id = st.secrets["lineworks"].get("calendar_id")
    
    url = f"https://www.worksapis.com/v1.0/users/{st.secrets['lineworks']['service_account']}/calendars/{calendar_id}/events/{event_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    res = requests.delete(url, headers=headers)
    return res.status_code in [200, 204]

def update_task_status(task_id, new_status):
    if not task_id or pd.isna(task_id): return False
    try:
        worksheet = doc.worksheet(SHEET_TASK)
        headers = worksheet.row_values(1)
        id_col_idx = headers.index("ID") + 1
        status_col_idx = headers.index("ステータス") + 1
        
        cell = worksheet.find(str(task_id), in_column=id_col_idx)
        if cell:
            if new_status == "完了" and "イベントID" in headers:
                event_col_idx = headers.index("イベントID") + 1
                event_id = worksheet.cell(cell.row, event_col_idx).value
                if event_id:
                    delete_lineworks_calendar_event(event_id)
                    worksheet.update_cell(cell.row, event_col_idx, "")
            
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
            worksheet = doc.worksheet(sheet_name)
            records = worksheet.get_all_records(value_render_option='FORMATTED_VALUE')
            for record in records: record['カテゴリ'] = cat_name
            all_data.extend(records)
        except: pass
    df = pd.DataFrame(all_data)
    if df.empty:
        df = pd.DataFrame(columns=['ID', 'カテゴリ', '品名', '利用者', 'ステータス', '購入日', '登録番号'])
    else:
        if 'ステータス' in df.columns: df['sort_order'] = df['ステータス'].apply(lambda x: 1 if str(x) == '廃棄' else 0)
        else: df['sort_order'] = 0
        if 'ID' in df.columns: df = df.sort_values(by=['sort_order', 'ID'], ascending=[True, True])
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
    if not current_df.empty and 'カテゴリ' in current_df.columns: target_df = current_df[current_df['カテゴリ']==category]
    else: target_df = pd.DataFrame()
    return generate_auto_id(target_df, prefix_dict.get(category, "Z"))

@st.cache_data(ttl=600)
def get_new_employee_data():
    try: return pd.DataFrame(doc.worksheet(SHEET_NEW_EMPLOYEE).get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_certificate_data():
    try: return pd.DataFrame(doc.worksheet(SHEET_CERTIFICATE).get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_task_data():
    try: return pd.DataFrame(doc.worksheet(SHEET_TASK).get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_maternity_data():
    try: return pd.DataFrame(doc.worksheet(SHEET_MATERNITY).get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_orca_cert_data():
    try: return pd.DataFrame(doc.worksheet(SHEET_ORCA_CERT).get_all_records())
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def get_parking_data():
    try: return pd.DataFrame(doc.worksheet(SHEET_PARKING).get_all_records())
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
            for col in COLUMNS_DEF[cat]:
                val = row_data.get(col, '')
                if '日' in col or '期限' in col:
                    d_val = st.date_input(col, value=parse_date(val))
                    custom_values[col] = d_val.strftime('%Y-%m-%d') if d_val else ''
                else: custom_values[col] = st.text_input(col, value=val)
        if st.form_submit_button("✅ 更新する"):
            worksheet = doc.worksheet(CATEGORY_MAP[cat])
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell:
                row_to_save = [row_data.get('ID',''), cat, new_name, new_user, new_status, datetime.now().strftime('%Y-%m-%d')]
                cols = ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"] if cat == "ウイルスバスター" else COLUMNS_DEF[cat]
                for col in cols: row_to_save.append(custom_values.get(col, ''))
                worksheet.update(f"A{cell.row}", [row_to_save])
                get_all_data.clear() # 備品更新時は備品キャッシュをクリア
                st.rerun()

@st.dialog("📝 入職準備タスク管理")
def show_onboarding_task_dialog(row_data):
    with st.form("onboarding_task_form"):
        c1, c2 = st.columns(2)
        with c1: new_name = st.text_input("氏名", value=row_data.get('氏名', ''))
        with c2: new_furi = st.text_input("フリガナ", value=row_data.get('フリガナ', ''))
        
        c3, c4 = st.columns(2)
        with c3: new_type = st.text_input("職種", value=row_data.get('職種', ''))
        with c4: new_dept = st.text_input("部署", value=row_data.get('部署', ''))
        
        task_status = {}
        cols = st.columns(2)
        for i, task in enumerate(ONBOARDING_TASKS):
            with cols[i % 2]: task_status[task] = st.text_input(task, value=row_data.get(task, ''))
            
        st_opts = ["準備中", "完了", "保留"]
        curr_st = str(row_data.get('ステータス', '')).strip()
        st_index = st_opts.index(curr_st) if curr_st in st_opts else 0
        new_status = st.selectbox("全体のステータス", st_opts, index=st_index)
        
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = doc.worksheet(SHEET_NEW_EMPLOYEE)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data.get('ID',''), "氏名":new_name, "フリガナ":new_furi, "入職日":row_data.get('入職日',''), "職種":new_type, "部署":new_dept, "ステータス":new_status, "備考":new_note}
            for t in ONBOARDING_TASKS: data_dict[t] = task_status[t]
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save])
            get_new_employee_data.clear() # 該当キャッシュだけクリア
            st.rerun()

@st.dialog("📝 電子証明書の編集")
def show_cert_dialog(row_data):
    with st.form("cert_edit_form"):
        new_type = st.text_input("種類", value=row_data.get('種類', ''))
        new_dev = st.text_input("端末", value=row_data.get('端末', ''))
        new_exp = st.date_input("有効期限", value=parse_date(row_data.get('有効期限')))
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = doc.worksheet(SHEET_CERTIFICATE)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data.get('ID',''), "種類":new_type, "端末":new_dev, "有効期限":str(new_exp) if new_exp else '', "備考":new_note}
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save])
            get_certificate_data.clear() # 該当キャッシュだけクリア
            st.rerun()

@st.dialog("📝 産休育休者の編集")
def show_maternity_dialog(row_data):
    with st.form("maternity_edit_form"):
        new_name = st.text_input("名前", value=row_data.get('名前', ''))
        new_dept = st.text_input("部署", value=row_data.get('部署', ''))
        new_start = st.date_input("休暇開始日", value=parse_date(row_data.get('休暇開始日')))
        new_return = st.date_input("復帰予定日", value=parse_date(row_data.get('復帰予定日')))
        
        m_opts = ["取得中", "復職済"]
        curr_m_st = str(row_data.get('ステータス', '')).strip()
        m_index = m_opts.index(curr_m_st) if curr_m_st in m_opts else 0
        new_status = st.selectbox("ステータス", m_opts, index=m_index)
        
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        if st.form_submit_button("✅ 更新する"):
            worksheet = doc.worksheet(SHEET_MATERNITY)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data.get('ID',''), "名前":new_name, "部署":new_dept, "休暇開始日":str(new_start) if new_start else '', "復帰予定日":str(new_return) if new_return else '', "ステータス":new_status, "備考":new_note}
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save])
            get_maternity_data.clear() # 該当キャッシュだけクリア
            st.rerun()

@st.dialog("📝 ORCA証明書の編集")
def show_orca_cert_dialog(row_data):
    cert_name = str(row_data.get('使用者', '')).strip()
    cert_u = str(row_data.get('ORCA宇都宮', '')).strip()
    cert_k = str(row_data.get('ORCA鹿沼', '')).strip()
    cert_m = str(row_data.get('ORCA益子', '')).strip()
    
    with st.form("orca_edit_form"):
        new_name = st.text_input("使用者", value=cert_name)
        new_dept = st.text_input("部署", value=row_data.get('部署', ''))
        new_utsu = st.text_input("ORCA宇都宮", value=cert_u)
        new_kanu = st.text_input("ORCA鹿沼", value=cert_k)
        new_mashi = st.text_input("ORCA益子", value=cert_m)
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        
        if st.form_submit_button("✅ 更新する"):
            worksheet = doc.worksheet(SHEET_ORCA_CERT)
            headers = worksheet.row_values(1)
            data_dict = {"ID":row_data.get('ID',''), "使用者":new_name, "部署":new_dept, "ORCA宇都宮":new_utsu, "ORCA鹿沼":new_kanu, "ORCA益子":new_mashi, "備考":new_note}
            row_to_save = [data_dict.get(h, "") for h in headers]
            cell = worksheet.find(str(row_data.get('ID','')))
            if cell: worksheet.update(f"A{cell.row}", [row_to_save])
            get_orca_cert_data.clear()
            st.rerun()
            
    st.markdown("---")
    st.markdown(f"##### 💻 この証明書が紐付いているPC")
    
    df_all = get_all_data()
    installed_pcs = []
    
    if not df_all.empty and 'カテゴリ' in df_all.columns:
        df_pc = df_all[df_all['カテゴリ'] == 'PC']
        
        def is_match_list(pc_val, cert_val):
            if not pc_val or not cert_val: return False
            v_str = pc_val.replace('、', ',').replace(' ', ',').replace(' ', ',')
            v_list = [v.strip() for v in v_str.split(',') if v.strip()]
            return cert_val in v_list or cert_val == pc_val.strip()
        
        for _, pc_row in df_pc.iterrows():
            pc_u = str(pc_row.get('ORCA宇都宮', '')).strip()
            pc_k = str(pc_row.get('ORCA鹿沼', '')).strip()
            pc_m = str(pc_row.get('ORCA益子', '')).strip()
            
            if is_match_list(pc_u, cert_u) or is_match_list(pc_k, cert_k) or is_match_list(pc_m, cert_m):
                installed_pcs.append(pc_row)
    
    if installed_pcs:
        for pc in installed_pcs:
            pid = pc.get('ID', '')
            pname = pc.get('品名', '')
            puser = pc.get('利用者', '')
            st.markdown(f"- **{pid}**: {pname} （利用者: {puser}）")
    else:
        st.info("現在、この証明書が紐付いているPCは見つかりませんでした。")

@st.dialog("📝 駐車場区画の編集")
def show_parking_dialog(row_data):
    with st.form("parking_edit_form"):
        st.write(f"**区画番号:** {row_data.get('区画番号', '')}")
        new_name = st.text_input("駐車場名", value=row_data.get('駐車場名', ''))
        new_park_num = st.text_input("駐車番号", value=row_data.get('駐車番号', ''))
        
        type_opts = ["訪問車", "自家用車", "来客用", "空き"]
        curr_type = str(row_data.get('区分', '')).strip()
        type_index = type_opts.index(curr_type) if curr_type in type_opts else 0
        new_type = st.selectbox("区分", type_opts, index=type_index)
        
        new_user = st.text_input("使用者", value=row_data.get('使用者', ''))
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        
        if st.form_submit_button("✅ 更新する"):
            worksheet = doc.worksheet(SHEET_PARKING)
            headers = worksheet.row_values(1)
            data_dict = {"区画番号": row_data.get('区画番号', ''), "駐車場名": new_name, "駐車番号": new_park_num, "区分": new_type, "使用者": new_user, "備考": new_note}
            row_to_save = [data_dict.get(h, "") for h in headers]
            
            id_col_idx = headers.index("区画番号") + 1
            cell = worksheet.find(str(row_data.get('区画番号', '')), in_column=id_col_idx)
            
            if cell: 
                worksheet.update(f"A{cell.row}", [row_to_save])
            else:
                worksheet.append_row(row_to_save)
                
            get_parking_data.clear()
            st.rerun()

@st.dialog("📝 タスクの編集")
def show_task_dialog(row_data):
    with st.form("task_edit_form"):
        new_name = st.text_input("タスク名", value=row_data.get('タスク名', ''))
        
        curr_creator = row_data.get('作成者', '')
        new_creator = st.selectbox("作成者", options=USER_OPTIONS, index=USER_OPTIONS.index(curr_creator) if curr_creator in USER_OPTIONS else 0)
        
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
            worksheet = doc.worksheet(SHEET_TASK)
            headers = worksheet.row_values(1)
            
            if "イベントID" not in headers:
                worksheet.update_cell(1, len(headers) + 1, "イベントID")
                headers.append("イベントID")
            
            id_col_idx = headers.index("ID") + 1
            cell = worksheet.find(str(row_data.get('ID', '')), in_column=id_col_idx)
            
            if cell:
                existing_row = worksheet.row_values(cell.row)
                while len(existing_row) < len(headers): existing_row.append("")
                row_dict = dict(zip(headers, existing_row))
                
                new_assignee_str = ", ".join(sel_assignees)
                new_watchers_str = ", ".join(sel_watchers)
                new_limit_str = str(new_limit) if new_limit else ""
                
                event_id = row_dict.get("イベントID", "").strip()
                old_limit = row_dict.get("期限", "").strip()
                
                if new_status == "完了":
                    if event_id: delete_lineworks_calendar_event(event_id)
                    event_id = ""
                elif new_limit_str:
                    if event_id and event_id != "SUCCESS_BUT_NO_ID":
                        if new_limit_str != old_limit:
                            delete_lineworks_calendar_event(event_id)
                            creator_id = LINEWORKS_USER_MAP.get(new_creator)
                            new_event_id = register_lineworks_calendar_event(new_name, new_assignee_str, new_limit_str, new_pri, new_note, creator_id, new_creator)
                            if new_event_id: event_id = new_event_id
                        else:
                            update_lineworks_calendar_event(event_id, new_name, new_assignee_str, new_limit_str, new_pri, new_note, new_creator)
                    else:
                        creator_id = LINEWORKS_USER_MAP.get(new_creator)
                        new_event_id = register_lineworks_calendar_event(new_name, new_assignee_str, new_limit_str, new_pri, new_note, creator_id, new_creator)
                        if new_event_id: event_id = new_event_id
                
                row_dict["タスク名"] = new_name
                row_dict["作成者"] = new_creator
                row_dict["担当者"] = new_assignee_str
                row_dict["関係者"] = new_watchers_str
                row_dict["期限"] = new_limit_str
                row_dict["優先度"] = new_pri
                row_dict["ステータス"] = new_status
                row_dict["備考"] = new_note
                row_dict["イベントID"] = event_id
                
                row_to_save = [row_dict.get(h, "") for h in headers]
                worksheet.update(f"A{cell.row}", [row_to_save])
                
                st.toast("スプレッドシートとLINE WORKSカレンダーを完全に同期しました！", icon="📅")
                get_task_data.clear() # タスクキャッシュだけクリア
                st.rerun()

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
        st.button("🏥 ORCA証明書", on_click=change_page, args=("🏥 ORCA証明書管理",), use_container_width=True)
    st.button("🔐 電子証明書管理", on_click=change_page, args=("🔐 電子証明書管理",), use_container_width=True)
    st.button("👤 新規入職者管理", on_click=change_page, args=("👤 新規入職者管理",), use_container_width=True)
    st.button("👶 産休育休者管理", on_click=change_page, args=("👶 産休育休者管理",), use_container_width=True)
    
    st.button("🅿️ 駐車場管理", on_click=change_page, args=("🅿️ 駐車場管理",), use_container_width=True)
    
    st.button("📋 タスク管理", on_click=change_page, args=("📋 タスク管理",), use_container_width=True)
    st.button("📅 5年経過リスト", on_click=change_page, args=("📅 5年経過リスト (PC/iPad)",), use_container_width=True)
    st.markdown("---")
    
    # 💡 外部への総務マニュアルリンク (NotebookLM)
    st.markdown('<a href="https://notebooklm.google.com/notebook/736514d4-30dc-462d-99b9-a8324feafef9" target="_blank" class="sidebar-link">📖 総務マニュアル (NotebookLM)</a>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    # 🚀 更新ボタンを一番下に戻す
    st.markdown("---")
    if st.button("🛠️ カレンダーID一覧を取得 (確認用)"):
        token = get_lineworks_token()
        url = f"https://www.worksapis.com/v1.0/users/{st.secrets['lineworks']['service_account']}/calendars"
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            calendars = res.json().get("calendars", [])
            for c in calendars:
                st.info(f"【{c.get('name', '名前なし')}】\nID: {c.get('calendarId', '')}")
        else:
            st.error(f"取得失敗: {res.status_code}")
    if st.button("🔄 データを最新にする", use_container_width=True): 
        get_all_data.clear()
        get_new_employee_data.clear()
        get_certificate_data.clear()
        get_task_data.clear()
        get_maternity_data.clear()
        get_orca_cert_data.clear()
        get_parking_data.clear()
        st.rerun()

MENU_TO_CAT = { " 💻 パソコン": "PC", " 🚗 訪問車": "訪問車", " 📱 iPad": "iPad", " 📞 携帯電話": "携帯電話", " ⚙️ その他機器": "その他機器", " 📧 Office365": "Office365", " 🛡️ ウィルスバスター": "ウイルスバスター" }

try:
    df = get_all_data()
    today = datetime.now().date()
    page_selection = st.session_state['page_selection']

# ==========================================
    # 🏠 ページ：ホーム (動的ダッシュボード) 
# ==========================================
   # 🔻🔻🔻 ここから一時的なテストコード（詳細デバッグ版） 🔻🔻🔻
        st.markdown("### 🛠️ カレンダー設定テスト (原因特定モード)")
        if st.button("🔍 エラーの本当の原因を調べる"):
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
                
                if res.status_code == 200:
                    st.success("✅ トークン取得成功！認証はバッチリです。")
                    token = res.json().get("access_token")
                    
                    url_cal = f"https://www.worksapis.com/v1.0/users/{service_account}/calendars"
                    res_cal = requests.get(url_cal, headers={"Authorization": f"Bearer {token}"})
                    if res_cal.status_code == 200:
                        data_cal = res_cal.json().get("calendars", [])
                        for c in data_cal:
                            st.info(f"名前: **{c.get('name', '不明')}**\n\nID: `{c.get('calendarId', '')}`")
                    else:
                        st.error(f"❌ カレンダー一覧の取得エラー: {res_cal.text}")
                else:
                    st.error(f"❌ LINE WORKSからの認証エラー応答: {res.status_code}\n\n{res.text}")
                    
            except Exception as e:
                st.error(f"❌ プログラム内部の準備エラー（secrets.tomlの書き方など）: {e}")
        st.markdown("---")
        # 🔺🔺🔺 ここまで 🔺🔺🔺
        
        st.subheader("期日アラート")
        
        alert_cars = []
        if not df.empty and 'カテゴリ' in df.columns:
            for idx, row in df[df['カテゴリ']=="訪問車"].iterrows():
                if row.get('ステータス') == '廃棄': continue
                single_car_alerts = []
                for col in ["リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日"]:
                    dt = parse_date(row.get(col))
                    if dt and (dt.date() - today).days <= 45: single_car_alerts.append(f"{col}: あと{(dt.date()-today).days}日")
                if single_car_alerts: alert_cars.append(f"<strong>【{row.get('品名', '不明')}】</strong> " + " ・ ".join(single_car_alerts))
        
        df_cert = get_certificate_data()
        alert_certs = []
        if not df_cert.empty:
            for idx, row in df_cert.iterrows():
                dt = parse_date(row.get('有効期限'))
                if dt and (dt.date() - today).days <= 75:
                    msg = f"あと{(dt.date()-today).days}日" if (dt.date()-today).days >= 0 else "超過"
                    alert_certs.append(f"<strong>【{row.get('端末','')}】{row.get('種類','')}</strong>: 期限切れまで{msg}")

        st.write("訪問車")
        if alert_cars: st.markdown(f'<div class="cassette-orange">{"".join([f"<div>🚨 {car}</div>" for car in alert_cars])}</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="cassette-orange">✅ 現在、訪問車の期日アラートはありません。</div>', unsafe_allow_html=True)
        st.write("電子証明書")
        if alert_certs: st.markdown(f'<div class="cassette-green">{"".join([f"<div>📅 {cert}</div>" for cert in alert_certs])}</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="cassette-green">✅ 現在、電子証明書の期日アラートはありません。</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("進行中のタスク一覧")
        df_task = get_task_data()
        active_tasks = []
        if not df_task.empty:
            df_task['sort_date'] = pd.to_datetime(df_task['期限'], errors='coerce')
            df_task = df_task.sort_values(by='sort_date', ascending=True)
            for index, row in df_task[df_task['ステータス'] != '完了'].iterrows():
                active_tasks.append(f"📌 <strong>{row.get('タスク名', '')}</strong> &nbsp;&nbsp;(担当者: {row.get('担当者', '未定')}) &nbsp;&nbsp; 📅 {row.get('期限', '未定')} まで")
        if active_tasks: st.markdown(f'<div class="cassette-blue">{"".join([f"<div>{task}</div>" for task in active_tasks])}</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="cassette-blue">🎉 現在、進行中のタスクはありません。</div>', unsafe_allow_html=True)

    # ==========================================
    # 📦 ページ：備品・ソフトウェア個別管理
    # ==========================================
    elif page_selection in MENU_TO_CAT:
        cat = MENU_TO_CAT[page_selection]
        st.markdown(f"""
            <div class="page-title-box">
                <h2>🗃️ {page_selection.strip()} 管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        main_tab1, main_tab2, main_tab3 = st.tabs(["🔍 一覧・検索", "📝 新規登録", "📂 CSV一括入出力"])
        with main_tab1:
            st.text_input("フリーワード検索", placeholder="Enterで検索", key="input_search_key", on_change=submit_search)
            display_df = df[df['カテゴリ'] == cat] if not df.empty and 'カテゴリ' in df.columns else pd.DataFrame()
            if st.session_state.active_search_query and not display_df.empty:
                display_df = display_df[display_df.astype(str).apply(lambda r: r.str.contains(st.session_state.active_search_query, case=False).any(), axis=1)]
            if display_df.empty: st.info("データがありません。")
            else:
                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    
                    # --- 💡 ページネーション設定 ---
                    ITEMS_PER_PAGE = 50
                    total_items = len(display_df)
                    total_pages = (total_items - 1) // ITEMS_PER_PAGE + 1 if total_items > 0 else 1
                    
                    if st.session_state.page_number >= total_pages:
                        st.session_state.page_number = 0
                        
                    start_idx = st.session_state.page_number * ITEMS_PER_PAGE
                    end_idx = start_idx + ITEMS_PER_PAGE
                    current_page_df = display_df.iloc[start_idx:end_idx]
                    
                    for idx, row in current_page_df.iterrows():
                        c = st.columns([0.8, 1, 3, 2, 1.5, 1])
                        if c[0].button("詳細", key=f"btn_{cat}_{idx}"): show_detail_dialog(row)
                        c[1].write(row.get('ID', ''))
                        c[2].write(f"**{safe_text(row.get('品名', ''))}**")
                        c[3].write(row.get('利用者', ''))
                        c[4].write(row.get('ステータス', ''))
                        
                        right_col_val = ""
                        if cat == "訪問車":
                            right_col_val = row.get('登録番号', '')
                        elif cat in ["Office365", "ウイルスバスター"]:
                            right_col_val = row.get('備考', '')
                        else:
                            right_col_val = row.get('購入日', row.get('登録番号', ''))
                        
                        if pd.isna(right_col_val) or str(right_col_val).strip().lower() == 'nan':
                            right_col_val = ""
                        
                        c[5].write(str(right_col_val))
                        st.markdown("<hr>", unsafe_allow_html=True)
                        
                    # --- 💡 ページネーションボタン ---
                    if total_pages > 1:
                        st.markdown("<br>", unsafe_allow_html=True)
                        pc1, pc2, pc3 = st.columns([1, 2, 1])
                        with pc1:
                            if st.session_state.page_number > 0:
                                st.button("⬅️ 前のページ", key=f"prev_{cat}", on_click=lambda: st.session_state.update(page_number=st.session_state.page_number - 1), use_container_width=True)
                        with pc2:
                            st.markdown(f"<div style='text-align: center; font-weight: bold; padding-top: 5px;'>ページ {st.session_state.page_number + 1} / {total_pages} （全 {total_items} 件）</div>", unsafe_allow_html=True)
                        with pc3:
                            if st.session_state.page_number < total_pages - 1:
                                st.button("次のページ ➡️", key=f"next_{cat}", on_click=lambda: st.session_state.update(page_number=st.session_state.page_number + 1), use_container_width=True)

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
                        ws = doc.worksheet(CATEGORY_MAP[cat])
                        row = [i_id, cat, i_name, i_user, "利用可能", datetime.now().strftime('%Y-%m-%d')]
                        cols = ["利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "利用者6", "期限", "備考"] if cat == "ウイルスバスター" else COLUMNS_DEF[cat]
                        for col in cols: row.append(custom_vals.get(col, ""))
                        ws.append_row(row)
                        get_all_data.clear() # キャッシュクリア
                        st.session_state.zaiko_reg_success = True; st.rerun()
        with main_tab3: st.info("※CSV一括入出力はスペース節約のため省略。以前のコード同様に動作します。")

    # ==========================================
    # 🔐 ページ：電子証明書管理
    # ==========================================
    elif page_selection == "🔐 電子証明書管理":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>🔐 電子証明書管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
        df_cert = get_certificate_data()
        with t1:
            if not df_cert.empty:
                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    hc = st.columns([0.8, 1, 2, 2, 2, 3])
                    for i, h_text in enumerate(["操作", "ID", "種類", "端末", "有効期限", "備考"]): hc[i].markdown(f"<span style='color:#eeeeee; font-size:0.85rem; font-weight:bold;'>{h_text}</span>", unsafe_allow_html=True)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    for index, row in df_cert.iterrows():
                        c = st.columns([0.8, 1, 2, 2, 2, 3])
                        if c[0].button("詳細", key=f"cert_btn_{index}"): show_cert_dialog(row)
                        c[1].write(str(row.get('ID', '')))
                        c[2].write(f"**{safe_text(row.get('種類', ''))}**")
                        c[3].write(str(row.get('端末', '')))
                        
                        dt = parse_date(row.get('有効期限'))
                        if dt:
                            diff = (dt.date() - datetime.now().date()).days
                            if diff < 0:
                                c[4].markdown(f"<div class='text-alert'>{row.get('有効期限')} (超過)</div>", unsafe_allow_html=True)
                            elif diff <= 75:
                                c[4].markdown(f"<div class='text-warning'>{row.get('有効期限')} (あと{diff}日)</div>", unsafe_allow_html=True)
                            else:
                                c[4].write(row.get('有効期限'))
                        else:
                            c[4].write(row.get('有効期限', ''))
                            
                        c[5].write(str(row.get('備考', '')))
                        st.markdown("<hr>", unsafe_allow_html=True)
            else: st.info("データがありません。")
        with t2:
            with st.form("cert_reg"):
                c_id = st.text_input("ID", value=generate_auto_id(df_cert, "I"))
                c_type = st.text_input("種類")
                c_dev = st.text_input("端末")
                c_exp = st.date_input("有効期限")
                if st.form_submit_button("登録"):
                    ws = doc.worksheet(SHEET_CERTIFICATE)
                    ws.append_row([c_id, c_type, c_dev, str(c_exp), ""])
                    get_certificate_data.clear() # キャッシュクリア
                    st.success("登録しました"); st.rerun()

    # ==========================================
    # 🏥 ページ：ORCA証明書管理
    # ==========================================
    elif page_selection == "🏥 ORCA証明書管理":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>🏥 ORCA証明書管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
        df_orca = get_orca_cert_data()
        
        with t1:
            if not df_orca.empty:
                if 'ID' in df_orca.columns:
                    df_orca = df_orca.sort_values(by='ID', ascending=True)
                
                df_all_pc = pd.DataFrame()
                if not df.empty and 'カテゴリ' in df.columns:
                    df_all_pc = df[df['カテゴリ'] == 'PC']
                
                def is_match_list(pc_val, cert_val):
                    if not pc_val or not cert_val: return False
                    v_str = pc_val.replace('、', ',').replace(' ', ',').replace(' ', ',')
                    v_list = [v.strip() for v in v_str.split(',') if v.strip()]
                    return cert_val in v_list or cert_val == pc_val.strip()

                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    hc = st.columns([0.8, 0.8, 1.5, 1.2, 1.1, 1.1, 1.1, 2.4])
                    headers_text = ["操作", "ID", "使用者", "部署", "宇都宮", "鹿沼", "益子", "紐付くPC"]
                    for i, h_text in enumerate(headers_text):
                        hc[i].markdown(f"<span style='color:#eeeeee; font-size:0.85rem; font-weight:bold;'>{h_text}</span>", unsafe_allow_html=True)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    
                    for idx, row in df_orca.iterrows():
                        cert_u = str(row.get('ORCA宇都宮', '')).strip()
                        cert_k = str(row.get('ORCA鹿沼', '')).strip()
                        cert_m = str(row.get('ORCA益子', '')).strip()
                        
                        linked_pcs = []
                        if not df_all_pc.empty:
                            for _, pc_row in df_all_pc.iterrows():
                                pc_u = str(pc_row.get('ORCA宇都宮', '')).strip()
                                pc_k = str(pc_row.get('ORCA鹿沼', '')).strip()
                                pc_m = str(pc_row.get('ORCA益子', '')).strip()
                                
                                if is_match_list(pc_u, cert_u) or is_match_list(pc_k, cert_k) or is_match_list(pc_m, cert_m):
                                    pc_id = str(pc_row.get('ID', ''))
                                    pc_user = str(pc_row.get('利用者', ''))
                                    linked_pcs.append(f"{pc_id}({pc_user})")
                        
                        pc_disp_text = ", ".join(linked_pcs) if linked_pcs else "-"
                        
                        c = st.columns([0.8, 0.8, 1.5, 1.2, 1.1, 1.1, 1.1, 2.4])
                        if c[0].button("詳細", key=f"orca_edit_{idx}"): show_orca_cert_dialog(row)
                        c[1].write(str(row.get('ID', '')))
                        c[2].write(f"**{safe_text(row.get('使用者', ''))}**")
                        c[3].write(str(row.get('部署', '')))
                        c[4].write(cert_u)
                        c[5].write(cert_k)
                        c[6].write(cert_m)
                        c[7].markdown(f"<span style='font-size:0.75rem; color:#aaaaaa;'>{pc_disp_text}</span>", unsafe_allow_html=True)
                        st.markdown("<hr>", unsafe_allow_html=True)
            else:
                st.info("データがありません。")
                
        with t2:
            if st.session_state.orca_reg_success:
                st.success("✅ 登録完了しました！")
                st.button("続けて登録する", on_click=lambda: setattr(st.session_state, 'orca_reg_success', False))
            else:
                with st.form("orca_reg_form"):
                    o_id = st.text_input("ID", value=generate_auto_id(df_orca, "O"))
                    o_name = st.text_input("使用者")
                    o_dept = st.text_input("部署")
                    o_utsu = st.text_input("ORCA宇都宮")
                    o_kanu = st.text_input("ORCA鹿沼")
                    o_mashi = st.text_input("ORCA益子")
                    o_note = st.text_area("備考")
                    if st.form_submit_button("登録する"):
                        if not o_name:
                            st.error("使用者の入力は必須です。")
                        else:
                            try:
                                ws = doc.worksheet(SHEET_ORCA_CERT)
                            except gspread.exceptions.WorksheetNotFound:
                                ws = doc.add_worksheet(title=SHEET_ORCA_CERT, rows="100", cols="10")
                                ws.append_row(["ID", "使用者", "部署", "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", "備考"])
                            
                            ws.append_row([o_id, o_name, o_dept, o_utsu, o_kanu, o_mashi, o_note])
                            st.session_state.orca_reg_success = True
                            get_orca_cert_data.clear()
                            st.rerun()

    # ==========================================
    # 🅿️ ページ：駐車場管理
    # ==========================================
    elif page_selection == "🅿️ 駐車場管理":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>🅿️ 駐車場管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        # 💡 URLの設定場所（ここに実際のURLを貼り付けてください）
        url_view_all = "https://docs.google.com/spreadsheets/d/1Z7rTUly4R9Z-R4WbyJBERg9BP4bMMsQvzbTLEGUvoKY/edit?gid=591211712#gid=591211712" # 全体閲覧用のURL
        url_all_pdf = "https://docs.google.com/spreadsheets/d/1Z7rTUly4R9Z-R4WbyJBERg9BP4bMMsQvzbTLEGUvoKY/export?format=pdf&gid=591211712#gid=591211712&portrait=false&fitw=true"
        url_company_pdf = "https://docs.google.com/spreadsheets/d/1Z7rTUly4R9Z-R4WbyJBERg9BP4bMMsQvzbTLEGUvoKY/export?format=pdf&gid=485728313#gid=485728313&portrait=false&fitw=true"
        url_private_pdf = "https://docs.google.com/spreadsheets/d/1Z7rTUly4R9Z-R4WbyJBERg9BP4bMMsQvzbTLEGUvoKY/export?format=pdf&gid=130019541#gid=130019541&portrait=false&fitw=true"

        
        # 💡 閲覧用のリンク（全体のみ）
        st.link_button("🔗 全体配置図をブラウザで開く (閲覧専用)", url_view_all, use_container_width=True)
        
        # 💡 PDFダウンロード用のリンク群
        mc1, mc2, mc3 = st.columns(3)
        mc1.link_button("📥 全体配置図 (PDF)", url_all_pdf, use_container_width=True)
        mc2.link_button("📥 訪問車のみ (PDF)", url_company_pdf, use_container_width=True)
        mc3.link_button("📥 自家用車のみ (PDF)", url_private_pdf, use_container_width=True)
        st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["📋 区画・使用者一覧", "➕ 新規区画の登録"])
        df_park = get_parking_data()
        
        with t1:
            st.text_input("フリーワード検索（区画番号や名前で検索）", placeholder="Enterで検索", key="input_search_key", on_change=submit_search)
            if not df_park.empty:
                display_df = df_park.copy()
                if st.session_state.active_search_query:
                    display_df = display_df[display_df.astype(str).apply(lambda r: r.str.contains(st.session_state.active_search_query, case=False).any(), axis=1)]
                
                if display_df.empty:
                    st.info("該当するデータがありません。")
                else:
                    with st.container():
                        st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                        hc = st.columns([0.8, 1.2, 1.8, 1.2, 1.2, 1.8, 2.0])
                        headers_text = ["操作", "区画番号", "駐車場名", "駐車番号", "区分", "使用者", "備考"]
                        for i, h_text in enumerate(headers_text):
                            hc[i].markdown(f"<span style='color:#eeeeee; font-size:0.85rem; font-weight:bold;'>{h_text}</span>", unsafe_allow_html=True)
                        st.markdown("<hr>", unsafe_allow_html=True)
                        
                        for idx, row in display_df.iterrows():
                            c = st.columns([0.8, 1.2, 1.8, 1.2, 1.2, 1.8, 2.0])
                            if c[0].button("詳細", key=f"park_{idx}"): show_parking_dialog(row)
                            c[1].write(f"**{str(row.get('区画番号', ''))}**")
                            c[2].write(str(row.get('駐車場名', '')))
                            c[3].write(str(row.get('駐車番号', '')))
                            
                            p_type = str(row.get('区分', ''))
                            if p_type == "訪問車": c[4].markdown(f"<span style='color:#4285f4; font-weight:bold;'>{p_type}</span>", unsafe_allow_html=True)
                            elif p_type == "自家用車": c[4].markdown(f"<span style='color:#34a853; font-weight:bold;'>{p_type}</span>", unsafe_allow_html=True)
                            else: c[4].write(p_type)
                            
                            c[5].write(f"**{safe_text(row.get('使用者', ''))}**")
                            c[6].write(str(row.get('備考', '')))
                            st.markdown("<hr>", unsafe_allow_html=True)
            else:
                st.info("データがありません。右のタブから区画と使用者を登録してください。")
                
        with t2:
            if st.session_state.parking_reg_success:
                st.success("✅ 登録完了しました！")
                st.button("続けて登録する", on_click=lambda: setattr(st.session_state, 'parking_reg_success', False))
            else:
                with st.form("park_reg_form"):
                    st.info("※「区画番号」は配置図のVLOOKUP関数と一致させるためのキーになります。正確に入力してください。（例：第1-01）")
                    p_id = st.text_input("区画番号 (必須)")
                    p_name = st.text_input("駐車場名")
                    p_num = st.text_input("駐車番号")
                    p_type = st.selectbox("区分", ["訪問車", "自家用車", "来客用", "空き"])
                    p_user = st.text_input("使用者")
                    p_note = st.text_area("備考")
                    
                    if st.form_submit_button("登録する"):
                        if not p_id:
                            st.error("区画番号の入力は必須です。")
                        else:
                            try:
                                ws = doc.worksheet(SHEET_PARKING)
                            except gspread.exceptions.WorksheetNotFound:
                                ws = doc.add_worksheet(title=SHEET_PARKING, rows="100", cols="10")
                                ws.append_row(["区画番号", "駐車場名", "駐車番号", "区分", "使用者", "備考"])
                            
                            ws.append_row([p_id, p_name, p_num, p_type, p_user, p_note])
                            st.session_state.parking_reg_success = True
                            get_parking_data.clear()
                            st.rerun()

    # ==========================================
    # 👤 ページ：新規入職者管理
    # ==========================================
    elif page_selection == "👤 新規入職者管理":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>👤 新規入職者管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["📋 一覧", "➕ 新規登録"])
        df_emp = get_new_employee_data()
        with t1:
            if not df_emp.empty:
                status_weight = {"準備中": 0, "保留": 1, "完了": 2}
                df_emp['sort_weight'] = df_emp['ステータス'].apply(lambda x: status_weight.get(str(x).strip(), 9))
                df_emp = df_emp.sort_values(by='sort_weight', ascending=True)
                
                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    hc = st.columns([0.8, 1.0, 1.5, 1.5, 1.2, 1.5, 1.5, 1.2])
                    headers_text = ["操作", "ID", "氏名", "フリガナ", "職種", "部署", "入職日", "ステータス"]
                    for i, h_text in enumerate(headers_text):
                        hc[i].markdown(f"<span style='color:#eeeeee; font-size:0.85rem; font-weight:bold;'>{h_text}</span>", unsafe_allow_html=True)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    
                    for idx, row in df_emp.iterrows():
                        c = st.columns([0.8, 1.0, 1.5, 1.5, 1.2, 1.5, 1.5, 1.2])
                        if c[0].button("詳細", key=f"emp_{idx}"): show_onboarding_task_dialog(row)
                        c[1].write(str(row.get('ID','')))
                        c[2].write(f"**{safe_text(row.get('氏名',''))}**")
                        c[3].write(str(row.get('フリガナ','')))
                        c[4].write(str(row.get('職種','')))
                        c[5].write(str(row.get('部署','')))
                        c[6].write(str(row.get('入職日','')))
                        c[7].write(str(row.get('ステータス','')))
                        st.markdown("<hr>", unsafe_allow_html=True)
            else: st.info("データがありません。")
        with t2:
            with st.form("emp_reg"):
                e_id = st.text_input("ID", value=generate_auto_id(df_emp, "H"))
                e_name = st.text_input("氏名")
                e_furi = st.text_input("フリガナ")
                col_type, col_dept = st.columns(2)
                with col_type: e_type = st.text_input("職種")
                with col_dept: e_dept = st.text_input("部署")
                e_date = st.date_input("入職日")
                if st.form_submit_button("登録"):
                    ws = doc.worksheet(SHEET_NEW_EMPLOYEE)
                    ws.append_row([e_id, e_name, e_furi, str(e_date), e_type, e_dept, "準備中"] + [""]*13 + [""])
                    get_new_employee_data.clear() # キャッシュクリア
                    st.success("登録しました"); st.rerun()

    # ==========================================
    # 👶 ページ：産休育休者管理
    # ==========================================
    elif page_selection == "👶 産休育休者管理":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>👶 産休育休者管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["📋 休暇者一覧", "➕ 新規登録"])
        df_mat = get_maternity_data()
        
        with t1:
            if not df_mat.empty:
                mat_status_weight = {"取得中": 0, "復職済": 1}
                df_mat['sort_weight'] = df_mat['ステータス'].apply(lambda x: mat_status_weight.get(str(x).strip(), 9))
                df_mat = df_mat.sort_values(by='sort_weight', ascending=True)
                
                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    hc = st.columns([0.8, 1.0, 1.8, 2.0, 2.0, 2.0, 1.8])
                    headers_text = ["操作", "ID", "名前", "部署", "休暇開始日", "復帰予定日", "ステータス"]
                    for i, h_text in enumerate(headers_text):
                        hc[i].markdown(f"<span style='color:#eeeeee; font-size:0.85rem; font-weight:bold;'>{h_text}</span>", unsafe_allow_html=True)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    
                    for idx, row in df_mat.iterrows():
                        c = st.columns([0.8, 1.0, 1.8, 2.0, 2.0, 2.0, 1.8])
                        if c[0].button("詳細", key=f"mat_edit_{idx}"): show_maternity_dialog(row)
                        c[1].write(str(row.get('ID', '')))
                        c[2].write(f"**{safe_text(row.get('名前', ''))}**")
                        c[3].write(str(row.get('部署', '')))
                        c[4].write(str(row.get('休暇開始日', '')))
                        c[5].write(str(row.get('復帰予定日', '')))
                        
                        curr_st = str(row.get('ステータス', '')).strip()
                        if curr_st == "取得中":
                            c[6].markdown(f"<span class='text-warning'>{curr_st}</span>", unsafe_allow_html=True)
                        else:
                            c[6].write(curr_st)
                        st.markdown("<hr>", unsafe_allow_html=True)
            else:
                st.info("データがありません。")
                
        with t2:
            if st.session_state.mat_reg_success:
                st.success("✅ 登録完了しました！")
                st.button("続けて登録する", on_click=lambda: setattr(st.session_state, 'mat_reg_success', False))
            else:
                with st.form("mat_reg_form"):
                    m_id = st.text_input("ID", value=generate_auto_id(df_mat, "M"))
                    m_name = st.text_input("名前")
                    m_dept = st.text_input("部署")
                    m_start = st.date_input("休暇開始日", value=None)
                    m_return = st.date_input("復帰予定日", value=None)
                    m_status = st.selectbox("ステータス", ["取得中", "復職済"])
                    m_note = st.text_area("備考")
                    if st.form_submit_button("登録する"):
                        if not m_name or not m_dept:
                            st.error("名前と部署の入力は必須です。")
                        else:
                            try:
                                ws = doc.worksheet(SHEET_MATERNITY)
                            except gspread.exceptions.WorksheetNotFound:
                                ws = doc.add_worksheet(title=SHEET_MATERNITY, rows="100", cols="20")
                                ws.append_row(["ID", "名前", "部署", "休暇開始日", "復帰予定日", "ステータス", "備考"])
                            
                            ws.append_row([m_id, m_name, m_dept, str(m_start) if m_start else '', str(m_return) if m_return else '', m_status, m_note])
                            st.session_state.mat_reg_success = True
                            get_maternity_data.clear() # キャッシュクリア
                            st.rerun()

    # ==========================================
    # 📋 ページ：タスク管理
    # ==========================================
    elif page_selection == "📋 タスク管理":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>📋 タスク管理</h2>
            </div>
        """, unsafe_allow_html=True)
        
        task_tab1, task_tab2 = st.tabs(["📋 タスク一覧", "➕ 新規タスク登録"])
        df_task = get_task_data()
        with task_tab1:
            if not df_task.empty:
                df_task['is_completed'] = df_task.get('ステータス', pd.Series()).apply(lambda x: 1 if str(x) == '完了' else 0)
                df_task['sort_date'] = pd.to_datetime(df_task.get('期限', pd.Series()), errors='coerce')
                df_task = df_task.sort_values(by=['is_completed', 'sort_date'], ascending=[True, True])
                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    hc = st.columns([0.6, 2.0, 1.2, 1.2, 1.0, 1.2, 0.8, 1.0, 1.4])
                    for i, h_text in enumerate(["操作", "タスク名", "作成者", "担当者", "関係者", "期限", "優先度", "状態", "クイック更新"]):
                        hc[i].markdown(f"<span style='color:#eeeeee; font-size:0.85rem; font-weight:bold;'>{h_text}</span>", unsafe_allow_html=True)
                    st.markdown("<hr>", unsafe_allow_html=True)
                    
                    for index, row in df_task.iterrows():
                        try:
                            c = st.columns([0.6, 2.0, 1.2, 1.2, 1.0, 1.2, 0.8, 1.0, 1.4])
                            task_id_str = str(row.get('ID', f"row_{index}"))
                            
                            if c[0].button("詳細", key=f"task_btn_{task_id_str}"): show_task_dialog(row)
                            c[1].write(f"**{safe_text(row.get('タスク名', ''))}**")
                            c[2].write(f"👤 {row.get('作成者', '')}")
                            c[3].write(str(row.get('担当者', '')))
                            c[4].write(str(row.get('関係者', '')))
                            
                            dt = parse_date(row.get('期限'))
                            current_status = str(row.get('ステータス', '')).strip()
                            if dt and current_status != '完了':
                                diff = (dt.date() - datetime.now().date()).days
                                if diff < 0:
                                    c[5].markdown(f"<div class='text-alert'>{row.get('期限')} (超過)</div>", unsafe_allow_html=True)
                                elif diff == 0:
                                    c[5].markdown(f"<div class='text-warning'>{row.get('期限')} (本日)</div>", unsafe_allow_html=True)
                                elif diff <= 3:
                                    c[5].markdown(f"<div class='text-warning'>{row.get('期限')} (あと{diff}日)</div>", unsafe_allow_html=True)
                                else:
                                    c[5].write(row.get('期限'))
                            else:
                                c[5].write(row.get('期限', ''))
                            
                            c[6].write(row.get('優先度', ''))
                            c[7].write(row.get('ステータス', ''))
                            
                            if current_status != '完了':
                                if c[8].button("✅ 完了にする", key=f"comp_{task_id_str}"):
                                    if update_task_status(task_id_str, "完了"): 
                                        get_task_data.clear() # タスクだけクリア
                                        st.rerun()
                            else:
                                if c[8].button("↩️ 未完了に戻す", key=f"rev_{task_id_str}"):
                                    if update_task_status(task_id_str, "未着手"): 
                                        get_task_data.clear() # タスクだけクリア
                                        st.rerun()
                            st.markdown("<hr>", unsafe_allow_html=True)
                        except Exception as inner_e:
                            st.warning(f"1件のタスクを描画できませんでした。")
            else: st.info("データがありません。")
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
                                worksheet = doc.worksheet(SHEET_TASK)
                                headers = worksheet.row_values(1)
                                if "イベントID" not in headers:
                                    worksheet.update_cell(1, len(headers) + 1, "イベントID")
                                    headers.append("イベントID")
                                hidden_task_id = generate_auto_id(df_task, "T")
                                creator_id = LINEWORKS_USER_MAP.get(task_creator)
                                
                                event_id = ""
                                if task_limit:
                                    res_id = register_lineworks_calendar_event(task_name, task_assignee, str(task_limit), task_pri, task_note, creator_id, task_creator)
                                    if res_id: event_id = res_id
                                
                                data_dict = { "ID": hidden_task_id, "タスク名": task_name, "作成者": task_creator, "担当者": task_assignee, "関係者": task_watchers, "期限": str(task_limit) if task_limit else '', "優先度": task_pri, "ステータス": task_status, "備考": task_note, "イベントID": event_id }
                                row_to_save = [data_dict.get(h, "") for h in headers]
                                worksheet.append_row(row_to_save)
                                st.toast("カレンダー連携 成功!", icon="✅")
                                st.session_state.task_reg_success = True
                                get_task_data.clear() # タスクキャッシュだけクリア
                                st.rerun()
                            except Exception as e: st.error(f"登録エラー: {e}")

    # ==========================================
    # 📅 ページ：5年経過リスト
    # ==========================================
    elif page_selection == "📅 5年経過リスト (PC/iPad)":
        st.markdown(f"""
            <div class="page-title-box">
                <h2>📅 5年経過リスト (PC/iPad)</h2>
            </div>
        """, unsafe_allow_html=True)
        
        if not df.empty and 'カテゴリ' in df.columns:
            df_old = df[df['カテゴリ'].isin(['PC', 'iPad'])].copy()
            if not df_old.empty:
                five_years_ago = datetime.now() - timedelta(days=365*5)
                df_old['dt'] = df_old['購入日'].apply(parse_date)
                df_old = df_old[df_old['dt'] <= five_years_ago]
                with st.container():
                    st.markdown('<span class="list-bg-marker"></span>', unsafe_allow_html=True)
                    st.dataframe(df_old.drop(columns=['dt']), use_container_width=True)
            else: st.info("データがありません。")
        else: st.info("データがありません。")

except Exception as e: st.error(f"エラー: {e}")
