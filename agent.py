from openai import OpenAI
import database as db
import data_api as api
import json
import streamlit as st
import os

def get_portfolio_context():
    """Returns a JSON string of the current portfolio state."""
    holdings_df = db.get_all_holdings()
    if holdings_df.empty:
        return "The user's portfolio is currently empty."
    
    total_inv, curr_val, total_pl, total_pl_pct, enriched_df = api.get_portfolio_metrics(holdings_df)
    
    # Format data for the AI
    portfolio_data = {
        "summary": {
            "total_invested": round(float(total_inv), 2),
            "current_value": round(float(curr_val), 2),
            "total_profit_loss": round(float(total_pl), 2),
            "total_profit_loss_percentage": round(float(total_pl_pct), 2)
        },
        "holdings": []
    }
    
    for _, row in enriched_df.iterrows():
        portfolio_data["holdings"].append({
            "symbol": row['symbol'],
            "type": row['asset_type'],
            "average_buy_price": round(float(row['avg_price']), 2),
            "quantity": float(row['quantity']),
            "current_price": round(float(row['current_price']), 2),
            "current_value": round(float(row['current_value']), 2),
            "unrealized_profit_loss": round(float(row['unrealized_pl']), 2),
            "profit_loss_percentage": round(float(row['unrealized_pl_pct']), 2)
        })
        
    return json.dumps(portfolio_data, indent=2)

def get_groq_client():
    """Initialize Groq client using OpenAI compatible API."""
    # Check for GROQ_API_KEY in environment/secrets
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            pass
            
    if not api_key:
        return None
        
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

def generate_agent_response(user_query, chat_history):
    client = get_groq_client()
    if not client:
        return "I'm sorry, the Groq API key is not configured. Please set GROQ_API_KEY in your environment."
    
    # Get portfolio context
    portfolio_context = get_portfolio_context()
    
    system_prompt = f"""
    You are the 'Personal AI Financial Guardian', a helpful investment assistant for the Indian market.
    Your goal is to help the user manage their portfolio of Stocks, ETFs, and Mutual Funds.
    
    CURRENT PORTFOLIO DATA:
    {portfolio_context}
    
    INSTRUCTIONS:
    - Analyze the portfolio and answer user queries accurately.
    - Focus on Indian market context.
    - DO NOT give direct buy/sell recommendations or definitive financial advice.
    - Be professional, guardian-like, and data-driven.
    - If the portfolio is empty, encourage the user to add assets.
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    # Handle chat history format (list of dicts with role/content)
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_query})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # High performance Groq model
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error communicating with Groq: {str(e)}"
