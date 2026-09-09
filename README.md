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

The GLB contains the analytic shock surface, Be star, and a display-scale
pulsar. A JSON file records the wind and disk pressure laws, flow parameters,
field ranges, units, and deliberate visual choices. Three.js uses those values
to reconstruct diffuse pressure fields and explanatory flow tracers, and wraps
an original thermal-emissivity texture around the browser-rendered pulsar.

## Explore the interactive scene

From the repository root, start a local web server:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/viewer/`. The viewer loads the generated GLB
and JSON files and adds two separate kinds of layers: static pressure-field
volumes and moving flow tracers. Their geometry and scaling laws come from the
model, but the visible points are a display sampling rather than simulation
particles. Optional orbital-context layers show the IBSEn barycentric orbits of
the Be star and pulsar.

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
- `public/textures/neutron-star-thermal-v0.3.png`


## Scientific scope

See [`docs/scientific-basis.md`](docs/scientific-basis.md) for the distinction
between model-derived quantities and artistic presentation choices.

## Attribution

The analytic shock and emission calculations come from
[IBSEn](https://github.com/juliagouveamamprim/IBSEn), distributed under the MIT
License. Binary Shock is a separate visualization project and does not vendor
the IBSEn source code.
