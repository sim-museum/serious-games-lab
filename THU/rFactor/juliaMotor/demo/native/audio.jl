# Engine audio for the native app — plays the car's own onboard engine samples
# (from the local rFactor install), crossfaded by RPM and pitch-trimmed, the way
# the sim does.  Runs on a dedicated thread (PortAudio) so the GL render loop's
# vsync waits never starve it.
module EngineAudio
using PortAudio, SampledSignals

"""Load a RIFF/WAVE PCM file → (mono Float32 samples, samplerate)."""
function load_wav(path)
    b = read(path)
    (length(b) >= 44 && String(b[1:4])=="RIFF" && String(b[9:12])=="WAVE") || error("not a WAVE: $path")
    u32(o)=Int(reinterpret(UInt32, b[o:o+3])[1]); u16(o)=Int(reinterpret(UInt16, b[o:o+1])[1])
    pos=13; channels=2; samplerate=44100; bits=16; data=Int16[]
    while pos+8 <= length(b)
        cid=String(b[pos:pos+3]); csz=u32(pos+4); body=pos+8
        if cid=="fmt "
            channels=u16(body+2); samplerate=u32(body+4); bits=u16(body+14)
        elseif cid=="data"
            stop=min(body+csz-1, length(b))
            data=collect(reinterpret(Int16, b[body:stop - (stop-body+1)%2]))
        end
        pos = body + csz + (csz & 1)
    end
    mono = if channels==2
        n=length(data)÷2
        Float32[(Float32(data[2i-1])+Float32(data[2i]))*(1f0/65536f0) for i in 1:n]
    else
        Float32.(data) .* (1f0/32768f0)
    end
    (mono, samplerate)
end

mutable struct Voice; data::Vector{Float32}; natural::Float64; phase::Float64; end
mutable struct Engine
    voices::Vector{Voice}
    rpm::Threads.Atomic{Float64}
    master::Threads.Atomic{Float64}
    running::Threads.Atomic{Bool}
    proc::Bool             # PROCEDURAL synth (Cosworth DFV V8) — fallback when GPL audio is absent
    phase::Float64         # crank-rotation phase for the synth [0,1)
    single::Bool           # SINGLE-loop wide-pitch playback (GPL engine sample)
end

const SAMPLES = (("idle1e.WAV",1600.0), ("v4g.wav",2700.0), ("l4f.wav",4500.0),
                 ("l2e.wav",6200.0), ("h1g.wav",8000.0))

# GPL's own Lotus 49 engine: the Ford Cosworth DFV V8 loop, pitch-shifted by RPM
# (GPL plays one steady loop across the whole rev range).  Measured firing pitch
# of the loop ≈ 347 Hz ⇒ ~5200 rpm (V8 4th order).
const GPL_ENGINE_WAV = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","sound","66fordV8.wav"))
const GPL_ENGINE_RPM = 5200.0

"Linear-resample mono Float32 audio from `sr` to 44.1 kHz (so playback pitch math is clean)."
function resample44k(data::Vector{Float32}, sr)
    sr == 44100 && return data
    n = max(1, round(Int, length(data)*44100/sr)); step = sr/44100
    out = Vector{Float32}(undef, n); L = length(data)
    @inbounds for i in 1:n
        p = (i-1)*step + 1; k = unsafe_trunc(Int, p); fr = Float32(p - k)
        a = data[clamp(k,1,L)]; b = data[clamp(k+1,1,L)]
        out[i] = a*(1f0-fr) + b*fr
    end
    out
end

"""Build the engine from the car's onboard sample set (`Sounds/F158/Vanwall_V254/IN`)."""
function build(gamedata)
    dir = joinpath(gamedata,"Sounds","F158","Vanwall_V254","IN")
    voices = Voice[]
    for (f,rpm) in SAMPLES
        p = joinpath(dir,f); isfile(p) || continue
        d,_ = load_wav(p); push!(voices, Voice(d, rpm, 0.0))
    end
    Engine(voices, Threads.Atomic{Float64}(1600.0), Threads.Atomic{Float64}(0.7), Threads.Atomic{Bool}(false), false, 0.0, false)
end

"""Build the Lotus 49 engine from GPL's own audio: the Ford Cosworth DFV V8 loop
(`GPL/sound/66fordV8.wav`), pitch-shifted by RPM the way GPL plays it.  Falls back
to a procedural DFV synth if the GPL audio isn't found (never to WAV voice clips)."""
function build_lotus(; gpl_engine = GPL_ENGINE_WAV, kwargs...)
    if isfile(gpl_engine)
        d, sr = load_wav(gpl_engine)
        v = Voice(resample44k(d, sr), GPL_ENGINE_RPM, 0.0)
        return Engine([v], Threads.Atomic{Float64}(1800.0), Threads.Atomic{Float64}(0.7),
                      Threads.Atomic{Bool}(false), false, 0.0, true)
    end
    Engine(Voice[], Threads.Atomic{Float64}(1800.0), Threads.Atomic{Float64}(0.7),
           Threads.Atomic{Bool}(false), true, 0.0, false)   # procedural fallback
end

# Single GPL loop, pitched across the whole rev range (rate = rpm / reference rpm).
function mix_single!(out::Matrix{Float32}, eng::Engine)
    v = eng.voices[1]; len = length(v.data)
    r = eng.rpm[]; rpm = isfinite(r) ? max(r, 500.0) : 500.0
    master = Float32(eng.master[])
    rate = clamp(rpm / v.natural, 0.22, 2.4)               # WIDE pitch (one loop, idle→redline)
    ph = isfinite(v.phase) ? v.phase : 0.0
    @inbounds for i in 1:size(out,1)
        idx = unsafe_trunc(Int, ph); fr = Float32(ph - idx)
        a = v.data[idx % len + 1]; b = v.data[(idx+1) % len + 1]
        s = (a*(1f0-fr) + b*fr) * master
        out[i,1] = s; out[i,2] = s
        ph += rate; ph >= len && (ph -= len)
    end
    v.phase = ph
end

# Cosworth DFV V8 exhaust spectrum, by ENGINE ORDER (k = harmonics of crank rotation):
# 4th order = the firing note (8 cyl, 4-stroke ⇒ 4 power strokes/rev); 2nd/6th give the
# V8 body/burble; 8/12/16 the metallic top-end wail.  (k, amplitude)
const DFV_ORDERS = ((1,0.10),(2,0.55),(3,0.16),(4,1.00),(5,0.18),(6,0.45),
                    (8,0.60),(10,0.24),(12,0.32),(16,0.14))

# Procedural V8 synth: fills the buffer from the crank phase at the current RPM.
function mix_proc!(out::Matrix{Float32}, eng::Engine)
    N = size(out,1)
    r = eng.rpm[]; rpm = isfinite(r) ? clamp(r, 700.0, 10500.0) : 700.0
    master = eng.master[]
    crank = rpm/60.0                                   # crank revs / second [Hz]
    inc = crank/44100.0                                # phase increment per sample
    amp = master * clamp(0.30 + 0.70*(rpm-1200.0)/8000.0, 0.20, 1.0)   # louder with revs
    ph = isfinite(eng.phase) ? eng.phase : 0.0
    @inbounds for i in 1:N
        s = 0.0
        for (k,a) in DFV_ORDERS; s += a*sin(2π*k*ph); end
        s += 0.05*(2rand() - 1)                        # induction / exhaust hiss
        v = Float32(tanh(s*0.55) * amp * 0.5)          # soft-clip for body, never hard-pin
        out[i,1] = v; out[i,2] = v
        ph += inc; ph >= 1.0 && (ph -= 1.0)
    end
    eng.phase = ph
end

# mix one output buffer (frames×2): procedural synth, OR triangular RPM crossfade + per-sample pitch
function mix!(out::Matrix{Float32}, eng::Engine)
    if eng.single; mix_single!(out, eng); return; end
    if eng.proc;   mix_proc!(out, eng);   return; end
    fill!(out, 0f0); N=size(out,1)
    r=eng.rpm[]; rpm = isfinite(r) ? max(r,700.0) : 700.0   # sanitise: a NaN rpm (stall transient)
    master=eng.master[]; span=2200.0                         # must NOT poison the voice phases forever
    tot=0.0; for v in eng.voices; tot += max(0.0,1-abs(rpm-v.natural)/span); end
    tot<1e-6 && (tot=1.0)
    @inbounds for v in eng.voices
        g=Float32(max(0.0,1-abs(rpm-v.natural)/span)/tot*master); g<1f-4 && continue
        rate=clamp(rpm/v.natural,0.5,1.5); len=length(v.data); ph=isfinite(v.phase) ? v.phase : 0.0   # heal a NaN phase
        for i in 1:N
            idx=unsafe_trunc(Int,ph); fr=Float32(ph-idx)
            a=v.data[idx % len + 1]; b=v.data[(idx+1) % len + 1]
            s=(a*(1f0-fr)+b*fr)*g; out[i,1]+=s; out[i,2]+=s
            ph+=rate; ph>=len && (ph-=len)
        end
        v.phase=ph
    end
end

"""Start the audio thread (needs Julia ≥2 threads).  Returns the Engine; update
`eng.rpm[]` from the game loop, call `stop!(eng)` to end."""
function start(eng::Engine)
    haskey(ENV, "JM_NOSOUND") && (println("  engine audio off (JM_NOSOUND)"); return eng)
    (!eng.proc && isempty(eng.voices)) && (@warn "no engine samples found — no sound"; return eng)
    if Threads.nthreads() < 2
        @warn "sound needs ≥2 threads — relaunch with: julia -t 2 …"; return eng
    end
    eng.running[]=true
    LAT = parse(Float64, get(ENV, "JM_AUDIO_LATENCY", "0.30"))   # bigger buffer = more headroom for a render hitch (GC, a heavy section) before it underflows
    Threads.@spawn begin
        buf = zeros(Float32, 1024, 2)
        # E95i (PO 2026-08-29: "sound was coming out of a monitor, not my speakers. My ubuntu sound
        # settings had no effect on the sound volume. The volume did increase when I reved.")
        # PortAudioStream(0,2) with no device asks PortAudio for ITS default, which on this box is a
        # RAW ALSA CARD -- the enumeration lists `HDA NVidia: Sceptre F27 (hw:1,3)`, the monitor's
        # HDMI audio, right next to `HDA Intel PCH (hw:0,0)`. Opening a card directly bypasses
        # PipeWire/PulseAudio completely, which is exactly why the engine was audible (it revved
        # correctly -- the audio path itself was fine) yet Ubuntu's mixer had nothing to control:
        # the sim was not a stream the sound server could see.
        #
        # Open the server's own ALSA plugin (`pulse`, device 13 here) instead. Then the sim appears
        # as a normal application stream: it follows whatever Ubuntu has set as the default sink,
        # moves with it if the user changes it, and obeys both the system and per-app volume.
        # Fall back through `default`/`sysdefault` and finally to PortAudio's choice, so a box
        # without a sound server still gets audio rather than silence.
        devpref = let e = get(ENV, "JM_AUDIO_DEV", "")
            isempty(e) ? ["pulse", "default", "sysdefault"] : [e]
        end
        havedev = Set{String}()
        try; for d in PortAudio.devices(); d.output_bounds.max_channels > 0 && push!(havedev, d.name); end
        catch; end
        audiodev = nothing
        for d in devpref; if d in havedev; audiodev = d; break; end; end
        if audiodev === nothing
            @warn "no PulseAudio/PipeWire audio device found — falling back to PortAudio's default; \
                   the system volume control may not affect the sim" candidates=devpref
        else
            println("  [audio] output -> '", audiodev, "' (follows the Ubuntu default sink; JM_AUDIO_DEV overrides)")
            flush(stdout)
        end
        openfails = 0; wfails = 0
        # Resilient feeder: a render-loop hitch (first-frame JIT, GC, a heavy trackside section) can
        # starve this thread and xrun the stream.  On a write error we REOPEN and keep going, with a
        # growing BACKOFF so we don't silently THRASH (open succeeds → next write fails → reopen …) — a
        # short sleep lets PipeWire/ALSA recover the stream so the engine sound returns on its own
        # instead of staying dead for the rest of the section (the PO's "sound cut out past the building,
        # came back at the line").
        while eng.running[]
            local stream
            try
                stream = audiodev === nothing ? PortAudioStream(0,2; samplerate=44100, latency=LAT) :
                                                PortAudioStream(audiodev, 0, 2; samplerate=44100, latency=LAT)
                openfails = 0
            catch e
                # couldn't open the device THIS attempt.  On PipeWire/PulseAudio the default ALSA
                # device (hw:0,0) can be momentarily held by the server when the game starts up, so
                # the FIRST open often loses an exclusive-access race.  RETRY for a few seconds; only
                # give up if it's genuinely unavailable.
                openfails += 1
                if openfails >= 60                      # ~6 s of retries
                    @warn "engine audio unavailable (couldn't open an audio device after retries) — running silently; set JM_NOSOUND=1 to skip audio" e
                    eng.running[]=false; break
                end
                sleep(0.1); continue                    # device busy/transient → wait and retry
            end
            try
                while eng.running[]
                    mix!(buf, eng)
                    # SANITISE before PortAudio: a single NaN/Inf or out-of-range sample makes
                    # the C Float32→Int32 converter crash the WHOLE process (uncatchable in
                    # Julia — it's a C-level fault).  Clamp to [-1,1] and zero any non-finite.
                    @inbounds for i in eachindex(buf)
                        x = buf[i]
                        buf[i] = isfinite(x) ? (x > 1f0 ? 1f0 : x < -1f0 ? -1f0 : x) : 0f0
                    end
                    write(stream, buf)
                    wfails = 0                           # a clean write → clear the failure backoff
                end
            catch e
                wfails += 1
                wfails <= 2 && @warn "audio xrun — reopening stream" e   # warn only the first couple (no log spam during a thrash)
            finally
                try; close(stream); catch; end
            end
            wfails > 0 && sleep(min(0.4, 0.05*wfails))   # back off on repeated write failures so the device can settle (breaks the silent reopen-thrash)
        end
    end
    eng
end
stop!(eng::Engine) = (eng.running[]=false)

end # module
