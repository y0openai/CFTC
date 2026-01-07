
import streamlit as st
import streamlit.components.v1 as components
import html

def render_ai_cards(phases):
    """
    Renders the AI Narrative cards using Streamlit Components (HTML/CSS/JS).
    """
    st.markdown(f"### 🍷 헤지펀드 전략가의 회고록")
    
    cards_html_inner = ""
    for p in phases:
        # Safe HTML Construction
        safe_title = html.escape(p['title'])
        safe_period = html.escape(p['period'])
        safe_narrative = html.escape(p['narrative']).replace("\n", "<br>")
        
        cards_html_inner += f"""
        <div class="card">
            <div class="card-header">{safe_title}</div>
            <div class="card-date">🗓️ {safe_period}</div>
            <div class="card-body">{safe_narrative}</div>
        </div>
        """
    
    # Complete HTML with CSS & JS for Buttons
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ background-color: transparent; margin: 0; font-family: sans-serif; }}
        .wrapper {{ position: relative; width: 100%; }}
        .container {{
            display: flex;
            overflow-x: auto;
            gap: 15px;
            padding: 10px 5px;
            scroll-behavior: smooth;
            scrollbar-width: thin;
            scrollbar-color: #555 transparent;
        }}
        .container::-webkit-scrollbar {{ height: 8px; }}
        .container::-webkit-scrollbar-track {{ background: transparent; }}
        .container::-webkit-scrollbar-thumb {{ background-color: #555; border-radius: 4px; }}
        
        .card {{
            min-width: 300px;
            max-width: 300px;
            height: 400px;
            background-color: #262730;
            border: 1px solid #454545;
            border-radius: 12px;
            padding: 20px;
            flex-shrink: 0;
            color: white;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .card-header {{ font-weight: bold; font-size: 1.1em; margin-bottom: 10px; color: #FFD700; }}
        .card-date {{ font-size: 0.8em; color: #ccc; margin-bottom: 15px; border-bottom: 1px solid #555; padding-bottom: 8px; }}
        .card-body {{ font-size: 0.95em; line-height: 1.6; color: #e0e0e0; overflow-y: auto; flex-grow: 1; }}
        .card-body::-webkit-scrollbar {{ width: 6px; }}
        .card-body::-webkit-scrollbar-thumb {{ background-color: #666; border-radius: 3px; }}

        .btn {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background-color: rgba(0,0,0,0.6);
            color: white;
            border: none;
            border-radius: 50%;
            width: 45px;
            height: 45px;
            font-size: 24px;
            cursor: pointer;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.2s;
        }}
        .btn:hover {{ background-color: rgba(255, 189, 69, 0.8); color: black; }}
        .prev {{ left: 0; }}
        .next {{ right: 0; }}
    </style>
    </head>
    <body>
        <div class="wrapper">
            <button class="btn prev" onclick="document.getElementById('scroll-container').scrollLeft -= 320;">&#10094;</button>
            <div id="scroll-container" class="container">
                {cards_html_inner}
            </div>
            <button class="btn next" onclick="document.getElementById('scroll-container').scrollLeft += 320;">&#10095;</button>
        </div>
    </body>
    </html>
    """
    
    components.html(full_html, height=450)
