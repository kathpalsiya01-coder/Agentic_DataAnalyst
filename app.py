import streamlit as st
import pandas as pd
import numpy as np
import os
import io
from dotenv import load_dotenv

# Set page config FIRST
st.set_page_config(
    page_title="Agentic Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

from agent import graph

load_dotenv()

# Ensure sample data folder and file exists
def ensure_sample_data():
    os.makedirs("sample_data", exist_ok=True)
    sample_path = os.path.join("sample_data", "sales_data.csv")
    if not os.path.exists(sample_path):
        # Generate high-quality sample sales data
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
        products = ["Laptop", "Smartphone", "Tablet", "Headphones", "Smartwatch"]
        categories = ["Electronics", "Electronics", "Electronics", "Accessories", "Accessories"]
        regions = ["North", "South", "East", "West"]
        
        data = {
            "Date": np.random.choice(dates, 100).astype(str),
            "Product": np.random.choice(products, 100),
            "Price": np.random.choice([999.99, 699.99, 399.99, 149.99, 249.99], 100),
            "Quantity": np.random.randint(1, 10, 100),
            "Region": np.random.choice(regions, 100)
        }
        
        df = pd.DataFrame(data)
        df["Revenue"] = df["Price"] * df["Quantity"]
        prod_cat = dict(zip(products, categories))
        df["Category"] = df["Product"].map(prod_cat)
        
        df = df.sort_values("Date").reset_index(drop=True)
        df.to_csv(sample_path, index=False)
    return sample_path

# Custom CSS for rich aesthetics
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Outfit', sans-serif;
    }
    
    .title-container {
        padding: 1rem 0rem;
        margin-bottom: 1.5rem;
    }
    
    .main-title {
        font-size: 2.75rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4F46E5, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: #64748B;
    }
    
    .preset-title {
        font-weight: 600;
        color: #475569;
        margin-bottom: 0.5rem;
    }
    
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #4F46E5 0%, #3B82F6 100%);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown("""
<div class="title-container">
    <h1 class="main-title">📊 Agentic Data Analyst</h1>
    <p class="subtitle">Upload a CSV file and ask questions. The AI agent will generate, execute, and self-correct pandas code in real-time.</p>
</div>
""", unsafe_allow_html=True)

# Initialize Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "preset_question" not in st.session_state:
    st.session_state.preset_question = ""

# Sidebar Configuration
st.sidebar.image("https://img.icons8.com/color/96/artificial-intelligence.png", width=80)
st.sidebar.markdown("### Settings & Data")

# API Key handling
api_key = os.getenv("GROQ_API_KEY", "")
if not api_key:
    api_key_input = st.sidebar.text_input("🔑 Groq API Key", type="password", help="Enter your Groq API key here. You can get one from the Groq console.")
    if api_key_input:
        os.environ["GROQ_API_KEY"] = api_key_input
        api_key = api_key_input
        st.sidebar.success("API Key applied!")
else:
    st.sidebar.success("✅ Groq API Key loaded")

# Data File Uploader
uploaded_file = st.sidebar.file_uploader("📂 Upload CSV File", type=["csv"])

df = None
data_source = ""

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        data_source = uploaded_file.name
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")
else:
    # Option to load sample data
    st.sidebar.info("No file uploaded. You can load sample data to test.")
    if st.sidebar.button("💡 Load Sample Sales CSV"):
        sample_file_path = ensure_sample_data()
        df = pd.read_csv(sample_file_path)
        data_source = "sales_data.csv"
        st.sidebar.success("Sample sales data loaded!")

# If DataFrame is loaded, show metadata in the sidebar
if df is not None:
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"🗃️ **Dataset:** `{data_source}`")
    st.sidebar.markdown(f"📏 **Dimensions:** `{df.shape[0]}` rows, `{df.shape[1]}` columns")
    
    with st.sidebar.expander("🔍 Columns & Data Types"):
        dtypes_df = pd.DataFrame(df.dtypes, columns=["Data Type"]).astype(str)
        st.dataframe(dtypes_df)
        
    with st.sidebar.expander("👀 Preview Data (Top 5 rows)"):
        st.dataframe(df.head(5))

# Main Screen Flow
if df is not None:
    if not api_key:
        st.warning("⚠️ Please configure your **Groq API Key** in the sidebar to start asking questions.")
    else:
        # Presets questions
        st.markdown('<p class="preset-title">💡 Try one of these sample questions:</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
           if st.button("📊 Show basic statistics", use_container_width=True):
             st.session_state.preset_question = "Show me the basic statistics of this dataset including count, mean, min and max for all numerical columns."

        with col2:
           if st.button("🔍 Find missing values", use_container_width=True):
             st.session_state.preset_question = "Which columns have missing values and how many? Show the count of missing values for each column."

        with col3:
          if st.button("📈 Show data distribution", use_container_width=True):
            st.session_state.preset_question = "Show me a bar chart of the most frequent values in the first categorical column of this dataset."

        # Question input form
        # Sync preset question if clicked
        if st.session_state.preset_question:
            st.session_state.question_input = st.session_state.preset_question
            st.session_state.preset_question = "" # Clear after syncing
            
        with st.form("query_form", clear_on_submit=False):
            # Create text input that reads/writes to st.session_state
            if "question_input" not in st.session_state:
                st.session_state.question_input = ""
            user_question = st.text_input("Ask a question about the dataset:", key="question_input")
            submit_button = st.form_submit_button("Run Agentic Analysis")

        # Execute analysis on submit
        if submit_button and user_question:
            # Prepare state
            df_info_str = (
                f"Columns & Types:\n{df.dtypes.to_string()}\n\n"
                f"Head:\n{df.head(3).to_string()}"
            )
            
            initial_state = {
                "question": user_question,
                "df_info": df_info_str,
                "code": "",
                "result": None,
                "error": None,
                "retry_count": 0,
                "explanation": "",
                "chart_generated": False,
                "history": []
            }
            
            # Spin up the agent execution
            with st.spinner("🤖 Agent is analyzing the dataset, writing, and executing code..."):
                try:
                    # Run compiled LangGraph graph
                    config = {"configurable": {"df": df}}
                    final_state = graph.invoke(initial_state, config)
                    
                    # Read chart if one was generated
                    chart_bytes = None
                    if final_state.get("chart_generated") and os.path.exists("chart.png"):
                        with open("chart.png", "rb") as f:
                            chart_bytes = f.read()
                        # Clean up chart.png so it doesn't persist across queries
                        try:
                            os.remove("chart.png")
                        except Exception:
                            pass
                            
                    # Save results to session state chat history
                    chat_item = {
                        "question": user_question,
                        "explanation": final_state.get("explanation", "No explanation generated."),
                        "result": final_state.get("result"),
                        "history": final_state.get("history", []),
                        "chart_bytes": chart_bytes,
                        "success": final_state.get("error") is None
                    }
                    st.session_state.chat_history.append(chat_item)
                except Exception as ex:
                    st.error(f"An error occurred during agent execution: {ex}")
                    
        # Render Chat History (Newest at the top)
        if st.session_state.chat_history:
            st.markdown("### 💬 Analysis History")
            for idx, item in enumerate(reversed(st.session_state.chat_history)):
                with st.container(border=True):
                    # Question Header
                    st.markdown(f"#### 🔍 Question: {item['question']}")
                    
                    # Status Indicator
                    if item["success"]:
                        st.markdown("🟢 **Success**")
                    else:
                        st.markdown("🔴 **Failed after maximum retries**")
                    
                    # Plain English Explanation
                    st.info(item["explanation"])
                    
                    # Result Display
                    if item["result"] is not None:
                        st.markdown("**Executed Code Output:**")
                        if isinstance(item["result"], (pd.DataFrame, pd.Series)):
                            st.dataframe(item["result"], use_container_width=True)
                        else:
                            st.markdown(f"```text\n{item['result']}\n```")
                            
                    # Chart Display
                    if item["chart_bytes"] is not None:
                        st.image(item["chart_bytes"], caption="Generated Chart", use_container_width=True)
                        
                    # Code Logs Expander
                    logs_label = f"🛠️ Code Execution History ({len(item['history'])} attempts)"
                    with st.expander(logs_label):
                        for i, attempt in enumerate(item["history"]):
                            st.markdown(f"##### Attempt {attempt['retry_count'] + 1}")
                            st.code(attempt["code"], language="python")
                            if attempt.get("error"):
                                st.error(f"Error details: {attempt['error']}")
                            else:
                                st.success("Execution completed successfully!")
else:
    # Welcome screen
    st.info("👋 Welcome! Please upload a CSV file in the sidebar, or click 'Load Sample Sales CSV' to test with mock data.")
    
    # Showcase layout for rich aesthetics
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### Features:
        - 🧠 **LangGraph Orchestrated Agent:** Integrates LLM code-generation and self-correction loops.
        - 🔄 **Self-Correction (Max 3 Retries):** Programmatic execution with real-time stack trace feedback to correct syntax/runtime errors.
        - 📊 **Smart Chart Generation:** Automatically outputs matplotlib charts for visual queries.
        - 🔐 **Restricted Namespace Exec:** Executes queries in a controlled namespace.
        """)
    with col2:
        st.image("https://img.icons8.com/color/384/dashboard.png", width=250)
