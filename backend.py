
# -*- coding: utf-8 -*-
"""Draft.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1JeEXxTzKYwB_uraxC4vlsq6IwYfs1qhh
"""

import getpass
import os
import logging
logging.getLogger("langchain_google_genai.chat_models").setLevel(logging.ERROR)
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "AIzaSyD_K258YPnc7_GuDDtQ5kHFfe4SO2cmpYY"
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_google_genai import GoogleGenerativeAIEmbeddings
import chromadb
from chromadb.config import Settings
# 1) Khởi raw embedder cho Gemini text-embedding-004 (768-dim)
raw_embedder = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

# Chuẩn hóa embedding
import numpy as np

def normalize_batch(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-8, norms)
    return embeddings / norms


class NormalizedEmbedder:
    def __init__(self, embedder):
        self.embedder = embedder

    def embed_documents(self, docs: list[str]) -> np.ndarray:
        emb = self.embedder.embed_documents(docs)
        return normalize_batch(emb)

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_documents([query])[0]

# Bọc raw_embedder để tự normalize
normalized_embedder = NormalizedEmbedder(raw_embedder)

# 2) Wrapper đúng interface (tham số phải tên “input”)aa
class ChromaEmbeddingWrapper768:
    def __init__(self, embedder, name: str):
        self.embedder = embedder
        self._name = name

    def __call__(self, input: list[str]) -> list[list[float]]:
        # ChromaDB sẽ gọi wrapper(self, input)
        return self.embedder.embed_documents(input)

    def name(self) -> str:
        return self._name

# Tạo instance wrapper
wrapper_768 = ChromaEmbeddingWrapper768(
    normalized_embedder,
    name="text-embedding-004"   # tên model embedding chính xác
)

# 3) Kết nối Chroma
client = chromadb.Client()

pdf_collection = client.get_or_create_collection(
    name="pdf_auto_khdl",
    embedding_function=wrapper_768,
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,   # sửa key ở đây
        "hnsw:search_ef": 50           # (tuỳ chọn) tốc độ/ngưỡng tìm kiếm
    }
)
excel_collection = client.get_or_create_collection(
    name="excel_manual_khdl",
    embedding_function=wrapper_768,
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,   # sửa key ở đây
        "hnsw:search_ef": 50           # (tuỳ chọn) tốc độ/ngưỡng tìm kiếm
    }
)

pdf_folder = "./BKI/Auto chunk"
pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]

#Auto chunking
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import (
TextLoader,
UnstructuredPDFLoader,
PyPDFLoader
)
from langchain_google_genai import GoogleGenerativeAIEmbeddings
splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", ".", "?", "!"],
    chunk_size=800,             # tăng lên để chứa đủ 1-2 đoạn ý liền mạch
    chunk_overlap=200,          # vừa phải, đủ để không mất ngữ cảnh
)
pdf_chunks = []
for file in pdf_files:
    file_path = os.path.join(pdf_folder, file)#lấy địa chỉ cụ thể của từng file trong folder
    loader = PyPDFLoader(file_path)
    pages = loader.load()  # Mỗi trang là 1 Document

    full_text = "\n".join([page.page_content for page in pages])#Nối các trang trong file thành một đoạn
    chunks = splitter.split_text(full_text)  # → list[str]
    pdf_chunks.extend(chunks)
    doc_id_base = "to_roi_KHDL_BMT_2025" # Tên file không đuôi

    documents = os.path.splitext(file)[0]
    metadatas = [{"source": doc_id_base, "content": chunk} for chunk in chunks]
    to_embed = [f"{documents} — {meta['content']}" for meta in metadatas]
    embeddings = normalized_embedder.embed_documents(to_embed)
    ids = [f"{documents}_chunk_{i}" for i in range(len(chunks))]
     # Nạp vào collection
    pdf_collection.upsert(
        documents=[documents] * len(chunks),  # tên file lặp lại
        metadatas=metadatas,
        embeddings=embeddings,
        ids=ids
    )

#Manual chunking
import pandas as pd
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Đọc Excel
df = pd.read_excel("./BKI/Manual chunk/Data.xlsx")  # Hoặc đúng đường dẫn Colab của bạn

# Hàm xử lý gạch đầu dòng nếu cần (không bắt buộc)
def format_bullets(raw: str) -> str:
    items = [s.strip() for s in str(raw).split(";") if s.strip()]
    return "\n".join(f"+ {it}" for it in items)
excel_chunks = []
for idx, row in df.iterrows():
    # a) Tạo document (tiêu đề) và content (nội dung đã format)
    documents = f"- {row['Doccument']}".strip()
    content = format_bullets(row["Content"])
    source = str(row["Source"])
    to_embed = [f"{documents} — {content}"]
    excel_chunks.append(to_embed)

    # b) Embed ngay chuỗi đó (list độ dài = 1)
    embedding = normalized_embedder.embed_documents(to_embed)
    # c) Add vào collection
    excel_collection.upsert(
        documents=[documents],
        metadatas=[{"source": source, "content": content}],
        embeddings=embedding,
        ids=[f"doc{idx+1}"]
    )

#Hybrid search (Embedding + BM25)
from rank_bm25 import BM25Okapi
def flatten_excel_chunks(raw_excel_chunks):
    excel_chunks = []
    for item in raw_excel_chunks:
        # Nếu là list và không rỗng, lấy phần tử đầu
        if isinstance(item, list) and len(item) > 0:
            item = item[0]
        # Nếu vẫn không phải string, chuyển thành string
        if not isinstance(item, str):
            item = str(item)
        excel_chunks.append(item)
    return excel_chunks
excel_chunks = flatten_excel_chunks(excel_chunks)
# 1) Tạo BM25 index cho mỗi nguồn
pdf_tokenized   = [chunk.split() for chunk in pdf_chunks]
excel_tokenized = [chunk.split() for chunk in excel_chunks]

bm25_pdf   = BM25Okapi(pdf_tokenized)
bm25_excel = BM25Okapi(excel_tokenized)

# 2) Hybrid retrieval function
def hybrid_retrieve(query: str, source: str, M: int = 50, K: int = 5, alpha: float = 0.3):
    """
    source: "pdf" hoặc "excel"
    M: số chunk lấy từ BM25
    K: số chunk cuối giữ lại
    alpha: trọng số BM25 vs embedding
    """
    # Chọn đúng nơi
    if source == "pdf":
        chunks    = pdf_chunks
        bm25      = bm25_pdf
        emb_query = normalized_embedder.embed_query(query)
    else:
        chunks    = excel_chunks
        bm25      = bm25_excel
        emb_query = normalized_embedder.embed_query(query)

    # 2.1) BM25 sơ bộ
    q_tokens = query.split()
    scores   = bm25.get_scores(q_tokens)
    top_idx  = sorted(range(len(chunks)), key=lambda i: -scores[i])[:M]
    cands    = [chunks[i]      for i in top_idx]
    bm25_sc  = [scores[i]      for i in top_idx]

    # 2.2) Embed và re-rank
    cands_emb    = normalized_embedder.embed_documents(cands)  # (M×D)
    cosine_sc    = np.dot(cands_emb, emb_query)               # (M,)

    # 2.3) Normalize BM25 scores về [0,1]
    mn, mx       = min(bm25_sc), max(bm25_sc)
    bm25_norm    = [(s-mn)/(mx-mn+1e-8) for s in bm25_sc]

    # 2.4) Kết hợp hybrid
    hybrid_score = [alpha*b + (1-alpha)*c for b,c in zip(bm25_norm, cosine_sc)]
    top_final    = sorted(range(len(hybrid_score)), key=lambda i: -hybrid_score[i])[:K]

    return [cands[i] for i in top_final]

#tính các điểm thành phần để tính điểm học lực
def calculate_nang_luc(math_score: float, other_score_sum: float) -> dict:
    """
    Điểm năng lực = (math_score * 2 + other_score_sum) / 15
    """
    weighted = math_score * 2 + other_score_sum
    nang_luc = round(weighted / 15, 2)
    return {"nang_luc_score": nang_luc}


def calculate_thpt_test_converted(total_three_subjects: float) -> dict:
    """
    Điểm TNTHPT quy đổi = (Tổng điểm thi 3 môn) / 3 * 10
    """
    converted = round(total_three_subjects / 3 * 10, 2)
    return {"thpt_test_converted": converted}


def calculate_hocba_converted(avg_grade_three_years: float) -> dict:
    """
    Điểm học THPT quy đổi = Trung bình cộng điểm TB 3 năm × 10
    """
    converted = round(avg_grade_three_years * 10, 2)
    return {"hocba_converted": converted}

#tính điểm học lực
def calculate_academic_score(math_score: float,
                             other_score_sum: float,
                             total_three_subjects: float,
                             avg_grade_three_years: float) -> dict:
    """
    Điểm học lực = Điểm năng lực * 0.7
                 + Điểm TNTHPT quy đổi * 0.2
                 + Điểm học THPT quy đổi * 0.1
    Trả về dict bao gồm các giá trị trung gian và kết quả cuối.
    """
    # Gọi các hàm con đã định nghĩa trước
    nang_luc = calculate_nang_luc(math_score, other_score_sum)["nang_luc_score"]
    thpt_converted = calculate_thpt_test_converted(total_three_subjects)["thpt_test_converted"]
    hocba_converted = calculate_hocba_converted(avg_grade_three_years)["hocba_converted"]

    # Tính Điểm học lực theo tỷ lệ
    academic = round(nang_luc * 0.7 + thpt_converted * 0.2 + hocba_converted * 0.1, 2)

    return {
        "academic_score": academic,
        "nang_luc_score": nang_luc,
        "thpt_test_converted": thpt_converted,
        "hocba_converted": hocba_converted
    }

#tính điểm cộng
def calculate_bonus(academic_score: float,
                    performance_bonus: float) -> dict:
    """
    - Giới hạn performance_bonus tối đa 10.
    - Nếu academic_score + raw_bonus < 100 -> bonus = raw_bonus
      Ngược lại -> bonus = 100 - academic_score
    """
    raw_bonus = min(performance_bonus, 10.0)
    if academic_score + raw_bonus < 100.0:
        bonus = raw_bonus
    else:
        bonus = max(0.0, 100.0 - academic_score)
    return {"bonus": round(bonus, 2)}

#tính điểm ưu tiên
def calculate_priority(academic_score: float,
                       bonus: float,
                       priority_group_score: float) -> dict:
    """
    - priority_converted = (priority_group_score / 3) * 10
    - Nếu academic_score + bonus < 75 -> priority = priority_converted
      Ngược lại -> priority = ((100 - academic_score - bonus)/25) * priority_converted
    - Làm tròn 2 chữ số
    """
    priority_converted = (priority_group_score / 3.0) * 10.0
    if academic_score + bonus < 75.0:
        priority = priority_converted
    else:
        priority = round((100.0 - academic_score - bonus) / 25.0 * priority_converted, 2)
    return {"priority": round(priority, 2)}

#tính điểm xét tuyển
def calculate_admission_score(math_score: float,
                              other_score_sum: float,
                              total_three_subjects: float,
                              avg_grade_three_years: float,
                              performance_bonus: float,
                              priority_group_score: float) -> dict:
    """
    Tính Điểm xét tuyển trên thang 100 bao gồm:
      1) Điểm học lực (70% năng lực + 20% TNTHPT quy đổi + 10% học bạ quy đổi)
      2) Điểm cộng thành tích (tối đa 10, không vượt 100)
      3) Điểm ưu tiên (quy đổi & điều chỉnh theo <75 / ≥75)
    Trả về dict với:
      - academic_score, bonus, priority, admission_score
      - cùng các điểm trung gian: nang_luc_score, thpt_test_converted, hocba_converted
    """
    # 1) Academic score
    acad = calculate_academic_score(
        math_score, other_score_sum,
        total_three_subjects, avg_grade_three_years
    )
    academic_score = acad["academic_score"]

    # 2) Bonus
    bonus = calculate_bonus(academic_score, performance_bonus)["bonus"]

    # 3) Priority
    priority = calculate_priority(academic_score, bonus, priority_group_score)["priority"]

    # 4) Total admission score
    admission_score = round(academic_score + bonus + priority, 2)

    return {
        "admission_score": admission_score,
        "academic_score": academic_score,
        "nang_luc_score": acad["nang_luc_score"],
        "thpt_test_converted": acad["thpt_test_converted"],
        "hocba_converted": acad["hocba_converted"],
        "bonus": bonus,
        "priority": priority
    }

# Định nghĩa các Tool sử dụng các hàm có sẵn
from langchain.tools import Tool
tools = [
    Tool(
        name="calculate_nang_luc",
        func=calculate_nang_luc,
        description="Tính Điểm năng lực = (math_score * 2 + other_score_sum) / 15",
        args_schema={
            "math_score": {"type": "number", "description": "Điểm ĐGNL môn Toán", "required": True},
            "other_score_sum": {"type": "number", "description": "Tổng điểm ĐGNL các môn còn lại", "required": True}
        }
    ),
    Tool(
        name="calculate_hocba_converted",
        func=calculate_hocba_converted,
        description="Tính Điểm học THPT quy đổi = Trung bình cộng điểm TB 3 năm × 10.",
        args_schema={
            "avg_grade_three_years": {"type": "number", "description": "Trung bình cộng điểm TB lớp 10, 11, 12 của các môn trong tổ hợp", "required": True}
        }
    ),
    Tool(
        name="calculate_thpt_test_converted",
        func=calculate_thpt_test_converted,
        description="Tính Điểm TNTHPT quy đổi = (Tổng điểm thi 3 môn trong tổ hợp) / 3 × 10.",
        args_schema={
            "total_three_subjects": {"type": "number", "description": "Tổng điểm thi THPT của 3 môn trong tổ hợp", "required": True}
        }
    ),
    Tool(
        name="calculate_academic_score",
        func=calculate_academic_score,
        description="Tính Điểm học lực trên thang 100: 70% từ Điểm năng lực, 20% từ Điểm TNTHPT quy đổi, 10% từ Điểm học bạ quy đổi.",
        args_schema={
            "math_score": {"type": "number", "description": "Điểm ĐGNL môn Toán", "required": True},
            "other_score_sum": {"type": "number", "description": "Tổng điểm ĐGNL các môn còn lại", "required": True},
            "total_three_subjects": {"type": "number", "description": "Tổng điểm thi THPT của 3 môn trong tổ hợp", "required": True},
            "avg_grade_three_years": {"type": "number", "description": "Trung bình cộng điểm TB 3 năm các môn trong tổ hợp", "required": True}
        }
    ),
    Tool(
        name="calculate_bonus",
        func=calculate_bonus,
        description="Tính Điểm cộng thành tích (tối đa 10 điểm, không vượt 100 điểm khi cộng với Điểm học lực).",
        args_schema={
            "academic_score": {"type": "number", "description": "Điểm học lực trên thang 100", "required": True},
            "performance_bonus": {"type": "number", "description": "Tổng điểm cộng thành tích ban đầu (tối đa 10)", "required": True}
        }
    ),
    Tool(
        name="calculate_priority",
        func=calculate_priority,
        description="Tính Điểm ưu tiên theo quy tắc: nếu academic_score+bonus <75 dùng nguyên, ngược lại phải điều chỉnh.",
        args_schema={
            "academic_score": {"type": "number", "description": "Điểm học lực đã tính", "required": True},
            "bonus": {"type": "number", "description": "Điểm cộng thành tích đã điều chỉnh", "required": True},
            "priority_group_score": {"type": "number", "description": "Điểm ưu tiên (khu vực/đối tượng) ban đầu trên thang 0–2.75", "required": True}
        }
    ),
    Tool(
        name="calculate_admission_score",
        func=calculate_admission_score,
        description="Tính Điểm xét tuyển trên thang 100, gộp điểm học lực, điểm cộng thành tích và điểm ưu tiên.",
        args_schema={
            "math_score": {"type": "number", "description": "Điểm ĐGNL môn Toán", "required": True},
            "other_score_sum": {"type": "number", "description": "Tổng điểm ĐGNL các môn còn lại", "required": True},
            "total_three_subjects": {"type": "number", "description": "Tổng điểm thi THPT của 3 môn trong tổ hợp", "required": True},
            "avg_grade_three_years": {"type": "number", "description": "Trung bình cộng điểm TB lớp 10,11,12 các môn trong tổ hợp", "required": True},
            "performance_bonus": {"type": "number", "description": "Điểm cộng thành tích ban đầu (tối đa 10)", "required": True},
            "priority_group_score": {"type": "number", "description": "Điểm ưu tiên (khu vực/đối tượng) ban đầu trên thang 0–2.75", "required": True}
        }
    )
]

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite-preview-06-17",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    # other params...
)

from langchain.schema import Document, HumanMessage, SystemMessage, AIMessage
import re
import inspect
from typing import Dict, Any, Set, List
# -------------------------------------------------------------------#
#                   REGEX PATTERNS CHO SLOT-FILLING                   #
# -------------------------------------------------------------------#
PATTERNS: Dict[str, str] = {
    "math_score":
        r"(?:điểm\s*)?toán(?:\s*của\s*bài\s*thi\s*đánh\s*giá\s*năng\s*lực|\s*đánh\s*giá\s*năng\s*lực)?\s*(?:là|=|:|đc|được)?\s*(\d+\.?\d*)",
    "other_score_sum":
        r"tổng\s*điểm\s*(?:các\s*môn\s*(?:khác|còn\s*lại)(?:\s*của\s*bài\s*thi\s*đánh\s*giá\s*năng\s*lực)?)?\s*(?:là|=|:|đc|được)?\s*(\d+\.?\d*)",
    "total_three_subjects":
        r"(?:(?:tổng\s*điểm\s*)?(?:điểm\s*)?thi\s*thpt)\s*(?:là|=|:|đc|được)?\s*(\d+\.?\d*)",
    "avg_grade_three_years":
        r"trung\s*bình\s*(?:ba|3)\s*năm(?:\s*học)?\s*(?:là|=|:|đc|được)?\s*(\d+\.?\d*)",
    "performance_bonus":
        r"(?:điểm\s*)?(?:thành\s*tích|cộng)\s*(?:là|=|:|đc|được)?\s*(\d+\.?\d*)",
    "priority_group_score":
        r"ưu\s*tiên\s*(?:khu\s*vực|đối\s*tượng)?\s*(?:là|=|:|đc|được)?\s*(\d+\.?\d*)",
}

# -------------------------------------------------------------------#
#                MÔ TẢ THAM SỐ CHO PROMPT HỎI BỔ SUNG                 #
# -------------------------------------------------------------------#
DESCRIPTIONS: Dict[str, str] = {
    "math_score": "Điểm toán của bài thi đánh giá năng lực",
    "other_score_sum": "Tổng điểm các môn còn lại của bài thi đánh giá năng lực",
    "total_three_subjects": "Tổng điểm thi THPT của 3 môn trong tổ hợp",
    "avg_grade_three_years": "Điểm trung bình 3 năm học (lớp 10-11-12)",
    "performance_bonus": "Điểm thành tích (mục cộng điểm)",
    "priority_group_score": "Điểm ưu tiên khu vực/đối tượng",
}

# -------------------------------------------------------------------#
#    MAPPING TỪ KHÓA → TOOL ĐỂ NHẬN DIỆN LIÊN TỤC (FALLBACK)          #
# -------------------------------------------------------------------#
DIRECT_TOOLS: Dict[str, str] = {
    "điểm xét tuyển": "calculate_admission_score",
    "điểm học lực": "calculate_academic_score",
    "điểm năng lực": "calculate_nang_luc",
    "tổng điểm thi": "calculate_thpt_test_converted",
    "thi thpt": "calculate_thpt_test_converted",
    "điểm thpt": "calculate_thpt_test_converted",
    "học bạ": "calculate_hocba_converted",
    "điểm học bạ": "calculate_hocba_converted",
    "thành tích": "calculate_bonus",
    "điểm cộng": "calculate_bonus",
    "ưu tiên": "calculate_priority",
}

# -------------------------------------------------------------------#
#          HÀM TRÍCH THAM SỐ QUA REGEX                                #
# -------------------------------------------------------------------#
def _extract_with_regex(query: str, needed: Set[str]) -> Dict[str, float]:
    text = query.lower()
    found: Dict[str, float] = {}
    for field in needed:
        pattern = PATTERNS.get(field)
        if not pattern:
            continue
        m = re.search(pattern, text)
        if m:
            try:
                found[field] = float(m.group(1))
            except ValueError:
                pass
    return found

# -------------------------------------------------------------------#
#    HÀM CHÍNH: SLOT-FILLING ĐA LƯỢT & TOOL CALL (CÓ RESET KHI TỪ KHÓA KHÔNG PHÙ HỢP)
# -------------------------------------------------------------------#
def process_function_call(query: str, llm_with_tools, tools: List[Any], memory: Dict[str, Any]) -> str:
    """
    Xử lý slot-filling đa lượt và gọi tool phù hợp.

    memory lưu:
      - pending_tool: tên tool đang chờ bổ sung
      - args: dict các tham số đã trích được
      - missing: Set[str] các tham số đang chờ
    """
    lower = query.lower()
    args: Dict[str, Any] = {}

    # Nếu đang chờ bổ sung nhưng user đổi topic không chứa bất kỳ missing field nào -> reset
    if memory.get("pending_tool") and memory.get("missing"):
        missing_prev: Set[str] = set(memory["missing"])
        # kiểm tra query có pattern của missing_prev không
        found_any = False
        for field in missing_prev:
            pat = PATTERNS.get(field)
            if pat and re.search(pat, lower):
                found_any = True
                break
        if not found_any:
            memory.clear()

    # 1️⃣ Lấy tool_name & args ban đầu
    if memory.get("pending_tool"):
        tool_name = memory["pending_tool"]
        args = memory.get("args", {})
    else:
        tool_name = None
        # 1a) nhận diện nhanh qua từ khóa
        for key, name in DIRECT_TOOLS.items():
            if key in lower:
                tool_name = name
                break
        # 1b) nếu không nhận diện -> nhờ LLM
        if not tool_name:
            sys_prompt = "Bạn là chatbot tính toán điểm tuyển sinh. Nhận diện tool và trích args."
            msgs = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
            resp = llm_with_tools.invoke(msgs)
            if resp.tool_calls:
                tc = resp.tool_calls[0]
                tool_name = tc["name"]
                args = tc.get("args", {})
            else:
                return "Xin lỗi, mình chưa xác định được phép tính bạn cần."
        # reset trạng thái cũ
        memory.clear()

    # 2️⃣ Tìm tool object
    tool = next((t for t in tools if t.name == tool_name), None)
    if not tool:
        return f"Không tìm thấy tool {tool_name}."

    # 3️⃣ Xác định tham số bắt buộc
    sig = inspect.signature(tool.func)
    required: Set[str] = {param for param, p in sig.parameters.items() if p.default is inspect._empty}

    # 4️⃣ Extract missing qua regex
    missing = required - set(args.keys())
    extra = _extract_with_regex(query, missing)
    args.update(extra)
    missing -= set(extra.keys())

    # 5️⃣ Nếu thiếu -> hỏi user, lưu lại missing
    if missing:
        memory["pending_tool"] = tool_name
        memory["args"] = args
        memory["missing"] = list(missing)
        descs = [DESCRIPTIONS.get(p, p) for p in missing]
        return f"Bạn có thể cung cấp thêm {', '.join(descs)} cho mình được không?"

    # 6️⃣ Đủ tham số -> gọi tool
    try:
        result = tool.func(**args)
    except Exception as e:
        memory.clear()
        return f"Lỗi khi gọi tool: {e}"
    memory.clear()

    # 7️⃣ Trả kết quả format
    if tool_name == "calculate_admission_score":
        return f"✅ Điểm xét tuyển: {result['admission_score']}"
    if tool_name == "calculate_academic_score":
        return f"✅ Điểm học lực: {result['academic_score']}"
    if tool_name == "calculate_nang_luc":
        return f"✅ Điểm năng lực: {result['nang_luc_score']}"
    if tool_name == "calculate_thpt_test_converted":
        return f"✅ Điểm thi THPT quy đổi: {result['thpt_test_converted']}"
    if tool_name == "calculate_hocba_converted":
        return f"✅ Điểm học bạ quy đổi: {result['hocba_converted']}"
    if tool_name == "calculate_bonus":
        return f"✅ Điểm cộng: {result['bonus']}"
    if tool_name == "calculate_priority":
        return f"✅ Điểm ưu tiên: {result['priority']}"

    return str(result)

# Prompt template cho intent classification
intent_prompt_template = """
Bạn là một chatbot hỗ trợ tư vấn tuyển sinh. Phân loại ý định (intent) của câu hỏi sau thành một trong ba loại:
- `auto_chunk`: Câu hỏi liên quan đến thông tin từ PDF, như quy định, quy trình xét tuyển.
- `manual_chunk`: Câu hỏi liên quan đến thông tin từ danh sách Excel, như tiêu chí, danh mục cụ thể.
- `calculate_score`: Câu hỏi yêu cầu tính điểm xét tuyển hoặc các điểm thành phần (như điểm năng lực, học bạ, ưu tiên).

Câu hỏi: "{query}"

**Output**:
Chỉ trả về tên intent (`auto_chunk`, `manual_chunk`, hoặc `calculate_score`). Không giải thích.
"""
# Gắn tools vào model
llm_with_tools = llm.bind_tools(tools)
def classify_intent(query: str) -> str:
    # Tạo nội dung message theo định dạng chuẩn của langchain
    prompt = intent_prompt_template.format(query=query)
    messages = [HumanMessage(content=prompt)]

    # Gọi mô hình
    response = llm_with_tools.invoke(messages)

    # Truy cập nội dung từ response (dùng .content vì response là AIMessage)
    if isinstance(response, AIMessage) and response.content:
        return response.content.strip()
    return "unknown"

def process_query(query: str, llm_model, memory: Dict[str, Any] = None) -> str:
    if memory is None:
        memory = {}

    # 1. Phân loại intent
    intent = classify_intent(query)

    # 2. Xử lý theo intent
    if intent == "auto_chunk":
        # Hybrid search cho PDF
        top_contexts = hybrid_retrieve(query, source="pdf")
        if top_contexts:
            context_str = "\n\n---\n\n".join(top_contexts)
            msgs = [
                SystemMessage(content='''Bạn là chuyên viên tư vấn tuyển sinh của bộ môn toán trường đại học bách khoa thành phố hồ chí minh.
Nhiệm vụ của bạn là thu hút tuyển sinh cho ngành Khoa học dữ liệu của bộ môn toán.

**Bạn tuân thủ những qui định sau**:
- sử dụng thông tin trong context để trả lời
- Bạn chỉ hỗ trợ trả lời cho ngành Khoa học Dữ liệu. Khi được hỏi về ngành khác thì từ chối trả lời.
- Trả lời ngắn gọn, dễ quan sát, không chào hỏi hay cảm ơn.
- Phong cách trả lời thân thiện, vui vẻ và ấm áp.'''),
                HumanMessage(content=f"Context:\n{context_str}"),
                HumanMessage(content=f"Câu hỏi: {query}")
            ]
            result = llm_model.invoke(msgs)
            return result.content.strip()
        else:
            return "Không tìm thấy thông tin phù hợp trong PDF."

    elif intent == "manual_chunk":
        # Hybrid search cho Excel
        top_contexts = hybrid_retrieve(query, source="excel")
        if top_contexts:
            context_str = "\n\n---\n\n".join(top_contexts)
            msgs = [
                SystemMessage(content='''Bạn là chuyên viên tư vấn tuyển sinh của bộ môn toán trường đại học bách khoa thành phố hồ chí minh.
Nhiệm vụ của bạn là thu hút tuyển sinh cho ngành Khoa học dữ liệu của bộ môn toán.

**Bạn tuân thủ những qui định sau**:
- sử dụng thông tin trong context để trả lời
- Bạn chỉ hỗ trợ trả lời cho ngành Khoa học Dữ liệu. Khi được hỏi về ngành khác thì từ chối trả lời.
- Trả lời ngắn gọn, dễ quan sát, không chào hỏi hay cảm ơn.
- Phong cách trả lời thân thiện, vui vẻ và ấm áp.'''),
                HumanMessage(content=f"Context:\n{context_str}"),
                HumanMessage(content=f"Câu hỏi: {query}")
            ]
            result = llm_model.invoke(msgs)
            return result.content.strip()
        else:
            return "Không tìm thấy thông tin phù hợp trong Excel."

    elif intent == "calculate_score":
        return process_function_call(query, llm_model, tools, memory)

    else:
        return "Không hiểu câu hỏi. Vui lòng hỏi lại."
    
