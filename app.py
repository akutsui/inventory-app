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
    "その他機器": "その他機器" # 変更
}

# --- 設定: 新規入職者管理用のシート名とタスク項目 ---
SHEET_NEW_EMPLOYEE = "新規入職者"
ONBOARDING_TASKS = [
    "PC", "iPad", "携帯", "駐車場", 
    "LineworksID", "モバカルモバナーID", 
    "MCS", "アルコールチェックID", "訪問車両", 
    "備品", "机・椅子"
]

# --- 設定: 各シートの列定義 ---
COLUMNS_DEF = {
    "PC": [
        "使用部署", "購入日", "OS", "プロダクトID(シリアルNo)", "ラベル",
        "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", 
        "officeのアカウント割振", "ウィルスバスターシリアルNo", "ウィルスバスター期限", "ウィルスバスター識別ネーム",
        "チームビューワID", "チームビューワPW", "備考"
    ],
    "訪問車": [
        "登録番号", "洗車グループ", "駐車場", 
        "タイヤサイズ", "スタッドレス有無", "タイヤ保管場所", 
        "リース開始日", "リース満了日", "車検満了日", 
        "駐禁除外指定満了日", "通行禁止許可満了日", "使用部署", "備考"
    ],
    "iPad": [
        "購入日", "ラベル", "AppleID", "AppleIDパスワード", "シリアルNo",
        "ストレージ", "製造番号IMEI", "端末番号", 
        "使用部署", "キャリア", "備考"
    ],
    "携帯電話": [
        "購入日", "電話番号", "SIM", "メーカー",
        "製造番号", "使用部署", "保管場所", "キャリア", "備考"
    ],
    "Office365": [
        "アカウントID", "パスワード", "利用者1", "利用者2", "利用者3", "利用者4", "利用者5", "備考"
    ],
    "ウイルスバスター": [
        "利用者1", "利用者2", "利用者3", "期限", "備考"
    ],
    "その他機器": [ # 変更
        "備考"
    ]
}

# --- 設定: クラウドの金庫(Secrets)から情報を取得 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- セッションステート初期化 ---
if 'form_data' not in st.session_state:
    st.session_state['form_data'] = {}
if 'page_number' not in st.session_state:
    st.session_state['page_number'] = 0
if 'active_search_query' not in st.session_state:
    st.session_state['active_search_query'] = ""

# --- データ取得関数 (在庫用) ---
@st.cache_data(ttl=600)
def get_all_data():
    all_data = []
    for cat_name, sheet_name in CATEGORY_MAP.items():
        try:
            worksheet = client.open(SPREADSHEET_NAME).worksheet(sheet_name)
            records = worksheet.get_all_records(value_render_option='FORMATTED_VALUE')
            for record in records:
                record['カテゴリ'] = cat_name
            all_data.extend(records)
        except gspread.WorksheetNotFound:
            pass
        except Exception:
            pass
    
    df = pd.DataFrame(all_data)
    
    if not df.empty:
        df['sort_order'] = df['ステータス'].apply(lambda x: 1 if x == '廃棄' else 0)
        df = df.sort_values(by=['sort_order', 'ID'], ascending=[True, True])
    
    return df

# --- データ取得関数 (新規入職者用: エラーハンドリング強化) ---
def get_new_employee_data():
    try:
        worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except gspread.WorksheetNotFound:
        return None
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return pd.DataFrame()

# --- ヘルパー関数: テキストの自動リンク化を防ぐ ---
def safe_text(text):
    if text is None: return ""
    return str(text).replace("@", "@\u200B")

# --- 【最強版】日付パース関数 ---
def parse_date(date_val):
    if date_val is None or date_val == "":
        return None
    
    if isinstance(date_val, (int, float)):
        try:
            return datetime(1899, 12, 30) + timedelta(days=date_val)
        except:
            pass

    date_str = str(date_val).strip()
    if not date_str:
        return None

    date_str = date_str.replace('.', '/').replace('-', '/').replace('年', '/').replace('月', '/').replace('日', '')
    
    try:
        ts = pd.to_datetime(date_str, errors='coerce')
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except:
        return None

# --- 検索実行用コールバック関数 ---
def submit_search():
    st.session_state.active_search_query = st.session_state.input_search_key
    st.session_state.input_search_key = "" 
    st.session_state.page_number = 0

# --- 検索解除用コールバック関数 ---
def clear_search():
    st.session_state.active_search_query = ""
    st.session_state.page_number = 0

# --- ポップアップ詳細・編集画面 (在庫用) ---
@st.dialog("📝 詳細情報の編集")
def show_detail_dialog(row_data):
    st.caption("ここで内容を修正して「更新」ボタンを押すと保存されます。")
    
    def get_date_val(key):
        return parse_date(row_data.get(key))

    with st.form("edit_dialog_form"):
        st.write(f"**ID:** {row_data['ID']}")
        st.write(f"**カテゴリ:** {row_data['カテゴリ']}")
        
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("品名", value=row_data['品名'])
            new_user = st.text_input("利用者(代表)", value=row_data['利用者'])
        with col2:
            status_options = ["利用可能", "利用中", "貸出中", "故障/修理中", "廃棄"]
            curr_status = row_data['ステータス']
            idx_status = status_options.index(curr_status) if curr_status in status_options else 0
            new_status = st.selectbox("ステータス", status_options, index=idx_status)
        
        st.markdown("---")
        
        cat = row_data['カテゴリ']
        custom_values = {}

        if cat == "PC":
            c1, c2 = st.columns(2)
            with c1:
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署'))
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['OS'] = st.text_input("OS", value=row_data.get('OS'))
                custom_values['プロダクトID(シリアルNo)'] = st.text_input("プロダクトID(シリアルNo)", value=row_data.get('プロダクトID(シリアルNo)'))
                custom_values['ラベル'] = st.text_input("ラベル", value=row_data.get('ラベル'))
            with c2:
                custom_values['officeのアカウント割振'] = st.text_input("officeのアカウント割振", value=row_data.get('officeのアカウント割振'))
                custom_values['ORCA宇都宮'] = st.text_input("ORCA宇都宮", value=row_data.get('ORCA宇都宮'))
                custom_values['ORCA鹿沼'] = st.text_input("ORCA鹿沼", value=row_data.get('ORCA鹿沼'))
                custom_values['ORCA益子'] = st.text_input("ORCA益子", value=row_data.get('ORCA益子'))
                custom_values['チームビューワID'] = st.text_input("チームビューワID", value=row_data.get('チームビューワID'))
                custom_values['チームビューワPW'] = st.text_input("チームビューワPW", value=row_data.get('チームビューワPW'))
            st.caption("ウィルスバスター情報")
            c3, c4, c5 = st.columns(3)
            with c3: custom_values['ウィルスバスターシリアルNo'] = st.text_input("VBシリアルNo", value=row_data.get('ウィルスバスターシリアルNo'))
            with c4: 
                d_vb = st.date_input("VB期限", value=get_date_val('ウィルスバスター期限'))
                custom_values['ウィルスバスター期限'] = d_vb.strftime('%Y-%m-%d') if d_vb else ''
            with c5: custom_values['ウィルスバスター識別ネーム'] = st.text_input("VB識別ネーム", value=row_data.get('ウィルスバスター識別ネーム'))
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        elif cat == "訪問車":
            c1, c2 = st.columns(2)
            with c1:
                custom_values['登録番号'] = st.text_input("登録番号", value=row_data.get('登録番号'))
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署'))
                custom_values['洗車グループ'] = st.text_input("洗車グループ", value=row_data.get('洗車グループ'))
                custom_values['駐車場'] = st.text_input("駐車場", value=row_data.get('駐車場'))
                custom_values['タイヤサイズ'] = st.text_input("タイヤサイズ", value=row_data.get('タイヤサイズ'))
                custom_values['タイヤ保管場所'] = st.text_input("タイヤ保管場所", value=row_data.get('タイヤ保管場所'))
                custom_values['スタッドレス有無'] = st.text_input("スタッドレス有無", value=row_data.get('スタッドレス有無'))
            with c2:
                d_lease_s = st.date_input("リース開始日", value=get_date_val('リース開始日'))
                custom_values['リース開始日'] = d_lease_s.strftime('%Y-%m-%d') if d_lease_s else ''
                d_lease_e = st.date_input("リース満了日", value=get_date_val('リース満了日'))
                custom_values['リース満了日'] = d_lease_e.strftime('%Y-%m-%d') if d_lease_e else ''
                d_syaken = st.date_input("車検満了日", value=get_date_val('車検満了日'))
                custom_values['車検満了日'] = d_syaken.strftime('%Y-%m-%d') if d_syaken else ''
                d_park = st.date_input("駐禁除外指定満了日", value=get_date_val('駐禁除外指定満了日'))
                custom_values['駐禁除外指定満了日'] = d_park.strftime('%Y-%m-%d') if d_park else ''
                d_road = st.date_input("通行禁止許可満了日", value=get_date_val('通行禁止許可満了日'))
                custom_values['通行禁止許可満了日'] = d_road.strftime('%Y-%m-%d') if d_road else ''
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        elif cat == "iPad":
            c1, c2 = st.columns(2)
            with c1:
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['ラベル'] = st.text_input("ラベル", value=row_data.get('ラベル'))
                custom_values['AppleID'] = st.text_input("AppleID", value=row_data.get('AppleID'))
                custom_values['AppleIDパスワード'] = st.text_input("AppleIDパスワード", value=row_data.get('AppleIDパスワード'))
                custom_values['シリアルNo'] = st.text_input("シリアルNo", value=row_data.get('シリアルNo'))
                custom_values['ストレージ'] = st.text_input("ストレージ", value=row_data.get('ストレージ'))
            with c2:
                custom_values['製造番号IMEI'] = st.text_input("製造番号IMEI", value=row_data.get('製造番号IMEI'))
                custom_values['端末番号'] = st.text_input("端末番号", value=row_data.get('端末番号'))
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署'))
                custom_values['キャリア'] = st.text_input("キャリア", value=row_data.get('キャリア'))
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        elif cat == "携帯電話":
            c1, c2 = st.columns(2)
            with c1:
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['電話番号'] = st.text_input("電話番号", value=row_data.get('電話番号'))
                custom_values['SIM'] = st.text_input("SIM", value=row_data.get('SIM'))
                custom_values['メーカー'] = st.text_input("メーカー", value=row_data.get('メーカー'))
            with c2:
                custom_values['製造番号'] = st.text_input("製造番号", value=row_data.get('製造番号'))
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署'))
                custom_values['保管場所'] = st.text_input("保管場所", value=row_data.get('保管場所'))
                custom_values['キャリア'] = st.text_input("キャリア", value=row_data.get('キャリア'))
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        elif cat == "Office365":
            c1, c2 = st.columns(2)
            with c1: custom_values['アカウントID'] = st.text_input("アカウントID", value=row_data.get('アカウントID'))
            with c2: custom_values['パスワード'] = st.text_input("パスワード", value=row_data.get('パスワード'))
            
            st.caption("共有利用者")
            c_u1, c_u2, c_u3 = st.columns(3)
            with c_u1: custom_values['利用者1'] = st.text_input("利用者1", value=row_data.get('利用者1'))
            with c_u2: custom_values['利用者2'] = st.text_input("利用者2", value=row_data.get('利用者2'))
            with c_u3: custom_values['利用者3'] = st.text_input("利用者3", value=row_data.get('利用者3'))
            
            c_u4, c_u5 = st.columns(2)
            with c_u4: custom_values['利用者4'] = st.text_input("利用者4", value=row_data.get('利用者4'))
            with c_u5: custom_values['利用者5'] = st.text_input("利用者5", value=row_data.get('利用者5'))
            
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        elif cat == "ウイルスバスター":
            st.caption("利用者情報")
            c1, c2, c3 = st.columns(3)
            with c1: custom_values['利用者1'] = st.text_input("利用者1", value=row_data.get('利用者1'))
            with c2: custom_values['利用者2'] = st.text_input("利用者2", value=row_data.get('利用者2'))
            with c3: custom_values['利用者3'] = st.text_input("利用者3", value=row_data.get('利用者3'))
            
            st.caption("期限")
            d_exp = st.date_input("期限", value=get_date_val('期限'))
            custom_values['期限'] = d_exp.strftime('%Y-%m-%d') if d_exp else ''
            
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        elif cat == "その他機器": # 変更
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

        st.markdown("---")
        if st.form_submit_button("✅ この内容で更新する"):
            try:
                target_sheet_name = CATEGORY_MAP[cat]
                worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                current_time = datetime.now().strftime('%Y-%m-%d')
                
                row_to_save = [
                    row_data['ID'], cat, new_name, new_user, new_status, current_time
                ]
                for col_name in COLUMNS_DEF.get(cat, []):
                    row_to_save.append(custom_values.get(col_name, ''))
                
                cell = worksheet.find(str(row_data['ID']))
                if cell:
                    r = cell.row
                    worksheet.update(f"A{r}", [row_to_save])
                    st.toast("更新しました！", icon="✅")
                    get_all_data.clear()
                    st.rerun()
                else:
                    st.error("エラー: IDが見つかりませんでした。")
            except Exception as e:
                st.error(f"更新エラー: {e}")

# --- ポップアップ詳細・タスク管理 (新規入職者用) ---
@st.dialog("📝 入職準備タスク管理")
def show_onboarding_task_dialog(row_data):
    st.write(f"### {row_data['氏名']} 様 (ID: {row_data['ID']})")
    
    with st.form("onboarding_task_form"):
        # 基本情報の編集
        c_basic1, c_basic2, c_basic3 = st.columns(3)
        with c_basic1:
            val_date = parse_date(row_data.get('入職日'))
            new_date = st.date_input("入職日", value=val_date)
        with c_basic2:
            new_job = st.text_input("職種", value=row_data.get('職種', ''))
        with c_basic3:
            new_dept = st.text_input("部署", value=row_data.get('部署', ''))

        st.markdown("---")
        st.subheader("準備アイテム (フリーワード入力)")
        
        # テキストボックスの状態を保持する辞書
        task_status = {}
        
        # 2列で表示
        cols = st.columns(2)
        for i, task_name in enumerate(ONBOARDING_TASKS):
            with cols[i % 2]:
                # 既存の値を初期値として表示. getで安全に取得
                current_val = str(row_data.get(task_name, ''))
                task_status[task_name] = st.text_input(task_name, value=current_val)
        
        st.markdown("---")
        status_options = ["準備中", "完了", "保留"]
        curr_status = row_data.get('ステータス', '準備中')
        if curr_status not in status_options: curr_status = "準備中"
        new_status = st.selectbox("全体のステータス", status_options, index=status_options.index(curr_status))
        
        new_note = st.text_area("備考", value=row_data.get('備考', ''))
        
        if st.form_submit_button("✅ 更新する"):
            try:
                worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
                
                # 更新用データの構築
                # ID, 氏名, 入職日, 職種, 部署, ステータス, PC...その他, 備考
                row_to_save = [
                    row_data['ID'],
                    row_data['氏名'],
                    str(new_date),  # 更新された日付
                    new_job,        # 更新された職種
                    new_dept,       # 更新された部署
                    new_status
                ]
                
                # タスク列の値を追加
                for task_name in ONBOARDING_TASKS:
                    row_to_save.append(task_status[task_name])
                
                row_to_save.append(new_note)
                
                # IDで行を検索して更新
                cell = worksheet.find(str(row_data['ID']))
                if cell:
                    r = cell.row
                    # A列から最後まで一括更新
                    worksheet.update(f"A{r}", [row_to_save])
                    st.toast("更新しました！", icon="✅")
                    st.rerun()
                else:
                    st.error("エラー: IDが見つかりませんでした。")
            except Exception as e:
                st.error(f"更新エラー: {e}")

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

with st.sidebar:
    # ページ切替ラジオボタン
    page_selection = st.radio("メニュー切替", ["📦 在庫管理 (メイン)", "👤 新規入職者管理", "📅 5年経過リスト (PC/iPad)"])
    
    st.markdown("---")
    
    if st.button("🔄 データを最新にする"):
        get_all_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    with st.expander("❓ 操作マニュアル", expanded=False):
        st.markdown("""
        **1. メニュー切替**
        * 左上のメニューで各機能画面を切り替えられます。

        **2. 新規入職者管理**
        * 入職者のPCや制服などの準備状況をフリーワードで管理できます。
        * ステータスが「完了」の人は一覧の下に移動します。
        
        **3. 検索機能 (在庫管理)**
        * 画面上部の枠に文字を入れて `Enter` を押すと検索できます。

        **4. 訪問車期日アラート**
        * 期限が **45日以内**（車）の場合、検索窓の下に赤字で警告が出ます。

        **5. 5年経過リスト**
        * 購入から5年以上経過したPCとiPadだけを一覧表示します。
        """)

try:
    df = get_all_data()

    # ==========================================
    # ページ1：在庫管理 (メイン)
    # ==========================================
    if page_selection == "📦 在庫管理 (メイン)":
        main_tab1, main_tab2, main_tab3 = st.tabs(["🔍 一覧・検索", "📝 新規登録", "📂 CSV一括入出力"])

        # === タブ1：一覧・検索 ===
        with main_tab1:
            st.markdown("#### 在庫データの検索")
            
            # --- アラートデータの収集 ---
            alert_items = []
            today = datetime.now().date()
            
            if not df.empty:
                for index, row in df.iterrows():
                    status = str(row.get('ステータス', '')).strip()
                    if status == '廃棄':
                        continue

                    cat = row.get('カテゴリ')
                    name = row.get('品名', '名称不明')
                    
                    msg_list = []
                    
                    # --- 訪問車アラート ---
                    if cat == "訪問車":
                        reg_num = str(row.get('登録番号', ''))
                        display_text = f"{name} {reg_num}".strip()
                        
                        check_cols = ["リース満了日", "車検満了日", "駐禁除外指定満了日", "通行禁止許可満了日"]
                        for col in check_cols:
                            val = row.get(col)
                            dt = parse_date(val)
                            if dt:
                                diff = (dt.date() - today).days
                                if diff < 0:
                                    msg_list.append(f"{col} 超過 ({dt.strftime('%Y-%m-%d')})")
                                elif diff <= 45:
                                    msg_list.append(f"{col} あと{diff}日 ({dt.strftime('%Y-%m-%d')})")
                        
                        if msg_list:
                            alert_items.append({
                                "row": row,
                                "title": f"訪問車【{display_text}】",
                                "messages": msg_list
                            })

            # --- アラートの表示 ---
            if alert_items:
                st.markdown("""
                    <div class="alert-box" style="background-color: #ffcccc; padding: 0.2rem 0.5rem; border-radius: 0.5rem; border: 1px solid #ff4b4b;">
                        <h5 style="margin: 0; padding: 0.2rem 0; color: #8B0000; font-size: 1rem;">⚠️ 訪問車期日アラート</h5>
                    </div>
                """, unsafe_allow_html=True)

                for i, item in enumerate(alert_items):
                    c1, c2 = st.columns([5, 1])
                    alert_str = f"{item['title']} : " + ", ".join(item['messages'])
                    c1.markdown(f"<div style='color: #8B0000; font-weight: bold;'>{alert_str}</div>", unsafe_allow_html=True)
                    if c2.button("詳細", key=f"alert_btn_{i}"):
                        show_detail_dialog(item['row'])
                    if i < len(alert_items) - 1:
                        st.markdown('<hr style="margin: 0.2rem 0; border-top: 1px dotted #ff9999;">', unsafe_allow_html=True)
                
                st.write("")

            # --- 検索窓 ---
            col_search_input, col_clear_btn = st.columns([4, 1])
            with col_search_input:
                st.text_input(
                    "フリーワード検索", 
                    placeholder="キーワード入力 (Enterで検索＆クリア)", 
                    key="input_search_key",
                    label_visibility="collapsed",
                    on_change=submit_search
                )
            
            current_query = st.session_state.active_search_query
            if current_query:
                st.info(f"🔍 検索中のワード: **{current_query}**")
                with col_clear_btn:
                    if st.button("検索解除", key="clear_search_btn"):
                        clear_search()
                        st.rerun()

            # --- フィルタリング実行 ---
            filtered_df = df.copy() if not df.empty else pd.DataFrame()
            if not filtered_df.empty:
                if current_query:
                    filtered_df = filtered_df[filtered_df.astype(str).apply(lambda row: row.str.contains(current_query, case=False).any(), axis=1)]
                st.success(f"検索結果: {len(filtered_df)} 件")
            else:
                filtered_df = df

            st.markdown('<hr style="margin: 5px 0; border: 0; border-top: 1px solid #eee;">', unsafe_allow_html=True)

            categories = ["すべて"] + list(CATEGORY_MAP.keys())
            cat_tabs = st.tabs(categories)

            for i, category in enumerate(categories):
                with cat_tabs[i]:
                    if filtered_df.empty:
                        st.warning("該当するデータがありません")
                    else:
                        if category == "すべて":
                            display_df = filtered_df
                            header_g = "詳細1 (G列)"
                            header_h = "詳細2 (H列)"
                        else:
                            display_df = filtered_df[filtered_df['カテゴリ'] == category]
                            cols_def = COLUMNS_DEF.get(category, [])
                            header_g = cols_def[0] if len(cols_def) > 0 else "-"
                            header_h = cols_def[1] if len(cols_def) > 1 else "-"

                        if display_df.empty:
                            st.warning("このカテゴリには該当するデータがありません")
                        else:
                            ITEMS_PER_PAGE = 50
                            total_items = len(display_df)
                            max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
                            if st.session_state.page_number > max_page:
                                st.session_state.page_number = 0
                            
                            current_page = st.session_state.page_number
                            start_idx = current_page * ITEMS_PER_PAGE
                            end_idx = start_idx + ITEMS_PER_PAGE
                            
                            df_to_show = display_df.iloc[start_idx:end_idx]
                            
                            st.caption(f"全 {total_items} 件中、{start_idx + 1} 〜 {min(end_idx, total_items)} 件目を表示中")

                            if category == "PC":
                                cols = st.columns([0.7, 1.0, 1.5, 2.0, 1.5, 1.5, 1.0])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**ラベル**")
                                cols[3].write("**品名**")
                                cols[4].write("**利用者**")
                                cols[5].write("**使用部署**")
                                cols[6].write("**OS**")

                            elif category == "訪問車":
                                cols = st.columns([0.7, 1.2, 1.8, 1.5, 1.5, 1.5, 1.0, 1.5])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**品名**")
                                cols[3].write("**登録番号**")
                                cols[4].write("**利用者**")
                                cols[5].write("**使用部署**")
                                cols[6].write("**ステータス**")
                                cols[7].write("**洗車G**")

                            elif category == "iPad":
                                cols = st.columns([0.7, 1.2, 1.5, 1.8, 1.5, 1.5, 1.0, 1.5])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**ラベル**")
                                cols[3].write("**品名**")
                                cols[4].write("**利用者**")
                                cols[5].write("**使用部署**")
                                cols[6].write("**ステータス**")
                                cols[7].write("**購入日**")

                            elif category == "携帯電話":
                                cols = st.columns([0.7, 1.2, 1.8, 1.5, 1.5, 1.0, 1.5, 1.5])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**品名**")
                                cols[3].write("**利用者**")
                                cols[4].write("**使用部署**")
                                cols[5].write("**ステータス**")
                                cols[6].write("**購入日**")
                                cols[7].write("**電話番号**")
                            
                            elif category == "Office365":
                                cols = st.columns([0.7, 1.0, 1.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**品名**")
                                cols[3].write("**利用者1**")
                                cols[4].write("**利用者2**")
                                cols[5].write("**利用者3**")
                                cols[6].write("**利用者4**")
                                cols[7].write("**利用者5**")

                            elif category == "ウイルスバスター":
                                cols = st.columns([0.7, 1.2, 2.0, 1.2, 1.2, 1.2, 1.0, 1.5])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**品名**")
                                cols[3].write("**利用者1**")
                                cols[4].write("**利用者2**")
                                cols[5].write("**利用者3**")
                                cols[6].write("**ステータス**")
                                cols[7].write("**期限**")

                            else:
                                cols = st.columns([0.7, 1.5, 2.0, 1.5, 1.2, 1.5, 1.5])
                                cols[0].write("**編集**")
                                cols[1].write("**ID**")
                                cols[2].write("**品名**")
                                cols[3].write("**利用者**")
                                cols[4].write("**ステータス**")
                                cols[5].write(f"**{header_g}**")
                                cols[6].write(f"**{header_h}**")
                            
                            with st.container(height=500, border=True):
                                for index, row in df_to_show.iterrows():
                                    if category == "PC":
                                        c = st.columns([0.7, 1.0, 1.5, 2.0, 1.5, 1.5, 1.0])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{row.get('ラベル', '')}**")
                                        c[3].write(f"**{safe_text(row['品名'])}**")
                                        c[4].write(f"{row['利用者']}")
                                        c[5].write(f"{row.get('使用部署', '')}") # 列があれば表示
                                        c[6].write(f"{row.get('OS', '')}")

                                    elif category == "訪問車":
                                        c = st.columns([0.7, 1.2, 1.8, 1.5, 1.5, 1.5, 1.0, 1.5])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{safe_text(row['品名'])}**")
                                        c[3].write(f"{row.get('登録番号', '')}")
                                        c[4].write(f"{row['利用者']}")
                                        c[5].write(f"{row.get('使用部署', '')}")
                                        
                                        status = row['ステータス']
                                        if status == "利用可能": c[6].info(status, icon="✅")
                                        elif status == "利用中": c[6].success(status, icon="👤")
                                        elif status == "貸出中": c[6].warning(status, icon="🏃")
                                        elif status == "故障/修理中": c[6].error(status, icon="⚠️")
                                        else: c[6].write(status)
                                        
                                        c[7].write(f"{row.get('洗車グループ', '')}")

                                    elif category == "iPad":
                                        c = st.columns([0.7, 1.2, 1.5, 1.8, 1.5, 1.5, 1.0, 1.5])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{row.get('ラベル', '')}**")
                                        c[3].write(f"**{safe_text(row['品名'])}**")
                                        c[4].write(f"{row['利用者']}")
                                        c[5].write(f"{row.get('使用部署', '')}")
                                        
                                        status = row['ステータス']
                                        if status == "利用可能": c[6].info(status, icon="✅")
                                        elif status == "利用中": c[6].success(status, icon="👤")
                                        elif status == "貸出中": c[6].warning(status, icon="🏃")
                                        elif status == "故障/修理中": c[6].error(status, icon="⚠️")
                                        else: c[6].write(status)
                                        
                                        c[7].write(f"{row.get('購入日', '')}")

                                    elif category == "携帯電話":
                                        c = st.columns([0.7, 1.2, 1.8, 1.5, 1.5, 1.0, 1.5, 1.5])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{safe_text(row['品名'])}**")
                                        c[3].write(f"{row['利用者']}")
                                        c[4].write(f"{row.get('使用部署', '')}")
                                        
                                        status = row['ステータス']
                                        if status == "利用可能": c[5].info(status, icon="✅")
                                        elif status == "利用中": c[5].success(status, icon="👤")
                                        elif status == "貸出中": c[5].warning(status, icon="🏃")
                                        elif status == "故障/修理中": c[5].error(status, icon="⚠️")
                                        else: c[5].write(status)

                                        c[6].write(f"{row.get('購入日', '')}")
                                        c[7].write(f"{row.get('電話番号', '')}")
                                    
                                    elif category == "Office365":
                                        c = st.columns([0.7, 1.0, 1.5, 1.0, 1.0, 1.0, 1.0, 1.0])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{safe_text(row['品名'])}**")
                                        c[3].write(f"{row.get('利用者1', '')}")
                                        c[4].write(f"{row.get('利用者2', '')}")
                                        c[5].write(f"{row.get('利用者3', '')}")
                                        c[6].write(f"{row.get('利用者4', '')}")
                                        c[7].write(f"{row.get('利用者5', '')}")

                                    elif category == "ウイルスバスター":
                                        c = st.columns([0.7, 1.2, 2.0, 1.2, 1.2, 1.2, 1.0, 1.5])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{safe_text(row['品名'])}**")
                                        c[3].write(f"{row.get('利用者1', '')}")
                                        c[4].write(f"{row.get('利用者2', '')}")
                                        c[5].write(f"{row.get('利用者3', '')}")
                                        
                                        status = row['ステータス']
                                        if status == "利用可能": c[6].info(status, icon="✅")
                                        elif status == "利用中": c[6].success(status, icon="👤")
                                        elif status == "貸出中": c[6].warning(status, icon="🏃")
                                        elif status == "故障/修理中": c[6].error(status, icon="⚠️")
                                        else: c[6].write(status)
                                        
                                        c[7].write(f"{row.get('期限', '')}")

                                    else:
                                        c = st.columns([0.7, 1.5, 2.0, 1.5, 1.2, 1.5, 1.5])
                                        if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                            show_detail_dialog(row)
                                        c[1].write(f"{row['ID']}")
                                        c[2].write(f"**{safe_text(row['品名'])}**")
                                        c[3].write(f"{row['利用者']}")
                                        
                                        status = row['ステータス']
                                        if status == "利用可能": c[4].info(status, icon="✅")
                                        elif status == "利用中": c[4].success(status, icon="👤")
                                        elif status == "貸出中": c[4].warning(status, icon="🏃")
                                        elif status == "故障/修理中": c[4].error(status, icon="⚠️")
                                        else: c[4].write(status)

                                        curr_cols_def = COLUMNS_DEF.get(category, [])
                                        val_g = row.get(curr_cols_def[0], '') if len(curr_cols_def) > 0 else ""
                                        val_h = row.get(curr_cols_def[1], '') if len(curr_cols_def) > 1 else ""
                                        c[5].write(f"{val_g}")
                                        c[6].write(f"{val_h}")
                                    
                                    st.markdown('<hr>', unsafe_allow_html=True)

                            st.write("")
                            col_prev, col_page_info, col_next = st.columns([1, 2, 1])
                            
                            with col_prev:
                                if current_page > 0:
                                    if st.button("⬅️ 前の50件", key=f"prev_{category}"):
                                        st.session_state.page_number -= 1
                                        st.rerun()
                            
                            with col_page_info:
                                st.markdown(f"<div style='text-align: center; color: gray;'>Page {current_page + 1} / {max_page + 1}</div>", unsafe_allow_html=True)

                            with col_next:
                                if end_idx < total_items:
                                    if st.button("次の50件 ➡️", key=f"next_{category}"):
                                        st.session_state.page_number += 1
                                        st.rerun()

        # === タブ2：新規登録 (在庫用) ===
        with main_tab2:
            st.header("新規データの登録")
            st.caption("※既存データの編集は、一覧タブの「詳細」ボタンから行ってください。")
            
            st.subheader("① カテゴリとIDを指定")
            selected_category_key = st.radio("カテゴリ", list(CATEGORY_MAP.keys()), horizontal=True, key="new_reg_cat")
            target_sheet_name = CATEGORY_MAP[selected_category_key]

            st.subheader("② 詳細情報の入力")
            with st.form("new_entry_form"):
                col_basic1, col_basic2 = st.columns(2)
                with col_basic1:
                    input_id = st.text_input("ID (資産番号)")
                    input_name = st.text_input("品名 (管理上の名称)")
                with col_basic2:
                    input_user = st.text_input("利用者(代表)")
                    input_status = st.selectbox("ステータス", ["利用可能", "利用中", "貸出中", "故障/修理中", "廃棄"])

                st.markdown("---")
                st.markdown(f"##### 📝 {selected_category_key} 詳細情報")
                
                custom_values = {}

                if selected_category_key == "PC":
                    c1, c2 = st.columns(2)
                    with c1:
                        custom_values['使用部署'] = st.text_input("使用部署")
                        d_buy = st.date_input("購入日", value=None)
                        custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                        custom_values['OS'] = st.text_input("OS")
                        custom_values['プロダクトID(シリアルNo)'] = st.text_input("プロダクトID(シリアルNo)")
                        custom_values['ラベル'] = st.text_input("ラベル")
                    with c2:
                        custom_values['officeのアカウント割振'] = st.text_input("officeのアカウント割振")
                        custom_values['ORCA宇都宮'] = st.text_input("ORCA宇都宮")
                        custom_values['ORCA鹿沼'] = st.text_input("ORCA鹿沼")
                        custom_values['ORCA益子'] = st.text_input("ORCA益子")
                        custom_values['チームビューワID'] = st.text_input("チームビューワID")
                        custom_values['チームビューワPW'] = st.text_input("チームビューワPW")
                    
                    st.caption("ウィルスバスター情報")
                    c3, c4, c5 = st.columns(3)
                    with c3: custom_values['ウィルスバスターシリアルNo'] = st.text_input("VBシリアルNo")
                    with c4: 
                        d_vb = st.date_input("VB期限", value=None)
                        custom_values['ウィルスバスター期限'] = d_vb.strftime('%Y-%m-%d') if d_vb else ''
                    with c5: custom_values['ウィルスバスター識別ネーム'] = st.text_input("VB識別ネーム")
                    custom_values['備考'] = st.text_area("備考")

                elif selected_category_key == "訪問車":
                    c1, c2 = st.columns(2)
                    with c1:
                        custom_values['登録番号'] = st.text_input("登録番号")
                        custom_values['使用部署'] = st.text_input("使用部署")
                        custom_values['洗車グループ'] = st.text_input("洗車グループ")
                        custom_values['駐車場'] = st.text_input("駐車場")
                        custom_values['タイヤサイズ'] = st.text_input("タイヤサイズ")
                        custom_values['タイヤ保管場所'] = st.text_input("タイヤ保管場所")
                        custom_values['スタッドレス有無'] = st.text_input("スタッドレス有無")
                    with c2:
                        d_lease_s = st.date_input("リース開始日", value=None)
                        custom_values['リース開始日'] = d_lease_s.strftime('%Y-%m-%d') if d_lease_s else ''
                        d_lease_e = st.date_input("リース満了日", value=None)
                        custom_values['リース満了日'] = d_lease_e.strftime('%Y-%m-%d') if d_lease_e else ''
                        d_syaken = st.date_input("車検満了日", value=None)
                        custom_values['車検満了日'] = d_syaken.strftime('%Y-%m-%d') if d_syaken else ''
                        d_park = st.date_input("駐禁除外指定満了日", value=None)
                        custom_values['駐禁除外指定満了日'] = d_park.strftime('%Y-%m-%d') if d_park else ''
                        d_road = st.date_input("通行禁止許可満了日", value=None)
                        custom_values['通行禁止許可満了日'] = d_road.strftime('%Y-%m-%d') if d_road else ''
                    custom_values['備考'] = st.text_area("備考")

                elif selected_category_key == "iPad":
                    c1, c2 = st.columns(2)
                    with c1:
                        d_buy = st.date_input("購入日", value=None)
                        custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                        custom_values['ラベル'] = st.text_input("ラベル")
                        custom_values['AppleID'] = st.text_input("AppleID")
                        custom_values['AppleIDパスワード'] = st.text_input("AppleIDパスワード")
                        custom_values['シリアルNo'] = st.text_input("シリアルNo")
                        custom_values['ストレージ'] = st.text_input("ストレージ")
                    with c2:
                        custom_values['製造番号IMEI'] = st.text_input("製造番号IMEI")
                        custom_values['端末番号'] = st.text_input("端末番号")
                        custom_values['使用部署'] = st.text_input("使用部署")
                        custom_values['キャリア'] = st.text_input("キャリア")
                    custom_values['備考'] = st.text_area("備考")

                elif selected_category_key == "携帯電話":
                    c1, c2 = st.columns(2)
                    with c1:
                        d_buy = st.date_input("購入日", value=None)
                        custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                        custom_values['電話番号'] = st.text_input("電話番号")
                        custom_values['SIM'] = st.text_input("SIM")
                        custom_values['メーカー'] = st.text_input("メーカー")
                    with c2:
                        custom_values['製造番号'] = st.text_input("製造番号")
                        custom_values['使用部署'] = st.text_input("使用部署")
                        custom_values['保管場所'] = st.text_input("保管場所")
                        custom_values['キャリア'] = st.text_input("キャリア")
                    custom_values['備考'] = st.text_area("備考")

                elif selected_category_key == "Office365":
                    c1, c2 = st.columns(2)
                    with c1: custom_values['アカウントID'] = st.text_input("アカウントID")
                    with c2: custom_values['パスワード'] = st.text_input("パスワード")
                    
                    st.caption("共有利用者")
                    c_u1, c_u2, c_u3 = st.columns(3)
                    with c_u1: custom_values['利用者1'] = st.text_input("利用者1")
                    with c_u2: custom_values['利用者2'] = st.text_input("利用者2")
                    with c_u3: custom_values['利用者3'] = st.text_input("利用者3")
                    
                    c_u4, c_u5 = st.columns(2)
                    with c_u4: custom_values['利用者4'] = st.text_input("利用者4")
                    with c_u5: custom_values['利用者5'] = st.text_input("利用者5")
                    
                    custom_values['備考'] = st.text_area("備考")

                elif selected_category_key == "ウイルスバスター":
                    st.caption("利用者情報")
                    c1, c2, c3 = st.columns(3)
                    with c1: custom_values['利用者1'] = st.text_input("利用者1")
                    with c2: custom_values['利用者2'] = st.text_input("利用者2")
                    with c3: custom_values['利用者3'] = st.text_input("利用者3")
                    
                    st.caption("期限")
                    d_exp = st.date_input("期限", value=None)
                    custom_values['期限'] = d_exp.strftime('%Y-%m-%d') if d_exp else ''
                    
                    custom_values['備考'] = st.text_area("備考")

                elif selected_category_key == "その他機器":
                    custom_values['備考'] = st.text_area("備考")

                st.markdown("---")
                if st.form_submit_button("新規登録"):
                    if not input_id or not input_name:
                        st.error("IDと品名は必須です！")
                    else:
                        try:
                            worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                            current_time = datetime.now().strftime('%Y-%m-%d')
                            row_to_save = [input_id, selected_category_key, input_name, input_user, input_status, current_time]
                            for col_name in COLUMNS_DEF.get(selected_category_key, []):
                                row_to_save.append(custom_values.get(col_name, ''))
                            
                            if worksheet.find(input_id):
                                st.error(f"エラー: ID '{input_id}' は既に登録されています。")
                            else:
                                worksheet.append_row(row_to_save)
                                st.toast(f"新規登録しました！ ID: {input_id}", icon="✅")
                                get_all_data.clear()
                                st.rerun()
                        except Exception as e:
                            st.error(f"書き込みエラー: {e}")

        # === タブ3：CSV一括入出力 ===
        with main_tab3:
            st.header("📂 CSVによる一括登録・編集")
            st.caption("既存データの編集や、大量の新規データをまとめて登録するのに便利です。")

            # --- エクスポート ---
            st.subheader("1. データのエクスポート (ダウンロード)")
            st.caption("現在登録されているデータをCSVファイルとしてダウンロードします。")
            
            export_cat = st.selectbox("カテゴリを選択", list(CATEGORY_MAP.keys()), key="export_cat")
            if st.button("CSVをダウンロード作成"):
                try:
                    target_sheet_name = CATEGORY_MAP[export_cat]
                    worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                    # 全データを取得してDataFrame化
                    records = worksheet.get_all_records()
                    export_df = pd.DataFrame(records)
                    
                    # CSV変換
                    csv = export_df.to_csv(index=False).encode('utf-8_sig')
                    
                    st.download_button(
                        label="📥 CSVをダウンロード",
                        data=csv,
                        file_name=f"{export_cat}_inventory_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error(f"エクスポートエラー: {e}")

            st.markdown("---")

            # --- インポート ---
            st.subheader("2. データのインポート (アップロード)")
            st.caption("編集したCSVファイルをアップロードしてください。**IDが一致するものは「更新」、新しいIDは「新規登録」**されます。")
            
            import_cat = st.selectbox("カテゴリを選択 (インポート先)", list(CATEGORY_MAP.keys()), key="import_cat")
            uploaded_file = st.file_uploader("CSVファイルをドラッグ＆ドロップ", type=["csv"])
            
            if uploaded_file is not None:
                try:
                    # CSV読み込み
                    import_df = pd.read_csv(uploaded_file)
                    st.write("プレビュー:", import_df.head())
                    
                    if st.button("🚀 この内容で一括更新を実行"):
                        target_sheet_name = CATEGORY_MAP[import_cat]
                        worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                        
                        # 現在の全データを取得してIDリストを作成 (行番号の特定用)
                        current_records = worksheet.get_all_records()
                        # IDをキー、行番号(2行目~)を値とする辞書を作成
                        id_map = {str(record['ID']): i + 2 for i, record in enumerate(current_records)}
                        
                        # プログレスバー
                        progress_bar = st.progress(0)
                        total_rows = len(import_df)
                        
                        for i, row in import_df.iterrows():
                            row_id = str(row['ID'])
                            current_time = datetime.now().strftime('%Y-%m-%d')
                            
                            # 保存するデータの並び順を作成 (基本列 + カテゴリ固有列)
                            # 基本列: ID, カテゴリ, 品名, 利用者, ステータス, 更新日
                            row_data = [
                                row_id,
                                import_cat,
                                row.get('品名', ''),
                                row.get('利用者', ''),
                                row.get('ステータス', '利用可能'),
                                current_time
                            ]
                            
                            # カテゴリ固有列
                            for col_name in COLUMNS_DEF.get(import_cat, []):
                                row_data.append(row.get(col_name, ''))
                            
                            # 更新 or 追加
                            if row_id in id_map:
                                # 既存IDならその行を更新
                                row_num = id_map[row_id]
                                # rangeを使って一括更新 (A列から最後まで)
                                worksheet.update(f"A{row_num}", [row_data])
                            else:
                                # 新規IDなら末尾に追加
                                worksheet.append_row(row_data)
                            
                            # 進捗更新
                            progress_bar.progress((i + 1) / total_rows)
                            time.sleep(0.1) # API制限考慮
                        
                        st.success("一括処理が完了しました！")
                        get_all_data.clear() # キャッシュクリア
                        time.sleep(1)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"インポートエラー: {e}")

    # ==========================================
    # ページ2：新規入職者管理
    # ==========================================
    elif page_selection == "👤 新規入職者管理":
        new_emp_tab1, new_emp_tab2 = st.tabs(["📋 タスク管理・一覧", "➕ 新規登録"])
        
        # --- データ取得 ---
        df_new_emp = get_new_employee_data()
        
        # === タブ1: 一覧 ===
        with new_emp_tab1:
            st.markdown("#### 新規入職者の準備状況")
            
            if df_new_emp is None:
                st.error(f"シート「{SHEET_NEW_EMPLOYEE}」が見つかりません。スプレッドシートに作成してください。")
            elif df_new_emp.empty:
                st.info("登録されているデータはありません。")
            else:
                # 必須カラムチェック
                req_cols = ["ID", "氏名", "入職日", "職種", "部署", "ステータス"]
                missing = [c for c in req_cols if c not in df_new_emp.columns]
                
                if missing:
                    st.error(f"エラー: スプレッドシートに以下の列が見つかりません: {', '.join(missing)}")
                    st.warning("シートの見出し行を確認してください。")
                else:
                    # ソート用フラグ作成: 完了=1, その他=0
                    df_new_emp['is_completed'] = df_new_emp['ステータス'].apply(lambda x: 1 if str(x) == '完了' else 0)
                    # 日付ソート用
                    df_new_emp['sort_date'] = pd.to_datetime(df_new_emp['入職日'], errors='coerce')
                    
                    # 並び替え: 完了フラグ(昇順 0->1) -> 日付(昇順)
                    df_new_emp = df_new_emp.sort_values(by=['is_completed', 'sort_date'], ascending=[True, True])

                    # テーブルヘッダー
                    cols = st.columns([0.8, 0.8, 1.5, 1.5, 1.5, 1.5, 1.5])
                    cols[0].write("**編集**")
                    cols[1].write("**ID**")
                    cols[2].write("**氏名**")
                    cols[3].write("**入職日**")
                    cols[4].write("**職種**")
                    cols[5].write("**部署**")
                    cols[6].write("**ステータス**")
                    st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)

                    for index, row in df_new_emp.iterrows():
                        c = st.columns([0.8, 0.8, 1.5, 1.5, 1.5, 1.5, 1.5])
                        
                        if c[0].button("詳細", key=f"ne_btn_{row['ID']}"):
                            show_onboarding_task_dialog(row)
                        
                        c[1].write(str(row['ID']))
                        c[2].write(f"**{row['氏名']}**")
                        c[3].write(str(row['入職日']))
                        c[4].write(str(row.get('職種', '')))
                        c[5].write(str(row['部署']))
                        
                        status = str(row['ステータス'])
                        if status == "完了": c[6].success("完了", icon="✅")
                        elif status == "準備中": c[6].warning("準備中", icon="🏃")
                        else: c[6].write(status)
                        
                        st.markdown("<hr style='margin: 5px 0; border-top: 1px dashed #eee;'>", unsafe_allow_html=True)

        # === タブ2: 新規登録 ===
        with new_emp_tab2:
            st.subheader("新規入職予定の登録")
            with st.form("add_new_emp_form"):
                col1, col2 = st.columns(2)
                with col1:
                    ne_id = st.text_input("ID (社員番号など)", placeholder="例: 9001")
                    ne_name = st.text_input("氏名", placeholder="例: 山田 太郎")
                with col2:
                    ne_date = st.date_input("入職予定日")
                    ne_job = st.text_input("職種")
                    ne_dept = st.text_input("配属部署")
                
                ne_note = st.text_area("備考")
                
                if st.form_submit_button("登録する"):
                    if not ne_id or not ne_name:
                        st.error("IDと氏名は必須です。")
                    else:
                        try:
                            worksheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NEW_EMPLOYEE)
                            
                            # ID重複チェック
                            cell = worksheet.find(ne_id)
                            if cell:
                                st.error(f"エラー: ID '{ne_id}' は既に登録されています。")
                            else:
                                # 保存データ作成
                                row_to_save = [
                                    ne_id, ne_name, str(ne_date), ne_job, ne_dept, "準備中"
                                ]
                                # タスク列はすべて空文字で初期化
                                row_to_save.extend([""] * len(ONBOARDING_TASKS))
                                row_to_save.append(ne_note)
                                
                                worksheet.append_row(row_to_save)
                                st.toast("新規入職者を登録しました！", icon="✅")
                                st.rerun()
                        except Exception as e:
                            st.error(f"登録エラー: {e}")

    # ==========================================
    # ページ3：5年経過リスト
    # ==========================================
    elif page_selection == "📅 5年経過リスト (PC/iPad)":
        st.title("📅 5年経過リスト (PC/iPad)")
        st.markdown("購入日から5年以上経過しているデバイスを自動抽出しています。")
        
        # 対象カテゴリ
        target_cats = ["PC", "iPad"]
        # 5年前の日付
        five_years_ago = datetime.now().date() - timedelta(days=365*5 + 1) # おおよそ5年前
        
        # データの抽出ロジック
        old_devices = []
        if not df.empty:
            for index, row in df.iterrows():
                # カテゴリ判定
                cat = row.get('カテゴリ')
                if cat not in target_cats:
                    continue
                
                # 廃棄済みは除外
                if row.get('ステータス') == '廃棄':
                    continue
                
                # 購入日のチェック
                purchase_date_val = row.get('購入日')
                p_date = parse_date(purchase_date_val)
                
                if p_date:
                    # 正確に5年経過を判定 (購入日 + 5年 <= 今日)
                    try:
                        deadline = p_date.date().replace(year=p_date.year + 5)
                    except ValueError: # うるう年対応 (2/29 -> 2/28)
                        deadline = p_date.date().replace(year=p_date.year + 5, month=2, day=28)
                    
                    if datetime.now().date() >= deadline:
                        # リストに追加
                        row_data = row.to_dict()
                        row_data['index'] = index # 元のインデックスを保持
                        old_devices.append(row_data)

        if not old_devices:
            st.success("🎉 購入から5年以上経過した対象デバイスはありません！")
        else:
            st.warning(f"⚠️ {len(old_devices)} 件のデバイスが購入から5年以上経過しています。")
            
            # テーブル表示用のデータフレーム作成
            display_cols = ["カテゴリ", "ID", "品名", "利用者", "購入日", "ステータス", "備考"]
            
            # PCとiPadで項目が違うため、共通項目 + α で表示
            for item in old_devices:
                # 1行ずつ表示
                with st.container():
                    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 2, 1.5, 1.5, 1])
                    
                    # 詳細ボタン
                    if c1.button("詳細", key=f"old_btn_{item['ID']}"):
                        # 元のDataFrameから該当行を取得してダイアログ表示
                        # (itemは辞書化されているので、元のSeries形式に戻すか、辞書対応のダイアログが必要)
                        # ここでは簡易的に、元のdfから再取得して渡す
                        original_row = df.loc[item['index']]
                        show_detail_dialog(original_row)
                    
                    c2.write(item.get('ID'))
                    c3.write(f"**{safe_text(item.get('品名'))}**")
                    c4.write(item.get('利用者'))
                    c5.write(f"{item.get('カテゴリ')} / {item.get('購入日')}")
                    
                    status = item.get('ステータス')
                    if status == "利用可能": c6.info(status)
                    elif status == "利用中": c6.success(status) # 追加
                    else: c6.write(status)
                    
                    st.markdown("<hr style='margin: 0.2rem 0'>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"エラー: {e}")
