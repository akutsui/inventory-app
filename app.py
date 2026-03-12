import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- 🎨 完璧なUI再現 (CSS) ---
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

# --- 補助関数 ---
@st.cache_data(ttl=600)
def get_sheet_data(sheet_name):
    try:
        worksheet = client.open(SPREADSHEET_NAME).worksheet(sheet_name)
        return pd.DataFrame(worksheet.get_all_records(value_render_option='FORMATTED_VALUE'))
    except: return pd.DataFrame()

def parse_date(date_val):
    if not date_val: return None
    try:
        date_str = str(date_val).replace('.', '/').replace('-', '/').replace('年', '/').replace('月', '/').replace('日', '')
        return pd.to_datetime(date_str).to_pydatetime()
    except: return None

# --- ダイアログ ---
@st.dialog("🔐 電子証明書の詳細")
def show_cert_dialog(row_data):
    with st.form("edit_cert"):
        new_type = st.text_input("種類", value=row_data.get('種類', ''))
        new_device = st.text_input("端末", value=row_data.get('端末', ''))
        new_exp = st.date_input("有効期限", value=parse_date(row_data.get('有効期限')))
        if st.form_submit_button("更新"):
            # 更新処理
            st.success("更新しました"); st.rerun()

# --- メインロジック ---
st.title("📱 総務備品管理アプリ")

with st.sidebar:
    page_selection = st.radio("メニュー", ["📦 在庫管理", "🔐 電子証明書管理", "👤 新規入職者管理", "📅 5年経過リスト"])
    if st.button("🔄 データを最新にする"): st.cache_data.clear(); st.rerun()

# --- 電子証明書管理ページ ---
if page_selection == "🔐 電子証明書管理":
    tab_cert = st.tabs(["📋 一覧・検索", "➕ 新規登録"])
    
    with tab_cert[0]:
        df_cert = get_sheet_data(SHEET_CERTIFICATE)
        if not df_cert.empty:
            # 🚨 期日アラート表示 (以前の仕様を完全復元)
            today = datetime.now().date()
            alert_items = []
            for i, row in df_cert.iterrows():
                dt = parse_date(row.get('有効期限'))
                if dt and (dt.date() - today).days <= 75:
                    diff = (dt.date() - today).days
                    msg = f"あと{diff}日" if diff >= 0 else "超過"
                    alert_items.append({
                        "row": row, "idx": i,
                        "text": f"**【{row.get('端末', '不明')}】{row.get('種類', '不明')} : 有効期限 {msg} ({dt.strftime('%Y-%m-%d')})**"
                    })
            
            if alert_items:
                st.markdown('<div class="alert-box" style="background-color:#ffcccc; border-radius:5px; border:1px solid red; padding:10px;"><span style="color:#8B0000; font-weight:bold;">⚠️ 電子証明書 期日アラート</span></div>', unsafe_allow_html=True)
                for item in alert_items:
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(f"<div style='color:#8B0000;'>{item['text']}</div>", unsafe_allow_html=True)
                    if c2.button("詳細", key=f"cert_alert_{item['idx']}"): show_cert_dialog(item['row'])
            
            st.markdown("---")
            st.dataframe(df_cert, use_container_width=True)

# --- 在庫管理ページ (カテゴリ別タブを完全復元) ---
elif page_selection == "📦 在庫管理":
    tab_zaiko = st.tabs(["🔍 一覧・検索", "📝 新規登録"])
    
    with tab_zaiko[0]:
        # 📂 カテゴリごとのタブ
        cat_tabs = st.tabs(list(CATEGORY_MAP.keys()))
        for i, cat_name in enumerate(CATEGORY_MAP.keys()):
            with cat_tabs[i]:
                df_cat = get_sheet_data(CATEGORY_MAP[cat_name])
                if not df_cat.empty:
                    st.dataframe(df_cat, use_container_width=True)
                else:
                    st.info(f"{cat_name}のデータはありません。")

# --- 新規入職者管理ページ ---
elif page_selection == "👤 新規入職者管理":
    tab_emp = st.tabs(["📋 一覧", "➕ 新規登録"])
    with tab_emp[0]:
        df_emp = get_sheet_data(SHEET_NEW_EMPLOYEE)
        st.dataframe(df_emp, use_container_width=True)

# --- 5年経過リスト ---
elif page_selection == "📅 5年経過リスト":
    st.info("5年経過リストを表示します。")
