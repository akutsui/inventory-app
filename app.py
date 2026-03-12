# --- 🔐 電子証明書管理セクション内のアラート表示部分を修正 ---

        elif st.session_state['tab_cert'] == "📋 一覧・検索":
            st.markdown("#### 電子証明書の管理")
            
            if df_cert is None:
                st.error(f"シート「{SHEET_CERTIFICATE}」が見つかりません。スプレッドシートに作成してください。")
            elif df_cert.empty:
                st.info("登録されているデータはありません。")
            else:
                # --- アラートの収集 (75日以内) ---
                alert_items_cert = []
                today = datetime.now().date()
                for index, row in df_cert.iterrows():
                    exp_val = row.get('有効期限')
                    dt = parse_date(exp_val)
                    if dt:
                        diff = (dt.date() - today).days
                        # 種類を取得（空の場合は「不明」）
                        cert_type = row.get('種類', '不明')
                        exp_date_str = dt.strftime('%Y-%m-%d')
                        
                        if diff < 0:
                            alert_items_cert.append({
                                "row": row,
                                "display_text": f"{cert_type} : 有効期限 超過 ({exp_date_str})"
                            })
                        elif diff <= 75:
                            alert_items_cert.append({
                                "row": row,
                                "display_text": f"{cert_type} : 有効期限 あと{diff}日 ({exp_date_str})"
                            })
                
                # --- アラートの表示 ---
                if alert_items_cert:
                    st.markdown("""
                        <div class="alert-box" style="background-color: #ffcccc; padding: 0.2rem 0.5rem; border-radius: 0.5rem; border: 1px solid #ff4b4b;">
                            <h5 style="margin: 0; padding: 0.2rem 0; color: #8B0000; font-size: 1rem;">⚠️ 電子証明書 期日アラート (75日以内)</h5>
                        </div>
                    """, unsafe_allow_html=True)

                    for i, item in enumerate(alert_items_cert):
                        c1, c2 = st.columns([5, 1])
                        # ご要望の形式で表示
                        c1.markdown(f"<div style='color: #8B0000; font-weight: bold;'>{item['display_text']}</div>", unsafe_allow_html=True)
                        if c2.button("詳細", key=f"alert_cert_btn_{i}"):
                            show_cert_dialog(item['row'])
                        if i < len(alert_items_cert) - 1:
                            st.markdown('<hr style="margin: 0.2rem 0; border-top: 1px dotted #ff9999;">', unsafe_allow_html=True)
                    
                    st.write("")
