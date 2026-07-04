        push_user(prompt)
        st.rerun()


# ============================================================================
# ITINERARY — destination-aware, rich cards, one-click PDF
# ============================================================================
elif page == "Itinerary":
    dest = st.session_state.current_destination
    it = get_itinerary(dest)

    head, action = st.columns([3, 1], vertical_alignment="center")
    with head:
        st.markdown(f"## 📍 {dest}")
        st.markdown(f'<p style="color:#94A3B8;margin-top:-.4rem">{it["month"]} · '
                    f'{len(it["days"])} days · group of {it["group"]} · budget '
                    f'{it["budget_label"]}</p>', unsafe_allow_html=True)
    with action:
        st.download_button("📄 Export PDF", data=itinerary_pdf(dest, it),
                           file_name=f"Horizon_{dest.split(',')[0]}.pdf",
                           mime="application/pdf", width="stretch")

    evidence_block(*it["overall"], key="it-overall")
    rule()

    total_walk = sum(d["walk"] for d in it["days"])
    total_cost = sum(s["cost"] or 0 for d in it["days"] for s in d["segments"])
    n_stops = sum(len(d["segments"]) for d in it["days"])
    fallbacks = sum(1 for d in it["days"] for s in d["segments"] if s["alt"])
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat(f"{total_walk:.0f} km", "total walking")
    with c2:
        stat(f"{it['currency']}{total_cost:,}" if total_cost else "—", "planned spend")
    with c3:
        stat(str(n_stops), "planned stops")
    with c4:
        stat(str(fallbacks), "fallbacks ready")

    for day in it["days"]:
        st.markdown(
            f"""<div class="hz-day"><span class="n">Day {day['n']}</span>
                  <span class="t">{day['date']} · {html.escape(day['theme'])}</span>
                  <span class="w">{day['weather']} · {day['walk']:.1f} km on foot</span>
                </div>""", unsafe_allow_html=True)
        for k, s in enumerate(day["segments"]):
            segment_card(s, it["currency"], key=f"d{day['n']}s{k}")


# ============================================================================
# TRAVEL DNA — radar + preferences + learning feed (PRD §2.2)
# ============================================================================
elif page == "Travel DNA":
    st.markdown("## 🧬 Your Travel DNA")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem">What Horizon has learned about '
                "how you travel — refined after every interaction, private by default.</p>",
                unsafe_allow_html=True)
    rule()

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.plotly_chart(dna_radar(), width="stretch", config={"displayModeBar": False})
        st.markdown('<div class="hz-kicker" style="text-align:center">each axis 0–100 · '
                    "hover for values · shaped by 4 completed trips</div>",
                    unsafe_allow_html=True)
    with right:
        st.markdown("#### Learned preferences")
        for kicker, value in DNA_PREFS:
            st.markdown(
                f'<div class="hz-card" style="padding:.75rem 1.05rem">'
                f'<div class="hz-kicker">{kicker}</div>'
                f'<div style="font-weight:500">{html.escape(value)}</div></div>',
                unsafe_allow_html=True)

    rule()
    st.markdown("#### Recent learning")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem;font-size:.9rem">The DNALearner '
                "agent explains every change it makes — nothing shifts silently.</p>",
                unsafe_allow_html=True)
    for ts, dim, change, trigger in DNA_EVENTS:
        st.markdown(
            f"""<div class="hz-card" style="padding:.8rem 1.05rem">
                  <div class="hz-kicker">{ts} · {dim}</div>
                  <div style="font-family:'Spline Sans Mono',monospace;color:#FFB800;
                              font-size:.9rem;margin:.2rem 0">{change}</div>
                  <div class="hz-body">{html.escape(trigger)}</div>
                </div>""", unsafe_allow_html=True)


# ============================================================================
# EXPLORE — Top 10, offline art, wired to itinerary
# ============================================================================
elif page == "Explore":
    st.markdown("## ✨ Top 10 Destinations")
    st.markdown('<p style="color:#94A3B8;margin-top:-.4rem">Ranked against your Travel DNA — '
                "with the reason for every score, not just the number.</p>",
                unsafe_allow_html=True)
    rule()

    cols = st.columns(2, gap="medium")
    for i, d in enumerate(DESTINATIONS):
        with cols[i % 2]:
            st.markdown(
                f"""<div class="hz-card hz-dest">
                      <img src="{scene_svg(d['c'][0], d['c'][1], d['emoji'])}" alt="">
                      <div class="inner">
                        <div style="display:flex;justify-content:space-between;align-items:baseline">
                          <div class="hz-title">{html.escape(d['name'])}</div>
                          <span class="match">{d['match']}% match</span>
                        </div>
                        <div class="hz-body">{html.escape(d['desc'])}</div>
                        <div class="hz-meta">
                          <span class="hz-chip">📅 <b>{d['months']}</b></span>
                          <span class="hz-chip">💰 <b>{d['budget']}</b></span>
                        </div>
                        <div class="why">{html.escape(d['why'])}</div>
                      </div>
                    </div>""", unsafe_allow_html=True)
            if st.button(f"🌟 Plan {d['name'].split(',')[0]}", key=f"plan_{i}",
                         width="stretch"):
                st.session_state.current_destination = d["name"]
                set_page("Itinerary")

st.caption("Horizon Travel AI • Capstone Demo")
