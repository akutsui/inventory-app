import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import calendar
import requests
import json
from google.oauth2.service_account import Credentials
import gspread
import io

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(
    page_title="業務・物品統合管理ダッシュボード",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS（デザイン調整）
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .cassette-green { background-color: #1b4332; border-left: 5px solid #2d6a4f; padding: 12px; border-radius: 6px; margin-bottom: 12px; }
    .cassette-blue { background-color: #1a3a5f; border-left: 5px solid #2b6cb0; padding: 12px; border-radius: 6px; margin-bottom: 12px; }
    .cassette-amber { background-color: #4a3b10; border-left: 5px solid #d97706; padding: 12px; border-radius: 6px; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔑 Googleスプレッドシート 連携ロジック
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        gcp_secrets = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(gcp_secrets, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Googleスプレッドシート認証エラー: {e}")
        return None

def get_sheet_data(sheet_name):
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try:
        spreadsheet_id = st.secrets["spreadsheet"]["id"]
        sh = client.open_by_key(spreadsheet_id)
        
        try:
            ws = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # シートが存在しない場合は空のシートを作成して返す
            ws = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
            return pd.DataFrame()
            
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"データ取得エラー ({sheet_name}): {e}")
        return pd.DataFrame()

def save_sheet_data(sheet_name, df):
    client = get_gspread_client()
    if not client: return False
    try:
        spreadsheet_id = st.secrets["spreadsheet"]["id"]
        sh = client.open_by_key(spreadsheet_id)
        
        try:
            ws = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
            
        ws.clear()
        df_clean = df.fillna("")
        if not df_clean.empty:
            ws.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())
        return True
    except Exception as e:
        st.error(f"データ保存エラー ({sheet_name}): {e}")
        return False

# ==========================================
# 🔑 LINE WORKS 連携ロジック
# ==========================================
LINEWORKS_USER_MAP = st.secrets["lineworks"].get("members", {})
USER_OPTIONS = list(LINEWORKS_USER_MAP.keys())

@st.cache_data(ttl=3000)
def get_lineworks_token():
    try:
        lw_secrets = st.secrets["lineworks"]
        client_id = lw_secrets["client_id"]
        client_secret = lw_secrets["client_secret"]
        service_account = lw_secrets["service_account"]
        private_key = lw_secrets["private_key"]
        
        import jwt
        import time
        
        now = int(time.time())
        payload = {
            "iss": client_id,
            "sub": service_account,
            "iat": now,
            "exp": now + 3600
        }
        encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
        
        url = "https://auth.worksmobile.com/oauth2/v2.0/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "assertion": encoded_jwt,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "calendar"
        }
        
        res = requests.post(url, headers=headers, data=data)
        if res.status_code == 200:
            return res.json().get("access_token")
        else:
            return None
    except Exception as e:
        return None

def add_lineworks_calendar_event(user_name, task_name, due_date_str):
    token = get_lineworks_token()
    if not token: return False
    
    user_email = LINEWORKS_USER_MAP.get(user_name)
    if not user_email: return False
    
    url = f"https://www.worksapis.com/v1.0/users/{user_email}/calendars/default/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    event_body = {
        "title": f"【期限】{task_name}",
        "start": {"date": due_date_str},
        "end": {"date": due_date_str},
        "isAllDay": True
    }
    
    try:
        res = requests.post(url, headers=headers, json=event_body)
        return res.status_code in [200, 201]
    except:
        return False

# ==========================================
# 📅 不在カレンダー取得（時間指定・終日 両対応）
# ==========================================
@st.cache_data(ttl=180)
def fetch_absence_events(year, month):
    token = get_lineworks_token()
    if not token: return {}
    
    service_account = st.secrets["lineworks"]["service_account"]
    calendar_id = "16f4dc1f-4b82-4c6e-9fb8-f2f27d7caf99"
    url = f"https://www.worksapis.com/v1.0/users/{service_account}/calendars/{calendar_id}/events"
    
    start_date = datetime(year, month, 1)
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "fromDateTime": start_date.strftime('%Y-%m-%dT00:00:00+09:00'),
        "untilDateTime": end_date.strftime('%Y-%m-%dT00:00:00+09:00'),
        "maxResults": 1000
    }
    
    res = requests.get(url, headers=headers, params=params)
    events_by_date = {}
    
    if res.status_code != 200:
        return {}
        
    events = res.json().get("events", [])
    target_names = ["橘田", "阿久津", "野崎", "水上", "森田", "仁平"]
    exclude_words = ["リモート", "鹿沼便"]
    
    for item in events:
        components = item.get("eventComponents", [])
        if not components:
            continue
            
        comp = components[0]
        summary = comp.get("summary", "")
        
        if any(n in summary for n in target_names) and not any(w in summary for w in exclude_words):
            start_dict = comp.get("start", {})
            end_dict = comp.get("end", {})
            
            start_raw = start_dict.get("date") or start_dict.get("dateTime", "")
            end_raw = end_dict.get("date") or end_dict.get("dateTime", "")
            
            start_str = start_raw[:10] if len(start_raw) >= 10 else ""
            end_str = end_raw[:10] if len(end_raw) >= 10 else ""
            
            if start_str:
                dt_start = datetime.strptime(start_str, '%Y-%m-%d')
                
                if end_str and end_str != start_str:
                    if "T" in end_raw:
                        dt_end = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
                    else:
                        dt_end = datetime.strptime(end_str, '%Y-%m-%d')
                else:
                    dt_end = dt_start + timedelta(days=1)
                
                curr_dt = dt_start
                while curr_dt < dt_end:
                    d_key = curr_dt.strftime('%Y-%m-%d')
                    if d_key not in events_by_date: events_by_date[d_key] = []
                    events_by_date[d_key].append(summary)
                    curr_dt += timedelta(days=1)
    return events_by_date

def render_monthly_calendar(year, month, events_by_date):
    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdatescalendar(year, month)
    
    html = """
    <style>
    .custom-calendar { width: 100%; border-collapse: collapse; margin-top: 10px; table-layout: fixed; }
    .custom-calendar th { background-color: #333; color: white; padding: 6px; text-align: center; border: 1px solid #555; font-size: 0.9rem; }
    .custom-calendar td { border: 1px solid #555; height: 90px; vertical-align: top; padding: 4px; background-color: #1a1a1a; overflow: hidden; }
    .custom-calendar td.different-month { background-color: #0a0a0a; opacity: 0.5; }
    .custom-calendar .day-num { font-weight: bold; margin-bottom: 4px; font-size: 0.85rem; color: #ddd; }
    .custom-calendar .day-num.sunday { color: #ff6b6b; }
    .custom-calendar .day-num.saturday { color: #4dabf7; }
    .custom-calendar .event-item { background-color: #e53935; color: white; border-radius: 4px; padding: 2px 4px; font-size: 0.75rem; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: bold; }
    </style>
    <table class="custom-calendar">
    <tr><th style="color:#ff6b6b;">日</th><th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th style="color:#4dabf7;">土</th></tr>
    """
    
    for week in month_days:
        html += "<tr>"
        for date_obj in week:
            td_class = "different-month" if date_obj.month != month else ""
            day_class = "sunday" if date_obj.weekday() == 6 else ("saturday" if date_obj.weekday() == 5 else "")
            html += f'<td class="{td_class}"><div class="day-num {day_class}">{date_obj.day}</div>'
            
            day_events = events_by_date.get(date_obj.strftime('%Y-%m-%d'), [])
            for ev in day_events: html += f'<div class="event-item" title="{ev}">{ev}</div>'
            html += "</td>"
        html += "</tr>"
    html += "</table>"
    return html

# 汎用管理画面描画関数
def render_generic_management_page(title, sheet_name, default_cols):
    st.title(title)
    df = get_sheet_data(sheet_name)
    
    if df.empty:
        df = pd.DataFrame(columns=default_cols)
        
    with st.expander(f"➕ 新しい{title}を追加する", expanded=False):
        with st.form(f"add_form_{sheet_name}"):
            inputs = {}
            for col in default_cols:
                inputs[col] = st.text_input(col)
            submitted = st.form_submit_button("保存")
            if submitted:
                if any(inputs.values()):
                    df_new = pd.concat([df, pd.DataFrame([inputs])], ignore_index=True)
                    if save_sheet_data(sheet_name, df_new):
                        st.success("追加しました！")
                        st.rerun()
                        
    st.markdown("---")
    st.subheader(f"📋 {title} 一覧・編集")
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{sheet_name}"
    )
    if st.button(f"💾 {title} の編集内容を保存", key=f"btn_{sheet_name}"):
        if save_sheet_data(sheet_name, edited_df):
            st.success("保存しました！")
            st.rerun()

# ==========================================
# 🚀 アプリケーション本体
# ==========================================
try:
    today = datetime.now().date()
    
    if 'cal_year' not in st.session_state: st.session_state.cal_year = today.year
    if 'cal_month' not in st.session_state: st.session_state.cal_month = today.month

    # 📌 サイドバー（全メニュー復活！）
    st.sidebar.title("📌 業務統合メニュー")
    page_selection = st.sidebar.radio(
        "機能を選択", 
        [
            "🏠 ホーム", 
            "📝 タスク管理", 
            "📦 在庫・消耗品管理", 
            "🚗 社用車管理", 
            "💻 PC・IT資産管理", 
            "🛋️ 備品・設備管理",
            "📥 CSV一括入出力"
        ]
    )

    # ------------------------------------------
    # 🏠 ホーム画面
    # ------------------------------------------
    if page_selection == "🏠 ホーム":
        st.title("🏠 業務管理ダッシュボード")
        
        # 進行中タスク表示
        df_task = get_sheet_data("Tasks")
        st.subheader("📌 進行中のタスク一覧")
        active_tasks = []
        if not df_task.empty and 'ステータス' in df_task.columns:
            df_active = df_task[df_task['ステータス'] != '完了'].copy()
            if '期限' in df_active.columns:
                df_active['sort_date'] = pd.to_datetime(df_active['期限'], errors='coerce')
                df_active = df_active.sort_values(by='sort_date', ascending=True)
                
                for _, row in df_active.iterrows():
                    active_tasks.append(f"📌 <strong>{row.get('タスク名', '')}</strong> &nbsp;&nbsp;(担当: {row.get('担当者', '未定')}) &nbsp;&nbsp;📅 {row.get('期限', '未定')} まで")
        
        if active_tasks:
            st.markdown(f'<div class="cassette-blue">{"".join([f"<div>{task}</div>" for task in active_tasks])}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cassette-blue">🎉 現在、進行中のタスクはありません。</div>', unsafe_allow_html=True)

        st.markdown("<br><hr><br>", unsafe_allow_html=True)

        # 不在カレンダー表示
        col_c1, col_c2, col_c3 = st.columns([1, 3, 1])
        with col_c1:
            if st.button("◀ 前月"):
                if st.session_state.cal_month == 1:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                else:
                    st.session_state.cal_month -= 1
                st.rerun()
        with col_c2:
            st.markdown(f"<h3 style='text-align: center;'>📅 {st.session_state.cal_year}年 {st.session_state.cal_month}月 不在予定一覧</h3>", unsafe_allow_html=True)
        with col_c3:
            if st.button("翌月 ▶"):
                if st.session_state.cal_month == 12:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                else:
                    st.session_state.cal_month += 1
                st.rerun()

        events_data = fetch_absence_events(st.session_state.cal_year, st.session_state.cal_month)
        cal_html = render_monthly_calendar(st.session_state.cal_year, st.session_state.cal_month, events_data)
        st.markdown(cal_html, unsafe_allow_html=True)

    # ------------------------------------------
    # 📝 タスク管理画面
    # ------------------------------------------
    elif page_selection == "📝 タスク管理":
        st.title("📝 タスク管理")
        df_task = get_sheet_data("Tasks")
        
        with st.expander("➕ 新しいタスクを追加する", expanded=False):
            with st.form("add_task_form"):
                task_name = st.text_input("タスク名")
                assignee = st.selectbox("担当者", USER_OPTIONS)
                due_date = st.date_input("期限", value=today)
                status = st.selectbox("ステータス", ["未対応", "進行中", "完了"])
                sync_lw = st.checkbox("LINE WORKSカレンダーに同期する", value=True)
                
                submitted = st.form_submit_button("タスクを保存")
                if submitted and task_name:
                    new_row = {
                        "タスク名": task_name,
                        "担当者": assignee,
                        "期限": due_date.strftime('%Y-%m-%d'),
                        "ステータス": status
                    }
                    df_new = pd.concat([df_task, pd.DataFrame([new_row])], ignore_index=True)
                    if save_sheet_data("Tasks", df_new):
                        st.success("タスクを追加しました！")
                        if sync_lw:
                            if add_lineworks_calendar_event(assignee, task_name, due_date.strftime('%Y-%m-%d')):
                                st.info("LINE WORKSカレンダーにも同期しました！")
                        st.rerun()

        st.markdown("---")
        st.subheader("📋 登録済みタスク一覧・編集")
        
        if not df_task.empty:
            edited_df = st.data_editor(
                df_task,
                num_rows="dynamic",
                use_container_width=True,
                key="task_editor"
            )
            if st.button("💾 編集内容を保存"):
                if save_sheet_data("Tasks", edited_df):
                    st.success("変更を保存しました！")
                    st.rerun()
        else:
            st.info("タスクがまだ登録されていません。")

    # ------------------------------------------
    # 📦 在庫・消耗品管理
    # ------------------------------------------
    elif page_selection == "📦 在庫・消耗品管理":
        render_generic_management_page("📦 在庫・消耗品管理", "Inventory", ["品名", "カテゴリ", "現在数", "適正在庫", "保管場所", "備考"])

    # ------------------------------------------
    # 🚗 社用車管理
    # ------------------------------------------
    elif page_selection == "🚗 社用車管理":
        render_generic_management_page("🚗 社用車管理", "Vehicles", ["車両名", "ナンバー", "管理者", "車検期限", "次回点検日", "状態"])

    # ------------------------------------------
    # 💻 PC・IT資産管理
    # ------------------------------------------
    elif page_selection == "💻 PC・IT資産管理":
        render_generic_management_page("💻 PC・IT資産管理", "IT_Assets", ["機器名", "管理番号", "使用者", "OS/スペック", "購入日", "状態"])

    # ------------------------------------------
    # 🛋️ 備品・設備管理
    # ------------------------------------------
    elif page_selection == "🛋️ 備品・設備管理":
        render_generic_management_page("🛋️ 備品・設備管理", "Equipment", ["備品名", "設置場所", "管理担当", "購入時期", "状態", "備考"])

    # ------------------------------------------
    # 📥 CSV一括入出力画面
    # ------------------------------------------
    elif page_selection == "📥 CSV一括入出力":
        st.title("📥 CSV一括入出力")
        target_sheet = st.selectbox("対象データを選択", ["Tasks", "Inventory", "Vehicles", "IT_Assets", "Equipment"])
        
        df_target = get_sheet_data(target_sheet)
        col_csv1, col_csv2 = st.columns(2)
        
        with col_csv1:
            st.subheader("📤 CSVダウンロード")
            if not df_target.empty:
                csv_data = df_target.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label=f"📥 {target_sheet} のCSVをダウンロード",
                    data=csv_data,
                    file_name=f"{target_sheet}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("ダウンロードできるデータがありません。")
                
        with col_csv2:
            st.subheader("📥 CSV一括インポート")
            uploaded_file = st.file_uploader("CSVファイルをアップロードしてください", type=["csv"])
            if uploaded_file is not None:
                try:
                    df_uploaded = pd.read_csv(uploaded_file)
                    st.write("🔍 プレビュー:")
                    st.dataframe(df_uploaded.head())
                    
                    if st.button("⚠️ 上書き保存を実行する"):
                        if save_sheet_data(target_sheet, df_uploaded):
                            st.success(f"{target_sheet} のデータを上書き保存しました！")
                            st.rerun()
                except Exception as e:
                    st.error(f"CSV読み込みエラー: {e}")

except Exception as e:
    st.error(f"予期せぬシステムエラーが発生しました: {e}")
