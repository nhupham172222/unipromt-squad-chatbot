import os
import streamlit as st
import backend
from datetime import datetime
from streamlit_option_menu import option_menu

st.set_page_config(page_title="Chatbot Khoa học Dữ liệu", layout="wide")
st.markdown("""
    <style>
    .sticky-header {
        position: fixed;
        top: 0;
        width: 100%;
        background: white;
        padding: 10px 20px;
        z-index: 1000;
        border-bottom: 1px solid #eee;
    }
    .main-content {
        margin-top: 70px;  /* cao hơn header */
    }
    .chat-container {
        padding-bottom: 100px; /* chừa chỗ cho khung nhập */
        height: calc(100vh - 170px);
        overflow-y: auto;
    }
    .chat-input {
        position: fixed;
        bottom: 0;
        width: calc(100% - 250px);
        background: white;
        padding: 10px 20px;
        border-top: 1px solid #eee;
        z-index: 1000;
    } 
    </style>
""", unsafe_allow_html=True)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.sidebar.title("📂 Chats")

    def new_chat():
        st.session_state.current_chat = []
        st.session_state.selected_chat = None

    # Init session state
    if "saved_chats" not in st.session_state:
        st.session_state.saved_chats = {}
    if "current_chat" not in st.session_state:
        st.session_state.current_chat = []
    if "selected_chat" not in st.session_state:
        st.session_state.selected_chat = None

    # Callback for New Chat: save then reset
    def new_chat():
        # Only save if not empty
        if st.session_state.current_chat:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.saved_chats[f"Chat {timestamp}"] = st.session_state.current_chat.copy()
        # Reset current chat
        st.session_state.current_chat = []
        st.session_state.selected_chat = None

    # New Chat button
    st.sidebar.button("+ New Chat", on_click=new_chat)
    # Saved Chats select
    actions = ["--"] + list(st.session_state.saved_chats.keys())
    choice = st.sidebar.selectbox("Saved Chats", actions, key="select_chat")
    st.session_state.selected_chat = choice if choice != "--" else None

    pages = {
        "Chatbot Tư vấn tuyển sinh": None,
        "Thông tin tuyển sinh": "content/thong_tin_tuyen_sinh.md",
        "Tin tức tuyển dụng":        "content/tin_tuc_tuyen_dung.md",
        "Thông tin học bổng":      "content/hoc_bong.md",
        "Tin tức công nghệ":       "content/tin_tuc_cong_nghe.md",
        "Góc SV":                  "content/goc_sv.md"
    }

    # === Sidebar menu ===
    selected = option_menu(
        menu_title=None,
        options=list(pages.keys()),
        icons=["chat-dots", "book", "briefcase", "award", "cpu", "people"], 
        menu_icon="cast",
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "text-decoration": "none",
                "color": "#333",
                "padding": "4px 0px",
            },
            "nav-link-selected": {
                "font-size": "16px",
                "font-weight": "bold",
                "color": "#000",
                "background-color": "transparent",
            },
        },
    )

# === Main area ===

st.markdown('<div class="sticky-header"><h1>📚 UniPrompt Chatbot</h1></div>', unsafe_allow_html=True)
st.markdown('<div class="main-content">', unsafe_allow_html=True)

md_path = pages[selected]
if md_path:
    # Hiển thị trang tĩnh
    with open(md_path, "r", encoding="utf-8") as f:
        st.markdown(f.read(), unsafe_allow_html=True)
else:
    # ---------- SELECT HISTORY ----------
    history = (st.session_state.saved_chats.get(st.session_state.selected_chat)
               if st.session_state.selected_chat else st.session_state.current_chat)
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)

    # Hiển thị phần giới thiệu khi chưa có câu hỏi nào
    if not history:
        st.markdown("""
            ### 🤖 Xin chào! Tôi là **UniPrompt Chatbot**  
            Đây là một sản phẩm dự thi **Bach Khoa Innovation 2025** của nhóm **UniPrompt Squad** gồm các thành viên:  
            - Phạm Thùy Anh 
            - Nguyễn Trung Nam 
            - Nguyễn Thị Thanh Ngân
            - Phạm Lê Quỳnh Như
            - Nguyễn Ngọc Nhi
            - Nguyễn Đỗ Bảo Long
            <br>
            Cùng với sự hỗ trợ của giáo viên hướng dẫn: **TS. Phan Thị Hường** và **TS. Nguyễn Tiến Dũng**.
        """, unsafe_allow_html=True)

    for q, a in history:
        # User on right
        _, col_user = st.columns([2, 3])
        with col_user:
            with st.chat_message("user", avatar="Capybara.png"):
                st.markdown(q)
        # Bot on left
        col_bot, _ = st.columns([3, 1])
        with col_bot:
            with st.chat_message("assistant", avatar="HCMUT_official_logo.png"):
                st.markdown(a)
        st.markdown("---")
    st.markdown('</div>', unsafe_allow_html=True)

    # ---------- INPUT AREA ----------
    if st.session_state.selected_chat is None:
        st.markdown('<div class="chat-input"></div>', unsafe_allow_html=True)
        query = st.chat_input("Nhập câu hỏi...")
        if query:
            # show user
            _, col_user = st.columns([2, 3])
            with col_user:
                with st.chat_message("user", avatar="Capybara.png"):
                    st.markdown(query)
            # process
            llm = backend.llm
            llm_with_tools = llm.bind_tools(backend.tools)
            answer = backend.process_query(query, llm_with_tools)
            # show bot
            col_bot, _ = st.columns([3, 1])
            with col_bot:
                with st.chat_message("assistant", avatar="HCMUT_official_logo.png"):
                    st.markdown(answer)
            # save
            st.session_state.current_chat.append((query, answer))
            
st.markdown('</div>', unsafe_allow_html=True)
