import os
import streamlit as st
import backend
from datetime import datetime

st.set_page_config(page_title="Chatbot Khoa học Dữ liệu", layout="wide")
st.markdown("""
    <style>
    .sticky-header {
        position: fixed;
        top: 0;
        width: 100%;
        background: white;
        padding: 10px 20px;
        z-index: 999;
        border-bottom: 1px solid #eee;
    }
    .chat-container {
        margin-top: 70px;  /* để không bị đè bởi header */
        padding-bottom: 100px; /* chừa chỗ cho khung nhập */
        height: calc(100vh - 170px);
        overflow-y: auto;
    }
    .chat-input {
        position: fixed;
        bottom: 0;
        width: 100%;
        background: white;
        padding: 10px 20px;
        border-top: 1px solid #eee;
        z-index: 999;
    }
    </style>
""", unsafe_allow_html=True)

# ---------- SIDEBAR ----------
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

# ---------- HEADER ----------
st.markdown('<div class="sticky-header"><h1>📚 UniPrompt Squad</h1></div>', unsafe_allow_html=True)

# ---------- SELECT HISTORY ----------
history = st.session_state.saved_chats.get(st.session_state.selected_chat, st.session_state.current_chat)

# ---------- CHAT ZONE ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

# Hiển thị phần giới thiệu khi chưa có câu hỏi nào
if not history:
    st.markdown("""
        ### 🤖 Xin chào! Tôi là **DaSci_BKchat**  
        Đây là một sản phẩm dự thi **BKI 2025** của nhóm **UniPrompt Squad** gồm các thành viên:  
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
