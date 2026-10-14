import csv
import io
import math
import random
from html import escape

import streamlit as st

st.set_page_config(page_title="Sports by the Numbers | Soccer Manager", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

st.markdown('''<style>
.block-container{padding-top:1rem;padding-bottom:1rem;max-width:1300px}
h1{font-size:1.9rem!important;margin:0 0 .35rem!important}
div.stButton>button{min-height:2.8rem;font-weight:650}
[data-testid="stMetric"]{background:#122b29;border:1px solid #296353;border-radius:12px;padding:9px 13px}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"]{color:#f3fbf7!important}
.mini{font-size:.88rem;color:#6b817a}.hint{padding:.75rem;border-radius:10px;background:#e9f5ef;color:#153d2e}
.event{padding:.5rem .7rem;border-bottom:1px solid #d7e4df;font-size:.91rem}
</style>''', unsafe_allow_html=True)

# Fictional classroom ratings, not scraped or official real-world statistics.
NAMES = {
    "Harbor City FC": ["M. Vega", "A. Okafor", "J. Park", "D. Silva", "E. Brooks", "K. Moreno", "L. Russo", "N. Price", "S. Diallo", "T. Chen", "R. Hayes", "I. Costa", "P. Reed", "F. Ibrahim"],
    "Mountain United": ["B. Novak", "O. Mensah", "C. Santos", "Y. Ito", "V. Morgan", "H. Rahman", "Z. Baker", "W. Cole", "G. Alvarez", "Q. Patel", "U. Fischer", "A. Wolfe", "D. Cruz", "M. Ali"],
    "Riverdale Rovers": ["P. Grant", "R. Kim", "F. Torres", "J. Hart", "N. Evans", "C. Adeyemi", "E. Roy", "K. Shah", "L. Flores", "T. Beck", "S. Malik", "W. Barnes", "I. Lin", "D. Young"],
    "Metro Athletic": ["D. Knight", "A. Bell", "S. Romero", "K. Soto", "J. Silva", "P. Fox", "R. Mason", "Y. Idris", "O. Lane", "B. Cruz", "T. Wells", "M. King", "N. Ford", "F. Diaz"],
}
ROLES = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD", "DEF", "MID", "FWD"]


def roster(club):
    players = []
    seed = sum((i + 1) * ord(c) for i, c in enumerate(club))
    rng = random.Random(seed)
    for i, (name, role) in enumerate(zip(NAMES[club], ROLES)):
        players.append({"id": f"{club}-{i}", "name": name, "role": role,
                        "passing": rng.randint(66, 88) if role != "GK" else rng.randint(45, 64),
                        "shooting": rng.randint(65, 88) if role == "FWD" else rng.randint(46, 71),
                        "defense": rng.randint(65, 88) if role == "DEF" else rng.randint(38, 69),
                        "keeping": rng.randint(72, 89) if role == "GK" else 0,
                        "stamina": 100, "on": i < 11})
    return players


def cap(v, lo, hi):
    return max(lo, min(hi, v))


def team_players(side, active=True):
    players = st.session_state.game["players"][side]
    return [p for p in players if p["on"]] if active else [p for p in players if not p["on"]]


def average(side, attr, role=None):
    group = [p for p in team_players(side) if role is None or p["role"] == role]
    return sum(p[attr] * (.55 + .45 * p["stamina"] / 100) for p in group) / len(group) if group else 65


def select_player(side, preferred):
    group = [p for p in team_players(side) if p["role"] == preferred]
    if not group:
        group = [p for p in team_players(side) if p["role"] != "GK"]
    return random.choice(group)


def log_event(desc, side="neutral", action="", outcome="", probability=None, xg=0):
    g = st.session_state.game
    g["events"].append({"minute": g["minute"], "team": g["clubs"].get(side, "—"),
                        "action": action, "outcome": outcome, "probability": round(probability * 100, 1) if probability is not None else "",
                        "xG": round(xg, 3), "commentary": desc})
    g["last"] = desc


def stats_zero():
    return {"shots": 0, "on_target": 0, "goals": 0, "xg": 0.0, "pass_att": 0, "pass_ok": 0,
            "tackles": 0, "tackles_ok": 0, "possessions": 0, "saves": 0}


def new_game(club, opponent, shape, tactic):
    st.session_state.game = {
        "clubs": {"home": club, "away": opponent}, "players": {"home": roster(club), "away": roster(opponent)},
        "formation": shape, "tactic": tactic, "minute": 0, "phase": "attack", "zone": 1,
        "ball": "home", "stats": {"home": stats_zero(), "away": stats_zero()}, "events": [],
        "last": "Kickoff! Read the scouting report, then choose a play.", "sub_count": 0, "finished": False,
        "half_reported": False, "choices": 0,
    }
    st.session_state.game["stats"]["home"]["possessions"] = 1


def probability(action):
    g = st.session_state.game
    attacking = g["ball"] == "home"
    if attacking:
        passer = average("home", "passing", "MID")
        defense = average("away", "defense", "DEF")
        zone = g["zone"]
        tactic = g["tactic"]
        if action == "Safe pass":
            return cap(.78 + (passer - 75) * .006 - (defense - 75) * .003 + (.05 if tactic == "Possession" else 0), .55, .94)
        if action == "Through ball":
            return cap(.53 + (passer - 75) * .006 - (defense - 75) * .004 + (.06 if tactic == "Attacking" else 0), .32, .78)
        if action == "Cross":
            return cap(.43 + (passer - 75) * .004 - (defense - 75) * .003 + (.04 if tactic == "Attacking" else 0), .25, .65)
        if action == "Shoot":
            xg = {1: .035, 2: .105, 3: .24}[zone]
            shooter = average("home", "shooting", "FWD")
            keeper = average("away", "keeping", "GK")
            return cap(xg * (1 + (shooter - 75) / 160 - (keeper - 78) / 210), .015, .47)
    else:
        defense = average("home", "defense", "DEF")
        attack = average("away", "passing", "MID")
        if action == "Press":
            return cap(.48 + (defense - 75) * .005 - (attack - 75) * .004 + (.06 if g["tactic"] == "Pressing" else 0), .28, .71)
        if action == "Contain":
            return cap(.64 + (defense - 75) * .004 - (attack - 75) * .003, .44, .82)
        if action == "Counter trap":
            return cap(.39 + (defense - 75) * .005 - (attack - 75) * .004, .22, .61)
    return .5


def advance_clock():
    g = st.session_state.game
    g["minute"] = min(90, g["minute"] + random.choice([3, 4, 5, 6]))
    for side in ("home", "away"):
        for p in team_players(side):
            loss = random.uniform(1.1, 2.8) * (1.15 if g["tactic"] == "Pressing" and side == "home" else 1)
            p["stamina"] = max(20, round(p["stamina"] - loss, 1))
    if g["minute"] >= 45 and not g["half_reported"]:
        g["half_reported"] = True
        log_event("⏸️ Halfway through the match. Consider changing tactics or using your bench.")
    if g["minute"] >= 90:
        g["finished"] = True
        log_event("🏁 Full time! Open the report to examine the decisions and outcomes.")


def switch_ball(side, zone=1):
    g = st.session_state.game
    g["ball"] = side
    g["zone"] = zone
    g["phase"] = "attack" if side == "home" else "defend"
    g["stats"][side]["possessions"] += 1


def make_shot(side, xg, source):
    g = st.session_state.game
    stats = g["stats"][side]
    stats["shots"] += 1
    stats["xg"] += xg
    scorer = select_player(side, "FWD")
    # A goal is a Bernoulli trial with the displayed xG probability.
    goal = random.random() < xg
    if goal:
        stats["goals"] += 1
        stats["on_target"] += 1
        log_event(f"⚽ GOAL! {scorer['name']} scores for {g['clubs'][side]} ({source}; xG {xg:.2f}).", side, source, "Goal", xg, xg)
    else:
        on_target = random.random() < .56
        if on_target:
            stats["on_target"] += 1
            g["stats"]["away" if side == "home" else "home"]["saves"] += 1
        log_event(f"🥅 {scorer['name']} shoots ({source}, xG {xg:.2f}) — {'saved!' if on_target else 'wide!'}", side, source, "Saved" if on_target else "Missed", xg, xg)
    switch_ball("away" if side == "home" else "home", 1)


def computer_attack():
    g = st.session_state.game
    if g["finished"]:
        return
    if g["ball"] == "home":
        return
    risk = random.random()
    # Opponent adapts: trails -> attacks more; leads -> protects possession.
    goal_diff = g["stats"]["away"]["goals"] - g["stats"]["home"]["goals"]
    danger = cap(.18 + .07 * g["zone"] + (-.06 if goal_diff > 0 else .06 if goal_diff < 0 else 0), .1, .48)
    if risk < danger:
        xg = cap({1: .035, 2: .10, 3: .22}[g["zone"]] * (average("away", "shooting", "FWD") / 75), .02, .37)
        make_shot("away", xg, "Opposition shot")
    else:
        prob = cap(.66 + (average("away", "passing", "MID") - 75) * .004 - (average("home", "defense", "DEF") - 75) * .003, .46, .83)
        g["stats"]["away"]["pass_att"] += 1
        if random.random() < prob:
            g["stats"]["away"]["pass_ok"] += 1
            g["zone"] = min(3, g["zone"] + 1)
            log_event("The opposition completes a pass and pushes into a more dangerous area.", "away", "Pass", "Complete", prob)
        else:
            log_event("Opposition pass intercepted! Your team wins possession.", "away", "Pass", "Intercepted", prob)
            switch_ball("home", 1)


def play(action):
    g = st.session_state.game
    if g["finished"]:
        return
    prob = probability(action)
    g["choices"] += 1
    if g["ball"] == "home":
        if action == "Shoot":
            make_shot("home", prob, "Student-selected shot")
        else:
            g["stats"]["home"]["pass_att"] += 1
            if random.random() < prob:
                g["stats"]["home"]["pass_ok"] += 1
                zone_advance = 2 if action == "Through ball" and random.random() < .30 else 1
                g["zone"] = min(3, g["zone"] + zone_advance)
                log_event(f"✅ {action} succeeds. Your team advances into zone {g['zone']}.", "home", action, "Complete", prob)
            else:
                log_event(f"❌ {action} fails. The opposition recovers the ball.", "home", action, "Lost possession", prob)
                switch_ball("away", 1)
    else:
        g["stats"]["home"]["tackles"] += 1
        if random.random() < prob:
            g["stats"]["home"]["tackles_ok"] += 1
            log_event(f"🛡️ {action} works! Your team wins the ball.", "home", action, "Won possession", prob)
            switch_ball("home", 2 if action == "Counter trap" else 1)
        else:
            if action == "Press":
                g["zone"] = min(3, g["zone"] + 1)
            elif action == "Contain":
                g["zone"] = max(1, g["zone"] - 1)
            else:
                g["zone"] = min(3, g["zone"] + 1)
            log_event(f"The {action.lower()} attempt doesn't regain possession.", "home", action, "Failed", prob)
    if g["ball"] == "away":
        computer_attack()
    advance_clock()


def make_sub(off_id, on_id):
    g = st.session_state.game
    if g["finished"] or g["sub_count"] >= 5:
        return False
    old = next((p for p in g["players"]["home"] if p["id"] == off_id and p["on"]), None)
    new = next((p for p in g["players"]["home"] if p["id"] == on_id and not p["on"]), None)
    if not old or not new or old["role"] == "GK" or new["role"] == "GK":
        return False
    old["on"], new["on"] = False, True
    g["sub_count"] += 1
    log_event(f"🔁 Substitution: {new['name']} replaces {old['name']} ({g['sub_count']}/5).", "home", "Substitution", "Completed")
    return True


def pitch():
    g = st.session_state.game
    # Self-contained SVG pitch; no local image assets required.
    H, W = 280, 660
    lines = ['<svg viewBox="0 0 660 280" width="100%" style="display:block;border-radius:12px;background:#187148">',
             '<rect width="660" height="280" fill="#187148"/>']
    for i in range(11):
        if i % 2 == 0:
            lines.append(f'<rect x="{i*60}" width="60" height="280" fill="#ffffff" opacity=".045"/>')
    lines += ['<rect x="18" y="18" width="624" height="244" fill="none" stroke="white" stroke-width="2"/>',
              '<line x1="330" y1="18" x2="330" y2="262" stroke="white" stroke-width="2"/>',
              '<circle cx="330" cy="140" r="42" fill="none" stroke="white" stroke-width="2"/>',
              '<rect x="18" y="68" width="94" height="144" fill="none" stroke="white" stroke-width="2"/>',
              '<rect x="548" y="68" width="94" height="144" fill="none" stroke="white" stroke-width="2"/>',
              '<rect x="8" y="111" width="10" height="58" fill="none" stroke="white" stroke-width="2"/>',
              '<rect x="642" y="111" width="10" height="58" fill="none" stroke="white" stroke-width="2"/>']
    # Abstract positional markers (not tracking an actual 22-player physics match).
    home_positions = [(56,140),(160,40),(160,104),(160,175),(160,240),(280,70),(280,140),(280,208),(430,55),(465,140),(430,225)]
    away_positions = [(608,140),(500,40),(500,104),(500,175),(500,240),(385,70),(385,140),(385,208),(235,55),(205,140),(235,225)]
    for side, poses, fill in [("home", home_positions, "#f8cf51"), ("away", away_positions, "#e5f4ff")]:
        for j, (x,y) in enumerate(poses):
            lines.append(f'<circle cx="{x}" cy="{y}" r="8.5" fill="{fill}" stroke="#17362b" stroke-width="1.8"/>')
    if g["ball"] == "home":
        x = {1:270, 2:420, 3:540}[g["zone"]]
    else:
        x = {1:390, 2:235, 3:125}[g["zone"]]
    lines.append(f'<circle cx="{x}" cy="140" r="7.2" fill="white" stroke="#111" stroke-width="2"/><text x="{x+14}" y="126" fill="white" font-size="13" font-family="sans-serif" font-weight="bold">BALL</text>')
    lines.append('</svg>')
    return ''.join(lines)


def percent(a, b):
    return f"{a / b * 100:.1f}%" if b else "—"


def csv_log(events):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["minute", "team", "action", "outcome", "probability", "xG", "commentary"])
    writer.writeheader()
    writer.writerows(events)
    return output.getvalue()


st.title("⚽ SPORTS BY THE NUMBERS  |  SOCCER MANAGER")
st.caption("Your tactics. Your data. Your decisions. Every chance is a probability, never a guarantee.")

if "game" not in st.session_state:
    st.subheader("Set up your match")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        club = st.selectbox("Your team", list(NAMES))
    with col2:
        opponent = st.selectbox("Opponent", [t for t in NAMES if t != club])
    with col3:
        shape = st.selectbox("Formation", ["4-3-3", "4-4-2", "3-5-2"])
    with col4:
        tactic = st.selectbox("Tactic", ["Balanced", "Possession", "Attacking", "Pressing"])
    st.info("🎓 These club names and player ratings are fictional. Pass %, shot xG, and tackle % are estimated by the game's formula; track what actually happens and compare it to expectations.")
    st.markdown("**Before kickoff:** Balanced is versatile; Possession improves safer passes; Attacking helps through balls and crosses; Pressing helps win tackles but drains stamina faster.")
    if st.button("🏟️ START MATCH", type="primary", use_container_width=True):
        new_game(club, opponent, shape, tactic)
        st.rerun()
    st.stop()

g = st.session_state.game
h, a = g["stats"]["home"], g["stats"]["away"]
header = st.columns([2,1,2,1])
header[0].markdown(f"### 🟡 {g['clubs']['home']}")
header[1].metric("SCORE", f"{h['goals']} – {a['goals']}")
header[2].markdown(f"### ⚪ {g['clubs']['away']}")
header[3].metric("MINUTE", f"{g['minute']}'")

left, right = st.columns([1.6, 1], gap="large")
with left:
    st.markdown(pitch(), unsafe_allow_html=True)
    st.caption("Schematic pitch, not player-motion tracking. 🟡 You attack right; ⚪ the computer attacks left.")
    if g["finished"]:
        st.success(f"🏁 FULL TIME — {g['clubs']['home']} {h['goals']}–{a['goals']} {g['clubs']['away']}")
    else:
        if g["ball"] == "home":
            st.markdown(f"**🟡 YOUR BALL · Zone {g['zone']}/3 · Choose a play**")
            options = ["Safe pass", "Through ball", "Cross", "Shoot"]
        else:
            st.markdown(f"**⚪ OPPONENT BALL · Danger zone {g['zone']}/3 · Defend!**")
            options = ["Press", "Contain", "Counter trap"]
        probs = {o: probability(o) for o in options}
        st.caption("Coach's scouting report: probability of the stated outcome. For a shot, the percentage is the chance of a goal (xG). Passing and defending percentages measure success of that specific action.")
        buttons = st.columns(len(options))
        for j, option in enumerate(options):
            if buttons[j].button(f"{option}\n{probs[option]:.0%}", key=f"act_{option}", use_container_width=True, type="primary" if option == "Shoot" else "secondary"):
                play(option)
                st.rerun()
    st.markdown(f"<div class='hint'><b>🎙️ Live commentary:</b> {escape(g['last'])}</div>", unsafe_allow_html=True)
    with st.expander("📻 Match play-by-play", expanded=False):
        if not g["events"]:
            st.write("No events yet. Make the first decision.")
        for e in reversed(g["events"][-18:]):
            st.markdown(f"<div class='event'><b>{e['minute']}'</b> — {escape(e['commentary'])}</div>", unsafe_allow_html=True)

with right:
    st.markdown("#### 📊 LIVE MATCH DATA")
    stat_rows = [
        ("Shots", h["shots"], a["shots"]),
        ("Shots on target", h["on_target"], a["on_target"]),
        ("Expected goals (xG)", f"{h['xg']:.2f}", f"{a['xg']:.2f}"),
        ("Pass completion", percent(h["pass_ok"], h["pass_att"]), percent(a["pass_ok"], a["pass_att"])),
        ("Possession share*", percent(h["possessions"], h["possessions"] + a["possessions"]), percent(a["possessions"], h["possessions"] + a["possessions"])),
        ("Tackles won", f"{h['tackles_ok']}/{h['tackles']}", f"{a['tackles_ok']}/{a['tackles']}"),
        ("Saves", h["saves"], a["saves"]),
    ]
    for label, home, away in stat_rows:
        cols = st.columns([1, 1.6, 1])
        cols[0].markdown(f"**{home}**")
        cols[1].markdown(f"<div style='text-align:center;font-size:.88rem'>{label}</div>", unsafe_allow_html=True)
        cols[2].markdown(f"<div style='text-align:right'><b>{away}</b></div>", unsafe_allow_html=True)
    st.caption("*Possession share is based on possession changes, not elapsed seconds; this is a classroom proxy.")
    st.divider()
    st.markdown("#### 🧠 MANAGER CONTROLS")
    tactic_options = ["Balanced", "Possession", "Attacking", "Pressing"]
    new_tactic = st.selectbox("Match tactic", tactic_options, index=tactic_options.index(g["tactic"]), disabled=g["finished"])
    if new_tactic != g["tactic"] and not g["finished"]:
        g["tactic"] = new_tactic
        log_event(f"📋 Tactical adjustment: {new_tactic}.", "home", "Tactic", new_tactic)
        st.rerun()
    active = [p for p in team_players("home") if p["role"] != "GK"]
    bench = [p for p in team_players("home", active=False) if p["role"] != "GK"]
    with st.expander(f"🔁 Substitutions ({g['sub_count']}/5 used)"):
        if not bench or g["sub_count"] >= 5:
            st.write("No more available substitutions.")
        else:
            out = st.selectbox("Player off · fatigue", active, format_func=lambda p: f"{p['name']} ({p['role']}) — {p['stamina']:.0f}% stamina")
            incoming = st.selectbox("Player on", bench, format_func=lambda p: f"{p['name']} ({p['role']}) — {p['stamina']:.0f}% stamina")
            if st.button("Confirm substitution", disabled=g["finished"], use_container_width=True):
                if make_sub(out["id"], incoming["id"]):
                    st.rerun()
    with st.expander("👥 Starting XI + stamina"):
        for p in team_players("home"):
            st.write(f"{p['name']} · {p['role']} · {p['stamina']:.0f}% energy")
    st.caption(f"Formation: {g['formation']} · Decisions: {g['choices']}")

if g["finished"]:
    st.divider()
    st.subheader("📝 FINAL MATCH REPORT — INVESTIGATE THE DATA")
    st.write(f"**Actual score:** {h['goals']}–{a['goals']} | **Expected goals:** {h['xg']:.2f}–{a['xg']:.2f}")
    st.write("**Think like a sports analyst:** Did the winning team create better chances, or simply convert more of them? What does the difference between xG and goals tell you about chance?")
    st.write(f"**Your shooting conversion:** {percent(h['goals'], h['shots'])}  |  **Your pass completion:** {percent(h['pass_ok'], h['pass_att'])}  |  **Your tackle success:** {percent(h['tackles_ok'], h['tackles'])}")
    st.download_button("⬇️ Download match event data (CSV)", data=csv_log(g["events"]), file_name="soccer_match_events.csv", mime="text/csv")
    with st.expander("Math reflection prompts"):
        st.markdown("1. Calculate goals ÷ shots × 100. How close was your conversion percentage to your total xG?\n\n2. Identify a low-probability decision that succeeded or a high-probability decision that failed.\n\n3. Was your team more accurate at passing or tackling? Show evidence.\n\n4. How did your tactics and substitutions change as the game progressed?")

st.divider()
with st.expander("ℹ️ How the probability engine works"):
    st.write("The model uses fictional player ratings and fatigue to adjust the probability of each pass, defensive play, and shot. A random draw then decides whether the action succeeds. Shot probability represents a simplified xG estimate based on the danger zone, shooter skill, and goalkeeper skill. A 25% shot can still miss, and a 5% shot can still score. This is intentionally **not** an official xG model or verified real-world performance data.")
    st.write("Gameplay moves 3–6 minutes per coaching decision, so one match fits into a class period. Computer opponents automatically pass or shoot and respond to the score. The visual pitch is schematic.")
if st.button("🔄 New match", use_container_width=False):
    del st.session_state.game
    st.rerun()
