# Render an audible rev-sweep of the Lotus 49 engine (idle -> redline -> idle)
# straight through EngineAudio.mix!, so we can verify the new sample set without
# the GL app or an audio device.  Writes a 44.1 kHz stereo WAV.
#
#   julia preview_engine.jl  [out.wav]

include(joinpath(@__DIR__, "..", "audio.jl")); using .EngineAudio

function write_wav(path, stereo::Matrix{Float32}, sr=44100)
    n = size(stereo,1); data = Int16[]
    for i in 1:n, c in 1:2
        push!(data, round(Int16, clamp(stereo[i,c], -1, 1) * 32767))
    end
    open(path, "w") do io
        bytes = length(data)*2
        write(io, "RIFF"); write(io, UInt32(36+bytes)); write(io, "WAVE")
        write(io, "fmt "); write(io, UInt32(16)); write(io, UInt16(1)); write(io, UInt16(2))
        write(io, UInt32(sr)); write(io, UInt32(sr*4)); write(io, UInt16(4)); write(io, UInt16(16))
        write(io, "data"); write(io, UInt32(bytes)); write(io, reinterpret(UInt8, data))
    end
end

eng = EngineAudio.build_lotus()
println("  Lotus engine: ", length(eng.voices), " voices @ ",
        [round(Int,v.natural) for v in eng.voices], " rpm")
@assert !isempty(eng.voices) "no Lotus samples loaded"

sr = 44100; dur = 10.0; N = round(Int, sr*dur)
out = zeros(Float32, N, 2)
buf = zeros(Float32, 1024, 2)
i = 1
while i <= N
    frac = (i-1)/N
    # idle -> redline -> idle, with a couple of blips
    rpm = 1800 + 7700*(0.5 - 0.5cos(2π*frac))           # smooth sweep up and back
    rpm += 600*sin(2π*6*frac)                            # small throttle ripple
    eng.rpm[] = rpm
    m = min(size(buf,1), N-i+1)
    EngineAudio.mix!(buf, eng)
    @views out[i:i+m-1, :] .= buf[1:m, :]
    global i += m
end
outpath = length(ARGS) >= 1 ? ARGS[1] : joinpath(@__DIR__, "lotus49_rev_preview.wav")
write_wav(outpath, out)
println("  wrote ", outpath, "  (", round(dur,digits=1), "s idle→redline→idle sweep)")
