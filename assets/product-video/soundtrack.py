"""Original procedural music and transition effects; no sampled or licensed recordings."""
import math, random, struct, wave
from pathlib import Path
rate=48000; duration=30; data=[0.0]*(rate*duration); rng=random.Random(41)
def note(start,freq,length,volume):
    begin=int(start*rate)
    for i in range(min(int(length*rate),len(data)-begin)):
        t=i/rate; env=min(1,t/.009)*math.exp(-t*4.2)*min(1,(length-t)/.04)
        data[begin+i]+=volume*env*(math.sin(2*math.pi*freq*t)+.23*math.sin(4*math.pi*freq*t)+.08*math.sin(6*math.pi*freq*t))
beat=60/104
chords=[[261.63,329.63,392,493.88],[220,261.63,329.63,440],[174.61,220,261.63,349.23],[196,246.94,293.66,392]]
for step in range(int(duration/(beat/2))):
    start=step*beat/2; chord=chords[(step//8)%4]
    note(start,chord[[0,2,1,3,2,1,3,2][step%8]]*(2 if step%4==3 else 1),.72,.085)
    if step%2==0: note(start,chord[0]/2,.5,.1)
    if step%4==2:
        for i in range(min(2100,len(data)-int(start*rate))):
            data[int(start*rate)+i]+=rng.uniform(-1,1)*math.exp(-i/320)*.024
for start in [4.32,9.32,14.32,19.32,24.32]:
    for i in range(int(.34*rate)):
        t=i/rate; data[int(start*rate)+i]+=rng.uniform(-1,1)*math.sin(math.pi*t/.34)**2*.027
for f in [261.63,329.63,392,523.25]: note(25,f,2,.055)
path=Path(__file__).parent/'soundtrack.wav'
with wave.open(str(path),'wb') as out:
    out.setparams((1,2,rate,0,'NONE','not compressed'))
    out.writeframes(b''.join(struct.pack('<h',int(max(-1,min(1,s*min(1,i/rate/.5,(duration-i/rate)/1.2)))*26000)) for i,s in enumerate(data)))
print(path)
