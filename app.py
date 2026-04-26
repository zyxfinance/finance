import streamlit as st
from openai import OpenAI
import fitz
import re
from collections import Counter
import math

st.set_page_config(page_title="智能财报助手", layout="wide")
st.title("📊 智能财报助手 (简化版)")

# 你的 API Key
ZHIPU_API_KEY = "3864073eb9be4530a1098fdb1f7d9f0a.VIDvcob8Fn11OohP"
client = OpenAI(api_key=ZHIPU_API_KEY, base_url="https://open.bigmodel.cn/api/paas/v4")

# 简单的文本检索（TF-IDF 风格）
def simple_search(query, texts, top_n=3):
    # 分词
    query_words = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', query))
    scores = []
    for i, item in enumerate(texts):
        content = item["text"]
        content_words = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', content))
        # 计算共同词数量作为分数
        common = query_words & content_words
        score = len(common)
        scores.append((score, i))
    scores.sort(reverse=True)
    top_indices = [idx for score, idx in scores[:top_n] if score > 0]
    if not top_indices:
        top_indices = list(range(min(top_n, len(texts))))
    return [texts[i] for i in top_indices]

# 处理 PDF
def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    texts = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        # 按段落切分
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if len(para.strip()) > 50:
                texts.append({
                    "text": para.strip(),
                    "source": pdf_path,
                    "page": page_num + 1
                })
    return texts

# 界面
uploaded_file = st.sidebar.file_uploader("上传财报 PDF", type="pdf")

if uploaded_file:
    with open("temp_report.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.sidebar.success("✅ 已上传")
    
    with st.spinner("正在处理..."):
        texts = process_pdf("temp_report.pdf")
    st.sidebar.success(f"✅ 已处理 {len(texts)} 段")
    
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
            with st.spinner("搜索中..."):
                # 检索相关段落
                relevant = simple_search(prompt, texts)
                context = "\n\n".join([r["text"] for r in relevant])
                sources = [f"第{r['page']}页" for r in relevant]
                
                full_prompt = f"""请根据下面的财报内容回答问题。如果内容里没有，就说"没找到"。

财报内容：
{context[:3000]}

问题：{prompt}

回答："""
                
                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=0.1
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                if sources:
                    st.caption(f"📎 参考：{', '.join(sources)}")
            st.session_state.messages.append({"role": "assistant", "content": answer})
else:
    st.info("👈 上传财报 PDF")