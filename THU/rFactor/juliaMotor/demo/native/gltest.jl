using GLFW, ModernGL
GLFW.Init()
GLFW.WindowHint(GLFW.VISIBLE, false)            # hidden — offscreen verification
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR, 3)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR, 3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE, GLFW.OPENGL_CORE_PROFILE)
GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT, true)
const W, H = 640, 360
win = GLFW.CreateWindow(W, H, "gltest")
GLFW.MakeContextCurrent(win)
println("GL_VERSION  : ", unsafe_string(glGetString(GL_VERSION)))
println("GL_RENDERER : ", unsafe_string(glGetString(GL_RENDERER)))
println("GLSL        : ", unsafe_string(glGetString(GL_SHADING_LANGUAGE_VERSION)))

# minimal shader + a triangle to prove the pipeline works
vsrc = """
#version 330 core
layout(location=0) in vec2 p; layout(location=1) in vec3 c; out vec3 col;
void main(){ col=c; gl_Position=vec4(p,0,1); }"""
fsrc = """
#version 330 core
in vec3 col; out vec4 o; void main(){ o=vec4(col,1); }"""
function mkshader(src, kind)
    s = glCreateShader(kind); glShaderSource(s, 1, Ptr{GLchar}[pointer(src)], C_NULL); glCompileShader(s)
    ok = Ref{GLint}(); glGetShaderiv(s, GL_COMPILE_STATUS, ok)
    ok[]==0 && error("shader compile failed")
    s
end
prog = glCreateProgram()
glAttachShader(prog, mkshader(vsrc, GL_VERTEX_SHADER))
glAttachShader(prog, mkshader(fsrc, GL_FRAGMENT_SHADER))
glLinkProgram(prog)
verts = Float32[ -0.6,-0.5, 1,0,0,  0.6,-0.5, 0,1,0,  0.0,0.6, 0,0,1 ]
vao = Ref{GLuint}(); glGenVertexArrays(1, vao); glBindVertexArray(vao[])
vbo = Ref{GLuint}(); glGenBuffers(1, vbo); glBindBuffer(GL_ARRAY_BUFFER, vbo[])
glBufferData(GL_ARRAY_BUFFER, sizeof(verts), verts, GL_STATIC_DRAW)
glVertexAttribPointer(0, 2, GL_FLOAT, false, 5*4, Ptr{Cvoid}(0)); glEnableVertexAttribArray(0)
glVertexAttribPointer(1, 3, GL_FLOAT, false, 5*4, Ptr{Cvoid}(2*4)); glEnableVertexAttribArray(1)

glViewport(0, 0, W, H); glClearColor(0.10, 0.12, 0.16, 1); glClear(GL_COLOR_BUFFER_BIT)
glUseProgram(prog); glBindVertexArray(vao[]); glDrawArrays(GL_TRIANGLES, 0, 3)
glFinish()

# read pixels → write a PPM (then convert)
buf = Vector{UInt8}(undef, W*H*3)
glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE, buf)
open("/tmp/gltest.ppm","w") do io
    write(io, "P6\n$W $H\n255\n")
    for y in H:-1:1, x in 1:W          # flip vertically (GL origin bottom-left)
        o = ((y-1)*W + (x-1))*3
        write(io, buf[o+1], buf[o+2], buf[o+3])
    end
end
println("wrote /tmp/gltest.ppm")
GLFW.Terminate()
