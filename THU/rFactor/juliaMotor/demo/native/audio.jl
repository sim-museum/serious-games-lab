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
end

const SAMPLES = (("idle1e.WAV",1600.0), ("v4g.wav",2700.0), ("l4f.wav",4500.0),
                 ("l2e.wav",6200.0), ("h1g.wav",8000.0))

"""Build the engine from the car's onboard sample set (`Sounds/F158/Vanwall_V254/IN`)."""
function build(gamedata)
    dir = joinpath(gamedata,"Sounds","F158","Vanwall_V254","IN")
    voices = Voice[]
    for (f,rpm) in SAMPLES
        p = joinpath(dir,f); isfile(p) || continue
        d,_ = load_wav(p); push!(voices, Voice(d, rpm, 0.0))
    end
    Engine(voices, Threads.Atomic{Float64}(1600.0), Threads.Atomic{Float64}(0.7), Threads.Atomic{Bool}(false))
end

# mix one output buffer (frames×2): triangular RPM crossfade + per-sample pitch
function mix!(out::Matrix{Float32}, eng::Engine)
    fill!(out, 0f0); N=size(out,1)
    rpm=max(eng.rpm[],700.0); master=eng.master[]; span=2200.0
    tot=0.0; for v in eng.voices; tot += max(0.0,1-abs(rpm-v.natural)/span); end
    tot<1e-6 && (tot=1.0)
    @inbounds for v in eng.voices
        g=Float32(max(0.0,1-abs(rpm-v.natural)/span)/tot*master); g<1f-4 && continue
        rate=clamp(rpm/v.natural,0.5,1.5); len=length(v.data); ph=v.phase
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
    isempty(eng.voices) && (@warn "no engine samples found — no sound"; return eng)
    if Threads.nthreads() < 2
        @warn "sound needs ≥2 threads — relaunch with: julia -t 2 …"; return eng
    end
    eng.running[]=true
    Threads.@spawn begin
        stream = PortAudioStream(0,2; samplerate=44100, latency=0.08)
        buf = zeros(Float32, 1024, 2)
        try
            while eng.running[]; mix!(buf, eng); write(stream, buf); end
        catch e; @warn "audio thread error" e
        finally; close(stream); end
    end
    eng
end
stop!(eng::Engine) = (eng.running[]=false)

end # module
