import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF

st.set_page_config(page_title="Horizon • Travel AI", page_icon="🌊", layout="wide")

st.markdown("""
<style>
    .main-header { font-family: 'Playfair Display', serif; color: #FF6B6B; text-align: center; }
    .destination-card { background: white; border-radius: 20px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.3s; }
    .destination-card:hover { transform: scale(1.03); }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://via.placeholder.com/180x180/FF6B6B/FFFFFF?text=🌊", width=150)
    st.title("Horizon")
    st.caption("Your Intelligent Travel Companion")
    page = st.radio("Navigate", ["Home", "Chat", "Itinerary", "Travel DNA", "Explore"])

def generate_mock_itinerary(dest="Kyoto"):
    return [
        {"day":1, "title":f"Arrival in {dest}", "activity":"Airport → Hotel + Evening Walk", "walking":"3.2 km", "confidence":95},
        {"day":2, "title":"Cultural Highlights", "activity":"Temples & Shrines", "walking":"6.5 km", "confidence":92},
        {"day":3, "title":"Nature Day", "activity":"Bamboo Forest", "walking":"5.8 km", "confidence":89}
    ]

if page == "Home":
    st.markdown("<h1 class='main-header'>Welcome to Horizon, Hirak! 🌴</h1>", unsafe_allow_html=True)
    st.image("https://picsum.photos/id/1015/1200/500", use_column_width=True)
    st.subheader("Your Next Trip Suggestion: Kyoto, Japan • October 2026")

elif page == "Chat":
    st.title("💬 Chat with Horizon")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi Hirak! How can I help plan your next adventure?"}]
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    if prompt := st.chat_input("Describe your dream trip..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            st.write("Planning using your Travel DNA...")

elif page == "Itinerary":
    st.title("📍 Your Interactive Itinerary")
    itinerary = generate_mock_itinerary()
    for day in itinerary:
        st.info(f"**Day {day['day']}**: {day['activity']} ({day['walking']}) — Confidence: {day['confidence']}%")
    if st.button("📄 Export as PDF", type="primary"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=16)
        pdf.cell(200, 10, txt="Horizon Itinerary - Kyoto", ln=True, align='C')
        for day in itinerary:
            pdf.cell(200, 10, txt=f"Day {day['day']}: {day['activity']}", ln=True)
        pdf.output("itinerary.pdf")
        with open("itinerary.pdf", "rb") as f:
            st.download_button("Download PDF", f, file_name="Horizon_Itinerary.pdf", mime="application/pdf")

elif page == "Travel DNA":
    st.title("🧬 Your Travel DNA")
    col1, col2 = st.columns(2)
    with col1:
        categories = ['Adventure','Culture','Food','Photography','Relax','Walking']
        values = [72,94,88,95,68,81]
        fig = go.Figure(go.Scatterpolar(r=values+[values[0]], theta=categories+[categories[0]], fill='toself', line_color='#FF6B6B'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Explore":
    st.title("✨ Top 10 International Destinations")
    destinations = [
        ("Kyoto, Japan", "Temples & Cherry Blossoms", "97%"),
        ("Bali, Indonesia", "Beaches & Culture", "92%"),
        ("Paris, France", "Art & Romance", "88%"),
        ("Santorini, Greece", "Sunsets", "91%"),
        ("Swiss Alps", "Mountains", "85%"),
        ("Marrakech, Morocco", "Markets", "79%"),
        ("Banff, Canada", "Lakes", "82%"),
        ("Barcelona, Spain", "Architecture", "87%"),
        ("Queenstown, New Zealand", "Adventure", "76%"),
        ("Dubai, UAE", "Luxury", "81%")
    ]
    cols = st.columns(2)
    for i, (name, desc, match) in enumerate(destinations):
        with cols[i % 2]:
            st.image(f"https://picsum.photos/id/10{i+1}/400/220", use_column_width=True)
            st.subheader(name)
            st.write(desc)
            st.success(f"DNA Match: {match}")
            if st.button(f"Plan Trip to {name.split(',')[0]}", key=f"plan_{i}"):
                st.success(f"Creating itinerary for {name}...")

st.caption("Horizon Travel AI • Capstone Demo")
