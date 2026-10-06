#!/bin/bash
# Build lc0 for Kramnik chess on the GPU (EPIC NN, sprint NN-9, 2026-10-06): lc0 v0.32.1 + lc0-kramnik.patch with the
# plain CUDA backend (cuBLAS, no cuDNN). No system CUDA toolkit is needed: the compiler and libraries come from pip
# into a private environment (engine/cuda-env, ~1.5 GB), pinned to CUDA 13.2, which needs an NVIDIA driver for
# CUDA 13.2 or later (nvidia-smi shows it). Measured on a GTX 1660 Super: ~37,000 nodes/s (cuda-fp16) against ~350
# on the CPU build.
#   CC_CUDA=75 engine/build_lc0_gpu.sh    (75 = Turing, e.g. GTX 16xx/RTX 20xx; 86 = RTX 30xx; 89 = RTX 40xx)
# Result: engine/lc0-kramnik-gpu (a wrapper that sets the library path) -> engine/lc0-kramnik-cuda
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG=v0.32.1
SRC="${LC0_SRC:-$HERE/lc0}"
ENV="$HERE/cuda-env"
[ -x "$ENV/bin/pip" ] || python3 -m venv "$ENV"
"$ENV/bin/pip" install -q "nvidia-cuda-nvcc==13.2.86" "nvidia-nvvm==13.2.86" "nvidia-cuda-crt==13.2.86" \
  "nvidia-cuda-cccl==13.2.*" "nvidia-cublas==13.1.1.3" "nvidia-cuda-runtime==13.0.96"
NV="$("$ENV/bin/python" -c 'import nvidia, os; print(os.path.join(list(nvidia.__path__)[0], "cu13"))')"
CUDA="$HERE/cuda"
mkdir -p "$CUDA/lib64"
ln -sfn "$NV/include" "$CUDA/include"
ln -sfn "$NV/bin" "$CUDA/bin"
for l in libcublas.so.13 libcublasLt.so.13 libcudart.so.13; do
  ln -sf "$NV/lib/$l" "$CUDA/lib64/$l"
  ln -sf "$NV/lib/$l" "$CUDA/lib64/${l%.13}"
done
[ -d "$SRC/.git" ] || git clone -q https://github.com/LeelaChessZero/lc0.git "$SRC"
cd "$SRC"
git checkout -q -f "$TAG"
git clean -fdq -e build
git apply "$HERE/lc0-kramnik.patch"
PATH="$CUDA/bin:$PATH" meson setup build/kramnik-gpu --reconfigure --buildtype release -Dgtest=false \
  -Dcpp_args=-DLC0_KRAMNIK -Dplain_cuda=true -Dcudnn=false -Dcc_cuda="${CC_CUDA:-75}" -Dopencl=false -Ddx=false \
  -Donednn=false -Dcudnn_libdirs="$CUDA/lib64" -Dcudnn_include="$CUDA/include" > "$HERE/build_lc0_gpu.log" 2>&1
PATH="$CUDA/bin:$PATH" ninja -C build/kramnik-gpu -j"${JOBS:-$(nproc)}" >> "$HERE/build_lc0_gpu.log" 2>&1
cp build/kramnik-gpu/lc0 "$HERE/lc0-kramnik-cuda"
git checkout -q -- .
cat > "$HERE/lc0-kramnik-gpu" <<EOF
#!/bin/bash
# lc0 for Kramnik chess on the GPU; use --backend=cuda-fp16 (or cuda). Built by build_lc0_gpu.sh.
export LD_LIBRARY_PATH="$CUDA/lib64:\${LD_LIBRARY_PATH:-}"
exec "$HERE/lc0-kramnik-cuda" "\$@"
EOF
chmod +x "$HERE/lc0-kramnik-gpu"
echo "built $HERE/lc0-kramnik-gpu"
