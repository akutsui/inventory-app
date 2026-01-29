import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- CSS (標準的な設定) ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 4rem !important;
            padding-bottom: 5rem;
        }
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
        .stButton button {
            height: 2.0rem;
            padding-top: 0;
            padding-bottom: 0;
            margin-top: 0px;
            font-size: 0.9rem;
        }
        div[data-testid="column"] {
            padding-bottom: 0px;
        }
        p {
            margin-bottom: 0.1rem;
            font-size: 0.95rem;
        }
        hr {
            margin: 0.2rem 0 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- 設定: カテゴリとシート名の対応表 ---
CATEGORY_MAP = {
    "PC": "PC",
    "訪問車": "訪問車",
    "iPad": "iPad",
    "携帯電話": "携帯電話",
    "その他": "その他"
}

# --- 設定: 各シートの列定義 ---
COLUMNS_DEF = {
    "PC": [
        "購入日", "OS", "プロダクトID(シリアルNo)", 
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
        "購入日", "ラベル", "AppleID", "シリアルNo", 
        "ストレージ", "製造番号IMEI", "端末番号", 
        "使用部署", "キャリア", "備考"
    ],
    "携帯電話": [
        "購入日", "電話番号", "SIM", "メーカー",
        "製造番号", "使用部署", "保管場所", "キャリア", "備考"
    ],
    "その他": [
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

# --- データ取得関数 ---
@st.cache_data(ttl=600)
def get_all_data():
    all_data = []
    for cat_name, sheet_name in CATEGORY_MAP.items():
        try:
            worksheet = client.open(SPREADSHEET_NAME).worksheet(sheet_name)
            records = worksheet.get_all_records()
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

# --- 【復元】シンプルかつ実績のある日付パース関数 ---
def parse_date(date_str):
    if not date_str: return None
    try:
        # シンプルにハイフン区切りのみを処理
        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
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

# --- ポップアップ詳細・編集画面 ---
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
            new_user = st.text_input("利用者", value=row_data['利用者'])
        with col2:
            status_options = ["利用可能", "貸出中", "故障/修理中", "廃棄"]
            curr_status = row_data['ステータス']
            idx_status = status_options.index(curr_status) if curr_status in status_options else 0
            new_status = st.selectbox("ステータス", status_options, index=idx_status)
        
        st.markdown("---")
        
        cat = row_data['カテゴリ']
        custom_values = {}

        if cat == "PC":
            c1, c2 = st.columns(2)
            with c1:
                d_buy = st.date_input("購入日", value=get_date_val('購入日'))
                custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                custom_values['OS'] = st.text_input("OS", value=row_data.get('OS'))
                custom_values['プロダクトID(シリアルNo)'] = st.text_input("プロダクトID(シリアルNo)", value=row_data.get('プロダクトID(シリアルNo)'))
                custom_values['officeのアカウント割振'] = st.text_input("officeのアカウント割振", value=row_data.get('officeのアカウント割振'))
            with c2:
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

        elif cat == "その他":
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

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

with st.sidebar:
    if st.button("🔄 データを最新にする"):
        get_all_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    with st.expander("❓ 操作マニュアル", expanded=False):
        st.markdown("""
        **1. 検索機能**
        * 画面上部の枠に文字を入れて `Enter` を押すと検索できます。
        * **バーコードリーダー対応:** 入力後、自動で文字が消えるので連続して読み取れます。
        * 「検索解除」ボタンで全表示に戻ります。

        **2. 期日アラート**
        * 期限が **45日以内**（車）または **5年経過**（iPad）の場合、検索窓の下に赤字で警告が出ます。
        * アラート右側の **「詳細」ボタン** を押すと、その場で編集・確認ができます。
        * 「廃棄」済みのものは表示されません。

        **3. 編集・更新**
        * リスト左の「詳細」ボタンで編集画面が開きます。
        * 内容を書き換えて「更新する」を押すと保存されます。

        **4. 新規登録**
        * 上部のタブを「📝 新規登録」に切り替えて入力してください。
        """)

try:
    df = get_all_data()

    main_tab1, main_tab2 = st.tabs(["🔍 一覧・検索", "📝 新規登録"])

    # ==========================================
    # タブ1：一覧・検索
    # ==========================================
    with main_tab1:
        st.markdown("#### 在庫データの検索")
        
        # --- アラートデータの収集 ---
        alert_items = []
        today = datetime.now().date()
        
        if not df.empty:
            for index, row in df.iterrows():
                # ステータス「廃棄」の判定
                status = str(row.get('ステータス', '')).strip()
                if status == '廃棄':
                    continue

                cat = row.get('カテゴリ')
                name = row.get('品名', '名称不明')
                
                msg_list = []
                
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
                
                elif cat == "iPad":
                    label = str(row.get('ラベル', ''))
                    display_text = f"{label} {name}".strip()
                    
                    val = row.get("購入日")
                    dt = parse_date(val)
                    if dt:
                        try:
                            target_date = dt.date().replace(year=dt.year + 5)
                        except ValueError:
                            target_date = dt.date().replace(year=dt.year + 5, month=2, day=28)
                        
                        if today >= target_date:
                            msg_list.append(f"購入から5年経過 ({dt.strftime('%Y-%m-%d')})")
                    
                    if msg_list:
                        alert_items.append({
                            "row": row,
                            "title": f"iPad【{display_text}】",
                            "messages": msg_list
                        })

        # --- アラートの表示 ---
        if alert_items:
            with st.error("⚠️ 期日アラート (詳細はボタンをクリック)"):
                for i, item in enumerate(alert_items):
                    c1, c2 = st.columns([5, 1])
                    
                    alert_str = f"**{item['title']}** : " + ", ".join(item['messages'])
                    c1.markdown(f"{alert_str}")
                    
                    if c2.button("詳細", key=f"alert_btn_{i}"):
                        show_detail_dialog(item['row'])
                    
                    # 最後の要素以外に区切り線を入れる
                    if i < len(alert_items) - 1:
                        st.markdown('<hr style="margin: 0.5rem 0; border-top: 1px dashed #ffcccc;">', unsafe_allow_html=True)

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

                        if category == "訪問車":
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
                            cols[6].write(f"**{header_g}**")
                            cols[7].write(f"**{header_h}**")

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
                                if category == "訪問車":
                                    c = st.columns([0.7, 1.2, 1.8, 1.5, 1.5, 1.5, 1.0, 1.5])
                                    if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                        show_detail_dialog(row)
                                    c[1].write(f"{row['ID']}")
                                    c[2].write(f"**{row['品名']}**")
                                    c[3].write(f"{row.get('登録番号', '')}")
                                    c[4].write(f"{row['利用者']}")
                                    c[5].write(f"{row.get('使用部署', '')}")
                                    
                                    status = row['ステータス']
                                    if status == "利用可能": c[6].info(status, icon="✅")
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
                                    c[3].write(f"**{row['品名']}**")
                                    c[4].write(f"{row['利用者']}")
                                    c[5].write(f"{row.get('使用部署', '')}")
                                    
                                    status = row['ステータス']
                                    if status == "利用可能": c[6].info(status, icon="✅")
                                    elif status == "貸出中": c[6].warning(status, icon="🏃")
                                    elif status == "故障/修理中": c[6].error(status, icon="⚠️")
                                    else: c[6].write(status)
                                    
                                    c[7].write(f"{row.get('購入日', '')}")

                                elif category == "携帯電話":
                                    c = st.columns([0.7, 1.2, 1.8, 1.5, 1.5, 1.0, 1.5, 1.5])
                                    if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                        show_detail_dialog(row)
                                    c[1].write(f"{row['ID']}")
                                    c[2].write(f"**{row['品名']}**")
                                    c[3].write(f"{row['利用者']}")
                                    c[4].write(f"{row.get('使用部署', '')}")
                                    
                                    status = row['ステータス']
                                    if status == "利用可能": c[5].info(status, icon="✅")
                                    elif status == "貸出中": c[5].warning(status, icon="🏃")
                                    elif status == "故障/修理中": c[5].error(status, icon="⚠️")
                                    else: c[5].write(status)

                                    curr_cols_def = COLUMNS_DEF.get(category, [])
                                    val_g = row.get(curr_cols_def[0], '') if len(curr_cols_def) > 0 else ""
                                    val_h = row.get(curr_cols_def[1], '') if len(curr_cols_def) > 1 else ""
                                    c[6].write(f"{val_g}")
                                    c[7].write(f"{val_h}")

                                else:
                                    c = st.columns([0.7, 1.5, 2.0, 1.5, 1.2, 1.5, 1.5])
                                    if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                        show_detail_dialog(row)
                                    c[1].write(f"{row['ID']}")
                                    c[2].write(f"**{row['品名']}**")
                                    c[3].write(f"{row['利用者']}")
                                    
                                    status = row['ステータス']
                                    if status == "利用可能": c[4].info(status, icon="✅")
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

    # ==========================================
    # タブ2：新規登録
    # ==========================================
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
                input_user = st.text_input("利用者")
                input_status = st.selectbox("ステータス", ["利用可能", "貸出中", "故障/修理中", "廃棄"])

            st.markdown("---")
            st.markdown(f"##### 📝 {selected_category_key} 詳細情報")
            
            custom_values = {}

            if selected_category_key == "PC":
                c1, c2 = st.columns(2)
                with c1:
                    d_buy = st.date_input("購入日", value=None)
                    custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                    custom_values['OS'] = st.text_input("OS")
                    custom_values['プロダクトID(シリアルNo)'] = st.text_input("プロダクトID(シリアルNo)")
                    custom_values['officeのアカウント割振'] = st.text_input("officeのアカウント割振")
                with c2:
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

            elif selected_category_key == "その他":
                custom_values['備考'] = st.text_area("備考", value=row_data.get('備考'))

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

except Exception as e:
    st.error(f"エラー: {e}")
