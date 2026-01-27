import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- ページ設定 ---
st.set_page_config(page_title="総務備品管理アプリ", page_icon="🏢", layout="centered")

# --- 設定: クラウドの金庫(Secrets)から情報を取得 ---
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
SPREADSHEET_NAME = 'management_db'

# --- データ取得関数 ---
def get_data():
    sheet = client.open(SPREADSHEET_NAME).worksheet('data')
    data = sheet.get_all_records()
    return sheet, data

# --- アプリの画面構成 ---
st.title('📱 総務備品管理アプリ')

try:
    # データを読み込む
    sheet, data = get_data()
    df = pd.DataFrame(data)

    # メインのタブ（一覧検索 と 登録更新）
    main_tab1, main_tab2 = st.tabs(["🔍 一覧・検索", "📝 新規登録・更新"])

    # ==========================================
    # タブ1：一覧・検索（機能強化版）
    # ==========================================
    with main_tab1:
        st.header("在庫データの検索")

        # --- 1. フリーワード検索 ---
        search_query = st.text_input("フリーワード検索 (品名、利用者、IDなど)", placeholder="例: MacBook, 鈴木, TEST01...")

        # 検索ロジック: 入力があればデータを絞り込む
        if search_query:
            # データフレーム全体を文字に変換して、検索ワードが含まれる行だけ抽出
            filtered_df = df[df.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)]
            st.success(f"検索結果: {len(filtered_df)} 件が見つかりました")
        else:
            filtered_df = df

        st.markdown("---")

        # --- 2. カテゴリ別タブ表示 ---
        # データに含まれるカテゴリ一覧を取得（なければ「なし」）
        if not df.empty:
            categories = ["すべて"] + sorted(list(df['カテゴリ'].unique()))
        else:
            categories = ["すべて"]

        # カテゴリの数だけサブタブを作成
        cat_tabs = st.tabs(categories)

        # 各タブの中身を作るループ
        for i, category in enumerate(categories):
            with cat_tabs[i]:
                # 「すべて」なら検索結果そのまま、それ以外ならカテゴリでさらに絞り込み
                if category == "すべて":
                    display_df = filtered_df
                else:
                    display_df = filtered_df[filtered_df['カテゴリ'] == category]

                # テーブル表示
                st.dataframe(display_df, use_container_width=True)
                
                # 件数表示
                if not display_df.empty:
                    st.caption(f"該当: {len(display_df)} 件")
                else:
                    st.warning("データがありません")

    # ==========================================
    # タブ2：登録・更新（前回と同じ高機能版）
    # ==========================================
    with main_tab2:
        st.header("データの登録")
        
        st.subheader("① カテゴリを選択")
        selected_category = st.radio("登録するカテゴリを選んでください", ["PC", "車両", "iPad/携帯", "その他"], horizontal=True)

        st.subheader("② 詳細情報の入力")
        with st.form("entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                input_id = st.text_input("ID (資産番号など)")
                input_name = st.text_input("品名 (例: プリウス / MacBook)")
            with col2:
                input_user = st.text_input("現在の利用者")
                input_status = st.selectbox("ステータス", ["利用可能", "貸出中", "故障/修理中", "廃棄"])

            input_syaken = ""
            input_os_detail = ""

            if selected_category == "車両":
                st.markdown("---")
                st.markdown("**🚗 車両専用項目**")
                d = st.date_input("車検満了日", value=None)
                if d:
                    input_syaken = d.strftime('%Y-%m-%d')
            
            elif selected_category == "PC" or selected_category == "iPad/携帯":
                st.markdown("---")
                st.markdown("**💻 IT機器専用項目**")
                input_os_detail = st.text_input("OS・スペック・電話番号など")

            st.markdown("---")
            submitted = st.form_submit_button("登録 / 更新")
            
            if submitted:
                if not input_id or not input_name:
                    st.error("IDと品名は必須です！")
                else:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_row = [
                        input_id, selected_category, input_name, input_user, input_status, current_time,
                        input_syaken, input_os_detail
                    ]
                    
                    cell = sheet.find(input_id)
                    if cell:
                        r = cell.row
                        sheet.update(f"A{r}:H{r}", [new_row])
                        st.success(f"ID: {input_id} を更新しました！")
                    else:
                        sheet.append_row(new_row)
                        st.success(f"ID: {input_id} を新規登録しました！")
                    
                    st.rerun()

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
