import math, sys
from pathlib import Path
def hexagon(cx, cy, r):
    return [(cx + r*math.cos(math.radians(ANG+60*i)), cy + r*math.sin(math.radians(ANG+60*i))) for i in range(6)]
def seg_inter(p1,p2,p3,p4):
    (x1,y1),(x2,y2),(x3,y3),(x4,y4)=p1,p2,p3,p4
    d=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    if abs(d)<1e-9: return None
    t=((x1-x3)*(y3-y4)-(y1-y3)*(x3-x4))/d; u=-((x1-x2)*(y1-y3)-(y1-y2)*(x1-x3))/d
    if 0<=t<=1 and 0<=u<=1: return (x1+t*(x2-x1), y1+t*(y2-y1))
def crossings(A,B):
    out=[]
    for i in range(6):
        for j in range(6):
            p=seg_inter(A[i],A[(i+1)%6],B[j],B[(j+1)%6])
            if p and all(abs(p[0]-q[0])+abs(p[1]-q[1])>0.5 for q in out): out.append(p)
    return out
ANG=float(sys.argv[8]) if len(sys.argv)>8 else 90
r=float(sys.argv[1]); dx=float(sys.argv[2]); yR=float(sys.argv[3]); yGB=float(sys.argv[4]); rad=float(sys.argv[5]); w=float(sys.argv[6]); out=sys.argv[7]
R=hexagon(32,yR,r); G=hexagon(32-dx,yGB,r); B=hexagon(32+dx,yGB,r)
def path(P): return "M"+" L".join(f"{x:.2f} {y:.2f}" for x,y in P)+" Z"
cRG=sorted(crossings(R,G)); cRB=sorted(crossings(R,B)); cGB=sorted(crossings(G,B), key=lambda p:p[1])
FLIP=len(sys.argv)>9 and sys.argv[9]=="flip"
patches=([("G",cRG[0]),("R",cRG[1]),("R",cRB[0]),("B",cRB[1]),("G",cGB[0]),("B",cGB[1])] if FLIP
         else [("R",cRG[0]),("G",cRG[1]),("B",cRB[0]),("R",cRB[1]),("G",cGB[0]),("B",cGB[1])])
rings={"R":(R,"#d62828"),"G":(G,"#3b3f47"),"B":(B,"#2f6fed")}
halo=w+2.6; bg="#ffffff"
defs="".join(f'<clipPath id="c{i}"><circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="{rad}"/></clipPath>' for i,(_,p) in enumerate(patches))
base="\n".join(f'<path d="{path(P)}" stroke="{col}" stroke-width="{w}"/>' for P,col in rings.values())
over="\n".join(f'<g clip-path="url(#c{i})"><path d="{path(rings[k][0])}" stroke="{bg}" stroke-width="{halo}"/><path d="{path(rings[k][0])}" stroke="{rings[k][1]}" stroke-width="{w}"/></g>' for i,(k,_) in enumerate(patches))
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<defs>{defs}</defs>
<rect width="64" height="64" rx="14" fill="{bg}"/>
<g fill="none" stroke-linejoin="round" stroke-linecap="round">
{base}
{over}
</g>
</svg>
'''
Path(out).write_text(svg); print(out, cRG, cRB, cGB)
