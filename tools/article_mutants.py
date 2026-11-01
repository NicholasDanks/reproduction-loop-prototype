"""Article mutants: hold the genuine package fixed, mutate what the ARTICLE says; a clause that still passes is vacuous."""
import copy, sys, json
from pathlib import Path
sys.path.insert(0, "tools"); import claim_tests as ct
PKG = Path(sys.argv[1])
BASE = copy.deepcopy(ct.ARTICLE_T1); B_DV, B_PERF, B_PERS = list(ct.DV_ORDER), list(ct.PERF_CONTROLS), list(ct.PERSONALITY)
def reset():
    ct.ARTICLE_T1 = copy.deepcopy(BASE); ct.DV_ORDER = list(B_DV); ct.PERF_CONTROLS = list(B_PERF); ct.PERSONALITY = list(B_PERS)
def setv(panel, kind, i, v): ct.ARTICLE_T1[panel][kind][i] = v
M = [
 ("A01 top b1 0.189->0.198", "VALUE top coefficients", lambda: setv("top","b",0,0.198)),
 ("A02 top b5 sign -0.045->0.045", "VALUE top coefficients", lambda: setv("top","b",4,0.045)),
 ("A03 bottom b3 0.250->0.205", "VALUE bottom coefficients", lambda: setv("bottom","b",2,0.205)),
 ("A04 top se2 0.102->0.120", "VALUE top standard errors", lambda: setv("top","se",1,0.120)),
 ("A05 bottom se5 0.129->0.192", "VALUE bottom standard errors", lambda: setv("bottom","se",4,0.192)),
 ("A06 swap top cols 1,2", "VALUE top coefficients", lambda: ct.ARTICLE_T1["top"].__setitem__("b", [BASE["top"]["b"][1], BASE["top"]["b"][0]] + BASE["top"]["b"][2:])),
 ("A07 article says N=418", "DESIGN top N", lambda: ct.ARTICLE_T1.__setitem__("N", 418)),
 ("A08 DV order: Switching first", "DESIGN column order", lambda: setattr(ct, "DV_ORDER", [B_DV[1], B_DV[0]] + B_DV[2:])),
 ("A09 perf controls named 15,25,90", "DESIGN performance controls", lambda: setattr(ct, "PERF_CONTROLS", ["performance_15","performance_25","performance_90"])),
 ("A10 personality adds 'stdgrit'", "DESIGN lower panel controls", lambda: setattr(ct, "PERSONALITY", B_PERS + ["stdgrit"])),
]
reset(); base = ct.stata_clauses(PKG)
out = []
for name, target, f in M:
    reset(); f(); r = ct.stata_clauses(PKG)
    changed = [k for k in r if r[k] != base[k]]
    hit = [k for k in changed if k.startswith(target.split(" ",1)[0]) and target.split(" ",1)[1] in k]
    out.append(dict(mutant=name, target=target, flipped=changed, caught=bool(hit)))
    print(f"{name:36s} caught={bool(hit)!s:5s} flipped={changed}")
reset()
print("baseline failing clauses (fidelity flags):", [k for k,v in base.items() if not v])
json.dump(out, open(sys.argv[2], "w"), indent=1)
