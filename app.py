import csv
import io
import math
import random
from html import escape

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Sports by the Numbers | Soccer Manager 2", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")
st.markdown('''<style>
.block-container{max-width:1420px;padding-top:.65rem;padding-bottom:1rem}
h1{font-size:1.7rem!important;margin-bottom:0!important}
[data-testid="stMetric"]{background:#123c33;border:1px solid #27745d;border-radius:12px;padding:8px 12px}
[data-testid="stMetricLabel"],[data-testid="stMetricValue"]{color:white!important}
div.stButton>button{min-height:2.8rem;font-weight:700}
.playbox{background:#10372c;border-radius:13px;color:#e6fff1;padding:.7rem 1rem;margin:.45rem 0}
.scout{background:#e7f2ec;color:#163d30;border-radius:12px;padding:.65rem .85rem;margin:.4rem 0}
.commentary{background:#142e3b;color:#f5fbff;border-left:4px solid #ffcb57;padding:.7rem .85rem;border-radius:8px;margin-top:.5rem}
</style>''', unsafe_allow_html=True)

NAMES = {
    "Harbor City FC": ["M. Vega", "A. Okafor", "J. Park", "D. Silva", "E. Brooks", "K. Moreno", "L. Russo", "N. Price", "S. Diallo", "T. Chen", "R. Hayes", "I. Costa", "P. Reed", "F. Ibrahim"],
    "Mountain United": ["B. Novak", "O. Mensah", "C. Santos", "Y. Ito", "V. Morgan", "H. Rahman", "Z. Baker", "W. Cole", "G. Alvarez", "Q. Patel", "U. Fischer", "A. Wolfe", "D. Cruz", "M. Ali"],
    "Riverdale Rovers": ["P. Grant", "R. Kim", "F. Torres", "J. Hart", "N. Evans", "C. Adeyemi", "E. Roy", "K. Shah", "L. Flores", "T. Beck", "S. Malik", "W. Barnes", "I. Lin", "D. Young"],
    "Metro Athletic": ["D. Knight", "A. Bell", "S. Romero", "K. Soto", "J. Silva", "P. Fox", "R. Mason", "Y. Idris", "O. Lane", "B. Cruz", "T. Wells", "M. King", "N. Ford", "F. Diaz"],
}
ROLES = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD", "DEF", "MID", "FWD"]
LANES = ["Left", "Center", "Right"]
TACTICS = ["Balanced", "Possession", "Attacking", "Pressing"]

def clamp(v, lo, hi): return max(lo, min(hi, v))
def roster(club):
    rng = random.Random(sum((i+1)*ord(c) for i,c in enumerate(club)))
    out=[]
    for i,(name,role) in enumerate(zip(NAMES[club],ROLES)):
        out.append(dict(id=f"{club}-{i}",name=name,role=role,passing=rng.randint(67,91) if role!="GK" else 51,
                        shooting=rng.randint(71,91) if role=="FWD" else rng.randint(43,69),
                        defense=rng.randint(67,91) if role=="DEF" else rng.randint(42,73),
                        keeping=rng.randint(72,90) if role=="GK" else 0,stamina=100.,on=i<11))
    return out

def stats(): return dict(shots=0,goals=0,on_target=0,xg=0.,passes=0,passes_ok=0,tackles=0,tackles_ok=0,possessions=0,saves=0)
def create_game(home,away,formation,tactic):
    st.session_state.game=dict(clubs={"home":home,"away":away},players={"home":roster(home),"away":roster(away)},
      formation=formation,tactic=tactic,minute=0,ball="home",zone=1,lane="Center",stats={"home":stats(),"away":stats()},
      events=[],last="Kickoff! Study the defense and create your first attack.",finished=False,half=False,subs=0,choices=0,
      danger_lane=random.choice(LANES),keeper_bias=random.choice(LANES),animation=None)
    st.session_state.game["stats"]["home"]["possessions"]=1

def active(side): return [p for p in st.session_state.game["players"][side] if p["on"]]
def avg(side,field,role=None):
    a=[p for p in active(side) if role is None or p["role"]==role]
    return sum(p[field]*(0.55+0.45*p["stamina"]/100) for p in a)/len(a) if a else 70

def log(msg,action="",outcome="",prob=None,xg=0,team="home"):
    g=st.session_state.game
    g["last"]=msg
    g["events"].append(dict(minute=g["minute"],team=g["clubs"][team],action=action,outcome=outcome,
      probability=round(prob*100,1) if prob is not None else "",xG=round(xg,3),commentary=msg))

def turnover(side,zone=1):
    g=st.session_state.game; g["ball"]=side;g["zone"]=zone
    g["stats"][side]["possessions"]+=1
    g["danger_lane"]=random.choice(LANES)

def pass_chance(action,lane):
    g=st.session_state.game
    base={"Safe pass":.83,"Through ball":.57,"Cross":.49}[action]
    skill=(avg("home","passing","MID")-75)*.006
    opponent=(avg("away","defense","DEF")-75)*.004
    guard=(.14 if lane==g["danger_lane"] else -.045)
    tactic={"Balanced":0,"Possession":.055 if action=="Safe pass" else .005,"Attacking":.045 if action!="Safe pass" else -.015,"Pressing":-.025}[g["tactic"]]
    return clamp(base+skill-opponent-guard+tactic, .18,.96)

def shot_chance(lane,power):
    g=st.session_state.game
    # Shot power is a tactical trade-off. Ideal power varies by shooting distance.
    ideal={1:90,2:77,3:61}[g["zone"]]
    err=abs(power-ideal)
    raw={1:.045,2:.15,3:.34}[g["zone"]]
    rating=(avg("home","shooting","FWD")-75)*.005
    keeper=(avg("away","keeping","GK")-78)*.003
    read= .075 if lane!=g["keeper_bias"] else -.09
    coverage=-.055 if lane==g["danger_lane"] else .025
    penalty=err*.0034
    tactic=.017 if g["tactic"]=="Attacking" else 0
    return clamp(raw+rating-keeper+read+coverage-penalty+tactic,.012,.68),ideal

def defensive_chance(action,lane):
    g=st.session_state.game
    base={"Press":.48,"Contain":.63,"Counter trap":.4}[action]
    skill=(avg("home","defense","DEF")-75)*.005-(avg("away","passing","MID")-75)*.004
    correct=.15 if lane==g["danger_lane"] else -.10
    fatigue=.04 if g["tactic"]=="Pressing" and action=="Press" else 0
    return clamp(base+skill+correct+fatigue,.16,.86)

def elapse():
    g=st.session_state.game
    g["minute"]=min(90,g["minute"]+random.randint(2,4))
    for side in ("home","away"):
        for p in active(side):
            drain=random.uniform(1.2,2.8)*(1.3 if side=="home" and g["tactic"]=="Pressing" else 1)
            p["stamina"]=round(max(18,p["stamina"]-drain),1)
    if g["minute"]>=45 and not g["half"]:
        g["half"]=True
        log("⏸️ HALFTIME reached. Use the statistical report to reconsider your strategy.","Halftime","Break")
    if g["minute"]>=90:
        g["finished"]=True
        log("🏁 FULL TIME! Compare expected and actual performance below.","Final whistle","Complete")

def trajectory(old_side,old_zone,old_lane,new_side,new_zone,new_lane,result):
    st.session_state.game["animation"]=dict(before=[old_side,old_zone,old_lane],after=[new_side,new_zone,new_lane],result=result,
        seed=random.randint(1000,999999))

def shoot(side,chance,source,lane):
    g=st.session_state.game
    team=g["stats"][side];opp="away" if side=="home" else "home"
    team["shots"]+=1;team["xg"]+=chance
    shooter=random.choice([p for p in active(side) if p["role"]=="FWD"])
    scored=random.random()<chance
    if scored:
        team["goals"]+=1;team["on_target"]+=1
        log(f"⚽ GOAL! {shooter['name']} finds the {lane.lower()} side of the net! Shot chance {chance:.0%}.",source,"Goal",chance,chance,side)
    else:
        target=random.random()<.63
        if target:
            team["on_target"]+=1;g["stats"][opp]["saves"]+=1
        log(f"🥅 {shooter['name']} shoots toward {lane.lower()} — {'saved by the goalkeeper' if target else 'off target'}! ({chance:.0%} chance)",source,"Saved" if target else "Missed",chance,chance,side)
    turnover(opp,1)
    return "goal" if scored else "shot"

def computer_turn():
    g=st.session_state.game
    if g["ball"]!="away":return "pass"
    diff=g["stats"]["away"]["goals"]-g["stats"]["home"]["goals"]
    eagerness=.12+g["zone"]*.095+(.09 if diff<0 else -.055 if diff>0 else 0)
    if random.random()<eagerness:
        chance=clamp({1:.04,2:.12,3:.27}[g["zone"]]+(avg("away","shooting","FWD")-75)*.003,
                    .018,.43)
        return shoot("away",chance,"Opponent shot",g["danger_lane"])
    chance=clamp(.7+(avg("away","passing","MID")-75)*.004-(avg("home","defense","DEF")-75)*.003,.48,.87)
    g["stats"]["away"]["passes"]+=1
    if random.random()<chance:
        g["stats"]["away"]["passes_ok"]+=1
        g["zone"]=min(3,g["zone"]+1)
        log(f"Opposition completes a pass through the {g['danger_lane'].lower()} channel.","Opponent pass","Completed",chance,team="away")
    else:
        log("Your defense intercepts an opposition pass!","Opponent pass","Intercepted",chance,team="away")
        turnover("home",1)
    return "pass"

def act(action,lane,power):
    g=st.session_state.game
    if g["finished"]:return
    old=(g["ball"],g["zone"],g["lane"])
    g["choices"]+=1
    result="pass"
    if g["ball"]=="home":
        if action=="Shoot":
            chance,_=shot_chance(lane,power)
            result=shoot("home",chance,"Shot",lane)
        else:
            chance=pass_chance(action,lane)
            g["stats"]["home"]["passes"]+=1
            if random.random()<chance:
                g["stats"]["home"]["passes_ok"]+=1
                g["zone"]=min(3,g["zone"]+(2 if action=="Through ball" and random.random()<.42 else 1))
                g["lane"]=lane
                log(f"✅ {action} through the {lane.lower()} channel! Now in attacking zone {g['zone']}.",action,"Completed",chance)
            else:
                log(f"❌ {action} intercepted in the {lane.lower()} channel. Your opponent counters!",action,"Lost ball",chance)
                turnover("away",1)
                computer_turn()
                result="turnover"
    else:
        chance=defensive_chance(action,lane)
        g["stats"]["home"]["tackles"]+=1
        if random.random()<chance:
            g["stats"]["home"]["tackles_ok"]+=1
            log(f"🛡️ Successful {action.lower()} on the {lane.lower()} side! You win the ball.",action,"Won ball",chance)
            turnover("home",2 if action=="Counter trap" else 1)
            result="intercept"
        else:
            g["zone"]=clamp(g["zone"]+(1 if action!="Contain" else -1),1,3)
            log(f"The {action.lower()} fails in the {lane.lower()} channel.",action,"Failed",chance)
            result=computer_turn()
    elapse()
    trajectory(*old,g["ball"],g["zone"],g["lane"],result)
    g["keeper_bias"]=random.choices(LANES,weights=[4,3,4],k=1)[0]

def substitute(off_id,on_id):
    g=st.session_state.game
    if g["finished"] or g["subs"]>=3:return False
    off=next((p for p in active("home") if p["id"]==off_id and p["role"]!="GK"),None)
    on=next((p for p in g["players"]["home"] if p["id"]==on_id and not p["on"] and p["role"]!="GK"),None)
    if not off or not on:return False
    off["on"]=False;on["on"]=True;g["subs"]+=1
    log(f"🔁 {on['name']} replaces {off['name']}. Fresh legs enter the match!","Substitution","Completed")
    return True

def football_svg(x,y):
    return f'''<g transform="translate({x} {y})"><circle r="11" fill="#fff" stroke="#0e1721" stroke-width="2.5"/><path d="M0,-5 L5,-2 L3,5 L-3,5 L-5,-2Z" fill="#111923"/><path d="M-5,-2 L-9,-6 M5,-2 L9,-6 M-3,5 L-7,9 M3,5 L7,9" stroke="#111923" stroke-width="1.8"/></g>'''

def pitch_html():
    g=st.session_state.game
    old=(g.get("animation") or {}).get("before",[g["ball"],g["zone"],g["lane"]])
    new=(g.get("animation") or {}).get("after",[g["ball"],g["zone"],g["lane"]])
    seed=(g.get("animation") or {}).get("seed",0)
    def ballpos(info):
        side,zone,lane=info
        x=({1:300,2:490,3:640} if side=="home" else {1:650,2:455,3:255})[zone]
        y={"Left":117,"Center":210,"Right":303}.get(lane,210)
        return x,y
    x0,y0=ballpos(old); x1,y1=ballpos(new)
    # Dynamic formations: markers shift to where play happens, with coordinated run animation on each new decision.
    shift=(g["zone"]-1)*25*(1 if g["ball"]=="home" else -1)
    homepos=[(65,210),(176,68),(175,161),(175,255),(176,346),(340,100),(325,210),(340,319),(490,95),(518,209),(490,321)]
    awaypos=[(895,210),(780,68),(780,161),(780,255),(780,346),(632,100),(650,210),(632,319),(470,95),(443,209),(470,321)]
    svg=['''<svg viewBox="0 0 960 420" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated soccer match with moving players and ball">
    <defs><linearGradient id="turf" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#19754b"/><stop offset="1" stop-color="#146842"/></linearGradient>
    <filter id="shadow"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity=".45"/></filter></defs>
    <rect width="960" height="420" fill="url(#turf)"/>''']
    for i in range(12):
        if i%2==0:svg.append(f'<rect x="{i*80}" y="0" width="80" height="420" fill="white" opacity=".035"/>')
    svg+=['''<rect x="30" y="25" width="900" height="370" fill="none" stroke="#dceede" stroke-width="2.5"/>
    <line x1="480" x2="480" y1="25" y2="395" stroke="white" stroke-width="2" opacity=".8"/>
    <circle cx="480" cy="210" r="63" fill="none" stroke="white" stroke-width="2" opacity=".8"/>
    <circle cx="480" cy="210" r="3" fill="white"/>
    <rect x="30" y="106" width="138" height="208" fill="none" stroke="white" stroke-width="2"/>
    <rect x="792" y="106" width="138" height="208" fill="none" stroke="white" stroke-width="2"/>
    <rect x="30" y="160" width="51" height="100" fill="none" stroke="white" stroke-width="2"/>
    <rect x="879" y="160" width="51" height="100" fill="none" stroke="white" stroke-width="2"/>
    <rect x="14" y="173" width="16" height="75" rx="2" fill="#e8f5ff" fill-opacity=".42" stroke="white" stroke-width="3"/>
    <rect x="930" y="173" width="16" height="75" rx="2" fill="#e8f5ff" fill-opacity=".42" stroke="white" stroke-width="3"/>''']
    # Animate runners by a slight run-in from prior positions; each action induces a new animation.
    for side,poses,color in [("home",homepos,"#ffcb47"),("away",awaypos,"#d6eaff")]:
        for j,(x,y) in enumerate(poses):
            delta=shift*(1 if side=="home" else .6)
            x=clamp(x+delta,43,916)
            # movement affects midfield / forwards most; keep GK close to its own goal
            if j==0:x=65 if side=="home" else 895
            lane_delta={"Left":-15,"Center":0,"Right":15}[g["lane"]] if j>4 else 0
            y=clamp(y+lane_delta,40,379)
            dx=(-18 if side=="home" else 18)*(0 if j==0 else 1)
            dy=(7 if j%2 else -7) if j else 0
            svg.append(f'''<g filter="url(#shadow)" transform="translate({x:.1f} {y:.1f})">
             <animateTransform attributeName="transform" type="translate" from="{x+dx:.1f} {y+dy:.1f}" to="{x:.1f} {y:.1f}" dur=".9s" fill="freeze" begin=".05s"/>
             <circle r="14.5" fill="{color}" stroke="#132c2c" stroke-width="3"/>
             <text text-anchor="middle" dominant-baseline="central" font-family="Arial" font-weight="bold" font-size="12" fill="#152c2b">{j+1}</text></g>''')
    svg.append(f'''<g filter="url(#shadow)">{football_svg(0,0)}
      <animateTransform attributeName="transform" type="translate" from="{x0} {y0}" to="{x1} {y1}" dur="1.1s" fill="freeze" begin=".2s"/>
      </g>''')
    # football_svg uses its own nested transform (0,0); ball is always independently visible.
    svg.append(f'''<text x="480" y="18" text-anchor="middle" fill="#e7ffe9" font-weight="bold" font-family="Arial" font-size="15">{escape(g['clubs']['home'])}  •  ATTACK →</text>''')
    svg.append('</svg>')
    return '''<!doctype html><html><body style="margin:0;background:#103b2d"><div style="width:100%;overflow:hidden">'''+''.join(svg)+'''</div></body></html>'''

def pct(a,b): return f"{100*a/b:.1f}%" if b else "—"
def events_csv():
    o=io.StringIO();cols=["minute","team","action","outcome","probability","xG","commentary"]
    w=csv.DictWriter(o,fieldnames=cols);w.writeheader();w.writerows(st.session_state.game["events"])
    return o.getvalue()

st.title("⚽ SPORTS BY THE NUMBERS  |  SOCCER MANAGER 2")
st.caption("Move the ball. Read the channels. Outsmart the goalkeeper. Make probability-based decisions.")
if "game" not in st.session_state:
    st.markdown("### 🏟️ Set up your match")
    a,b,c,d=st.columns(4)
    home=a.selectbox("Your club",list(NAMES))
    away=b.selectbox("Opponent",[x for x in NAMES if x!=home])
    formation=c.selectbox("Formation",["4-3-3","4-4-2","3-5-2"])
    tactic=d.selectbox("Tactic",TACTICS)
    st.info("Fictional player ratings for classroom play. The probabilities are modeled, not real-world measurements. The moving pitch is an animated tactical visualization, not a full physics engine.")
    if st.button("⚽ KICK OFF",type="primary",use_container_width=True):
        create_game(home,away,formation,tactic);st.rerun()
    st.stop()
g=st.session_state.game
h,a=g["stats"]["home"],g["stats"]["away"]
top=st.columns([2,1.3,2,1])
top[0].markdown(f"### 🟡 {g['clubs']['home']}")
top[1].metric("SCORE",f"{h['goals']} – {a['goals']}")
top[2].markdown(f"### ⚪ {g['clubs']['away']}")
top[3].metric("TIME",f"{g['minute']}'")
left,right=st.columns([1.85,1],gap="large")
with left:
    components.html(pitch_html(),height=355,scrolling=False)
    st.caption("Players run to new positions after each decision. Numbered yellow/white markers are players; the black-and-white football is the ball. You attack right.")
    if g["finished"]:
        st.success(f"🏁 FULL TIME — {g['clubs']['home']} {h['goals']}–{a['goals']} {g['clubs']['away']}")
    else:
        if g["ball"]=="home":
            st.markdown(f"<div class='playbox'><b>🟡 IN POSSESSION</b> • Zone {g['zone']}/3 • Ball in the {g['lane']} channel</div>",unsafe_allow_html=True)
            st.markdown(f"<div class='scout'>🔎 <b>Scouting:</b> Opponent's strongest defensive coverage: <b>{g['danger_lane']}</b>. Goalkeeper tends to protect: <b>{g['keeper_bias']}</b>. Choose where to attack.</div>",unsafe_allow_html=True)
            lane=st.radio("Attack down which channel?",LANES,index=LANES.index(g["lane"]),horizontal=True)
            power=st.slider("Shot power (aim for the sweet spot for this distance)",35,100,70,5)
            desired={1:90,2:77,3:61}[g["zone"]]
            st.caption(f"Coaching clue: From zone {g['zone']}, around **{desired}% power** provides the best accuracy. Different aim and power decisions change shot xG.")
            options=["Safe pass","Through ball","Cross","Shoot"]
            probs={o:(shot_chance(lane,power)[0] if o=="Shoot" else pass_chance(o,lane)) for o in options}
            cols=st.columns(4)
            for i,o in enumerate(options):
                if cols[i].button(f"{o} · {probs[o]:.0%}",key="play_"+o,type="primary" if o=="Shoot" else "secondary",use_container_width=True):
                    act(o,lane,power);st.rerun()
        else:
            st.markdown(f"<div class='playbox'><b>⚪ DEFEND!</b> • Opposition danger zone {g['zone']}/3</div>",unsafe_allow_html=True)
            st.markdown(f"<div class='scout'>📋 <b>Analyst warning:</b> Their most likely attacking channel is <b>{g['danger_lane']}</b>. Anticipate the passing lane and choose your defensive approach.</div>",unsafe_allow_html=True)
            lane=st.radio("Cover which channel?",LANES,index=LANES.index(g["danger_lane"]),horizontal=True)
            options=["Press","Contain","Counter trap"]
            cols=st.columns(3)
            for i,o in enumerate(options):
                p=defensive_chance(o,lane)
                if cols[i].button(f"{o} · {p:.0%}",key="def_"+o,use_container_width=True):
                    act(o,lane,70);st.rerun()
    st.markdown(f"<div class='commentary'><b>🎙️ MATCH CALL:</b> {escape(g['last'])}</div>",unsafe_allow_html=True)
    with st.expander("📻 Play-by-play",expanded=False):
        for e in reversed(g["events"][-20:]):st.write(f"{e['minute']}' • {e['commentary']}")
with right:
    st.markdown("#### 📊 LIVE STATISTICS")
    rows=[("Shots",h["shots"],a["shots"]),("Goals",h["goals"],a["goals"]),
          ("Shots on target",h["on_target"],a["on_target"]),("Expected goals",f"{h['xg']:.2f}",f"{a['xg']:.2f}"),
          ("Pass accuracy",pct(h["passes_ok"],h["passes"]),pct(a["passes_ok"],a["passes"])),
          ("Tackles won",f"{h['tackles_ok']}/{h['tackles']}",f"{a['tackles_ok']}/{a['tackles']}"),
          ("Goalkeeper saves",h["saves"],a["saves"])]
    for name,v1,v2 in rows:
        s=st.columns([1,1.8,1]);s[0].markdown(f"**{v1}**");s[1].caption(name);s[2].markdown(f"**{v2}**")
    st.divider()
    st.markdown("#### 🧠 MANAGER'S OFFICE")
    new_tactic=st.selectbox("Team tactics",TACTICS,index=TACTICS.index(g["tactic"]),disabled=g["finished"])
    if new_tactic!=g["tactic"] and not g["finished"]:
        g["tactic"]=new_tactic;log(f"📋 Formation stays {g['formation']}, tactical approach changed to {new_tactic}.","Tactic",new_tactic);st.rerun()
    starters=[p for p in active("home") if p["role"]!="GK"]
    subs=[p for p in g["players"]["home"] if not p["on"] and p["role"]!="GK"]
    with st.expander(f"🔁 Substitutions ({g['subs']}/3)"):
        if subs and g["subs"]<3 and not g["finished"]:
            outgoing=st.selectbox("Player to replace",starters,format_func=lambda p:f"{p['name']} · {p['role']} · {p['stamina']:.0f}% energy")
            incoming=st.selectbox("Replacement",subs,format_func=lambda p:f"{p['name']} · {p['role']} · {p['stamina']:.0f}% energy")
            if st.button("Make substitution",use_container_width=True):
                if substitute(outgoing["id"],incoming["id"]):st.rerun()
        else:st.write("No substitutions available.")
    with st.expander("👥 Player scouting & fatigue"):
        for p in active("home"):
            st.caption(f"{p['name']} ({p['role']}) | Pass {p['passing']} | Shot {p['shooting']} | Defense {p['defense']} | Energy {p['stamina']:.0f}%")
    st.caption(f"Formation: {g['formation']} · Decisions: {g['choices']} · Fatigue lowers skill effectiveness")
if g["finished"]:
    st.divider();st.subheader("🏆 POSTMATCH DATA LAB")
    st.write(f"Final: **{h['goals']}–{a['goals']}** | Expected goals: **{h['xg']:.2f}–{a['xg']:.2f}**")
    st.write(f"Your shooting conversion: **{pct(h['goals'],h['shots'])}** | Passing: **{pct(h['passes_ok'],h['passes'])}** | Defending: **{pct(h['tackles_ok'],h['tackles'])}**")
    st.download_button("⬇️ Download all match events (CSV)",events_csv(),"soccer_manager_v2_events.csv",mime="text/csv")
    with st.expander("Student reflection questions"):
        st.write("1. Did a lower-probability decision work out? Give evidence from the log.")
        st.write("2. How did shot aim, shot power, and shot location affect predicted xG?")
        st.write("3. Did your actual goal total exceed or fall below xG? Explain why both are possible.")
        st.write("4. Did fatigue or substitutions change your strategy?")
with st.expander("About the simulator"):
    st.write("This is a classroom probability model using fictional ratings. The moving pitch is a tactical animation, not continuous independent player tracking. The displayed probabilities represent model estimates; a random draw determines success or failure. No actual football statistics feed the engine yet.")
if st.button("🔄 Start another match"):
    del st.session_state.game;st.rerun()
