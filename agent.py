from typing import Any, Optional, TypedDict, List, Dict
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig

load_dotenv()

class AgentState(TypedDict):
    question: str
    df_info: str
    code: str
    result: Any
    error: Optional[str]
    retry_count: int
    explanation: str
    chart_generated: bool
    history: List[Dict[str, Any]]

def generate_code(state: AgentState, config: RunnableConfig):
    question = state["question"]
    df_info = state["df_info"]
    retry_count = state.get("retry_count", 0)
    error = state.get("error")
    code = state.get("code", "")
    
    # If the state has an error, we are in a retry step
    if error is not None:
        retry_count += 1
        
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
    
    if retry_count > 0:
        system_message = (
            "You are an expert Python data analyst agent. You write python pandas code to answer data questions.\n"
            "You have access to a pandas DataFrame named `df`.\n"
            "Your previous code attempt failed with an error. Review the error, analyze the DataFrame structure, "
            "and output corrected Python code that fixes the issue.\n\n"
            "Rules:\n"
            "1. You must assign the final answer to a variable called `result` (e.g., `result = df['column'].sum()`).\n"
            "2. If the question requires plotting, visualization, or trends, create a matplotlib chart and save it as 'chart.png' using `plt.savefig('chart.png')`. Do NOT call `plt.show()`.\n"
            "3. Do not import pandas or redefine the `df` variable.\n"
            "4. Output ONLY the raw Python code. Do NOT wrap it in markdown codeblocks (such as ```python) or provide explanations. Output only plain text python code."
        )
        user_message = (
            f"DataFrame Schema & Head:\n{df_info}\n\n"
            f"User Question: {question}\n\n"
            f"Previous Code Attempt:\n{code}\n\n"
            f"Error Message Received:\n{error}\n\n"
            f"Please fix the code and output the corrected version."
        )
    else:
        system_message = (
            "You are an expert Python data analyst agent. You write python pandas code to answer data questions.\n"
            "You have access to a pandas DataFrame named `df`.\n\n"
            "Rules:\n"
            "1. You must assign the final answer to a variable called `result` (e.g., `result = df['column'].sum()`).\n"
            "2. If the question requires plotting, visualization, or trends, create a matplotlib chart and save it as 'chart.png' using `plt.savefig('chart.png')`. Do NOT call `plt.show()`.\n"
            "3. Do not import pandas or redefine the `df` variable.\n"
            "4. Output ONLY the raw Python code. Do NOT wrap it in markdown codeblocks (such as ```python) or provide explanations. Output only plain text python code."
        )
        user_message = (
            f"DataFrame Schema & Head:\n{df_info}\n\n"
            f"User Question: {question}\n\n"
            f"Please generate the Python code."
        )
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])
    
    response = llm.invoke(prompt.format_messages())
    raw_code = response.content.strip()
    
    # Strip markdown codeblock backticks if present
    cleaned_code = raw_code
    if cleaned_code.startswith("```"):
        lines = cleaned_code.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned_code = "\n".join(lines).strip()
        
    return {
        "code": cleaned_code,
        "retry_count": retry_count,
        "error": None  # Reset error so execute_code starts fresh
    }

def execute_code(state: AgentState, config: RunnableConfig):
    code = state.get("code", "").strip()
    df = config.get("configurable", {}).get("df")
    
    if df is None:
        return {
            "error": "DataFrame is not available in configuration.",
            "result": None,
            "chart_generated": False
        }
        
    # Remove existing chart.png to avoid false positives from previous runs
    if os.path.exists("chart.png"):
        try:
            os.remove("chart.png")
        except Exception:
            pass
            
    # Reset matplotlib plot state
    plt.close('all')
    
    # Create the restricted execution environment
    local_vars = {
        'df': df,
        'pd': pd,
        'plt': plt,
        'os': os
    }
    
    # SAFETY NOTE: exec() is used here for a learning project. In production, 
    # this code execution should run in a sandboxed environment (e.g., Docker, 
    # restricted subprocess, WASM sandbox) to prevent arbitrary code execution 
    # on the server hosting the Streamlit app.
    
    error = None
    result = None
    
    try:
        # Run the code
        exec(code, {}, local_vars)
        
        # Verify the result variable is present
        if 'result' in local_vars:
            result = local_vars['result']
        else:
            error = (
                "Code executed successfully, but you did not store the final answer in "
                "the `result` variable as instructed. Please assign your final answer "
                "to `result = ...`."
            )
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}"
        
    # Check if a chart was generated
    chart_generated = os.path.exists("chart.png")
    
    # Maintain execution history
    history = state.get("history", []) or []
    history.append({
        "code": code,
        "error": error,
        "retry_count": state.get("retry_count", 0),
        "success": error is None
    })
    
    return {
        "result": result,
        "error": error,
        "chart_generated": chart_generated,
        "history": history
    }

def explain_result(state: AgentState, config: RunnableConfig):
    question = state["question"]
    result = state["result"]
    df_info = state["df_info"]
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
    
    system_message = (
        "You are a helpful and polite data analyst assistant.\n"
        "Explain the answer to the user's question based on the query result.\n"
        "Provide your explanation in 2-3 plain English sentences suitable for a non-technical user.\n"
        "Directly answer their question. Do not mention python variables, code, or pandas."
    )
    user_message = (
        f"DataFrame Information:\n{df_info}\n\n"
        f"User Question: {question}\n\n"
        f"Execution Result: {result}\n\n"
        f"Please write the explanation."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])
    
    response = llm.invoke(prompt.format_messages())
    return {
        "explanation": response.content.strip()
    }

def explain_failure(state: AgentState, config: RunnableConfig):
    question = state["question"]
    error = state["error"]
    code = state["code"]
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
    
    system_message = (
        "You are a helpful and polite data analyst assistant.\n"
        "Explain to the user in 2-3 friendly sentences that you attempted to answer their question "
        "but encountered persistent errors. Explain what the error means in plain English, and apologize "
        "for the failure."
    )
    user_message = (
        f"User Question: {question}\n\n"
        f"Last Code Attempted:\n{code}\n\n"
        f"Error Encountered: {error}\n\n"
        f"Please explain the failure in plain English."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])
    
    response = llm.invoke(prompt.format_messages())
    return {
        "explanation": response.content.strip()
    }

def check_result(state: AgentState):
    error = state.get("error")
    retry_count = state.get("retry_count", 0)
    
    if error is not None:
        if retry_count < 3:
            return "generate_code"
        else:
            return "explain_failure"
    return "explain_result"

# Define LangGraph StateGraph
builder = StateGraph(AgentState)

builder.add_node("generate_code", generate_code)
builder.add_node("execute_code", execute_code)
builder.add_node("explain_result", explain_result)
builder.add_node("explain_failure", explain_failure)

builder.add_edge(START, "generate_code")
builder.add_edge("generate_code", "execute_code")

builder.add_conditional_edges(
    "execute_code",
    check_result,
    {
        "generate_code": "generate_code",
        "explain_result": "explain_result",
        "explain_failure": "explain_failure"
    }
)

builder.add_edge("explain_result", END)
builder.add_edge("explain_failure", END)

graph = builder.compile()
