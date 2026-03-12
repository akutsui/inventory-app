import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- 🎨 以前のUIデザインを完全復元 (CSS) ---
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

# --- Google Sheets API 接続 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- セッションステート初期化（エラー回避用フラグ） ---
if 'force_switch_cert' not in st.session_state: st.session_state['force_switch_cert'] = False

# --- データ取得関数 ---
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

# --- ダイアログ ---
@st.dialog("🔐 電子証明書の詳細編集")
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
    page_selection = st.radio("メニュー", ["📦 在庫管理", "🔐 電子証明書管理", "👤 新規入職者管理", "📅 5年経過リスト"])
    if st.button("🔄 データを最新にする"): get_all_data.clear(); st.rerun()

# --- 各ページのコンテンツ ---
if page_selection == "🔐 電子証明書管理":
    # エラー回避用のタブ切り替え制御
    if st.session_state.force_switch_cert:
        st.session_state.tab_cert_key = "📋 一覧・検索"
        st.session_state.force_switch_cert = False

    tab_cert = st.radio("機能", ["📋 一覧・検索", "➕ 新規登録"], horizontal=True, key="tab_cert_key")
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
                        exp_date_str = dt.strftime('%Y-%m-%d')
                        alert_items.append({
                            "row": row,
                            "index": i,
                            "display_text": f"**【{device_name}】{cert_type} : 有効期限 {msg} ({exp_date_str})**"
                        })
            
            if alert_items:
                st.markdown("""
                    <div class="alert-box" style="background-color: #ffcccc; padding: 0.2rem 0.5rem; border-radius: 0.5rem; border: 1px solid #ff4b4b;">
                        <h5 style="margin: 0; padding: 0.2rem 0; color: #8B0000; font-size: 1rem;">⚠️ 電子証明書 期日アラート (75日以内)</h5>
                    </div>
                """, unsafe_allow_html=True)
                for item in alert_items:
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(f"<div style='color: #8B0000;'>{item['display_text']}</div>", unsafe_allow_html=True)
                    if c2.button("詳細", key=f"alert_cert_btn_{item['index']}"):
                        show_cert_dialog(item['row'])
                    st.markdown('<hr style="margin: 0.2rem 0; border-top: 1px dotted #ff9999;">', unsafe_allow_html=True)
            
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

elif page_selection == "📦 在庫管理":
    st.markdown("#### 在庫・備品一覧")
    df = get_all_data()
    st.dataframe(df, use_container_width=True)

else:
    st.info(f"{page_selection} 画面は現在準備中です。")
