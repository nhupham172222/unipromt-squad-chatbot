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
        margin-top: 10px;  /* cao hơn header */
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
    .stChatMessage:first-child {
        margin-top: 0rem !important;
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
        st.session_state.welcome_sent = False  # 👈 Reset lại để hiện lời chào mới
        
    # New Chat button
    st.sidebar.button("+ New Chat", on_click=new_chat)
    # Saved Chats select
    actions = ["--"] + list(st.session_state.saved_chats.keys())
    choice = st.sidebar.selectbox("Saved Chats", actions, key="select_chat")
    st.session_state.selected_chat = choice if choice != "--" else None

    pages = {
        "Chatbot Tư vấn tuyển sinh": None,
        "About Us": "content/about_us.md",
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

import base64

def image_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_hcmut = image_to_base64("HCMUT logo.jpg")
logo_che   = image_to_base64("CHE logo.jpg")
logo_as    = image_to_base64("AS logo.jpg")

# CSS cho sticky header
st.markdown(f"""
    <style>
        .block-container {{
            padding-top: 0rem !important;
        }}
        .my-sticky-header {{
            position: -webkit-sticky;
            position: sticky;
            top: 0;
            background-color: white;
            z-index: 999;
            padding: 10px 20px;
            border-bottom: 1px solid #eee;
        }}
        .my-sticky-header-content {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .my-sticky-header h1 {{
            font-size: 3.5rem;
            margin: 0;
            font-weight: 700;
        }}
        .logo-set img {{
            height: 65px;
            margin-left: 15px;
        }}
    </style>
""", unsafe_allow_html=True)

# Gắn vào st.container để Streamlit giữ vị trí
with st.container():
    st.markdown(f"""
        <div class="my-sticky-header">
            <div class="my-sticky-header-content">
                <h1>📚 UniPrompt Chatbot</h1>
                <div class="logo-set">
                    <img src="data:image/jpeg;base64,{logo_hcmut}" />
                    <img src="data:image/jpeg;base64,{logo_che}" />
                    <img src="data:image/jpeg;base64,{logo_as}" />
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("""
<p style="font-size: 0.9rem; font-style: italic; color: #666; margin-top: 1em; margin-bottom: 1.5em;">
    Phiên bản 1.0 – Đứa con tinh thần của <strong>The UniPrompt Squad</strong>, 
    chính thức “chào đời” ngày <strong>23/06/2025</strong>. Chatbot vẫn đang trong quá trình hoàn thiện. 
    Rất mong nhận được mọi góp ý và phản hồi để chúng tôi ngày càng nâng cao chất lượng và trải nghiệm!
</p>
""", unsafe_allow_html=True)


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
        
    if "welcome_sent" not in st.session_state:
        st.session_state.welcome_sent = False
    
    if not history and not st.session_state.welcome_sent:
        welcome_msg = (
            "**Chào bạn, mình là UNIPROMPT CHATBOT – một trợ lý ảo**  \n"
            "Mình hỗ trợ tư vấn tuyển sinh cho ngành Khoa học dữ liệu, thuộc bộ môn Toán Ứng dụng – Khoa Khoa học Ứng dụng – ĐH Bách Khoa TP.HCM.  \n"
            "Bạn có câu hỏi gì cần hỗ trợ không?  \n\n"
            "_(Nếu không muốn hỏi thêm điều gì, bạn có thể dừng cuộc trò chuyện bất cứ lúc nào!)_"
        )

        with st.chat_message("assistant", avatar="HCMUT_official_logo.png"):
            st.markdown(welcome_msg)

        # Gửi đúng 1 lần mỗi chat mới
        st.session_state.welcome_sent = True

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
            
            # --- Setup memory cho slot-filling ---
            if "memory" not in st.session_state:
                st.session_state.memory = {}
            
            answer = backend.process_query(query, llm_with_tools, st.session_state.memory)
            # show bot
            col_bot, _ = st.columns([3, 1])
            with col_bot:
                with st.chat_message("assistant", avatar="HCMUT_official_logo.png"):
                    st.markdown(answer)
            # save
            st.session_state.current_chat.append((query, answer))
            
st.markdown('</div>', unsafe_allow_html=True)