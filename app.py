import streamlit as st
import fitz
import re
from openai import OpenAI

st.set_page_config(page_title="智能财报助手", layout="wide")
st.title("📊 智能财报助手 (RAG版)")

# ========== 请替换成你的真实 API Key ==========
ZHIPU_API_KEY = "3864073eb9be4530a1098fdb1f7d9f0a.VIDvcob8Fn11OohP"
# =============================================

client = OpenAI(api_key=ZHIPU_API_KEY, base_url="https://open.bigmodel.cn/api/paas/v4")

def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    texts = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        for para in text.split('\n\n'):
            if len(para.strip()) > 50:
                texts.append({"text": para.strip(), "page": page_num + 1})
    return texts

def extract_financial_data(texts):
    full_text = " ".join([t["text"] for t in texts])
    revenue = "--"
    profit = "--"
    
    rev_match = re.search(r"营业收入[^\d]*([\d,]+\.?\d*)", full_text)
    if rev_match:
        num = rev_match.group(1).replace(',', '')
        if len(num) > 8:
            revenue = f"{round(float(num)/100000000, 1)} 亿元"
        else:
            revenue = f"{num} 万元"
    
    profit_match = re.search(r"净利润[^\d]*([\d,]+\.?\d*)", full_text)
    if profit_match:
        num = profit_match.group(1).replace(',', '')
        if len(num) > 8:
            profit = f"{round(float(num)/100000000, 1)} 亿元"
        else:
            profit = f"{num} 万元"
    
    return revenue, profit

def search_relevant(query, texts, top_n=3):
    query_words = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', query))
    scores = []
    for i, item in enumerate(texts):
        content = item["text"]
        content_words = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', content))
        common = query_words & content_words
        score = len(common)
        scores.append((score, i))
    scores.sort(reverse=True)
    top_indices = [idx for score, idx in scores[:top_n] if score > 0]
    if not top_indices:
        top_indices = list(range(min(top_n, len(texts))))
    return [texts[i] for i in top_indices]

# ---------- 状态初始化 ----------
if 'revenue' not in st.session_state:
    st.session_state.revenue = "--"
    st.session_state.profit = "--"
if 'texts' not in st.session_state:
    st.session_state.texts = []
if 'need_rerun' not in st.session_state:
    st.session_state.need_rerun = False

# 如果需要刷新，执行一次无参数的刷新
if st.session_state.need_rerun:
    st.session_state.need_rerun = False
    st.rerun()

# ---------- 侧边栏 ----------
st.sidebar.markdown("## 📊 核心财务数据")
col1, col2 = st.sidebar.columns(2)
col1.metric("营业收入", st.session_state.revenue)
col2.metric("净利润", st.session_state.profit)

# ---------- 文件上传 ----------
uploaded_file = st.sidebar.file_uploader("上传财报 PDF", type="pdf")

if uploaded_file:
    # 只在第一次上传时处理
    if not st.session_state.texts:
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        with st.spinner("处理中..."):
            texts = process_pdf("temp.pdf")
        st.sidebar.success(f"✅ 已处理 {len(texts)} 段")
        
        revenue, profit = extract_financial_data(texts)
        st.session_state.revenue = revenue
        st.session_state.profit = profit
        st.session_state.texts = texts
        st.session_state.need_rerun = True
        st.rerun()
    else:
        st.sidebar.success(f"✅ 已使用已上传的财报（{len(st.session_state.texts)} 段）")

# ---------- 聊天区域 ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("请输入问题"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        if not st.session_state.texts:
            with st.spinner("思考中..."):
                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
        else:
            with st.spinner("检索财报中..."):
                relevant = search_relevant(prompt, st.session_state.texts, top_n=3)
                context = "\n\n".join([r["text"] for r in relevant])
                sources = [f"第{r['page']}页" for r in relevant]
                full_prompt = f"请根据以下财报内容回答问题：\n\n财报内容：{context}\n\n问题：{prompt}\n\n回答："
                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=0.1
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                if sources:
                    st.caption(f"📎 参考来源：{', '.join(sources)}")
    st.session_state.messages.append({"role": "assistant", "content": answer})