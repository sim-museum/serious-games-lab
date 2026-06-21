# ffb.jl — Linux evdev force-feedback writer for the wheel (Stage 2 of TX FFB).
#
# GLFW is input-only (no force output), so we talk to the wheel's /dev/input/eventN
# directly via the kernel FF API: upload ONE FF_CONSTANT effect, start it playing, then
# update its signed `level` every frame from the physics (self-aligning torque). The
# ioctl/struct layout mirrors the verified `ffbtest.py` (ff_effect = 48 bytes, level at
# byte offset 16). Writing is allowed for the logged-in user via the session uaccess ACL
# (hid-tmff2's udev rules), so no root is needed.
module FFB

export FFBDevice, open_ffb, set_force!, close_ffb

const FF_CONSTANT = 0x0052
const EV_FF       = 0x0015
const EFFSZ       = 48
# _IOW('E', nr, size):  (dir=1<<30) | (size<<16) | ('E'=0x45 <<8) | nr
# NOTE: write 'E' as Int, not the UInt8 literal 0x45 — `0x45 << 8` on a UInt8 shifts
# every bit out (→ 0), which silently drops the type byte from the ioctl number.
const _E = Int(0x45)
const EVIOCSFF  = Culong((1<<30) | (EFFSZ<<16) | (_E<<8) | 0x80)
const EVIOCRMFF = Culong((1<<30) | (4<<16)     | (_E<<8) | 0x81)
const O_RDWR    = Cint(2)

mutable struct FFBDevice
    fd::Cint
    id::Int16
    buf::Vector{UInt8}          # the 48-byte ff_effect (reused for live updates)
    ok::Bool
    path::String
end

@inline function _put16!(buf, off, v::UInt16)   # off = 0-based byte offset, little-endian
    @inbounds buf[off+1] = UInt8(v & 0xff)
    @inbounds buf[off+2] = UInt8((v >> 8) & 0xff)
end
_puti16!(buf, off, v::Integer) = _put16!(buf, off, reinterpret(UInt16, Int16(v)))
_getu16(buf, off) = UInt16(buf[off+1]) | (UInt16(buf[off+2]) << 8)

"Find the wheel's event node by name substring (default: a Thrustmaster wheel)."
function find_event(match = "Thrustmaster")
    base = "/sys/class/input"
    isdir(base) || return nothing
    for d in readdir(base)
        startswith(d, "event") || continue
        nf = joinpath(base, d, "device", "name")
        isfile(nf) || continue
        try
            occursin(match, read(nf, String)) && return joinpath("/dev/input", d)
        catch
        end
    end
    nothing
end

"Open the wheel for FFB and upload+start a zero-level constant force. Returns an
FFBDevice; check `.ok`. Safe to call when no wheel/FFB is present (ok=false)."
function open_ffb(path = nothing; match = "Thrustmaster")
    path === nothing && (path = find_event(match))
    path === nothing && return FFBDevice(-1, 0, UInt8[], false, "")
    fd = ccall(:open, Cint, (Cstring, Cint), path, O_RDWR)
    fd < 0 && return FFBDevice(-1, 0, UInt8[], false, path)
    buf = zeros(UInt8, EFFSZ)
    _put16!(buf, 0,  FF_CONSTANT)        # type
    _puti16!(buf, 2, -1)                 # id = -1 → kernel assigns
    _put16!(buf, 4,  UInt16(0x4000))     # direction along the steering axis; sign of level picks side
    _put16!(buf, 10, UInt16(0))          # replay.length = 0  → play until stopped
    _put16!(buf, 12, UInt16(0))          # replay.delay
    _puti16!(buf, 16, 0)                 # u.constant.level = 0
    rc = ccall(:ioctl, Cint, (Cint, Culong, Ptr{UInt8}), fd, EVIOCSFF, buf)
    if rc < 0
        ccall(:close, Cint, (Cint,), fd)
        return FFBDevice(-1, 0, UInt8[], false, path)
    end
    id = reinterpret(Int16, _getu16(buf, 2))
    dev = FFBDevice(fd, id, buf, true, path)
    _play(dev, true)                     # start playing (level updates take effect live)
    dev
end

# write an input_event {time(16), type u16, code u16, value i32} = 24 bytes
function _play(dev::FFBDevice, on::Bool)
    ev = zeros(UInt8, 24)
    _put16!(ev, 16, UInt16(EV_FF))
    _put16!(ev, 18, reinterpret(UInt16, dev.id))
    val = Int32(on ? 1 : 0)
    @inbounds for k in 0:3; ev[20+1+k] = UInt8((reinterpret(UInt32, val) >> (8k)) & 0xff); end
    ccall(:write, Cssize_t, (Cint, Ptr{UInt8}, Csize_t), dev.fd, ev, 24)
end

"""Set the steering force, `f ∈ [-1,1]` (sign = direction). Updates the running effect
live (one ioctl). No-op if the device isn't OK."""
function set_force!(dev::FFBDevice, f::Real)
    dev.ok || return dev
    lvl = round(Int, clamp(f, -1.0, 1.0) * 32767)
    _puti16!(dev.buf, 16, lvl)           # u.constant.level
    ccall(:ioctl, Cint, (Cint, Culong, Ptr{UInt8}), dev.fd, EVIOCSFF, dev.buf)   # update in place
    dev
end

"Stop the effect, remove it, and close the device."
function close_ffb(dev::FFBDevice)
    dev.ok || return
    _play(dev, false)
    ccall(:ioctl, Cint, (Cint, Culong, Clong), dev.fd, EVIOCRMFF, Clong(dev.id))  # id BY VALUE
    ccall(:close, Cint, (Cint,), dev.fd)
    dev.ok = false
    nothing
end

end # module
