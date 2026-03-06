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

# --- 設定: 新規入職者管理用のシート名とタスク項目 ---
SHEET_NEW_EMPLOYEE = "新規入職者"
ONBOARDING_TASKS = [
    "PC", "iPad", "携帯", "駐車場", 
    "LineworksID", "モバカルモバナーID", 
    "MCS", "アルコールチェックID", "訪問車両", 
    "備品", "机・椅子", "三文判", "シャチハタ"
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
    "その他機器": [
        "使用部署", "使用場所", "使用開始日", "備考"
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
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署', ''))
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['OS'] = st.text_input("OS", value=row_data.get('OS', ''))
                custom_values['プロダクトID(シリアルNo)'] = st.text_input("プロダクトID(シリアルNo)", value=row_data.get('プロダクトID(シリアルNo)', ''))
                custom_values['ラベル'] = st.text_input("ラベル", value=row_data.get('ラベル', ''))
            with c2:
                custom_values['officeのアカウント割振'] = st.text_input("officeのアカウント割振", value=row_data.get('officeのアカウント割振', ''))
                custom_values['ORCA宇都宮'] = st.text_input("ORCA宇都宮", value=row_data.get('ORCA宇都宮', ''))
                custom_values['ORCA鹿沼'] = st.text_input("ORCA鹿沼", value=row_data.get('ORCA鹿沼', ''))
                custom_values['ORCA益子'] = st.text_input("ORCA益子", value=row_data.get('ORCA益子', ''))
                custom_values['チームビューワID'] = st.text_input("チームビューワID", value=row_data.get('チームビューワID', ''))
                custom_values['チームビューワPW'] = st.text_input("チームビューワPW", value=row_data.get('チームビューワPW', ''))
            st.caption("ウィルスバスター情報")
            c3, c4, c5 = st.columns(3)
            with c3: custom_values['ウィルスバスターシリアルNo'] = st.text_input("VBシリアルNo", value=row_data.get('ウィルスバスターシリアルNo', ''))
            with c4: 
                d_vb = st.date_input("VB期限", value=get_date_val('ウィルスバスター期限'))
                custom_values['ウィルスバスター期限'] = d_vb.strftime('%Y-%m-%d') if d_vb else ''
            with c5: custom_values['ウィルスバスター識別ネーム'] = st.text_input("VB識別ネーム", value=row_data.get('ウィルスバスター識別ネーム', ''))
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

        elif cat == "訪問車":
            c1, c2 = st.columns(2)
            with c1:
                custom_values['登録番号'] = st.text_input("登録番号", value=row_data.get('登録番号', ''))
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署', ''))
                custom_values['洗車グループ'] = st.text_input("洗車グループ", value=row_data.get('洗車グループ', ''))
                custom_values['駐車場'] = st.text_input("駐車場", value=row_data.get('駐車場', ''))
                custom_values['タイヤサイズ'] = st.text_input("タイヤサイズ", value=row_data.get('タイヤサイズ', ''))
                custom_values['タイヤ保管場所'] = st.text_input("タイヤ保管場所", value=row_data.get('タイヤ保管場所', ''))
                custom_values['スタッドレス有無'] = st.text_input("スタッドレス有無", value=row_data.get('スタッドレス有無', ''))
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
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

        elif cat == "iPad":
            c1, c2 = st.columns(2)
            with c1:
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['ラベル'] = st.text_input("ラベル", value=row_data.get('ラベル', ''))
                custom_values['AppleID'] = st.text_input("AppleID", value=row_data.get('AppleID', ''))
                custom_values['AppleIDパスワード'] = st.text_input("AppleIDパスワード", value=row_data.get('AppleIDパスワード', ''))
                custom_values['シリアルNo'] = st.text_input("シリアルNo", value=row_data.get('シリアルNo', ''))
                custom_values['ストレージ'] = st.text_input("ストレージ", value=row_data.get('ストレージ', ''))
            with c2:
                custom_values['製造番号IMEI'] = st.text_input("製造番号IMEI", value=row_data.get('製造番号IMEI', ''))
                custom_values['端末番号'] = st.text_input("端末番号", value=row_data.get('端末番号', ''))
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署', ''))
                custom_values['キャリア'] = st.text_input("キャリア", value=row_data.get('キャリア', ''))
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

        elif cat == "携帯電話":
            c1, c2 = st.columns(2)
            with c1:
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['電話番号'] = st.text_input("電話番号", value=row_data.get('電話番号', ''))
                custom_values['SIM'] = st.text_input("SIM", value=row_data.get('SIM', ''))
                custom_values['メーカー'] = st.text_input("メーカー", value=row_data.get('メーカー', ''))
            with c2:
                custom_values['製造番号'] = st.text_input("製造番号", value=row_data.get('製造番号', ''))
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署', ''))
                custom_values['保管場所'] = st.text_input("保管場所", value=row_data.get('保管場所', ''))
                custom_values['キャリア'] = st.text_input("キャリア", value=row_data.get('キャリア', ''))
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

        elif cat == "Office365":
            c1, c2 = st.columns(2)
            with c1: custom_values['アカウントID'] = st.text_input("アカウントID", value=row_data.get('アカウントID', ''))
            with c2: custom_values['パスワード'] = st.text_input("パスワード", value=row_data.get('パスワード', ''))
            
            st.caption("共有利用者")
            c_u1, c_u2, c_u3 = st.columns(3)
            with c_u1: custom_values['利用者1'] = st.text_input("利用者1", value=row_data.get('利用者1', ''))
            with c_u2: custom_values['利用者2'] = st.text_input("利用者2", value=row_data.get('利用者2', ''))
            with c_u3: custom_values['利用者3'] = st.text_input("利用者3", value=row_data.get('利用者3', ''))
            
            c_u4, c_u5 = st.columns(2)
            with c_u4: custom_values['利用者4'] = st.text_input("利用者4", value=row_data.get('利用者4', ''))
            with c_u5: custom_values['利用者5'] = st.text_input("利用者5", value=row_data.get('利用者5', ''))
            
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

        elif cat == "ウイルスバスター":
            st.caption("利用者情報")
            c1, c2, c3 = st.columns(3)
            with c1: custom_values['利用者1'] = st.text_input("利用者1", value=row_data.get('利用者1', ''))
            with c2: custom_values['利用者2'] = st.text_input("利用者2", value=row_data.get('利用者2', ''))
            with c3: custom_values['利用者3'] = st.text_input("利用者3", value=row_data.get('利用者3', ''))
            
            st.caption("期限")
            d_exp = st.date_input("期限", value=get_date_val('期限'))
            custom_values['期限'] = d_exp.strftime('%Y-%m-%d') if d_exp else ''
            
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

        elif cat == "その他機器":
            c1, c2 = st.columns(2)
            with c1:
                custom_values['使用部署'] = st.text_input("使用部署", value=row_data.get('使用部署', ''))
                custom_values['使用場所'] = st.text_input("使用場所", value=row_data.get('使用場所', ''))
            with c2:
                d_start = st.date_input("使用開始日", value=get_date_val('使用開始日'))
                custom_values['使用開始日'] = d_start.strftime('%Y-%m-%d') if d_start else ''
            
            custom_values['備考'] = st.text_area("備考", value=row_data.get('備考', ''))

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
    st.write(f"### ID: {row_data.get('ID', '')}")
    
    with st.form("onboarding_task_form"):
        # 基本情報の編集
        c_name1, c_name2 = st.columns(2)
        with c_name1:
            new_name = st.text_input("氏名", value=row_data.get('氏名', ''))
        with c_name2:
            new_furigana = st.text_input("フリガナ", value=row_data.get('フリガナ', ''))
            
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
                # 既存の値を初期値として表示
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
                headers = worksheet.row_values(1) # スプレッドシートの見出しを取得
                
                # 更新用データを辞書で構築
                data_dict = {
                    "ID": row_data.get('ID', ''),
                    "氏名": new_name,
                    "フリガナ": new_furigana,
                    "入職日": str(new_date) if new_date else '',
                    "職種": new_job,
                    "部署": new_dept,
                    "ステータス": new_status,
                    "備考": new_note
                }
                # タスク列の値を辞書に追加
                for task_name in ONBOARDING_TASKS:
                    data_dict[task_name] = task_status[task_name]
                
                # ★スプレッドシートの見出し順に合わせてリスト化（列ズレを完全に防止）
                row_to_save = [data_dict.get(h, "") for h in headers]
                
                # IDで行を検索して更新
                cell = worksheet.find(str(row_data.get('ID', '')))
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
        * 左上のメニューで各機能画面
