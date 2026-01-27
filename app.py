import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

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
        "購入日", "製品名", "OS", "プロダクトID(シリアルNo)", 
        "ORCA宇都宮", "ORCA鹿沼", "ORCA益子", 
        "officeのアカウント割振", "ウィルスバスターシリアルNo", "ウィルスバスター期限", "ウィルスバスター識別ネーム",
        "チームビューワID", "チームビューワPW", "備考"
    ],
    "訪問車": [
        "登録番号", "使用部署", "洗車グループ", "駐車場", 
        "タイヤサイズ", "スタッドレス有無", "タイヤ保管場所", 
        "リース開始日", "リース満了日", "車検満了日", 
        "駐禁除外指定満了日", "通行禁止許可満了日", "備考"
    ],
    "iPad": [
        "購入日", "ラベル", "AppleID", "型番", "シリアルNo", 
        "モデル", "ストレージ", "製造番号IMEI", "端末番号", 
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

# --- データ取得関数（キャッシュ付き） ---
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
    return pd.DataFrame(all_data)

# --- 日付変換ヘルパー ---
def parse_date(date_str):
    if not date_str: return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except:
        return None

# --- 【新機能】詳細ポップアップ (Dialog) ---
@st.dialog("📋 備品詳細情報")
def show_detail_dialog(row_data):
    # 基本情報
    st.subheader(f"{row_data['品名']}")
    st.caption(f"ID: {row_data['ID']} / カテゴリ: {row_data['カテゴリ']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**👤 利用者:** {row_data['利用者']}")
    with col2:
        st.write(f"**📌 ステータス:** {row_data['ステータス']}")
    
    st.markdown("---")
    
    # 詳細項目を列挙
    # 隠されている項目も含めて全て表示する
    target_cols = COLUMNS_DEF.get(row_data['カテゴリ'], [])
    
    for col_key in target_cols:
        val = row_data.get(col_key, '')
        if val: # 値がある場合のみ表示
            st.write(f"**{col_key}:** {val}")
    
    st.markdown("---")
    st.caption(f"最終更新日: {row_data.get('更新日', '')}")

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

if st.sidebar.button("🔄 データを最新にする"):
    get_all_data.clear()
    st.rerun()

try:
    df = get_all_data()

    main_tab1, main_tab2 = st.tabs(["🔍 一覧・検索", "📝 新規登録・編集"])

    # ==========================================
    # タブ1：一覧・検索（ポップアップ機能付き）
    # ==========================================
    with main_tab1:
        st.header("在庫データの検索")
        search_query = st.text_input("フリーワード検索", placeholder="品名、ID、利用者名、備考など...")

        if search_query and not df.empty:
            filtered_df = df[df.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)]
            st.success(f"検索結果: {len(filtered_df)} 件")
        else:
            filtered_df = df

        st.markdown("---")

        categories = ["すべて"] + list(CATEGORY_MAP.keys())
        cat_tabs = st.tabs(categories)

        for i, category in enumerate(categories):
            with cat_tabs[i]:
                if df.empty:
                    st.info("データがありません")
                else:
                    # 表示用データの作成
                    if category == "すべて":
                        # 一覧では見やすくするため共通項目のみにする
                        common_cols = ['ID', 'カテゴリ', '品名', '利用者', 'ステータス', '更新日']
                        available_cols = [c for c in common_cols if c in filtered_df.columns]
                        display_df = filtered_df[available_cols].copy()
                        st.caption("👇 行をクリックして選択すると、詳細ポップアップボタンが表示されます")
                    else:
                        display_df = filtered_df[filtered_df['カテゴリ'] == category].copy()
                        # 不要な列を一覧から隠す
                        target_cols = ['ID', '品名', '利用者', 'ステータス', '更新日'] + COLUMNS_DEF.get(category, [])
                        valid_cols = [c for c in target_cols if c in display_df.columns]
                        display_df = display_df[valid_cols]
                        st.caption("👇 行をクリックして選択すると、詳細ポップアップボタンが表示されます")

                    # --- テーブル表示 (選択モード有効) ---
                    selection = st.dataframe(
                        display_df,
                        use_container_width=True,
                        on_select="rerun",           # 選択したらリロードしてボタンを出す
                        selection_mode="single-row"  # 1行だけ選択可能
                    )

                    # --- 行が選択されたらボタンを表示 ---
                    if len(selection.selection.rows) > 0:
                        # 選択された行のインデックスを取得
                        selected_index = selection.selection.rows[0]
                        # 表示中のデータフレームからIDを取得
                        selected_id = display_df.iloc[selected_index]['ID']
                        
                        # ボタンを表示
                        if st.button(f"🔍 {selected_id} の詳細をポップアップで見る", key=f"btn_{category}_{i}"):
                            # 全データ(df)から該当IDの完全な情報を探す（隠れた列も取得するため）
                            full_row_data = df[df['ID'] == selected_id].iloc[0]
                            show_detail_dialog(full_row_data)

    # ==========================================
    # タブ2：登録・更新
    # ==========================================
    with main_tab2:
        st.header("データの登録・編集")
        
        st.subheader("① カテゴリとIDを指定")
        selected_category_key = st.radio("カテゴリ", list(CATEGORY_MAP.keys()), horizontal=True)
        target_sheet_name = CATEGORY_MAP[selected_category_key]

        col_load1, col_load2 = st.columns([3, 1])
        with col_load1:
            input_search_id = st.text_input("編集する場合はIDを入力して「呼び出す」を押してください", key="search_id_input")
        with col_load2:
            st.write("") 
            st.write("") 
            load_btn = st.button("📥 データを呼び出す")

        # 呼び出し処理
        if load_btn and input_search_id:
            try:
                worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                cell = worksheet.find(input_search_id)
                if cell:
                    all_records = worksheet.get_all_records()
                    if len(all_records) >= cell.row - 1:
                        row_data = all_records[cell.row - 2]
                        st.session_state['form_data'] = row_data
                        st.success(f"ID: {input_search_id} を読み込みました。")
                    else:
                        st.error("データの読み込み位置がズレています。")
                else:
                    st.error("指定されたIDは見つかりませんでした。")
                    st.session_state['form_data'] = {}
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

        # --- 入力フォーム ---
        st.subheader("② 詳細情報の入力")
        current_data = st.session_state.get('form_data', {})
        is_load_mode = (current_data.get('ID') == input_search_id) and (input_search_id != "")
        
        def get_val(key):
            return current_data.get(key, '') if is_load_mode else ''

        with st.form("entry_form"):
            st.markdown("##### 📌 基本情報")
            col_basic1, col_basic2 = st.columns(2)
            with col_basic1:
                input_id = st.text_input("ID (資産番号)", value=get_val('ID') or input_search_id)
                input_name = st.text_input("品名 (管理上の名称)", value=get_val('品名'))
            with col_basic2:
                input_user = st.text_input("利用者", value=get_val('利用者'))
                status_options = ["利用可能", "貸出中", "故障/修理中", "廃棄"]
                curr_status = get_val('ステータス')
                idx_status = status_options.index(curr_status) if curr_status in status_options else 0
                input_status = st.selectbox("ステータス", status_options, index=idx_status)

            # === カテゴリ別項目 ===
            st.markdown("---")
            st.markdown(f"##### 📝 {selected_category_key} 詳細情報")
            
            custom_values = {}

            if selected_category_key == "PC":
                c1, c2 = st.columns(2)
                with c1:
                    d_buy = st.date_input("購入日", value=parse_date(get_val('購入日')))
                    custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                    custom_values['製品名'] = st.text_input("製品名", value=get_val('製品名'))
                    custom_values['OS'] = st.text_input("OS", value=get_val('OS'))
                    custom_values['プロダクトID(シリアルNo)'] = st.text_input("プロダクトID(シリアルNo)", value=get_val('プロダクトID(シリアルNo)'))
                    custom_values['officeのアカウント割振'] = st.text_input("officeのアカウント割振", value=get_val('officeのアカウント割振'))
                with c2:
                    custom_values['ORCA宇都宮'] = st.text_input("ORCA宇都宮", value=get_val('ORCA宇都宮'))
                    custom_values['ORCA鹿沼'] = st.text_input("ORCA鹿沼", value=get_val('ORCA鹿沼'))
                    custom_values['ORCA益子'] = st.text_input("ORCA益子", value=get_val('ORCA益子'))
                    custom_values['チームビューワID'] = st.text_input("チームビューワID", value=get_val('チームビューワID'))
                    custom_values['チームビューワPW'] = st.text_input("チームビューワPW", value=get_val('チームビューワPW'))
                
                st.caption("ウィルスバスター情報")
                c3, c4, c5 = st.columns(3)
                with c3: custom_values['ウィルスバスターシリアルNo'] = st.text_input("VBシリアルNo", value=get_val('ウィルスバスターシリアルNo'))
                with c4: 
                    d_vb = st.date_input("VB期限", value=parse_date(get_val('ウィルスバスター期限')))
                    custom_values['ウィルスバスター期限'] = d_vb.strftime('%Y-%m-%d') if d_vb else ''
                with c5: custom_values['ウィルスバスター識別ネーム'] = st.text_input("VB識別ネーム", value=get_val('ウィルスバスター識別ネーム'))
                custom_values['備考'] = st.text_area("備考", value=get_val('備考'))

            elif selected_category_key == "訪問車":
                c1, c2 = st.columns(2)
                with c1:
                    custom_values['登録番号'] = st.text_input("登録番号", value=get_val('登録番号'))
                    custom_values['使用部署'] = st.text_input("使用部署", value=get_val('使用部署'))
                    custom_values['洗車グループ'] = st.text_input("洗車グループ", value=get_val('洗車グループ'))
                    custom_values['駐車場'] = st.text_input("駐車場", value=get_val('駐車場'))
                    custom_values['タイヤサイズ'] = st.text_input("タイヤサイズ", value=get_val('タイヤサイズ'))
                    custom_values['タイヤ保管場所'] = st.text_input("タイヤ保管場所", value=get_val('タイヤ保管場所'))
                    
                    st.caption("スタッドレス有無")
                    studless_opts = ["有", "無"]
                    curr_stud = get_val('スタッドレス有無')
                    idx_stud = studless_opts.index(curr_stud) if curr_stud in studless_opts else 1
                    custom_values['スタッドレス有無'] = st.radio("スタッドレス有無", studless_opts, index=idx_stud, horizontal=True)

                with c2:
                    d_lease_s = st.date_input("リース開始日", value=parse_date(get_val('リース開始日')))
                    custom_values['リース開始日'] = d_lease_s.strftime('%Y-%m-%d') if d_lease_s else ''
                    
                    d_lease_e = st.date_input("リース満了日", value=parse_date(get_val('リース満了日')))
                    custom_values['リース満了日'] = d_lease_e.strftime('%Y-%m-%d') if d_lease_e else ''
                    
                    d_syaken = st.date_input("車検満了日", value=parse_date(get_val('車検満了日')))
                    custom_values['車検満了日'] = d_syaken.strftime('%Y-%m-%d') if d_syaken else ''
                    
                    d_park = st.date_input("駐禁除外指定満了日", value=parse_date(get_val('駐禁除外指定満了日')))
                    custom_values['駐禁除外指定満了日'] = d_park.strftime('%Y-%m-%d') if d_park else ''
                    
                    d_road = st.date_input("通行禁止許可満了日", value=parse_date(get_val('通行禁止許可満了日')))
                    custom_values['通行禁止許可満了日'] = d_road.strftime('%Y-%m-%d') if d_road else ''
                custom_values['備考'] = st.text_area("備考", value=get_val('備考'))

            elif selected_category_key == "iPad":
                c1, c2 = st.columns(2)
                with c1:
                    d_buy = st.date_input("購入日", value=parse_date(get_val('購入日')))
                    custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                    custom_values['ラベル'] = st.text_input("ラベル", value=get_val('ラベル'))
                    custom_values['AppleID'] = st.text_input("AppleID", value=get_val('AppleID'))
                    custom_values['型番'] = st.text_input("型番", value=get_val('型番'))
                    custom_values['シリアルNo'] = st.text_input("シリアルNo", value=get_val('シリアルNo'))
                    custom_values['モデル'] = st.text_input("モデル", value=get_val('モデル'))
                with c2:
                    custom_values['ストレージ'] = st.text_input("ストレージ", value=get_val('ストレージ'))
                    custom_values['製造番号IMEI'] = st.text_input("製造番号IMEI", value=get_val('製造番号IMEI'))
                    custom_values['端末番号'] = st.text_input("端末番号", value=get_val('端末番号'))
                    custom_values['使用部署'] = st.text_input("使用部署", value=get_val('使用部署'))
                    custom_values['キャリア'] = st.text_input("キャリア", value=get_val('キャリア'))
                custom_values['備考'] = st.text_area("備考", value=get_val('備考'))

            elif selected_category_key == "携帯電話":
                c1, c2 = st.columns(2)
                with c1:
                    d_buy = st.date_input("購入日", value=parse_date(get_val('購入日')))
                    custom_values['購入日'] = d_buy.strftime('%Y-%m-%d') if d_buy else ''
                    custom_values['電話番号'] = st.text_input("電話番号", value=get_val('電話番号'))
                    custom_values['SIM'] = st.text_input("SIM", value=get_val('SIM'))
                    custom_values['メーカー'] = st.text_input("メーカー", value=get_val('メーカー'))
                with c2:
                    custom_values['製造番号'] = st.text_input("製造番号", value=get_val('製造番号'))
                    custom_values['使用部署'] = st.text_input("使用部署", value=get_val('使用部署'))
                    custom_values['保管場所'] = st.text_input("保管場所", value=get_val('保管場所'))
                    custom_values['キャリア'] = st.text_input("キャリア", value=get_val('キャリア'))
                custom_values['備考'] = st.text_area("備考", value=get_val('備考'))

            elif selected_category_key == "その他":
                custom_values['備考'] = st.text_area("備考", value=get_val('備考'))

            st.markdown("---")
            submitted = st.form_submit_button(f"「{selected_category_key}」として登録 / 更新")
            
            if submitted:
                if not input_id or not input_name:
                    st.error("IDと品名は必須です！")
                else:
                    try:
                        worksheet = client.open(SPREADSHEET_NAME).worksheet(target_sheet_name)
                        current_time = datetime.now().strftime('%Y-%m-%d')
                        
                        row_to_save = [
                            input_id, selected_category_key, input_name, input_user, input_status, current_time
                        ]
                        for col_name in COLUMNS_DEF.get(selected_category_key, []):
                            row_to_save.append(custom_values.get(col_name, ''))
                        
                        cell = worksheet.find(input_id)
                        if cell:
                            r = cell.row
                            worksheet.update(f"A{r}", [row_to_save])
                            st.success(f"更新完了！")
                        else:
                            worksheet.append_row(row_to_save)
                            st.success(f"新規登録完了！")
                        
                        get_all_data.clear()
                        st.session_state['form_data'] = {}
                        st.rerun()
                    except Exception as e:
                        st.error(f"書き込みエラー: {e}")

except Exception as e:
    st.error(f"エラー: {e}")
