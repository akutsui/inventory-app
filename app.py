import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time
import jwt
import requests

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- CSS (UI調整: 極限までコンパクト化) ---
st.markdown("""
    <style>
        .block-container { padding-top: 4rem !important; padding-bottom: 5rem; }
        div[data-testid="stVerticalBlock"] > div:has(h1) {
            position: sticky !important; top: 2.875rem !important; background-color: white !important;
            z-index: 1000 !important; padding-top: 1rem !important; padding-bottom: 0.5rem !important;
            border-bottom: 2px solid #f0f2f6; margin-bottom: 0 !important;
        }
        h1 { margin: 0 !important; padding: 0 !important; font-size: 1.8rem !important; }
        div[data-baseweb="tab-list"], div[role="tablist"], div[data-testid="stTabs"] > div:first-child {
            position: sticky !important; top: 6.8rem !important; background-color: white !important;
            z-index: 999 !important; padding-top: 0.5rem !important; padding-bottom: 0.5rem !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        div[data-testid="stTabs"] button { background-color: white !important; }
        .stButton button { height: 1.6rem !important; min-height: 1.6rem !important; padding-top: 0 !important; padding-bottom: 0 !important; margin-top: 2px !important; font-size: 0.8rem !important; }
        p { margin-bottom: 0px !important; padding-bottom: 0px !important; font-size: 0.9rem !important; line-height: 1.7rem !important; }
        hr { margin: 2px 0 !important; padding: 0 !important; }
        div[data-testid="column"] { padding: 0px !important; }
        div.stMarkdown { margin-bottom: 0px !important; }
        div.alert-box { padding: 0.5rem 1rem !important; }
        div[data-testid="stToggle"] { margin-top: 0px; padding-top: 5px; }
        div[data-testid="stToggle"] label { font-size: 0.9rem !important; }
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
# 案A: 名前とLINE WORKS ID（メールアドレス等）の変換辞書
LINEWORKS_USER_MAP = {
    "山田": "yamada@yourdomain.com",  # ←ここを実際のIDに書き換えてください
    "佐藤": "sato@yourdomain.com",
    "鈴木": "suzuki@yourdomain.com"
}
# このリストがプルダウンの選択肢になります
USER_OPTIONS = list(LINEWORKS_USER_MAP.keys())


def get_lineworks_token():
    """LINE WORKSのアクセストークンを取得する関数"""
    try:
        lw_secrets = st.secrets["lineworks"]
        client_id = lw_secrets["client_id"]
        client_secret = lw_secrets["client_secret"]
        service_account = lw_secrets["service_account"]
        private_key = lw_secrets["private_key"]
        
        current_time = int(time.time())
        payload = {
            "iss": client_id,
            "sub": service_account,
            "iat": current_time,
            "exp": current_time + 3600
        }
        encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
        
        url = "https://auth.worksmobile.com/oauth2/v2.0/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "assertion": encoded_jwt,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "task user.read bot"
        }
        res = requests.post(url, headers=headers, data=data)
        if res.status_code == 200:
            return res.json().get("access_token")
        else:
            st.error(f"LINE WORKS トークン取得エラー: {res.text}")
            return None
    except Exception as e:
        st.error(f"LINE WORKS トークン生成エラー: {e}\n（Secretsの設定を確認してください）")
        return None

def create_lineworks_task(task_name, assignee_str, watcher_str, deadline_date, note_text):
    """LINE WORKS APIを使ってタスクを作成する関数"""
    token = get_lineworks_token()
    if not token: return False
    
    # 名前(カンマ区切り)をLINE WORKSのID形式のリストに変換
    assignees = []
    if assignee_str:
        for name in str(assignee_str).split(","):
            user_id = LINEWORKS_USER_MAP.get(name.strip())
            if user_id: assignees.append({"userId": user_id})
            
    watchers = []
    if watcher_str:
        for name in str(watcher_str).split(","):
            user_id = LINEWORKS_USER_MAP.get(name.strip())
            if user_id: watchers.append({"userId": user_id})
            
    payload = {
        "title": task_name,
        "content": note_text if note_text else ""
    }
    if assignees: payload["assignees"] = assignees
    if watchers: payload["watchers"] = watchers
    
    # 期限の設定 (LINE WORKSの仕様上 ISO8601形式が必要)
    if deadline_date:
        # 期限日の23:59:59を期限とする
        deadline_str = f"{deadline_date}T23:59:59+09:00"
        payload["dueDate"] = deadline_str
        
    url = "https://www.worksapis.com/v1.0/tasks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code in [200, 201]:
        return True
    else:
        st.error(f"LINE WORKS タスク作成エラー: {res.text}")
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

def clear_search():
    st.session_state.active_search_query = ""
    st.session_state.page_number = 0

# --- ダイアログ ---
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
                else:
                    custom_values[col] = st.text_input(col, value=val)

        if st.form_submit_button("✅ 更新する"):
            worksheet = client.open(SPREADSHEET_NAME).worksheet(CATEGORY_MAP[cat])
            cell = worksheet.find(str(row_data['ID']))
            if cell:
                row_to_save = [row_data['ID'], cat, new_name, new_user, new_status, datetime.now().strftime('%Y-%m-%d')]
                cols = ["利用者1", "利用者2
