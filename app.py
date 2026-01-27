import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="wide")

# --- カスタムCSS（行間を狭くする設定） ---
st.markdown("""
    <style>
        /* ボタンの上下の余白を減らす */
        .stButton button {
            height: 2.2rem;
            padding-top: 0;
            padding-bottom: 0;
            margin-top: 0px;
        }
        /* 列（カラム）の隙間を詰める */
        div[data-testid="column"] {
            padding-bottom: 0px;
        }
        /* テキストの余白を詰める */
        p {
            margin-bottom: 0.2rem;
        }
        /* 区切り線の余白を極限まで減らす */
        hr {
            margin: 0.3rem 0 !important;
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
if 'page_number' not in st.session_state:
    st.session_state['page_number'] = 0

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
    return pd.DataFrame(all_data)

def parse_date(date_str):
    if not date_str: return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except:
        return None

# --- ポップアップ詳細画面 (Dialog) ---
@st.dialog("📋 備品詳細情報")
def show_detail_dialog(row_data):
    st.subheader(f"{row_data['品名']}")
    st.caption(f"ID: {row_data['ID']} / カテゴリ: {row_data['カテゴリ']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**👤 利用者:** {row_data['利用者']}")
    with col2:
        st.write(f"**📌 ステータス:** {row_data['ステータス']}")
    
    st.markdown("---")
    
    target_cols = COLUMNS_DEF.get(row_data['カテゴリ'], [])
    for col_key in target_cols:
        val = row_data.get(col_key, '')
        if val: 
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
    # タブ1：一覧・検索
    # ==========================================
    with main_tab1:
        st.header("在庫データの検索")
        
        # 検索機能
        col_search, col_spacer = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("フリーワード検索", placeholder="品名、ID、利用者名、備考など...")

        # 検索フィルタ実行
        if search_query and not df.empty:
            filtered_df = df[df.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)]
            # 検索時はページを0に戻す
            if 'last_search' not in st.session_state or st.session_state.last_search != search_query:
                st.session_state.page_number = 0
                st.session_state.last_search = search_query
            st.success(f"検索結果: {len(filtered_df)} 件")
        else:
            filtered_df = df
            # 検索ワードが消えたらリセット
            if 'last_search' in st.session_state and st.session_state.last_search != "":
                 st.session_state.page_number = 0
                 st.session_state.last_search = ""

        # カスタム区切り線（薄くて狭い線）
        st.markdown('<hr style="margin: 5px 0; border: 0; border-top: 1px solid #eee;">', unsafe_allow_html=True)

        categories = ["すべて"] + list(CATEGORY_MAP.keys())
        cat_tabs = st.tabs(categories)

        for i, category in enumerate(categories):
            with cat_tabs[i]:
                # カテゴリを切り替えたらページ番号をリセットするための処理
                # (タブの切り替え検知は難しいので、ボタン操作以外でデータが変わったとみなす)
                
                if df.empty:
                    st.info("データがありません")
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
                        st.warning("該当するデータがありません")
                    else:
                        # --- ページネーション設定 ---
                        ITEMS_PER_PAGE = 50
                        total_items = len(display_df)
                        
                        # ページ番号が範囲外にならないよう調整
                        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
                        if st.session_state.page_number > max_page:
                            st.session_state.page_number = 0
                        
                        current_page = st.session_state.page_number
                        start_idx = current_page * ITEMS_PER_PAGE
                        end_idx = start_idx + ITEMS_PER_PAGE
                        
                        # 現在のページのデータを切り出す
                        df_to_show = display_df.iloc[start_idx:end_idx]
                        
                        st.caption(f"全 {total_items} 件中、{start_idx + 1} 〜 {min(end_idx, total_items)} 件目を表示中")

                        # --- ヘッダー行 ---
                        # ボタンの高さを揃えるために少しCSSハックを入れた列構成
                        cols = st.columns([0.7, 1.5, 2.0, 1.5, 1.2, 1.5, 1.5])
                        cols[0].write("**詳細**")
                        cols[1].write("**ID**")
                        cols[2].write("**品名**")
                        cols[3].write("**利用者**")
                        cols[4].write("**ステータス**")
                        cols[5].write(f"**{header_g}**")
                        cols[6].write(f"**{header_h}**")
                        
                        # ヘッダー下の線
                        st.markdown('<hr style="margin: 2px 0; border-top: 2px solid #bbb;">', unsafe_allow_html=True)

                        # --- データ表示ループ ---
                        for index, row in df_to_show.iterrows():
                            c = st.columns([0.7, 1.5, 2.0, 1.5, 1.2, 1.5, 1.5])
                            
                            # ボタンの余白を詰めるため、縦位置調整
                            if c[0].button("詳細", key=f"btn_{category}_{index}"):
                                show_detail_dialog(row)
                            
                            # 文字サイズや行間を少し小さくするHTML表示も可能だが、
                            # 今回はst.writeのままCSSで行間を詰めて対応
                            c[1].write(f"{row['ID']}")
                            c[2].write(f"**{row['品名']}**")
                            c[3].write(f"{row['利用者']}")
                            
                            status = row['ステータス']
                            if status == "利用可能":
                                c[4].info(status, icon="✅")
                            elif status == "貸出中":
                                c[4].warning(status, icon="🏃")
                            elif status == "故障/修理中":
                                c[4].error(status, icon="⚠️")
                            else:
                                c[4].write(status)

                            # G/H列
                            curr_cols_def = COLUMNS_DEF.get(row['カテゴリ'], [])
                            val_g = row.get(curr_cols_def[0], '') if len(curr_cols_def) > 0 else ""
                            val_h = row.get(curr_cols_def[1], '') if len(curr_cols_def) > 1 else ""
                            
                            c[5].write(f"{val_g}")
                            c[6].write(f"{val_h}")
                            
                            # 行ごとの区切り線（CSSで極細に設定したhrタグ）
                            st.markdown('<hr>', unsafe_allow_html=True)

                        # --- ページネーションボタン ---
                        st.write("") # スペース
                        col_prev, col_page_info, col_next = st.columns([1, 2, 1])
                        
                        # 前へボタン
                        with col_prev:
                            if current_page > 0:
                                if st.button("⬅️ 前の50件", key=f"prev_{category}"):
                                    st.session_state.page_number -= 1
                                    st.rerun()
                        
                        # ページ情報
                        with col_page_info:
                            st.markdown(f"<div style='text-align: center; color: gray;'>Page {current_page + 1} / {max_page + 1}</div>", unsafe_allow_html=True)

                        # 次へボタン
                        with col_next:
                            if end_idx < total_items:
                                if st.button("次の50件 ➡️", key=f"next_{category}"):
                                    st.session_state.page_number += 1
                                    st.rerun()

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

            st.markdown("---")
            st.markdown(f"##### 📝 {selected_category_key} 詳細情報")
            
            custom_values = {}

            # 項目の定義は長くなるので省略せず全て記述します
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
