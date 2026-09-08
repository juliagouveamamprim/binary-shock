# Binary Shock

An interactive 3D scientific visualization of the analytic intrabinary shock model implemented by [IBSEn](https://github.com/juliagouveamamprim/IBSEn).

The first milestone exports a frozen PSR B1259−63 scene to GLB and loads it in
a browser-based Three.js viewer. The goal is a cinematic scientific diorama
whose geometry and scalar mappings remain traceable to the model. Binary Shock
does not claim to be a 3D hydrodynamic simulation.


## Prototype pipeline

```text
IBSEn (Python) -> GLB + scientific metadata -> Three.js viewer
```

The GLB contains the analytic shock surface, Be star, decretion disk, and a
display-scale pulsar. The winds determine the shock geometry in the IBSEn model
but are not exported as simulated particles. A JSON file records physical
parameters, field ranges, units, and deliberate visual choices.

## Explore the interactive scene

From the repository root, start a local web server:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/viewer/`. The viewer loads the generated GLB
and JSON files and adds explanatory wind and disk-flow particles. Those
particles follow model-defined flow directions but are not simulation output.

## Reproduce the prototype scene

Create an isolated Python 3.12 environment and install the project. The project configuration specifies the exact version of the IBSEn source code used to generate this prototype.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install .
MPLCONFIGDIR=/tmp/binary-shock-mpl .venv/bin/python generator/export_scene.py
```

Outputs:

- `public/models/binary-shock-v0.1.glb`
- `public/models/binary-shock-v0.1.metadata.json`
- `public/previews/binary-shock-v0.1.png`


## Scientific scope

See [`docs/scientific-basis.md`](docs/scientific-basis.md) for the distinction
between model-derived quantities and artistic presentation choices.

## Attribution

The analytic shock and emission calculations come from
[IBSEn](https://github.com/juliagouveamamprim/IBSEn), distributed under the MIT
License. Binary Shock is a separate visualization project and does not vendor
the IBSEn source code.
