import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- 🎨 UIデザインの復元 (CSS) ---
st.markdown("""
    <style>
        /* メインコンテナの余白調整 */
        .block-container { padding-top: 4rem !important; padding-bottom: 5rem; }
        
        /* タイトルヘッダーを上部に固定 */
        div[data-testid="stVerticalBlock"] > div:has(h1) {
            position: sticky !important; top: 2.875rem !important; background-color: white !important;
            z-index: 1000 !important; padding-top: 1rem !important; padding-bottom: 0.5rem !important;
            border-bottom: 2px solid #f0f2f6; margin-bottom: 0 !important;
        }
        h1 { margin: 0 !important; padding: 0 !important; font-size: 1.8rem !important; }
        
        /* タブ/ラジオボタンの固定 */
        div[data-baseweb="tab-list"], div[role="tablist"], .stRadio > div {
            position: sticky !important; top: 6.8rem !important; background-color: white !important;
            z-index: 999 !important; padding-top: 0.5rem !important; padding-bottom: 0.5rem !important;
        }
        
        /* ボタンを小さく、行間をタイトに */
        .stButton button { height: 1.8rem !important; min-height: 1.8rem !important; font-size: 0.85rem !important; padding: 0 1rem !important; }
        p, .stMarkdown { margin-bottom: 0px !important; font-size: 0.95rem !important; line-height: 1.8rem !important; }
        hr { margin: 5px 0 !important; }
        
        /* アラートボックスの装飾 */
        .alert-row {
            background-color: #fff5f5;
            border-left: 5px solid #ff4b4b;
            padding: 0.5rem 1rem;
            margin-bottom: 5px;
            border-radius: 0 5px 5px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    </style>
""", unsafe_allow_html=True)

# --- 設定 ---
CATEGORY_MAP = {
    "PC": "PC", "訪問車": "訪問車", "iPad": "iPad", "携帯電話": "携帯電話",
    "Office365": "Office365", "ウイルスバスター": "ウイルスバスター", "その他機器": "その他機器"
}
SHEET_NEW_EMPLOYEE = "新規入職者"
SHEET_CERTIFICATE = "電子証明書"

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

# --- データ操作関数 ---
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
st.title("🏢 総務備品管理システム")

with st.sidebar:
    page = st.radio("メニュー", ["📦 在庫管理", "🔐 電子証明書管理", "👤 新規入職者管理", "📅 5年経過リスト"])
    st.markdown("---")
    if st.button("🔄 データを最新に更新"): get_all_data.clear(); st.rerun()

# --- 電子証明書管理ページ ---
if page == "🔐 電子証明書管理":
    st.subheader("電子証明書の管理")
    tab_cert = st.radio("表示切替", ["📋 一覧・アラート", "➕ 新規登録"], horizontal=True)
    df_cert = get_certificate_data()

    if tab_cert == "📋 一覧・アラート":
        if not df_cert.empty:
            today = datetime.now().date()
            alert_found = False
            
            # アラート表示エリア
            for i, row in df_cert.iterrows():
                dt = parse_date(row.get('有効期限'))
                if dt:
                    diff = (dt.date() - today).days
                    if diff <= 75:
                        if not alert_found:
                            st.markdown("##### ⚠️ 期限切れ間近のアラート (75日以内)")
                            alert_found = True
                        
                        # 指定のフォーマットで表示
                        msg = f"あと{diff}日" if diff >= 0 else "超過"
                        exp_str = dt.strftime('%Y-%m-%d')
                        cert_type = row.get('種類', '不明')
                        
                        col_text, col_btn = st.columns([5, 1])
                        with col_text:
                            st.markdown(f"**{cert_type} : 有効期限 {msg} ({exp_str})**")
                        with col_btn:
                            if st.button("詳細", key=f"btn_cert_{i}"):
                                show_cert_dialog(row)
                        st.markdown('<hr>', unsafe_allow_html=True)
            
            if not alert_found:
                st.success("期限が近い証明書はありません。")
            
            st.markdown("##### 📋 全データ一覧")
            st.dataframe(df_cert, use_container_width=True)

    elif tab_cert == "➕ 新規登録":
        with st.form("new_cert_form"):
            new_id = generate_auto_id(df_cert, "I")
            c_type = st.text_input("種類 (例: 電子請求書, e-Tax)")
            c_dev = st.text_input("インストール端末")
            c_exp = st.date_input("有効期限")
            c_note = st.text_area("備考")
            if st.form_submit_button("新規登録"):
                worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_CERTIFICATE)
                worksheet.append_row([new_id, c_type, c_dev, str(c_exp), c_note])
                st.success("登録完了しました！"); st.rerun()

# --- その他のページ (在庫管理など) ---
elif page == "📦 在庫管理":
    st.subheader("在庫・備品一覧")
    df = get_all_data()
    st.dataframe(df, use_container_width=True)

else:
    st.info(f"{page} 画面は現在調整中です。")
