"""Original soundtrack for the TND brag video: D major, 120 BPM, SFX tuned to the key.
Usage: python3 -I audio.py <out.wav>"""
import sys, wave
import numpy as np

SR = 48000
DUR = 21.5
N = int(SR * DUR)
rng = np.random.default_rng(7)


def hz(note):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    n, o = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o + 1) - 69) / 12)


def buf():
    return np.zeros((2, N))


def add(bus, sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[0, i:i + len(sig)] += sig * gain * l * 1.414
    bus[1, i:i + len(sig)] += sig * gain * r * 1.414


def tt(d):
    return np.arange(int(d * SR)) / SR


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


# ---- instruments ----
def pad_note(f, d, att=0.5, rel=0.8):
    t = tt(d + rel)
    sig = np.zeros_like(t)
    for det in (-0.12, 0.12):
        for k in range(1, 7):
            sig += np.sin(2 * np.pi * f * k * (1 + det / 100 * k) * t + rng.uniform(0, 6.28)) / k ** 1.8
    env = np.minimum(1, t / att) * np.where(t > d, np.exp(-(t - d) / (rel / 3)), 1)
    return sig * env * 0.5


def pluck(f, d=0.6, bright=4):
    t = tt(d)
    sig = sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t * (6 + k * bright)) / k for k in range(1, 6))
    return sig * np.minimum(1, t / 0.003)


def bell(f, d=2.2):
    t = tt(d)
    parts = [(1, 1, 1.6), (2.0, .35, 2.4), (2.76, .25, 3.2), (5.4, .08, 6)]
    sig = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * dec) for m, a, dec in parts)
    return sig * np.minimum(1, t / 0.004)


def kick():
    t = tt(0.32)
    f = 45 + 85 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 11) * np.minimum(1, t / 0.002)


def hat():
    t = tt(0.06)
    n = rng.standard_normal(len(t))
    n = np.diff(n, prepend=0)
    n = lowpass(n, 8000)
    return n * np.exp(-t * 80) * 0.25


def tick(f):
    t = tt(0.05)
    return (np.sin(2 * np.pi * f * t) * 0.6 + rng.standard_normal(len(t)) * 0.15) * np.exp(-t * 90)


def whoosh(d, rise=True):
    t = tt(d)
    n = lowpass(rng.standard_normal(len(t)), 1800)
    env = (t / d) ** 2 if rise else np.sin(np.pi * t / d) ** 2
    return n * env


music, sfx, padbus = buf(), buf(), buf()

# ---- chord plan (2s bars): D Bm G A ... with a turnaround into a final D ----
CHORDS = {"D": ["D3", "A3", "D4", "F#4"], "Bm": ["B2", "F#3", "B3", "D4"],
          "G": ["G2", "D3", "B3", "D4"], "A": ["A2", "E3", "A3", "C#4"]}
plan = []
prog = ["D", "Bm", "G", "A"]
for b in range(9):
    plan.append((b * 2.0, 2.0, prog[b % 4]))
plan.append((18.0, 0.5, "A"))
plan.append((18.5, 3.0, "D"))

for t0, d, ch in plan:
    for i, n in enumerate(CHORDS[ch]):
        add(padbus, pad_note(hz(n), d, att=0.35 if t0 else 0.9), t0, 0.085, pan=(i - 1.5) * 0.35)

# bass + arp + drums from the stage entrance (5.5s) until the outro (18.5s)
ARP = {"D": ["D5", "F#5", "A5", "F#5"], "Bm": ["B4", "D5", "F#5", "D5"],
       "G": ["G4", "B4", "D5", "B4"], "A": ["A4", "C#5", "E5", "C#5"]}
for t0, d, ch in plan:
    beats = np.arange(t0, t0 + d - 1e-6, 0.5)
    for j, bt in enumerate(beats):
        if 5.5 <= bt < 18.5:
            root = CHORDS[ch][0]
            if j % 2 == 0:
                add(music, pluck(hz(root.replace("3", "2")) if "3" in root else hz(root), 0.9, bright=8), bt, 0.32)
            add(music, kick(), bt, 0.42 if j % 2 == 0 else 0.3)
            add(music, hat(), bt + 0.25, 0.13, pan=0.3)
            for k in range(2):
                at = bt + k * 0.25
                note = ARP[ch][(j * 2 + k) % 4]
                add(music, pluck(hz(note), 0.5), at, 0.05, pan=-0.35 if k else 0.35)

# ---- sound effects (all on scale tones of D major) ----
add(sfx, bell(hz("A5")), 1.55, 0.10, pan=-0.2)          # "On"
add(sfx, bell(hz("D6")), 1.69, 0.10, pan=0.2)           # "purpose."
add(sfx, whoosh(0.55), 2.98, 0.05)                       # into logo
add(sfx, bell(hz("D5"), 3.0), 3.5, 0.16)                 # logo hit
add(sfx, bell(hz("F#5"), 3.0), 3.5, 0.08, pan=-0.3)
add(sfx, bell(hz("A5"), 3.0), 3.5, 0.08, pan=0.3)
add(sfx, kick(), 3.5, 0.5)
add(sfx, whoosh(0.5, rise=False), 5.25, 0.035)           # stage in
for i in range(20):                                       # typing
    add(sfx, tick(hz("A6") * (1 + (i % 3) * 0.02)), 6.25 + i * 1.05 / 20, 0.07, pan=rng.uniform(-.3, .3))
for ct in (7.85, 8.35, 16.95):                            # clicks
    add(sfx, tick(hz("D6")), ct, 0.18)
    add(sfx, pluck(hz("A5"), 0.3, bright=10), ct, 0.06)
for i, n in enumerate(["D5", "F#5", "B5", "D6"]):         # loading steps
    add(sfx, pluck(hz(n), 1.0, bright=2), 9.0 + i * 0.5, 0.13, pan=(i - 1.5) * 0.2)
add(sfx, whoosh(0.45, rise=False), 11.2, 0.04)           # page swap
for i, n in enumerate(["G5", "A5", "B5", "D6", "E6", "G6"]):   # score count-up
    k = (i + 1) / 6
    add(sfx, tick(hz(n)), 12.0 + 1.1 * (1 - (1 - k) ** (1 / 3)) - 0.06, 0.08)
add(sfx, bell(hz("G5"), 2.0), 13.1, 0.09)
add(sfx, bell(hz("B5"), 2.0), 13.1, 0.05)
add(sfx, whoosh(0.85, rise=False), 15.0, 0.03)           # scroll
add(sfx, whoosh(0.4), 18.25, 0.04)                       # into outro
add(sfx, kick(), 18.65, 0.45)
for n, g, p in (("D5", .16, 0), ("F#5", .08, -.3), ("A5", .08, .3), ("D6", .06, 0)):
    add(sfx, bell(hz(n), 2.8), 18.65, g, pan=p)

# high-pass the pad so bass and kick own the low end
padbus = np.stack([ch - lowpass(ch, 170) for ch in padbus])
music += padbus

# ---- mix: shared reverb so music and SFX sit in one space ----
def reverb(x, secs=1.6):
    t = tt(secs)
    ir = rng.standard_normal(len(t)) * np.exp(-t * 4.0)
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2))
    L = N + len(ir)
    nfft = 1 << (L - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:N]

dry = music + sfx * 0.85
send = music * 0.25 + sfx * 0.5
wet = np.stack([reverb(send[0]), reverb(send[1])])
mix = dry + wet * 0.35

tt_all = np.arange(N) / SR
mix *= np.minimum(1, tt_all / 0.05) * np.clip((DUR - tt_all) / 1.0, 0, 1) ** 1.5   # fade out last second
mix /= np.max(np.abs(mix)) + 1e-9
mix = np.tanh(mix * 1.15) / np.tanh(1.15) * 0.89                                    # gentle limit, ~-1 dBFS

pcm = (mix.T * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", sys.argv[1])
