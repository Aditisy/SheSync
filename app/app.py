import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import time
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(
    page_title="SheSync — Your Period Companion",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.caption('Legacy Streamlit prototype. The updated SheSync website provides period history, exact-schema model inference and real service integrations.')
st.link_button('Open the updated SheSync website', 'http://localhost:5000')


st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #1a0a2e; }
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stRadio label { color: white !important; }

.hero-card {
    background: linear-gradient(135deg, #6a11cb 0%, #c850c0 100%);
    padding: 1.2rem 1.5rem; border-radius: 14px; text-align: center;
    color: white; margin: 6px;
}
.hero-card h2 { font-size: 2rem; margin: 0; }
.hero-card p  { font-size: 0.85rem; margin: 4px 0 0; opacity: 0.9; }

.info-box {
    background: #f0e8ff; border-left: 4px solid #6a11cb;
    padding: 0.75rem 1rem; border-radius: 0 8px 8px 0;
    margin: 8px 0; color: #1a0a2e;
}
.risk-high { background:#ff4757;color:white;padding:1.2rem;border-radius:12px;text-align:center; }
.risk-med  { background:#ffa502;color:white;padding:1.2rem;border-radius:12px;text-align:center; }
.risk-low  { background:#2ed573;color:white;padding:1.2rem;border-radius:12px;text-align:center; }

.log-card {
    background: #fff0f8; border: 1.5px solid #e91e8c;
    border-radius: 12px; padding: 1rem 1.2rem; margin: 6px 0;
}
.doctor-card {
    border: 1.5px solid #c850c0; border-radius: 12px;
    padding: 1rem; text-align: center; background: #fdf4ff;
    color: #1a0a2e;
}
.stage-btn {
    background: linear-gradient(135deg,#6a11cb,#c850c0);
    color: white; border: none; padding: 0.6rem 1.2rem;
    border-radius: 8px; font-size: 14px; cursor: pointer;
}
.phase-tag {
    display:inline-block; padding:4px 12px; border-radius:20px;
    font-size:13px; font-weight:600; margin:3px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ──────────────────────────────────────────────────
if "logs" not in st.session_state:
    st.session_state.logs = []
if "last_period" not in st.session_state:
    st.session_state.last_period = None
if "cycle_lengths" not in st.session_state:
    st.session_state.cycle_lengths = []

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌸 SheSync")
    st.markdown("*Your Period & Wellness Companion*")
    st.markdown("---")

    st.markdown("**Who are you?**")
    life_stage = st.selectbox("My life stage", [
        "I'm getting my first period (9–14)",
        "I'm a teenager (14–19)",
        "I'm in my 20s–30s",
        "I'm in my 40s+ (perimenopause)"
    ], label_visibility="collapsed")

    st.markdown("---")
    page = st.radio("Go to", [
        "🏠 Home",
        "📓 Daily Log",
        "📅 My Cycle",
        "🔬 PCOS Risk Check",
        "📡 Wearable Data",
        "👩‍⚕️ Find a Doctor",
        "🔔 Set Reminder"
    ])
    st.markdown("---")
    st.caption("SheSync v2.0 | GAT AIML 2025-26")
    st.caption("Not a replacement for medical advice.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE 1 — HOME
# ══════════════════════════════════════════════════════════════════════════
if page == "🏠 Home":
    st.title("🌸 Welcome to SheSync")
    st.markdown("*Your smart period and health companion — built for every woman, at every stage of life.*")
    st.markdown("---")

    # Life-stage personalised welcome
    if "first period" in life_stage:
        st.info("👋 Hi! Getting your first period can feel scary — but we're here to help you understand "
                "your body, stay prepared, and know what's normal.")
    elif "teenager" in life_stage:
        st.info("👋 Hi! Irregular periods are super common for teens. SheSync helps you track your cycle, "
                "understand your moods, and know when to talk to a doctor.")
    elif "40s" in life_stage:
        st.info("👋 Hi! Perimenopause can bring unpredictable changes. SheSync helps you track symptoms, "
                "understand your patterns, and prepare for what's ahead.")
    else:
        st.info("👋 Hi! SheSync helps you understand your unique cycle, detect irregularities early, "
                "and check your PCOS risk — all in one place.")

    st.markdown("---")

    # What SheSync does — simple language
    st.markdown("### What SheSync Does For You")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""
        <div class="hero-card">
        <h2>📓</h2>
        <p><strong>Daily Log</strong></p>
        <p>Tell us how you feel today — mood, pain, sleep. Takes 30 seconds.</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="hero-card">
        <h2>📅</h2>
        <p><strong>Cycle Tracking</strong></p>
        <p>We predict your next period based on YOUR cycle — not a fixed 28-day assumption.</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="hero-card">
        <h2>🔬</h2>
        <p><strong>PCOS Check</strong></p>
        <p>Answer a few simple questions. Our AI checks your PCOS risk based on 541 real cases.</p>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown("""
        <div class="hero-card">
        <h2>👩‍⚕️</h2>
        <p><strong>Find Doctors</strong></p>
        <p>Real gynaecologists in Bengaluru you can consult if needed.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # How it is different
    st.markdown("### Why SheSync is Different")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("""
        <div class="info-box">
        ❌ <strong>Other apps assume a 28-day cycle for everyone.</strong><br>
        ✅ <strong>SheSync learns YOUR cycle length</strong> — whether it's 21 days or 45 days, 
        irregular or regular. We predict based on your history, not a textbook.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="info-box">
        ❌ <strong>Other apps only track periods.</strong><br>
        ✅ <strong>SheSync tracks mood, sleep, pain, and symptoms daily</strong> — 
        so patterns emerge naturally over time without you needing to remember dates.
        </div>
        """, unsafe_allow_html=True)
    with d2:
        st.markdown("""
        <div class="info-box">
        ❌ <strong>PCOS is usually detected only after expensive tests.</strong><br>
        ✅ <strong>SheSync flags early risk signals</strong> using AI trained on real 
        data from 541 women across 10 hospitals in Kerala.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="info-box">
        ❌ <strong>No app supports women getting their first period or entering menopause.</strong><br>
        ✅ <strong>SheSync supports every stage</strong> — from first period anxiety 
        to perimenopause symptoms. You are never alone.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 About Our AI")
    st.markdown("""
    Our PCOS risk checker was trained on real health data. Here's what that means in simple terms:

    - **541 women** — real health records from 10 hospitals in Kerala were used to train our AI
    - **2 AI models** — we use two different algorithms and compare their answers for accuracy  
    - **83.4% accuracy** — our AI correctly identifies PCOS risk 83 times out of 100
    - **41 health signals** — the AI looks at 41 different things (like hormone levels, symptoms, lifestyle) to make a prediction

    👉 This doesn't replace a doctor — but it can tell you if you should see one.
    """)

# ══════════════════════════════════════════════════════════════════════════
# PAGE 2 — DAILY LOG
# ══════════════════════════════════════════════════════════════════════════
elif page == "📓 Daily Log":
    st.title("📓 Daily Log")
    st.markdown("Takes 30 seconds. Log how you feel today — no medical knowledge needed.")
    st.markdown("---")

    today = date.today()
    st.markdown(f"### Today: {today.strftime('%A, %d %B %Y')}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Did your period start or end today?**")
        period_status = st.selectbox("Period today?", [
            "No period today",
            "Period started today 🔴",
            "Period ended today",
            "Period is ongoing"
        ])

        st.markdown("**How heavy is the flow?**")
        flow = st.select_slider("Flow", ["None", "Light", "Medium", "Heavy", "Very Heavy"],
                                value="None")

        st.markdown("**Pain or cramps?**")
        pain = st.select_slider("Pain level", ["None", "Mild", "Moderate", "Severe"],
                                value="None")

        st.markdown("**How did you sleep last night?**")
        sleep = st.select_slider("Sleep quality", ["Very Poor", "Poor", "Okay", "Good", "Great"],
                                 value="Okay")

    with col2:
        st.markdown("**How is your mood today?**")
        mood = st.select_slider("Mood", [
            "😢 Very Low", "😔 Low", "😐 Neutral", "🙂 Good", "😄 Great"
        ], value="😐 Neutral")

        st.markdown("**Any symptoms today?** (tick all that apply)")
        sym_col1, sym_col2 = st.columns(2)
        with sym_col1:
            bloating = st.checkbox("Bloating")
            headache = st.checkbox("Headache")
            acne = st.checkbox("Acne / pimples")
            fatigue = st.checkbox("Fatigue / tiredness")
        with sym_col2:
            breast_pain = st.checkbox("Breast tenderness")
            back_pain = st.checkbox("Back pain")
            cravings = st.checkbox("Food cravings")
            anxiety = st.checkbox("Anxiety / stress")

        st.markdown("**Notes (optional)**")
        notes = st.text_area("Anything else to note?", placeholder="e.g. Stressed about exams, didn't eat well...",
                             height=80)

    st.markdown("---")
    if st.button("✅ Save Today's Log", use_container_width=True):
        log_entry = {
            "date": str(today),
            "period": period_status,
            "flow": flow,
            "pain": pain,
            "sleep": sleep,
            "mood": mood,
            "symptoms": [s for s, v in [("Bloating", bloating), ("Headache", headache),
                                          ("Acne", acne), ("Fatigue", fatigue),
                                          ("Breast tenderness", breast_pain), ("Back pain", back_pain),
                                          ("Food cravings", cravings), ("Anxiety", anxiety)] if v],
            "notes": notes
        }
        if "Period started" in period_status:
            st.session_state.last_period = str(today)
        st.session_state.logs.append(log_entry)
        st.success(f"✅ Log saved for {today.strftime('%d %B %Y')}! Come back tomorrow.")
        st.balloons()

    # Show recent logs
    if st.session_state.logs:
        st.markdown("---")
        st.markdown("### 📋 Your Recent Logs")
        for log in reversed(st.session_state.logs[-5:]):
            syms = ", ".join(log["symptoms"]) if log["symptoms"] else "None"
            st.markdown(f"""
            <div class="log-card">
            <strong>📅 {log['date']}</strong> &nbsp;|&nbsp;
            {log['period']} &nbsp;|&nbsp; Flow: {log['flow']} &nbsp;|&nbsp;
            Pain: {log['pain']} &nbsp;|&nbsp; Mood: {log['mood']}<br>
            <small>Symptoms: {syms}</small>
            {f"<br><small>📝 {log['notes']}</small>" if log['notes'] else ""}
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# PAGE 3 — MY CYCLE
# ══════════════════════════════════════════════════════════════════════════
elif page == "📅 My Cycle":
    st.title("📅 My Cycle")
    st.markdown("Tell us just what you remember — even one date is enough to get started.")
    st.markdown("---")

    st.markdown("### 📍 When did your last period start?")
    st.markdown("*(Just pick the approximate date — it's okay if you're not 100% sure)*")

    last_start = st.date_input("Last period start date",
                               value=date.today() - timedelta(days=14),
                               max_value=date.today())

    st.markdown("---")
    st.markdown("### ⏱️ How long does your period usually last?")
    period_duration = st.slider("Period duration (days)", 2, 10, 5,
                                help="How many days does your bleeding last?")

    st.markdown("---")
    st.markdown("### 📊 Add past period dates (optional — add as many as you remember)")
    st.markdown("*You don't need 6 months of data. Even 2-3 dates help us predict better.*")

    num_past = st.slider("How many past periods can you remember?", 0, 6, 1)
    past_dates = []
    if num_past > 0:
        cols = st.columns(min(num_past, 3))
        for i in range(num_past):
            with cols[i % 3]:
                d = st.date_input(f"Period {i+1} start",
                                  value=date.today() - timedelta(days=28*(i+1)),
                                  key=f"past_{i}")
                past_dates.append(d)

    if st.button("🔮 Predict My Next Period", use_container_width=True):
        # Calculate cycle length from available data
        all_dates = sorted([last_start] + past_dates, reverse=True)

        if len(all_dates) >= 2:
            diffs = [(all_dates[i] - all_dates[i+1]).days for i in range(len(all_dates)-1)]
            avg_cycle = int(np.mean(diffs))
            std_cycle = np.std(diffs)
        else:
            # Use life-stage defaults if only one date
            if "first period" in life_stage or "teenager" in life_stage:
                avg_cycle = 32  # teens often have longer cycles
            elif "40s" in life_stage:
                avg_cycle = 26  # perimenopause cycles shorten
            else:
                avg_cycle = 29
            std_cycle = 0

        next_period = last_start + timedelta(days=avg_cycle)
        fertile_start = last_start + timedelta(days=avg_cycle - 16)
        fertile_end = last_start + timedelta(days=avg_cycle - 10)
        days_until = (next_period - date.today()).days

        st.markdown("---")
        st.markdown("### 🌸 Your Personalised Cycle Prediction")

        m1, m2, m3 = st.columns(3)
        m1.metric("Your cycle length", f"{avg_cycle} days",
                  help="Based on YOUR data, not the 28-day assumption")
        m2.metric("Next period expected", next_period.strftime("%d %b %Y"))
        if days_until >= 0:
            m3.metric("Days from today", f"{days_until} days")
        else:
            m3.metric("Status", "Period may be here!")

        st.markdown("---")

        # Phase detection
        days_since = (date.today() - last_start).days
        current_phase = ""
        if days_since <= period_duration:
            current_phase = "🔴 Menstrual phase — your period is active"
            phase_tip = "Rest, use a heat pad for cramps, stay hydrated."
        elif days_since <= avg_cycle // 2 - 2:
            current_phase = "🌱 Follicular phase — energy is rising"
            phase_tip = "Great time to be active, try new things, and socialise!"
        elif days_since <= avg_cycle // 2 + 2:
            current_phase = "🥚 Ovulation — peak fertility window"
            phase_tip = "You may feel more confident and energetic. Fertile window is now."
        else:
            current_phase = "🌙 Luteal phase — pre-period time"
            phase_tip = "You may feel more tired or moody. Self-care is important now."

        st.info(f"**You are currently in:** {current_phase}\n\n💡 **Tip:** {phase_tip}")

        # Phase timeline
        st.markdown("### 🗓️ Your Cycle Phases")
        p1, p2, p3, p4 = st.columns(4)
        p1.error(f"**🔴 Menstrual**\nDay 1–{period_duration}\nBleeding phase")
        p2.success(f"**🌱 Follicular**\nDay {period_duration+1}–{avg_cycle//2 - 2}\nEnergy rises")
        p3.warning(f"**🥚 Ovulation**\nDay {avg_cycle//2 - 2}–{avg_cycle//2 + 2}\nFertile window")
        p4.info(f"**🌙 Luteal**\nDay {avg_cycle//2 + 3}–{avg_cycle}\nPre-period")

        if len(all_dates) >= 2 and std_cycle > 7:
            st.warning(f"⚠️ Your cycle varies by {std_cycle:.0f} days. This is considered irregular. "
                       f"Consider visiting a gynaecologist if this has been happening for 3+ months.")
        elif len(all_dates) >= 2:
            st.success("✅ Your cycle appears regular based on your data.")

        # Life-stage specific advice
        st.markdown("---")
        if "first period" in life_stage:
            st.markdown("""
            ### 💜 For Your First Period — What to Expect
            - Your first few periods may be irregular — **this is completely normal**
            - Cycles can range from 21 to 45 days in the first 2 years
            - Stock up on pads, keep a spare in your bag
            - Tell a trusted adult (parent, older sister, school nurse) how you're feeling
            - If you have severe pain that stops you from going to school, tell a doctor
            """)
        elif "40s" in life_stage:
            st.markdown("""
            ### 💜 Perimenopause — What SheSync Tracks For You
            - Cycles may shorten or become irregular — **this is normal**
            - Hot flashes, sleep changes, and mood shifts are common
            - Track your symptoms daily so your doctor has a clear picture
            - Missed periods for 12 consecutive months = menopause
            - You are not alone — this is a transition, not a disorder
            """)

# ══════════════════════════════════════════════════════════════════════════
# PAGE 4 — PCOS RISK CHECK
# ══════════════════════════════════════════════════════════════════════════
elif page == "🔬 PCOS Risk Check":
    st.info("This legacy page uses a rule-based checklist. For actual saved Random Forest / XGBoost inference and SHAP, open the updated website above.")
    st.title("🔬 PCOS Risk Check")
    st.markdown("Answer in simple terms — no medical knowledge needed. Takes about 3 minutes.")
    st.markdown("""
    <div class="info-box">
    ℹ️ <strong>What is PCOS?</strong> Polycystic Ovary Syndrome is a hormonal condition that affects 
    1 in 8 women. It can cause irregular periods, weight changes, acne, and unwanted hair growth. 
    Early awareness helps — this check does NOT diagnose you, it tells you if you should see a doctor.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    with st.form("pcos_simple_form"):
        st.markdown("### 👤 Basic Information")
        c1, c2, c3 = st.columns(3)
        with c1:
            age = st.number_input("Your age", 10, 55, 25)
            weight = st.number_input("Your weight (kg)", 30, 130, 60)
            height = st.number_input("Your height (cm)", 140, 185, 160)
        with c2:
            bmi = weight / ((height / 100) ** 2)
            if bmi < 18.5:
                bmi_cat = "Underweight"
            elif bmi < 25:
                bmi_cat = "Healthy"
            elif bmi < 30:
                bmi_cat = "Overweight"
            else:
                bmi_cat = "Obese"
            st.metric("Your BMI", f"{bmi:.1f} — {bmi_cat}")
            blood_group = st.selectbox("Blood group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"])
        with c3:
            cycle_type = st.selectbox("Your periods are usually", [
                "Regular (come around the same time each month)",
                "Irregular (unpredictable timing)",
                "I've never had a period yet",
                "My periods have stopped"
            ])
            cycle_length = st.number_input("Roughly how many days between periods?", 18, 60, 28,
                                           help="Count from day 1 of one period to day 1 of the next")

        st.markdown("### 🩺 A Few Health Questions")
        st.markdown("*(These are based on clinical PCOS indicators — answer as best you can)*")
        c4, c5 = st.columns(2)
        with c4:
            st.markdown("**Have you noticed any of these?**")
            weight_gain = st.checkbox("Weight gain that's hard to explain")
            hair_face = st.checkbox("Hair growing on face, chest, or stomach")
            hair_loss_head = st.checkbox("Hair thinning or falling from head")
            skin_dark = st.checkbox("Dark patches of skin (neck, underarms, groin)")
            acne_check = st.checkbox("Persistent acne or pimples")
        with c5:
            st.markdown("**Lifestyle**")
            fast_food = st.checkbox("I eat fast food 3+ times a week")
            no_exercise = st.checkbox("I rarely exercise (less than once a week)")
            stress_high = st.checkbox("I've been under a lot of stress lately")
            sleep_bad = st.checkbox("I regularly sleep less than 6 hours")

        st.markdown("### 🔬 Do you have any of these test results? (skip if you don't know)")
        st.markdown("*These help improve accuracy but are completely optional*")
        c6, c7 = st.columns(2)
        with c6:
            know_hormones = st.checkbox("I have hormone test results")
            if know_hormones:
                fsh = st.slider("FSH level (mIU/mL) — normal is 3-10", 1.0, 20.0, 7.0)
                lh = st.slider("LH level (mIU/mL) — normal is 2-15", 1.0, 30.0, 10.0)
                amh = st.slider("AMH level (ng/mL) — normal is 1-4", 0.5, 10.0, 3.5)
            else:
                fsh, lh, amh = 7.0, 10.0, 3.5
        with c7:
            know_scan = st.checkbox("I have ultrasound results")
            if know_scan:
                follicle_r = st.slider("Follicle count — right ovary (normal < 12)", 0, 25, 6,
                                       help="Your sonography report will have this number")
                follicle_l = st.slider("Follicle count — left ovary (normal < 12)", 0, 25, 6)
            else:
                follicle_r, follicle_l = 6, 6

        submitted = st.form_submit_button("🔍 Check My PCOS Risk", use_container_width=True)

    if submitted:
        with st.spinner("Analysing your responses..."):
            time.sleep(1.5)

        # Risk scoring
        score = 0
        if follicle_r > 12: score += 28
        elif follicle_r > 8: score += 14
        if follicle_l > 12: score += 18
        elif follicle_l > 8: score += 9
        if fast_food: score += 10
        if amh > 4.5: score += 10
        if weight_gain: score += 8
        if hair_face: score += 9
        if "Irregular" in cycle_type: score += 10
        if skin_dark: score += 6
        if acne_check: score += 5
        if bmi > 30: score += 8
        if no_exercise: score += 5
        if hair_loss_head: score += 5
        if stress_high: score += 4
        if sleep_bad: score += 4
        score = min(score, 98)

        st.markdown("---")
        st.markdown("### 🧠 Your PCOS Risk Result")
        r1, r2 = st.columns([1, 2])

        with r1:
            if score >= 55:
                st.markdown(f'<div class="risk-high"><h2>{score}%</h2><h3>⚠️ Higher Risk</h3><p>Please see a doctor</p></div>',
                            unsafe_allow_html=True)
            elif score >= 30:
                st.markdown(f'<div class="risk-med"><h2>{score}%</h2><h3>🔶 Some Risk</h3><p>Worth monitoring</p></div>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="risk-low"><h2>{score}%</h2><h3>✅ Lower Risk</h3><p>Keep it up!</p></div>',
                            unsafe_allow_html=True)

        with r2:
            st.markdown("**What contributed to your score:**")
            factors = {
                "Ultrasound: follicle count": min((follicle_r + follicle_l) * 1.5, 46),
                "Fast food habit": 10 if fast_food else 0,
                "Irregular periods": 10 if "Irregular" in cycle_type else 0,
                "Unexplained weight gain": 8 if weight_gain else 0,
                "Unusual hair growth": 9 if hair_face else 0,
                "Skin darkening": 6 if skin_dark else 0,
                "Acne": 5 if acne_check else 0,
                "BMI": 8 if bmi > 30 else 0,
            }
            active = {k: v for k, v in factors.items() if v > 0}
            if active:
                fig, ax = plt.subplots(figsize=(6, 2.5))
                ax.barh(list(active.keys()), list(active.values()), color='#c850c0')
                ax.set_xlabel("Risk contribution")
                ax.set_title("Factors that raised your score")
                st.pyplot(fig)
                plt.close()
            else:
                st.success("No significant risk factors detected in your answers.")

        st.markdown("---")
        if score >= 55:
            st.error("""
            ### What you should do next
            - **Book an appointment with a gynaecologist** — use the Find a Doctor page
            - Ask for a blood test: FSH, LH, AMH, testosterone, and insulin levels
            - Ask for a pelvic ultrasound scan
            - **This is not a diagnosis** — only a doctor can confirm PCOS
            """)
        elif score >= 30:
            st.warning("""
            ### What you should do next
            - Monitor your symptoms using the Daily Log for 2-3 months
            - Reduce fast food and increase physical activity
            - If your periods remain irregular, book a gynaecologist appointment
            """)
        else:
            st.success("""
            ### You're doing well!
            - Keep up your healthy habits
            - Continue logging your cycle monthly
            - Annual gynaecologist check-up is always a good idea
            """)

        st.caption("⚠️ This tool is for awareness only. It does not diagnose PCOS. "
                   "Always consult a qualified gynaecologist for medical decisions.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE 5 — WEARABLE DATA
# ══════════════════════════════════════════════════════════════════════════
elif page == "📡 Wearable Data":
    st.title("📡 Wearable Integration")
    st.markdown("SheSync connects to a low-cost wearable device (ESP32-based) to capture "
                "your body signals automatically — no manual entry needed.")
    st.markdown("---")

    st.markdown("### 🔌 Our Wearable Device")
    h1, h2, h3 = st.columns(3)
    with h1:
        st.info("**What it measures:**\n\n"
                "- ❤️ Heart rate\n"
                "- 🌡️ Body temperature\n"
                "- 🏃 Steps and activity\n"
                "- ⚡ Stress (skin response)")
    with h2:
        st.warning("**How it works:**\n\n"
                   "- Worn on the wrist\n"
                   "- Reads data every minute\n"
                   "- Sends to app via Bluetooth\n"
                   "- Battery lasts 3 days")
    with h3:
        st.success("**Why it helps:**\n\n"
                   "- Research readiness for temperature trends\n"
                   "- Tracks stress before periods\n"
                   "- Catches HRV changes linked to hormones\n"
                   "- Requires hardware and clinical validation")

    st.markdown("---")
    st.markdown("### 📊 Demonstration Sensor Stream")
    st.info("In the actual device, these numbers update every 60 seconds via Bluetooth.")

    if st.button("▶ Start demo simulation", use_container_width=True):
        prog = st.progress(0)
        status = st.empty()
        b1, b2, b3, b4 = st.columns(4)
        hr_box = b1.empty()
        temp_box = b2.empty()
        act_box = b3.empty()
        stress_box = b4.empty()

        for i in range(10):
            prog.progress((i + 1) * 10)
            status.markdown(f"*Reading sensors... {i+1}/10*")
            hr_box.metric("❤️ Heart Rate", f"{int(np.random.normal(72, 4))} bpm")
            temp_box.metric("🌡️ Temperature", f"{round(np.random.normal(36.6, 0.25), 1)} °C")
            act_box.metric("🏃 Steps today", f"{int(np.random.normal(5200, 600))}")
            stress_box.metric("⚡ Stress level", f"{round(np.random.uniform(0.2, 0.6), 2)}")
            time.sleep(0.35)

        prog.progress(100)
        status.markdown("✅ Reading complete!")

        st.markdown("---")
        st.markdown("### 📈 7-Day Trends")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hr_t = [70, 72, 74, 73, 77, 75, 71]
        temp_t = [36.4, 36.5, 36.5, 36.8, 37.1, 36.9, 36.7]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3))
        ax1.plot(days, hr_t, marker="o", color="#c850c0", linewidth=2)
        ax1.set_title("Heart Rate (7 days)")
        ax1.set_ylabel("bpm")

        ax2.plot(days, temp_t, marker="o", color="#6a11cb", linewidth=2)
        ax2.axhline(36.7, color="red", linestyle="--", alpha=0.5, label="Illustrative reference line")
        ax2.set_title("Basal Body Temperature (7 days)")
        ax2.set_ylabel("°C")
        ax2.legend()

        st.pyplot(fig)
        plt.close()

        st.info("These seven-day values are demonstration samples, not measurements or evidence of ovulation.")

# ══════════════════════════════════════════════════════════════════════════
# PAGE 6 — FIND A DOCTOR
# ══════════════════════════════════════════════════════════════════════════
elif page == "👩‍⚕️ Find a Doctor":
    st.title("Find women's healthcare")
    st.info("Real location-based Google Places discovery is available in the updated SheSync website. Static doctor ratings and booking availability are no longer displayed.")
    st.link_button("Open real doctor discovery", "http://localhost:5000/#doctors")
    st.link_button("Search Google Maps", "https://www.google.com/maps/search/?api=1&query=gynecologist+near+me")

elif page == "🔔 Set Reminder":
    st.title("🔔 Set a Reminder")
    st.markdown("Get a real email reminder before your next period or for your daily log.")
    st.markdown("---")

    # ── Check secrets ──────────────────────────────────────────────────────
    try:
        SENDER = st.secrets["SENDER_EMAIL"]
        PASSWORD = st.secrets["SENDER_PASSWORD"]
        secrets_ok = True
    except Exception:
        secrets_ok = False

    if not secrets_ok:
        st.warning("""
        ⚙️ **Email not configured yet.**

        To enable real email reminders, create the file:
         in your SheSync folder with:

        

        Follow the setup guide provided separately.
        """)

    st.markdown("### 📧 Send a Real Email Reminder")
    rem_email = st.text_input("Send reminder to this email", placeholder="yourname@gmail.com")

    reminder_type = st.selectbox("Type of reminder", [
        "Period starting soon (3 days notice)",
        "Period starting tomorrow (1 day notice)",
        "Daily log reminder",
        "Weekly cycle summary",
    ])

    st.markdown("---")
    st.markdown("### 📅 Your Period Estimate")

    if st.session_state.last_period:
        last = date.fromisoformat(st.session_state.last_period)
        next_p = last + timedelta(days=29)
        st.success(f"Next period estimated: **{next_p.strftime('%d %B %Y')}**")
    else:
        next_p_input = st.date_input("Enter your expected next period date",
                                     value=date.today() + timedelta(days=14))
        next_p = next_p_input

    days_to_period = (next_p - date.today()).days

    # ── In-app alert ───────────────────────────────────────────────────────
    if days_to_period <= 3 and days_to_period >= 0:
        st.error(f"🔴 **Period Alert:** Your period is expected in {days_to_period} days! Prepare your supplies.")
    elif days_to_period <= 7 and days_to_period >= 0:
        st.warning(f"🔶 **Coming Soon:** About {days_to_period} days until your next period.")
    elif days_to_period > 7:
        st.info(f"🟢 About {days_to_period} days until your next period. You are in your safe window.")
    else:
        st.error("🔴 Your period may have started or be overdue. Please log today in the Daily Log.")

    st.markdown("---")

    if st.button("📧 Send Reminder Email Now", use_container_width=True):
        if not rem_email or "@" not in rem_email:
            st.error("Please enter a valid email address.")
        elif not secrets_ok:
            st.error("Email credentials not configured. Please set up secrets.toml first.")
        else:
            subject = "🌸 SheSync — Period Reminder"
            body = f"""Hi there!

This is your SheSync health reminder.

╔══════════════════════════════════╗
   🌸 SHESYNC PERIOD REMINDER
╚══════════════════════════════════╝

Reminder type   : {reminder_type}
Next period     : {next_p.strftime('%d %B %Y')} ({days_to_period} days away)

✅ THINGS TO PREPARE:
• Stock up on sanitary pads or tampons
• Keep a heat pad handy for cramps
• Stay hydrated and reduce salty foods
• Plan lighter activities during your period
• Log your symptoms daily in SheSync

💜 SELF-CARE TIPS:
• Get 7-8 hours of sleep
• Light stretching or yoga helps with cramps
• Dark chocolate is okay! 🍫

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SheSync — Your Period Companion
Global Academy of Technology, AIML Dept.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Note: This is an AI-generated reminder.
For medical concerns please consult a gynaecologist.
"""
            try:
                msg = MIMEMultipart()
                msg["From"] = SENDER
                msg["To"] = rem_email
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))

                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(SENDER, PASSWORD)
                    server.send_message(msg)

                st.success(f"✅ Reminder email sent to **{rem_email}**! Check your inbox.")
                st.balloons()

                with st.expander("📧 Preview of email sent"):
                    st.text(body)

            except smtplib.SMTPAuthenticationError:
                st.error("Gmail authentication failed. Make sure you used a Gmail App Password "                         "(not your regular password). Check secrets.toml.")
            except smtplib.SMTPException as e:
                st.error(f"Email sending failed: {str(e)}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")