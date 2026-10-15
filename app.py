import csv
import io
import math
import random
import time
from html import escape

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Sports by the Numbers | Soccer Manager 5", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")
st.markdown('''<style>
.block-container {max-width:1120px;padding-top:.45rem;padding-bottom:1rem}
header[data-testid="stHeader"]{height:2.2rem}
h1{font-size:1.55rem!important;margin:.1rem 0!important}
[data-testid="stVerticalBlock"]{gap:.65rem}
div.stButton>button{min-height:4rem;font-size:1.15rem;font-weight:800;border-radius:13px}
[data-testid="stTextInput"] input{font-size:1.55rem;min-height:3.5rem}
[data-testid="stFormSubmitButton"] button{min-height:4rem;font-size:1.2rem}
.livecall{background:#142f3c;color:#fff;border-radius:12px;padding:13px 17px;font-size:1.12rem;font-weight:650}
.resultcall{background:#eaf6ee;color:#173a29;border-radius:10px;padding:10px 15px;font-size:1rem}
.mathstage{background:#142f3c;color:#fff;padding:18px 22px;border-radius:16px}
.scorecard{background:#112d37;color:white;border-radius:16px;padding:12px 22px;display:flex;align-items:center;justify-content:space-between;gap:10px}
.scorecard .club{font-weight:900;font-size:clamp(1rem,2.3vw,1.45rem);width:33%}
.scorecard .score{font-size:clamp(2rem,5vw,3.2rem);font-weight:950;white-space:nowrap}
.scorecard .minute{font-size:1rem;color:#f6d16b;text-align:center}
[data-testid="stCaptionContainer"]{font-size:.9rem}
</style>''', unsafe_allow_html=True)

# Named-player snapshots for a classroom simulation (not live rosters or official ratings).
# Lists contain one goalkeeper, four defenders, three midfielders, three forwards, then three reserves.
NAMES = {
    "Arsenal": ["David Raya","William Saliba","Gabriel Magalhães","Jurrien Timber","Riccardo Calafiori","Declan Rice","Martin Ødegaard","Mikel Merino","Bukayo Saka","Kai Havertz","Gabriel Martinelli","Ben White","Ethan Nwaneri","Leandro Trossard"],
    "Real Madrid": ["Thibaut Courtois","Antonio Rüdiger","Éder Militão","Dean Huijsen","Trent Alexander-Arnold","Jude Bellingham","Federico Valverde","Aurélien Tchouaméni","Kylian Mbappé","Vinícius Júnior","Rodrygo","Dani Carvajal","Arda Güler","Endrick"],
    "Barcelona": ["Joan García","Jules Koundé","Pau Cubarsí","Alejandro Balde","Ronald Araújo","Pedri","Gavi","Frenkie de Jong","Lamine Yamal","Raphinha","Robert Lewandowski","Eric García","Dani Olmo","Ferran Torres"],
    "Liverpool": ["Alisson Becker","Virgil van Dijk","Ibrahima Konaté","Joe Gomez","Andy Robertson","Alexis Mac Allister","Dominik Szoboszlai","Ryan Gravenberch","Mohamed Salah","Cody Gakpo","Hugo Ekitiké","Conor Bradley","Curtis Jones","Federico Chiesa"],
    "Manchester City": ["Gianluigi Donnarumma","Rúben Dias","Joško Gvardiol","John Stones","Rico Lewis","Rodri","Bernardo Silva","Phil Foden","Erling Haaland","Jérémy Doku","Omar Marmoush","Nathan Aké","Mateo Kovačić","Savinho"],
    "Bayern Munich": ["Manuel Neuer","Dayot Upamecano","Jonathan Tah","Alphonso Davies","Konrad Laimer","Joshua Kimmich","Leon Goretzka","Jamal Musiala","Harry Kane","Michael Olise","Luis Díaz","Kim Min-jae","Aleksandar Pavlović","Serge Gnabry"],
    "Paris Saint-Germain": ["Gianluigi Donnarumma","Achraf Hakimi","Marquinhos","Willian Pacho","Nuno Mendes","Vitinha","João Neves","Fabián Ruiz","Ousmane Dembélé","Khvicha Kvaratskhelia","Désiré Doué","Lucas Hernández","Warren Zaïre-Emery","Bradley Barcola"],
    "Inter Miami": ["Óscar Ustari","Jordi Alba","Maximiliano Falcón","Tomás Avilés","Ian Fray","Sergio Busquets","Rodrigo De Paul","Federico Redondo","Lionel Messi","Luis Suárez","Tadeo Allende","Noah Allen","Benjamin Cremaschi","Telasco Segovia"],
}
TEAM_COLORS={
    "Arsenal":"#ed3a3a","Real Madrid":"#d2caff","Barcelona":"#b93e72",
    "Liverpool":"#ee4747","Manchester City":"#88d6f7","Bayern Munich":"#f06a70",
    "Paris Saint-Germain":"#3760b5","Inter Miami":"#ff9cc5"}

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
def create_game(home,away,formation,tactic,math_mode):
    st.session_state.game=dict(clubs={"home":home,"away":away},players={"home":roster(home),"away":roster(away)},
      formation=formation,tactic=tactic,math_mode=math_mode,math_by_grade={5:{"correct":0,"total":0},6:{"correct":0,"total":0},7:{"correct":0,"total":0}},minute=0,ball="home",zone=1,lane="Center",stats={"home":stats(),"away":stats()},
      events=[],last="Kickoff! Study the defense and create your first attack.",finished=False,half=False,subs=0,choices=0,
      danger_lane=random.choice(LANES),keeper_bias=random.choice(LANES),animation=None,challenge=None,math_correct=0,math_total=0,math_times=[],math_last="")
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

def act(action,lane,power,math_modifier=0):
    g=st.session_state.game
    if g["finished"]:return
    old=(g["ball"],g["zone"],g["lane"])
    g["choices"]+=1
    result="pass"
    if g["ball"]=="home":
        if action=="Shoot":
            chance,_=shot_chance(lane,power)
            chance=clamp(chance+math_modifier,.01,.85)
            result=shoot("home",chance,"Shot",lane)
        else:
            chance=clamp(pass_chance(action,lane)+math_modifier,.05,.99)
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
        chance=clamp(defensive_chance(action,lane)+math_modifier,.05,.97)
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

# One decision = one math challenge. Server timestamps determine the result (not the browser countdown).
MATH_LEVELS={
    "Safe pass": ("Rookie",18,.055,-.12),
    "Contain": ("Rookie",18,.055,-.12),
    "Press": ("Intermediate",13,.075,-.14),
    "Cross": ("Intermediate",13,.085,-.14),
    "Through ball": ("Expert",10,.12,-.17),
    "Counter trap": ("Expert",10,.12,-.17),
    "Shoot": ("Expert",10,.12,-.17),
}

# NJSLS Mathematics (2023) aligned quick questions. The displayed codes identify
# the mathematical skill being rehearsed; individual prompts are brief practice,
# not complete assessments of their standards.
MATH_MODES = ["Mixed review (5–7)", "Grade 5 review", "Grade 6 review", "Grade 7 focus"]

def select_grade(mode):
    if mode == "Grade 5 review": return 5
    if mode == "Grade 6 review": return 6
    if mode == "Grade 7 focus": return 7
    return random.choices([5,6,7], weights=[30,35,35], k=1)[0]

def make_question(grade, level):
    """Returns prompt, numeric answer, standard, strand, explanatory solution."""
    kind=random.choice(["a","b","c","d","e"])
    if grade==5:
        if kind=="a":
            a,b,c=random.randint(3,12),random.randint(2,9),random.randint(2,6)
            return f"A soccer drill has {a} groups of ({b} + {c}) cones. How many cones?",a*(b+c),"5.OA.A.1","Expressions",f"{a} × ({b} + {c}) = {a*(b+c)}"
        if kind=="b":
            a,b=random.randint(12,65),random.randint(10,35)
            return f"A team runs {a/10:.1f} km in the morning and {b/10:.1f} km in the afternoon. Total km?",(a+b)/10,"5.NBT.B.7","Decimals",f"{a/10:.1f} + {b/10:.1f} = {(a+b)/10:.1f} km"
        if kind=="c":
            a,b=random.randint(2,8),random.randint(2,8)
            return f"A practice zone is {a}/2 m long and {b} m wide. What is its area (m²)?",a*b/2,"5.NF.B.4b","Fractional area",f"({a}/2) × {b} = {a*b/2:g} m²"
        if kind=="d":
            a,b=random.randint(2,9),random.randint(2,9)
            return f"Player A is at ({a}, {b}) on a coordinate grid. What is the x-coordinate?",a,"5.G.A.1","Coordinates",f"In (x, y), the first coordinate is x = {a}."
        a,b=random.randint(2,7),random.choice([2,4,5,10]);value=a*b
        return f"The goalie practices {value} minutes in {b} equal sessions. Minutes each?",a,"5.NBT.B.6","Division",f"{value} ÷ {b} = {a} minutes"
    if grade==6:
        if kind=="a":
            goals,games=random.randint(2,8),random.randint(2,7)
            return f"A forward scored {goals*games} goals in {games} games. Goals per game?",goals,"6.RP.A.2","Unit rates",f"{goals*games} ÷ {games} = {goals} goals per game"
        if kind=="b":
            attempts,made=random.choice([(10,7),(20,12),(20,17),(10,6),(25,15)])
            return f"A player made {made} of {attempts} passes. What percent succeeded?",100*made/attempts,"6.RP.A.3","Percent review",f"{made} ÷ {attempts} × 100 = {100*made/attempts:g}%"
        if kind=="c":
            a,b=random.randint(2,15),random.randint(1,12)
            return f"The temperature starts at −{a}°C and rises {b}°. What is the new temperature?",-a+b,"6.NS.C.5","Integers",f"−{a} + {b} = {-a+b}°C"
        if kind=="d":
            a,b=random.randint(2,8),random.randint(3,10)
            return f"There are {a} rows of {b} seats in a stadium section. How many seats?",a*b,"6.EE.A.2","Expressions",f"{a} × {b} = {a*b}"
        a,b=random.randint(4,15),random.randint(3,12)
        return f"Two training sessions lasted {a} and {b} minutes. What's their mean duration?",(a+b)/2,"6.SP.B.5","Statistics",f"({a} + {b}) ÷ 2 = {(a+b)/2:g} minutes"
    # Grade 7
    if kind=="a":
        made,attempts=random.choice([(9,12),(12,20),(14,20),(16,25),(18,30)])
        return f"A winger completes {made} of {attempts} crosses. What percent succeed?",100*made/attempts,"7.RP.A.3","Proportions",f"{made}/{attempts} × 100 = {100*made/attempts:g}%"
    if kind=="b":
        a,b=random.randint(-14,-2),random.randint(4,16)
        return f"A team gains {b} meters, then loses {abs(a)} meters. Net change (m)?",b+a,"7.NS.A.1","Rational numbers",f"{b} + ({a}) = {b+a} m"
    if kind=="c":
        x,k=random.randint(3,13),random.randint(2,7)
        return f"A defender's rating satisfies x + {k} = {x+k}. What is x?",x,"7.EE.B.4","Equations",f"Subtract {k} from both sides: x = {x}"
    if kind=="d":
        a,b=random.randint(2,8),random.randint(2,7)
        return f"A triangular training zone has base {a*2} m and height {b} m. What is its area (m²)?",a*b,"7.G.B.6","Geometry",f"½ × {a*2} × {b} = {a*b} m²"
    goals,shots=random.choice([(3,10),(4,20),(7,20),(6,25),(9,30)])
    return f"A striker scored on {goals} of {shots} attempts. Experimental probability as a percent?",100*goals/shots,"7.SP.C.6","Probability",f"{goals} ÷ {shots} × 100 = {100*goals/shots:g}%"

def begin_challenge(action,lane,power):
    g=st.session_state.game
    if g["finished"] or g.get("challenge") is not None:return
    level,seconds,bonus,penalty=MATH_LEVELS[action]
    grade=select_grade(g["math_mode"])
    question,answer,standard,strand,solution=make_question(grade,level)
    # Multi-step, conceptual content gets more time than basic arithmetic.
    seconds += {5:7,6:14,7:20}[grade]
    g["challenge"]=dict(action=action,lane=lane,power=power,level=level,seconds=seconds,
      bonus=bonus,penalty=penalty,question=question,answer=answer,grade=grade,standard=standard,strand=strand,solution=solution,started=time.time(),token=random.randint(100000,999999))

def submit_challenge(text):
    g=st.session_state.game
    c=g.get("challenge")
    if not c or g["finished"]:return
    elapsed=time.time()-c["started"]
    try:correct=(float(text.strip())==c["answer"])
    except (ValueError,AttributeError):correct=False
    within=elapsed<=c["seconds"]
    won=correct and within
    # Quick accurate answers earn the full reward, slower accurate answers get a smaller boost.
    speed=clamp((c["seconds"]-elapsed)/c["seconds"],0,1)
    modifier=(c["bonus"]*(.65+.35*speed)) if won else c["penalty"]
    g["math_total"]+=1
    g["math_by_grade"][c["grade"]]["total"]+=1
    if won:g["math_by_grade"][c["grade"]]["correct"]+=1
    if won:g["math_correct"]+=1;g["math_times"].append(round(elapsed,1))
    outcome=(f"✅ Correct in {elapsed:.1f}s — success chance boosted by {modifier:+.1%}." if won else
             f"{'⌛ Time expired' if not within else '❌ Incorrect'} — correct answer: {c['answer']}. Chance adjusted by {modifier:+.1%}.")
    outcome += f"  |  Grade {c['grade']} · {c['standard']} · {c['solution']}"
    g["math_last"]=outcome
    action,lane,power=c["action"],c["lane"],c["power"]
    g["challenge"]=None
    act(action,lane,power,modifier)

def countdown_html(deadline):
    left=max(0,deadline-time.time())
    return f'''<!doctype html><html><body style="margin:0;background:#132d39;color:#fff;font-family:Arial,sans-serif">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;padding:10px 14px;border-radius:10px">
    <b>⏱ ANSWER BEFORE THE WHISTLE</b><strong id="sec" style="font-size:29px;color:#ffce5b">{left:.1f}s</strong></div>
    <script>const deadline=Date.now()+{int(left*1000)};setInterval(()=>{{let x=Math.max(0,(deadline-Date.now())/1000);
    document.getElementById('sec').textContent=x.toFixed(1)+'s';document.getElementById('sec').style.color=x<4?'#ff6b6b':'#ffce5b';}},100);</script>
    </body></html>'''

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
    for side,poses,color in [("home",homepos,TEAM_COLORS[g["clubs"]["home"]]),("away",awaypos,TEAM_COLORS[g["clubs"]["away"]])]:
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

    svg.append('</svg>')
    return '''<!doctype html><html><body style="margin:0;background:#103b2d"><div style="width:100%;overflow:hidden">'''+''.join(svg)+'''</div></body></html>'''

def pct(a,b): return f"{100*a/b:.1f}%" if b else "—"
def events_csv():
    o=io.StringIO();cols=["minute","team","action","outcome","probability","xG","commentary"]
    w=csv.DictWriter(o,fieldnames=cols);w.writeheader();w.writerows(st.session_state.game["events"])
    return o.getvalue()

st.title("⚽ SPORTS BY THE NUMBERS · SOCCER")
if "game" not in st.session_state:
    st.subheader("🏟️ Choose your match")
    x,y=st.columns(2)
    home=x.selectbox("YOUR CLUB",list(NAMES))
    away=y.selectbox("OPPONENT",[c for c in NAMES if c!=home])
    math_mode=st.selectbox("MATH LEVEL",MATH_MODES)
    st.caption("Real club and player names, fictional gameplay ratings. Player lists are illustrative historical snapshots, not guaranteed current transfers or lineups.")
    if st.button("⚽ KICK OFF",type="primary",use_container_width=True):
        create_game(home,away,"4-3-3","Balanced",math_mode)
        st.rerun()
    st.stop()

g=st.session_state.game
h,a=g["stats"]["home"],g["stats"]["away"]
score=(f'<div class="scorecard"><div class="club" style="color:{TEAM_COLORS[g["clubs"]["home"]]}">{escape(g["clubs"]["home"])}</div>'
       f'<div style="text-align:center"><div class="score">{h["goals"]} – {a["goals"]}</div><div class="minute">{g["minute"]} min · {"FULL TIME" if g["finished"] else "LIVE MATCH"}</div></div>'
       f'<div class="club" style="text-align:right;color:{TEAM_COLORS[g["clubs"]["away"]]}">{escape(g["clubs"]["away"])}</div></div>')
st.markdown(score,unsafe_allow_html=True)
components.html(pitch_html(),height=465,scrolling=False)
st.markdown(f'<div class="livecall">🎙️ {escape(g["last"])}</div>',unsafe_allow_html=True)
if g.get("math_last"):
    st.markdown(f'<div class="resultcall">{escape(g["math_last"].split("  |  ")[0])}</div>',unsafe_allow_html=True)

if g["finished"]:
    st.success("🏁 FULL TIME! Open the Match Report for the data.")
elif g.get("challenge"):
    c=g["challenge"]
    st.markdown(f'### 🧠 {c["action"].upper()} · Grade {c["grade"]} math')
    st.markdown(f'**{c["question"]}**')
    st.caption(f'{c["standard"]} · {c["seconds"]} seconds · {c["level"]} risk')
    components.html(countdown_html(c["started"]+c["seconds"]),height=74,scrolling=False)
    with st.form(key=f'math_{c["token"]}'):
        answer=st.text_input('YOUR ANSWER',placeholder='Type a number',key=f'answer_{c["token"]}')
        submit=st.form_submit_button('⚽ SUBMIT & PLAY',type='primary',use_container_width=True)
    if submit:
        submit_challenge(answer);st.rerun()
else:
    st.markdown('### ' + ('⚡ YOUR MOVE' if g["ball"]=="home" else '🛡️ DEFEND'))
    # Only one compact choice of direction. Tactical options are intentionally removed.
    lane=st.segmented_control('PLAY DIRECTION',LANES,default=g["lane"],key=f'lane_{g["choices"]}')
    lane=lane or 'Center'
    if g["ball"]=="home":
        st.caption('Low risk = more time. High risk = bigger reward and a tougher math question.')
        actions=[('Safe pass','🟢 SAFE PASS'),('Through ball','⚡ ATTACK'),('Cross','↗️ CROSS'),('Shoot','🥅 SHOOT')]
    else:
        st.caption('Stop their attack with a math challenge. Choose how aggressively to defend.')
        actions=[('Contain','🟢 CONTAIN'),('Press','🛡️ PRESS'),('Counter trap','⚡ COUNTER')]
    columns=st.columns(len(actions))
    for col,(action,label) in zip(columns,actions):
        if col.button(label,key=f'v5_{g["choices"]}_{action}',use_container_width=True,type='primary' if action in ('Shoot','Counter trap') else 'secondary'):
            begin_challenge(action,lane,70);st.rerun()

with st.expander('📊 Match report, players & teacher details',expanded=g["finished"]):
    col1,col2,col3,col4=st.columns(4)
    col1.metric('Shots',f'{h["shots"]} – {a["shots"]}')
    col2.metric('xG',f'{h["xg"]:.2f} – {a["xg"]:.2f}')
    col3.metric('Passing',pct(h['passes_ok'],h['passes']))
    col4.metric('Math solved',f'{g["math_correct"]}/{g["math_total"]}')
    for grade,results in g['math_by_grade'].items():
        st.write(f'**Grade {grade}:** {results["correct"]}/{results["total"]} correct on time')
    st.markdown('**Players on the field**')
    for team in ['home','away']:
        st.caption(g['clubs'][team]+': '+', '.join(p['name'] for p in active(team)))
    if not g['finished']:
        with st.expander(f'Optional substitutions ({g["subs"]}/3)'):
            starters=[p for p in active('home') if p['role']!='GK']
            bench=[p for p in g['players']['home'] if not p['on'] and p['role']!='GK']
            if g['subs']<3 and bench:
                out=st.selectbox('Replace',starters,format_func=lambda p:f'{p["name"]} ({p["stamina"]:.0f}% stamina)')
                incoming=st.selectbox('Bring on',bench,format_func=lambda p:p['name'])
                if st.button('Make substitution'):
                    substitute(out['id'],incoming['id']);st.rerun()
    with st.expander('Full play-by-play'):
        for e in reversed(g['events'][-35:]): st.write(f"{e['minute']} min · {e['commentary']}")
    if g['finished']:
        st.download_button('⬇️ Export event log (CSV)',events_csv(),'soccer_v5_events.csv',mime='text/csv')
        st.write('**Student reflection:** Did the team outperform its expected goals? Which math strands were hardest?')
    st.caption('Game ratings and success percentages are fictional estimates. Player names are recognizable club snapshots, not a live transfer database or licensed product.')
if st.button('🔄 New match'):
    del st.session_state.game;st.rerun()
