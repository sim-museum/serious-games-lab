# bridgeIQ — quick run

```bash
cd /home/h/sgl/FRI/bridgeIQ/bridgeIQ
./run.sh
```

`run.sh` uses the project venv's Python directly and sets `PYTHONPATH` itself, so
no manual activation is needed. To run by hand:

```bash
source /home/h/sgl/FRI/bridgeIQ/venv/bin/activate
cd /home/h/sgl/FRI/bridgeIQ/bridgeIQ
export PYTHONPATH=".:$PYTHONPATH"
python main.py
```

See `bridgeIQ_README.md` (in this folder) for the full guide, and
`../bridgeIQ/CLAUDE.md` for engineering notes.
