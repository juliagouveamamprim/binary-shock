import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const MODEL_URL = "../public/models/binary-shock-v0.1.glb";
const METADATA_URL = "../public/models/binary-shock-v0.1.metadata.json";
const PULSAR_TEXTURE_URL = "../public/textures/neutron-star-thermal-v0.3.png";
const VIEW_PRESET = new URLSearchParams(window.location.search).get("preset") === "artistic"
  ? "artistic"
  : "paper";

document.body.dataset.preset = VIEW_PRESET;

const canvas = document.getElementById("scene-canvas");
const statusElement = document.getElementById("load-status");
const errorPanel = document.getElementById("error-panel");
const errorMessage = document.getElementById("error-message");
const controlPanel = document.getElementById("control-panel");
const panelToggle = document.getElementById("panel-toggle");

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: false,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x02030a);
scene.fog = new THREE.FogExp2(0x02030a, 0.034);

const camera = new THREE.PerspectiveCamera(42, 1, 0.003, 100);
camera.up.set(0, 0, 1);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.055;
controls.zoomToCursor = true;
controls.minDistance = 0.06;
controls.maxDistance = 12;

scene.add(new THREE.HemisphereLight(0x879dff, 0x170914, 0.75));
const coolLight = new THREE.DirectionalLight(0x76caff, 1.7);
coolLight.position.set(-2.5, -1.0, 3.2);
scene.add(coolLight);

const layerObjects = {};
const layerLabels = {};
const animatedFlows = [];
const labelTargets = {};
const PAPER_LABEL_OFFSETS = {
  "star-label": [58, 54],
  "pulsar-label": [-54, -34],
  "apex-label": [-88, 0],
  "barycenter-label": [-58, 42],
  "x-axis-label": [28, -2],
  "y-axis-label": [12, -32],
  "disk-normal-label": [34, -38],
  "los-label": [22, 30],
};

function setStatus(message, state) {
  statusElement.querySelector("span:last-child").textContent = message;
  statusElement.classList.toggle("is-ready", state === "ready");
  statusElement.classList.toggle("is-error", state === "error");
}

function showError(error) {
  const message = error instanceof Error ? error.message : String(error);
  setStatus("Load failed", "error");
  errorMessage.textContent = message;
  errorPanel.hidden = false;
  console.error(error);
}

function seededRandom(seed) {
  let state = seed % 2147483647;
  return function random() {
    state = (state * 16807) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

function randomUnitVector(random) {
  const z = random() * 2 - 1;
  const angle = random() * Math.PI * 2;
  const radius = Math.sqrt(Math.max(0, 1 - z * z));
  return new THREE.Vector3(
    radius * Math.cos(angle),
    radius * Math.sin(angle),
    z,
  );
}

function makePointTexture() {
  const textureCanvas = document.createElement("canvas");
  textureCanvas.width = 64;
  textureCanvas.height = 64;
  const context = textureCanvas.getContext("2d");
  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.22, "rgba(255,255,255,.88)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(textureCanvas);
}

const pointTexture = makePointTexture();

function makePressureTexture() {
  const textureCanvas = document.createElement("canvas");
  textureCanvas.width = 256;
  textureCanvas.height = 256;
  const context = textureCanvas.getContext("2d");
  const gradient = context.createRadialGradient(128, 128, 3, 128, 128, 128);
  gradient.addColorStop(0, "rgba(255,255,255,.95)");
  gradient.addColorStop(0.08, "rgba(255,255,255,.82)");
  gradient.addColorStop(0.26, "rgba(255,255,255,.42)");
  gradient.addColorStop(0.58, "rgba(255,255,255,.13)");
  gradient.addColorStop(0.82, "rgba(255,255,255,.035)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(textureCanvas);
}

const pressureTexture = makePressureTexture();

function addBackgroundStars() {
  const random = seededRandom(7341);
  const count = 1300;
  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    const direction = randomUnitVector(random);
    const radius = 8 + random() * 18;
    direction.multiplyScalar(radius).toArray(positions, index * 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    color: 0xbac9ff,
    size: 0.018,
    transparent: true,
    opacity: 0.62,
    sizeAttenuation: true,
    depthWrite: false,
  });
  const points = new THREE.Points(geometry, material);
  points.name = "Background stars — artistic context";
  scene.add(points);
  return points;
}

function findObject(root, predicate) {
  let match = null;
  root.traverse(function inspect(object) {
    if (!match && predicate(object)) match = object;
  });
  return match;
}

function prepareModel(root) {
  root.traverse(function prepare(object) {
    if (!object.isMesh) return;
    object.frustumCulled = false;
    const name = object.name.toLowerCase();
    const sourceWasArray = Array.isArray(object.material);
    const materials = sourceWasArray ? object.material : [object.material];
    const preparedMaterials = materials.map(function prepareMaterial(source) {
      const material = source.clone();
      if (name.includes("shock")) {
        material.transparent = true;
        material.opacity = VIEW_PRESET === "paper" ? 0.56 : 0.68;
        material.depthWrite = false;
        material.side = THREE.DoubleSide;
        material.vertexColors = true;
        if (material.emissive) {
          material.emissive.multiplyScalar(VIEW_PRESET === "paper" ? 0.72 : 1.35);
        }
      } else if (name.includes("disk")) {
        material.transparent = true;
        material.opacity = 0.52;
        material.depthWrite = false;
        material.side = THREE.DoubleSide;
        material.vertexColors = true;
      }
      material.needsUpdate = true;
      return material;
    });
    object.material = sourceWasArray ? preparedMaterials : preparedMaterials[0];
  });
}

function createTexturedPulsar(position, radius, texture) {
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());

  const material = new THREE.MeshBasicMaterial({
    map: texture,
    color: new THREE.Color().setRGB(1.07, 1.07, 1.07),
    toneMapped: false,
  });
  const geometry = new THREE.SphereGeometry(radius, 128, 64);
  const sphere = new THREE.Mesh(geometry, material);
  sphere.name = "Pulsar textured surface — visual";

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: pointTexture,
    color: 0xffffff,
    transparent: true,
    opacity: 0.28,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  }));
  glow.name = "Pulsar compact glow — visual";
  glow.scale.setScalar(radius * 3.2);

  const group = new THREE.Group();
  group.name = "Pulsar browser surface";
  group.position.copy(position);
  group.add(glow, sphere);
  return group;
}

function makeReferenceMarkerTexture(color, glyph) {
  const textureCanvas = document.createElement("canvas");
  textureCanvas.width = 128;
  textureCanvas.height = 128;
  const context = textureCanvas.getContext("2d");
  context.clearRect(0, 0, 128, 128);
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = 5;
  context.beginPath();
  context.arc(64, 64, 27, 0, Math.PI * 2);
  context.stroke();

  context.lineWidth = 4;
  context.beginPath();
  if (glyph === "crosshair") {
    context.moveTo(64, 15);
    context.lineTo(64, 42);
    context.moveTo(64, 86);
    context.lineTo(64, 113);
    context.moveTo(15, 64);
    context.lineTo(42, 64);
    context.moveTo(86, 64);
    context.lineTo(113, 64);
    context.stroke();
    context.beginPath();
    context.arc(64, 64, 5, 0, Math.PI * 2);
    context.fill();
  } else {
    context.moveTo(45, 45);
    context.lineTo(83, 83);
    context.moveTo(83, 45);
    context.lineTo(45, 83);
    context.stroke();
  }

  const texture = new THREE.CanvasTexture(textureCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createReferenceMarker(position, options) {
  const material = new THREE.SpriteMaterial({
    map: makeReferenceMarkerTexture(options.color, options.glyph),
    color: 0xffffff,
    transparent: true,
    opacity: 0.96,
    depthWrite: false,
    depthTest: false,
    toneMapped: false,
  });
  const marker = new THREE.Sprite(material);
  marker.name = options.name;
  marker.position.copy(position);
  marker.scale.setScalar(options.size);
  marker.renderOrder = 30;
  return marker;
}

function createSceneLabel(text, position, options) {
  const labelCanvas = document.createElement("canvas");
  labelCanvas.width = 512;
  labelCanvas.height = 128;
  const context = labelCanvas.getContext("2d");
  context.clearRect(0, 0, labelCanvas.width, labelCanvas.height);
  context.font = "500 42px Inter, Arial, sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.shadowColor = "rgba(0,0,0,0.95)";
  context.shadowBlur = 9;
  context.lineWidth = 7;
  context.strokeStyle = "rgba(0,0,0,0.92)";
  context.strokeText(text, 256, 64);
  context.fillStyle = options.color;
  context.fillText(text, 256, 64);

  const texture = new THREE.CanvasTexture(labelCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
  }));
  const height = options.height || 0.22;
  sprite.scale.set(height * 4, height, 1);
  const offset = options.offset || new THREE.Vector3();
  sprite.position.copy(offset);
  sprite.center.set(0.5, 0.5);
  sprite.renderOrder = 40;
  sprite.name = text + " — fixed 3D annotation";

  const connectorEnd = offset.clone().multiplyScalar(0.78);
  const connectorGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(),
    connectorEnd,
  ]);
  const connector = new THREE.Line(
    connectorGeometry,
    new THREE.LineBasicMaterial({
      color: options.color,
      transparent: true,
      opacity: options.connectorOpacity || 0.66,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  connector.name = text + " — 3D label connector";
  connector.renderOrder = 18;

  const annotation = new THREE.Group();
  annotation.name = text + " — anchored 3D annotation";
  annotation.position.copy(position);
  if (options.connector !== false) annotation.add(connector);
  annotation.add(sprite);
  scene.add(annotation);
  if (options.layer) {
    if (!layerLabels[options.layer]) layerLabels[options.layer] = [];
    layerLabels[options.layer].push(annotation);
  }
  return annotation;
}

function createVectorArrow(origin, direction, options) {
  const normalizedDirection = direction.clone().normalize();
  const arrow = new THREE.ArrowHelper(
    normalizedDirection,
    origin,
    options.length,
    options.color,
    options.headLength,
    options.headWidth,
  );
  arrow.name = options.name;
  arrow.line.material.transparent = true;
  const opacity = options.opacity === undefined ? 0.92 : options.opacity;
  arrow.line.material.opacity = opacity;
  if (options.dashed) {
    arrow.line.material.dispose();
    arrow.line.material = new THREE.LineDashedMaterial({
      color: options.color,
      transparent: true,
      opacity,
      dashSize: options.dashSize === undefined ? 0.035 : options.dashSize,
      gapSize: options.gapSize === undefined ? 0.022 : options.gapSize,
    });
    arrow.line.computeLineDistances();
  }
  arrow.cone.material.transparent = true;
  arrow.cone.material.opacity = opacity;
  arrow.userData.labelPosition = origin.clone().addScaledVector(
    normalizedDirection,
    options.length,
  );
  return arrow;
}

function createCoordinateAxes(origin, referenceGeometry) {
  const group = new THREE.Group();
  group.name = "IBSEn x-y coordinate axes";
  const length = 0.34;
  const xArrow = createVectorArrow(
    origin,
    new THREE.Vector3().fromArray(referenceGeometry.coordinate_axes.x_unit_vector),
    {
      name: "IBSEn x axis",
      length,
      color: 0xef5a5a,
      headLength: 0.038,
      headWidth: 0.016,
      opacity: 0.78,
    },
  );
  const yArrow = createVectorArrow(
    origin,
    new THREE.Vector3().fromArray(referenceGeometry.coordinate_axes.y_unit_vector),
    {
      name: "IBSEn y axis",
      length,
      color: 0x62d67c,
      headLength: 0.038,
      headWidth: 0.016,
      opacity: 0.78,
    },
  );
  group.add(xArrow, yArrow);
  group.userData.labelPositions = {
    x: xArrow.userData.labelPosition,
    y: yArrow.userData.labelPosition,
  };
  return group;
}

function createLaminarBeam(origin, magneticAxis, pulsarRadius, visualGeometry) {
  const group = new THREE.Group();
  group.name = "Pulsar antipodal radio beam — model-informed visual";
  group.position.copy(origin);

  const axis = magneticAxis.clone().normalize();
  const sheetCount = visualGeometry.lamina_count;
  const bundleRadius = pulsarRadius
    * visualGeometry.bundle_radius_pulsar_display_radii;
  const startDistance = pulsarRadius * 0.34;
  const beamLength = visualGeometry.length_each_direction_separation_units;
  const orbitalNormal = new THREE.Vector3(0, 0, 1);

  [axis, axis.clone().negate()].forEach(function addBeamDirection(direction, directionIndex) {
    const bundle = new THREE.Group();
    bundle.name = directionIndex === 0 ? "Radio beam" : "Antipodal radio beam";
    let sheetNormal = new THREE.Vector3().crossVectors(direction, orbitalNormal);
    if (sheetNormal.lengthSq() < 1e-8) sheetNormal.set(1, 0, 0);
    sheetNormal.normalize();
    const sheetWidthAxis = new THREE.Vector3()
      .crossVectors(direction, sheetNormal)
      .normalize();
    bundle.setRotationFromMatrix(
      new THREE.Matrix4().makeBasis(sheetWidthAxis, direction, sheetNormal),
    );

    for (let index = 0; index < sheetCount; index += 1) {
      const normalizedOffset = THREE.MathUtils.mapLinear(
        index,
        0,
        sheetCount - 1,
        -0.92,
        0.92,
      );
      const offset = normalizedOffset * bundleRadius;
      const chord = 2 * bundleRadius * Math.sqrt(
        Math.max(0.0, 1 - normalizedOffset * normalizedOffset),
      );
      const centerWeight = 1 - Math.abs(normalizedOffset);
      const color = new THREE.Color();
      if (centerWeight > 0.72) {
        color.set(0xd9ffff);
      } else if (centerWeight > 0.34) {
        color.set(0x42edff);
      } else {
        color.set(0x00bfe8);
      }

      const geometry = new THREE.PlaneGeometry(chord, beamLength, 1, 12);
      geometry.translate(0, startDistance + beamLength * 0.5, 0);
      const material = new THREE.ShaderMaterial({
        uniforms: {
          beamColor: { value: color },
          sheetOpacity: { value: 0.30 + 0.66 * Math.pow(centerWeight, 1.35) },
        },
        vertexShader: `
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 beamColor;
          uniform float sheetOpacity;
          varying vec2 vUv;
          void main() {
            float transverse = pow(max(0.0, sin(3.14159265 * vUv.x)), 1.55);
            float fineStriation = 0.72 + 0.28 * pow(
              abs(sin(18.8495559 * vUv.x)),
              7.0
            );
            float baseFade = smoothstep(0.0, 0.006, vUv.y);
            float alpha = sheetOpacity * transverse * fineStriation * baseFade;
            gl_FragColor = vec4(beamColor, alpha);
          }
        `,
        side: THREE.DoubleSide,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        toneMapped: false,
      });
      const sheet = new THREE.Mesh(geometry, material);
      sheet.name = "Parallel radio-beam lamina " + String(index + 1);
      sheet.position.z = offset;
      sheet.renderOrder = 7;
      bundle.add(sheet);
    }
    group.add(bundle);
  });

  group.visible = false;
  return group;
}

function createRadialFlow(options) {
  const random = seededRandom(options.seed);
  const positions = new Float32Array(options.count * 3);
  const colors = new Float32Array(options.count * 3);
  const directions = [];
  const phases = new Float32Array(options.count);
  const limits = new Float32Array(options.count);
  const baseColor = new THREE.Color(options.color);

  for (let index = 0; index < options.count; index += 1) {
    directions.push(randomUnitVector(random));
    phases[index] = random();
    limits[index] = options.maxRadius * (0.72 + random() * 0.28);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    map: pointTexture,
    vertexColors: true,
    size: options.size,
    transparent: true,
    opacity: options.opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.userData.flow = {
    origin: options.origin.clone(),
    directions,
    phases,
    limits,
    minRadius: options.minRadius,
    maxRadius: options.maxRadius,
    speed: options.speed,
    baseColor,
  };
  updateRadialFlow(points, 0);
  animatedFlows.push({ type: "radial", object: points });
  return points;
}

function updateRadialFlow(points, deltaSeconds) {
  const flow = points.userData.flow;
  const positions = points.geometry.attributes.position.array;
  const colors = points.geometry.attributes.color.array;

  for (let index = 0; index < flow.phases.length; index += 1) {
    const span = Math.max(0.001, flow.limits[index] - flow.minRadius);
    flow.phases[index] = (flow.phases[index] + deltaSeconds * flow.speed / span) % 1;
    const phase = flow.phases[index];
    const radius = flow.minRadius + phase * span;
    const direction = flow.directions[index];
    positions[index * 3] = flow.origin.x + direction.x * radius;
    positions[index * 3 + 1] = flow.origin.y + direction.y * radius;
    positions[index * 3 + 2] = flow.origin.z + direction.z * radius;

    const pressureCue = 0.22 + 0.78 * Math.pow(1 - phase, 0.72);
    colors[index * 3] = flow.baseColor.r * pressureCue;
    colors[index * 3 + 1] = flow.baseColor.g * pressureCue;
    colors[index * 3 + 2] = flow.baseColor.b * pressureCue;
  }

  points.geometry.attributes.position.needsUpdate = true;
  points.geometry.attributes.color.needsUpdate = true;
}

function clipFlowAtShock(points, shockRoot) {
  const flow = points.userData.flow;
  const raycaster = new THREE.Raycaster();
  shockRoot.updateMatrixWorld(true);

  for (let index = 0; index < flow.directions.length; index += 1) {
    raycaster.set(flow.origin, flow.directions[index]);
    raycaster.far = flow.maxRadius;
    const hits = raycaster.intersectObject(shockRoot, true);
    const hit = hits.find(function firstUsefulHit(candidate) {
      return candidate.distance > flow.minRadius + 0.012;
    });
    if (hit) {
      flow.limits[index] = Math.max(flow.minRadius + 0.008, hit.distance - 0.008);
    }
  }
}

function smoothstep(edge0, edge1, value) {
  const t = THREE.MathUtils.clamp((value - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function createRadialPressureGlow(options) {
  const group = new THREE.Group();
  group.position.copy(options.origin);
  const layers = [
    { radius: options.maxRadius, sampleRadius: options.maxRadius * 0.72, weight: 0.64 },
    { radius: options.maxRadius * 0.58, sampleRadius: options.maxRadius * 0.40, weight: 0.84 },
    { radius: options.maxRadius * 0.27, sampleRadius: options.maxRadius * 0.18, weight: 1.0 },
  ];
  layers.forEach(function addLayer(layer) {
    const pressure = options.pressureNormalization * Math.pow(
      options.referenceRadius / layer.sampleRadius,
      options.pressureIndex,
    );
    // The same monotonic transfer function is used for both winds. It
    // compresses their large dynamic range but preserves their ordering.
    const pressureLight = Math.pow(
      THREE.MathUtils.clamp(pressure / options.displayPressureMax, 1e-10, 1),
      0.1,
    );
    const material = new THREE.SpriteMaterial({
      map: pressureTexture,
      color: options.color,
      transparent: true,
      opacity: options.opacity * layer.weight * pressureLight,
      blending: options.blending === undefined
        ? THREE.AdditiveBlending
        : options.blending,
      depthWrite: false,
      depthTest: true,
    });
    const sprite = new THREE.Sprite(material);
    sprite.scale.setScalar(layer.radius * 2);
    group.add(sprite);
  });
  return group;
}

function createRadialPressureIsosurface(options) {
  const geometry = new THREE.SphereGeometry(options.radius, 96, 64);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(options.color) },
      uOpacity: { value: options.opacity },
    },
    vertexShader: `
      varying vec3 vViewNormal;
      varying vec3 vViewPosition;
      void main() {
        vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
        vViewPosition = viewPosition.xyz;
        vViewNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * viewPosition;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uOpacity;
      varying vec3 vViewNormal;
      varying vec3 vViewPosition;
      void main() {
        vec3 viewDirection = normalize(-vViewPosition);
        float rim = pow(1.0 - abs(dot(vViewNormal, viewDirection)), 2.15);
        float alpha = uOpacity * (0.10 + 0.90 * rim);
        gl_FragColor = vec4(uColor, alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.NormalBlending,
  });
  const surface = new THREE.Mesh(geometry, material);
  surface.name = options.name;
  surface.position.copy(options.origin);
  surface.renderOrder = 2;
  surface.userData.pressureAtSurface = options.pressureAtSurface;
  surface.userData.scientificMeaning =
    "Radial-wind isobar evaluated at the analytic shock-apex distance";
  return surface;
}

function sampleDiskRadius(random, innerRadius, outerRadius, pressureIndex) {
  const areaWeightedExponent = 1 - pressureIndex;
  const integralExponent = areaWeightedExponent + 1;
  const sample = random();
  if (Math.abs(integralExponent) < 1e-6) {
    return innerRadius * Math.pow(outerRadius / innerRadius, sample);
  }
  const low = Math.pow(innerRadius, integralExponent);
  const high = Math.pow(outerRadius, integralExponent);
  return Math.pow(low + sample * (high - low), 1 / integralExponent);
}

function gaussianRandom(random) {
  const u = Math.max(random(), 1e-7);
  const v = random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function diskBasis(normal) {
  const normalized = normal.clone().normalize();
  const helper = Math.abs(normalized.z) > 0.92
    ? new THREE.Vector3(1, 0, 0)
    : new THREE.Vector3(0, 0, 1);
  const basisU = new THREE.Vector3().crossVectors(normalized, helper).normalize();
  const basisV = new THREE.Vector3().crossVectors(normalized, basisU).normalize();
  return { normal: normalized, basisU, basisV };
}

function createDiskPressureVolume(options) {
  const group = new THREE.Group();
  group.position.copy(options.origin);
  group.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 0, 1),
    options.normal.clone().normalize(),
  );
  const halfHeight = options.scaleHeightRatio
    * options.outerRadius
    * Math.pow(options.outerRadius / options.starRadius, options.scaleHeightExponent);
  const extent = halfHeight * 2.8;
  const vertexShader = `
    varying vec3 vDiskPosition;
    varying vec3 vViewNormal;
    varying vec3 vViewPosition;
    void main() {
      vDiskPosition = position;
      vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
      vViewPosition = viewPosition.xyz;
      vViewNormal = normalize(normalMatrix * normal);
      gl_Position = projectionMatrix * viewPosition;
    }
  `;
  const fragmentShader = `
    uniform vec3 uColor;
    uniform float uInnerRadius;
    uniform float uOuterRadius;
    uniform float uStarRadius;
    uniform float uScaleHeightRatio;
    uniform float uScaleHeightExponent;
    uniform float uPressureIndex;
    uniform float uPressureNormalization;
    uniform float uDisplayPressureMax;
    uniform float uSliceOpacity;
    varying vec3 vDiskPosition;
    varying vec3 vViewNormal;
    varying vec3 vViewPosition;

    void main() {
      float radius = length(vDiskPosition.xy);
      if (radius < uInnerRadius || radius > uOuterRadius) discard;
      float scaleHeight = uScaleHeightRatio * radius
        * pow(radius / uStarRadius, uScaleHeightExponent);
      float vertical = exp(-0.5 * pow(vDiskPosition.z / scaleHeight, 2.0));
      float pressure = uPressureNormalization
        * pow(uStarRadius / radius, uPressureIndex) * vertical;
      float normalizedPressure = clamp(pressure / uDisplayPressureMax, 1e-10, 1.0);
      float pressureSignal = pow(normalizedPressure, 0.24);
      float pressureLight = 0.34 + 1.10 * pressureSignal;
      float innerFade = smoothstep(uInnerRadius, uInnerRadius * 1.16, radius);
      float edgeFade = 1.0 - smoothstep(uOuterRadius * 0.70, uOuterRadius, radius);
      float pressureOpacity = 0.42 + 0.58 * pressureSignal;
      vec3 viewDirection = normalize(-vViewPosition);
      float viewWeight = pow(abs(dot(vViewNormal, viewDirection)), 2.0);
      float alpha = uSliceOpacity * pressureOpacity
        * innerFade * edgeFade * pow(vertical, 0.56) * viewWeight;
      gl_FragColor = vec4(uColor * pressureLight, alpha);
    }
  `;

  const sliceAxes = options.triplanar
    ? ["x", "y", "z"]
    : ["z"];
  sliceAxes.forEach(function addSliceStack(axis) {
    const limit = axis === "z" ? extent : options.outerRadius;
    for (let index = 0; index < options.slices; index += 1) {
      const fraction = options.slices === 1 ? 0.5 : index / (options.slices - 1);
      const coordinate = THREE.MathUtils.lerp(-limit, limit, fraction);
      let geometry;
      if (axis === "z") {
        geometry = new THREE.PlaneGeometry(
          options.outerRadius * 2,
          options.outerRadius * 2,
        );
        geometry.translate(0, 0, coordinate);
      } else if (axis === "x") {
        geometry = new THREE.PlaneGeometry(extent * 2, options.outerRadius * 2);
        geometry.rotateY(Math.PI * 0.5);
        geometry.translate(coordinate, 0, 0);
      } else {
        geometry = new THREE.PlaneGeometry(options.outerRadius * 2, extent * 2);
        geometry.rotateX(Math.PI * 0.5);
        geometry.translate(0, coordinate, 0);
      }
      const material = new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: new THREE.Color(options.color) },
          uInnerRadius: { value: options.innerRadius },
          uOuterRadius: { value: options.outerRadius },
          uStarRadius: { value: options.starRadius },
          uScaleHeightRatio: { value: options.scaleHeightRatio },
          uScaleHeightExponent: { value: options.scaleHeightExponent },
          uPressureIndex: { value: options.pressureIndex },
          uPressureNormalization: { value: options.pressureNormalization },
          uDisplayPressureMax: { value: options.displayPressureMax },
          uSliceOpacity: { value: options.opacity },
        },
        vertexShader,
        fragmentShader,
        transparent: true,
        blending: options.blending === undefined
          ? THREE.AdditiveBlending
          : options.blending,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
      const slice = new THREE.Mesh(geometry, material);
      slice.name = "Decretion-disk " + axis + "-axis volume slice";
      slice.frustumCulled = false;
      slice.renderOrder = options.renderOrder || 0;
      group.add(slice);
    }
  });

  for (let index = 0; index < (options.contours || 0); index += 1) {
    const fraction = index / Math.max(1, options.contours - 1);
    const minimumContourRadius = Math.max(
      options.innerRadius * 1.6,
      options.outerRadius * 0.12,
    );
    const radius = minimumContourRadius * Math.pow(
      options.outerRadius * 0.90 / minimumContourRadius,
      fraction,
    );
    const scaleHeight = options.scaleHeightRatio
      * radius
      * Math.pow(radius / options.starRadius, options.scaleHeightExponent);
    [-1, 0, 1].forEach(function addHeightContour(heightIndex) {
      const contourPoints = [];
      for (let segment = 0; segment < 192; segment += 1) {
        const angle = segment / 192 * Math.PI * 2;
        contourPoints.push(new THREE.Vector3(
          radius * Math.cos(angle),
          radius * Math.sin(angle),
          heightIndex * scaleHeight,
        ));
      }
      const contourGeometry = new THREE.BufferGeometry().setFromPoints(contourPoints);
      const contourMaterial = new THREE.LineBasicMaterial({
        color: options.color,
        transparent: true,
        opacity: THREE.MathUtils.lerp(
          heightIndex === 0 ? 0.12 : 0.065,
          heightIndex === 0 ? 0.03 : 0.018,
          fraction,
        ),
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        toneMapped: false,
      });
      const contour = new THREE.LineLoop(contourGeometry, contourMaterial);
      contour.name = heightIndex === 0
        ? "Decretion-disk midplane pressure contour"
        : "Decretion-disk one-scale-height contour";
      contour.renderOrder = (options.renderOrder || 0) + 1;
      group.add(contour);
    });
  }

  for (let guide = 0; guide < (options.heightGuides || 0); guide += 1) {
    const angle = guide / options.heightGuides * Math.PI * 2;
    [-1, 1].forEach(function addScaleHeightGuide(side) {
      const guidePoints = [];
      for (let sample = 0; sample < 80; sample += 1) {
        const fraction = sample / 79;
        const radius = THREE.MathUtils.lerp(
          Math.max(options.innerRadius * 1.6, options.outerRadius * 0.12),
          options.outerRadius * 0.92,
          fraction,
        );
        const scaleHeight = options.scaleHeightRatio
          * radius
          * Math.pow(radius / options.starRadius, options.scaleHeightExponent);
        guidePoints.push(new THREE.Vector3(
          radius * Math.cos(angle),
          radius * Math.sin(angle),
          side * scaleHeight,
        ));
      }
      const guideGeometry = new THREE.BufferGeometry().setFromPoints(guidePoints);
      const guideMaterial = new THREE.LineBasicMaterial({
        color: options.color,
        transparent: true,
        opacity: 0.026,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        toneMapped: false,
      });
      const profile = new THREE.Line(guideGeometry, guideMaterial);
      profile.name = "Decretion-disk flared scale-height guide";
      profile.renderOrder = (options.renderOrder || 0) + 1;
      group.add(profile);
    });
  }
  return group;
}

function createOrbitPath(pathCoordinates, options) {
  const points = pathCoordinates.map(function toVector(point) {
    return new THREE.Vector3().fromArray(point);
  });
  // The metadata closes the orbit by repeating the first point.
  const curvePoints = points.slice(0, -1);
  const curve = new THREE.CatmullRomCurve3(curvePoints, true, "centripetal");
  const group = new THREE.Group();

  if (VIEW_PRESET === "paper") {
    const sampledPoints = curve.getSpacedPoints(720);
    const lineGeometry = new THREE.BufferGeometry().setFromPoints(sampledPoints);
    const lineMaterial = new THREE.LineBasicMaterial({
      color: options.coreColor,
      transparent: true,
      opacity: 0.68,
      depthWrite: false,
      toneMapped: false,
    });
    const line = new THREE.LineLoop(lineGeometry, lineMaterial);
    line.name = "Thin barycentric orbit — paper reference";
    group.add(line);
    group.visible = false;
    return group;
  }

  const glowGeometry = new THREE.TubeGeometry(
    curve,
    512,
    options.glowRadius,
    6,
    true,
  );
  const glowMaterial = new THREE.MeshBasicMaterial({
    color: options.glowColor,
    transparent: true,
    opacity: 0.16,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  group.add(new THREE.Mesh(glowGeometry, glowMaterial));

  const coreGeometry = new THREE.TubeGeometry(
    curve,
    512,
    options.coreRadius,
    6,
    true,
  );
  const coreMaterial = new THREE.MeshBasicMaterial({
    color: options.coreColor,
    transparent: true,
    opacity: 0.88,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  group.add(new THREE.Mesh(coreGeometry, coreMaterial));
  group.visible = false;
  return group;
}

function createDiskFlow(options) {
  const random = seededRandom(options.seed);
  const positions = new Float32Array(options.count * 3);
  const colors = new Float32Array(options.count * 3);
  const radii = new Float32Array(options.count);
  const angles = new Float32Array(options.count);
  const heights = new Float32Array(options.count);
  const basis = diskBasis(options.normal);
  const normal = basis.normal;
  const basisU = basis.basisU;
  const basisV = basis.basisV;
  const inner = Math.max(options.innerRadius, options.starRadius * 1.3);

  for (let index = 0; index < options.count; index += 1) {
    const radius = sampleDiskRadius(
      random,
      inner,
      options.outerRadius,
      Math.max(1.0, options.pressureIndex * 0.5),
    );
    const scaleHeight = options.scaleHeightRatio
      * radius
      * Math.pow(radius / options.starRadius, options.scaleHeightExponent);
    radii[index] = radius;
    angles[index] = random() * Math.PI * 2;
    heights[index] = THREE.MathUtils.clamp(gaussianRandom(random), -1.8, 1.8)
      * scaleHeight;
    const edgeFade = 1 - smoothstep(0.76, 1, radius / options.outerRadius);
    const heat = (0.45 + 0.55 * (1 - radius / options.outerRadius)) * edgeFade;
    colors[index * 3] = 1.0 * heat;
    colors[index * 3 + 1] = 0.18 + 0.18 * heat;
    colors[index * 3 + 2] = 0.055;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({
    map: pointTexture,
    vertexColors: true,
    size: options.size,
    transparent: true,
    opacity: 0.74,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.userData.flow = {
    origin: options.origin.clone(),
    radii,
    angles,
    heights,
    basisU,
    basisV,
    normal,
    angularSpeed: options.angularSpeed,
  };
  updateDiskFlow(points, 0);
  animatedFlows.push({ type: "disk", object: points });
  return points;
}

function updateDiskFlow(points, deltaSeconds) {
  const flow = points.userData.flow;
  const positions = points.geometry.attributes.position.array;
  for (let index = 0; index < flow.radii.length; index += 1) {
    const radius = flow.radii[index];
    // Keplerian angular frequency scales as r^(-3/2). The global multiplier
    // controls visual playback speed, not the physical orbital clock.
    flow.angles[index] += deltaSeconds * flow.angularSpeed * Math.pow(radius, -1.5);
    const cosAngle = Math.cos(flow.angles[index]);
    const sinAngle = Math.sin(flow.angles[index]);
    const height = flow.heights[index];
    positions[index * 3] = flow.origin.x
      + flow.basisU.x * radius * cosAngle
      + flow.basisV.x * radius * sinAngle
      + flow.normal.x * height;
    positions[index * 3 + 1] = flow.origin.y
      + flow.basisU.y * radius * cosAngle
      + flow.basisV.y * radius * sinAngle
      + flow.normal.y * height;
    positions[index * 3 + 2] = flow.origin.z
      + flow.basisU.z * radius * cosAngle
      + flow.basisV.z * radius * sinAngle
      + flow.normal.z * height;
  }
  points.geometry.attributes.position.needsUpdate = true;
}

function addSystemLighting(starPosition, pulsarPosition) {
  const starLight = new THREE.PointLight(0xffa15e, 2.2, 3.4, 1.8);
  starLight.position.copy(starPosition);
  scene.add(starLight);

  const pulsarLight = new THREE.PointLight(0x83d9ff, 1.5, 1.8, 2.0);
  pulsarLight.position.copy(pulsarPosition);
  scene.add(pulsarLight);
}

function applyMetadata(metadata) {
  const physical = metadata.physical_model;
  const shock = metadata.shock_surface;
  document.getElementById("meta-epoch").textContent =
    "+" + physical.time_after_periastron_days.toFixed(0) + " days";
  document.getElementById("meta-separation").textContent =
    physical.separation_au.toFixed(3) + " AU";
  document.getElementById("meta-beta").textContent =
    physical.effective_wind_momentum_ratio_beta.toFixed(4);
  document.getElementById("meta-doppler").textContent =
    shock.field_min.toFixed(2) + "–" + shock.field_max.toFixed(2);
}

function applyViewPreset(name) {
  const visibility = name === "paper"
    ? {
        shock: true,
        pulsarBeam: false,
        starOrbit: true,
        pulsarOrbit: true,
        apex: true,
        barycenter: true,
        coordinateAxes: true,
        diskNormal: true,
        lineOfSight: true,
        stellarPressure: true,
        diskPressure: true,
        pulsarPressure: true,
        stellarWind: false,
        pulsarWind: false,
        diskGas: false,
        backgroundStars: false,
      }
    : {
        shock: true,
        pulsarBeam: false,
        starOrbit: false,
        pulsarOrbit: false,
        apex: false,
        barycenter: false,
        coordinateAxes: false,
        diskNormal: false,
        lineOfSight: false,
        stellarPressure: true,
        diskPressure: true,
        pulsarPressure: true,
        stellarWind: true,
        pulsarWind: true,
        diskGas: true,
        backgroundStars: true,
      };

  Object.entries(visibility).forEach(function setVisibility(entry) {
    const layerName = entry[0];
    const visible = entry[1];
    if (layerObjects[layerName]) layerObjects[layerName].visible = visible;
    (layerLabels[layerName] || []).forEach(function setLabelVisibility(label) {
      label.visible = visible;
    });
    const input = document.querySelector(`[data-layer="${layerName}"]`);
    if (input) input.checked = visible;
  });

  if (name === "paper") {
    scene.background.set(0x000000);
    scene.fog = null;
    renderer.toneMappingExposure = 0.92;
  }
}

function setCameraView(name, targets) {
  const views = {
    system: {
      position: new THREE.Vector3(-2.2, -4.0, 3.58),
      target: new THREE.Vector3(0, 0.52, 0),
    },
    star: {
      position: targets.star.clone().add(new THREE.Vector3(0.82, -0.72, 0.62)),
      target: targets.star,
    },
    pulsar: {
      position: targets.pulsar.clone().add(new THREE.Vector3(0.18, -0.17, 0.13)),
      target: targets.pulsar.clone().add(new THREE.Vector3(0, 0, -0.045)),
    },
    shock: {
      position: new THREE.Vector3(2.8, 0.1, 1.55),
      target: targets.shock,
    },
    orbits: {
      position: targets.orbits.center.clone().add(new THREE.Vector3(
        0,
        -targets.orbits.radius * 1.15,
        targets.orbits.radius * 2.9,
      )),
      target: targets.orbits.center,
    },
  };
  const view = views[name] || views.system;
  camera.position.copy(view.position);
  controls.target.copy(view.target);
  controls.update();
}

function bindControls(targets) {
  document.querySelectorAll("[data-view]").forEach(function bind(button) {
    button.addEventListener("click", function selectView() {
      document.querySelectorAll("[data-view]").forEach(function clear(item) {
        item.classList.remove("is-active");
      });
      button.classList.add("is-active");
      setCameraView(button.dataset.view, targets);
    });
  });

  document.querySelectorAll("[data-layer]").forEach(function bind(input) {
    input.addEventListener("change", function toggleLayer() {
      const object = layerObjects[input.dataset.layer];
      if (object) object.visible = input.checked;
      (layerLabels[input.dataset.layer] || []).forEach(function toggleLabel(label) {
        label.visible = input.checked;
      });
    });
  });

  function setPanelOpen(open) {
    controlPanel.classList.toggle("is-open", open);
    panelToggle.setAttribute("aria-expanded", String(open));
    panelToggle.textContent = open ? "Close" : "Layers";
  }

  panelToggle.addEventListener("click", function togglePanel() {
    setPanelOpen(!controlPanel.classList.contains("is-open"));
  });
  window.addEventListener("keydown", function closePanel(event) {
    if (event.key === "Escape") setPanelOpen(false);
  });
  setPanelOpen(VIEW_PRESET !== "paper");
}

function updateLabel(elementId, point, layerName) {
  const element = document.getElementById(elementId);
  if (
    !point
    || (layerName && (!layerObjects[layerName] || !layerObjects[layerName].visible))
  ) {
    element.hidden = true;
    return;
  }
  const projected = point.clone().project(camera);
  const visible = projected.z > -1 && projected.z < 1;
  element.hidden = !visible;
  if (!visible) return;
  const targetX = (projected.x + 1) * 0.5 * window.innerWidth;
  const targetY = (1 - projected.y) * 0.5 * window.innerHeight;
  const offset = VIEW_PRESET === "paper"
    ? (PAPER_LABEL_OFFSETS[elementId] || [14, -14])
    : [0, 0];
  const labelX = targetX + offset[0];
  const labelY = targetY + offset[1];
  element.style.left = labelX + "px";
  element.style.top = labelY + "px";
  if (VIEW_PRESET === "paper") {
    element.dataset.anchor = offset[0] < 0 ? "right" : "left";
  }
}

function resize() {
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

async function loadScene() {
  const metadataPromise = fetch(METADATA_URL).then(function parse(response) {
    if (!response.ok) throw new Error("Metadata request failed: " + response.status);
    return response.json();
  });
  const modelPromise = new GLTFLoader().loadAsync(MODEL_URL);
  const texturePromise = new THREE.TextureLoader().loadAsync(PULSAR_TEXTURE_URL);
  const results = await Promise.all([metadataPromise, modelPromise, texturePromise]);
  const metadata = results[0];
  const model = results[1].scene;
  const pulsarTexture = results[2];
  prepareModel(model);
  scene.add(model);
  applyMetadata(metadata);

  const physical = metadata.physical_model;
  const positions = physical.scene_positions;
  const flowModel = physical.flow_model;
  const beamModel = physical.pulsar_radio_beam_display;
  const referenceGeometry = physical.reference_geometry;
  const display = metadata.visual_interpretation;
  const starPosition = new THREE.Vector3().fromArray(positions.be_star);
  const pulsarPosition = new THREE.Vector3().fromArray(positions.pulsar);
  const diskNormal = new THREE.Vector3().fromArray(
    flowModel.decretion_disk.normal_scene_coordinates,
  ).normalize();

  const glbPulsar = findObject(model, function isPulsarBody(object) {
    return object.isMesh && object.name.toLowerCase() === "pulsar";
  });
  if (!glbPulsar) {
    throw new Error("The display-scale pulsar object was not found in the GLB.");
  }
  glbPulsar.visible = false;
  const pulsarSurface = createTexturedPulsar(
    pulsarPosition,
    display.pulsar_display_radius_separation_units,
    pulsarTexture,
  );
  scene.add(pulsarSurface);

  const pulsarBeam = createLaminarBeam(
    pulsarPosition,
    new THREE.Vector3().fromArray(beamModel.magnetic_axis_scene_coordinates),
    display.pulsar_display_radius_separation_units,
    beamModel.visual_geometry,
  );
  scene.add(pulsarBeam);
  layerObjects.pulsarBeam = pulsarBeam;

  const orbitDisplay = physical.orbit_display;
  const starOrbit = createOrbitPath(
    orbitDisplay.be_star_path_scene_coordinates,
    {
      glowColor: 0xff6e32,
      coreColor: 0xffb06f,
      glowRadius: 0.009,
      coreRadius: 0.0032,
    },
  );
  scene.add(starOrbit);
  layerObjects.starOrbit = starOrbit;

  const pulsarOrbit = createOrbitPath(
    orbitDisplay.pulsar_path_scene_coordinates,
    {
      glowColor: 0x167fbd,
      coreColor: 0x72dcff,
      glowRadius: 0.012,
      coreRadius: 0.004,
    },
  );
  scene.add(pulsarOrbit);
  layerObjects.pulsarOrbit = pulsarOrbit;

  const apexPosition = new THREE.Vector3().fromArray(
    referenceGeometry.apex.scene_coordinates,
  );
  const apexMarker = createReferenceMarker(apexPosition, {
    name: "Shock apex — model reference marker",
    color: "#ffe36e",
    glyph: "crosshair",
    size: 0.050,
  });
  scene.add(apexMarker);
  layerObjects.apex = apexMarker;

  const barycenterPosition = new THREE.Vector3().fromArray(
    referenceGeometry.barycenter.scene_coordinates,
  );
  const barycenterMarker = createReferenceMarker(barycenterPosition, {
    name: "Binary barycenter — orbit reference marker",
    color: "#f1f4ff",
    glyph: "cross",
    size: 0.046,
  });
  scene.add(barycenterMarker);
  layerObjects.barycenter = barycenterMarker;

  const axesOrigin = new THREE.Vector3().fromArray(
    referenceGeometry.coordinate_axes.origin_scene_coordinates,
  );
  const axes = createCoordinateAxes(axesOrigin, referenceGeometry);
  scene.add(axes);
  layerObjects.coordinateAxes = axes;

  const diskNormalArrow = createVectorArrow(
    starPosition,
    new THREE.Vector3().fromArray(referenceGeometry.disk_normal.unit_vector),
    {
      name: "Decretion-disk normal — IBSEn OpticalStar.n_disk",
      length: 0.50,
      color: 0xffad43,
      headLength: 0.052,
      headWidth: 0.021,
      opacity: 0.82,
    },
  );
  scene.add(diskNormalArrow);
  layerObjects.diskNormal = diskNormalArrow;

  const lineOfSightArrow = createVectorArrow(
    barycenterPosition,
    new THREE.Vector3().fromArray(referenceGeometry.line_of_sight.unit_vector),
    {
      name: "Line of sight — IBSEn IBS3D.unit_los",
      length: 0.72,
      color: 0x59d4ff,
      headLength: 0.055,
      headWidth: 0.022,
      opacity: 0.80,
      dashed: VIEW_PRESET === "paper",
    },
  );
  scene.add(lineOfSightArrow);
  layerObjects.lineOfSight = lineOfSightArrow;

  const orbitPoints = orbitDisplay.be_star_path_scene_coordinates
    .concat(orbitDisplay.pulsar_path_scene_coordinates)
    .map(function toOrbitVector(point) {
      return new THREE.Vector3().fromArray(point);
    });
  const orbitSphere = new THREE.Sphere();
  new THREE.Box3().setFromPoints(orbitPoints).getBoundingSphere(orbitSphere);

  const shockObject = findObject(model, function isShock(object) {
    return object.name.toLowerCase().includes("shock");
  });
  if (!shockObject) {
    throw new Error("The analytic shock object was not found in the GLB.");
  }

  layerObjects.shock = shockObject;
  const shockCenter = new THREE.Box3().setFromObject(shockObject).getCenter(new THREE.Vector3());
  const starWind = flowModel.stellar_polar_wind;
  const pulsarWindModel = flowModel.pulsar_wind;
  const diskModel = flowModel.decretion_disk;
  const starReferenceRadius = starWind.pressure_reference_radius_cm
    / physical.separation_cm;
  const pulsarReferenceRadius = pulsarWindModel.pressure_reference_radius_cm
    / physical.separation_cm;
  const starFieldInner = display.star_radius_separation_units * 1.3;
  const pulsarFieldInner = display.pulsar_display_radius_separation_units * 1.22;
  const pressureDisplayMax = Math.max(
    starWind.pressure_normalization_f_w * Math.pow(
      starReferenceRadius / starFieldInner,
      starWind.pressure_radial_power_law_index,
    ),
    pulsarWindModel.pressure_normalization_f_p * Math.pow(
      pulsarReferenceRadius / pulsarFieldInner,
      pulsarWindModel.pressure_radial_power_law_index,
    ),
  );
  const windDisplayRadius = Math.max(1.55, display.disk_outer_radius_separation_units);

  const stellarPressure = createRadialPressureGlow({
    origin: starPosition,
    maxRadius: windDisplayRadius,
    pressureIndex: starWind.pressure_radial_power_law_index,
    pressureNormalization: starWind.pressure_normalization_f_w,
    referenceRadius: starReferenceRadius,
    displayPressureMax: pressureDisplayMax,
    opacity: 0.68,
    color: 0xff9845,
  });
  const stellarApexRadius = starPosition.distanceTo(apexPosition);
  const stellarApexPressure = starWind.pressure_normalization_f_w * Math.pow(
    starReferenceRadius / stellarApexRadius,
    starWind.pressure_radial_power_law_index,
  );
  const paperStellarPressure = createRadialPressureIsosurface({
    name: "Stellar-wind pressure isobar through shock apex",
    origin: starPosition,
    radius: stellarApexRadius,
    pressureAtSurface: stellarApexPressure,
    opacity: 0.18,
    color: 0xc98f58,
  });
  scene.add(paperStellarPressure);
  paperStellarPressure.visible = VIEW_PRESET === "paper";
  if (VIEW_PRESET !== "paper") scene.add(stellarPressure);
  layerObjects.stellarPressure = VIEW_PRESET === "paper"
    ? paperStellarPressure
    : stellarPressure;

  const pulsarPressure = createRadialPressureGlow({
    origin: pulsarPosition,
    maxRadius: windDisplayRadius,
    pressureIndex: pulsarWindModel.pressure_radial_power_law_index,
    pressureNormalization: pulsarWindModel.pressure_normalization_f_p,
    referenceRadius: pulsarReferenceRadius,
    displayPressureMax: pressureDisplayMax,
    opacity: 0.68,
    color: 0x55cfff,
  });
  const pulsarApexRadius = pulsarPosition.distanceTo(apexPosition);
  const pulsarApexPressure = pulsarWindModel.pressure_normalization_f_p * Math.pow(
    pulsarReferenceRadius / pulsarApexRadius,
    pulsarWindModel.pressure_radial_power_law_index,
  );
  const paperPulsarPressure = createRadialPressureIsosurface({
    name: "Pulsar-wind pressure isobar through shock apex",
    origin: pulsarPosition,
    radius: pulsarApexRadius,
    pressureAtSurface: pulsarApexPressure,
    opacity: 0.24,
    color: 0x4f93b5,
  });
  if (VIEW_PRESET === "paper") scene.add(paperPulsarPressure);
  if (VIEW_PRESET !== "paper") scene.add(pulsarPressure);
  layerObjects.pulsarPressure = VIEW_PRESET === "paper"
    ? paperPulsarPressure
    : pulsarPressure;

  const diskPressure = createDiskPressureVolume({
    origin: starPosition,
    normal: diskNormal,
    innerRadius: display.disk_inner_radius_separation_units,
    outerRadius: display.disk_outer_radius_separation_units,
    starRadius: display.star_radius_separation_units,
    pressureIndex: diskModel.pressure_radial_power_law_index,
    pressureNormalization: diskModel.pressure_normalization_f_d,
    referenceRadius: display.star_radius_separation_units,
    displayPressureMax: pressureDisplayMax,
    scaleHeightRatio: diskModel.scale_height_ratio_at_stellar_surface,
    scaleHeightExponent: diskModel.scale_height_exponent,
    slices: VIEW_PRESET === "paper" ? 49 : 46,
    opacity: VIEW_PRESET === "paper" ? 0.105 : 0.028,
    color: VIEW_PRESET === "paper" ? 0xff5538 : 0xff4a28,
    blending: THREE.AdditiveBlending,
    renderOrder: VIEW_PRESET === "paper" ? 3 : 0,
    contours: VIEW_PRESET === "paper" ? 3 : 0,
    heightGuides: VIEW_PRESET === "paper" ? 4 : 0,
    triplanar: VIEW_PRESET === "paper",
  });
  scene.add(diskPressure);
  layerObjects.diskPressure = diskPressure;

  const stellarWind = createRadialFlow({
    seed: 12041,
    count: 520,
    origin: starPosition,
    minRadius: display.star_radius_separation_units * 1.45,
    maxRadius: 1.4,
    speed: 0.16,
    size: 0.018,
    opacity: 0.72,
    color: 0xffa34b,
  });
  clipFlowAtShock(stellarWind, shockObject);
  scene.add(stellarWind);
  layerObjects.stellarWind = stellarWind;

  const pulsarWind = createRadialFlow({
    seed: 7127,
    count: 380,
    origin: pulsarPosition,
    minRadius: display.pulsar_display_radius_separation_units * 1.35,
    maxRadius: 0.58,
    speed: 0.24,
    size: 0.016,
    opacity: 0.76,
    color: 0x55cfff,
  });
  clipFlowAtShock(pulsarWind, shockObject);
  scene.add(pulsarWind);
  layerObjects.pulsarWind = pulsarWind;

  const diskGas = createDiskFlow({
    seed: 9931,
    count: 820,
    origin: starPosition,
    normal: diskNormal,
    innerRadius: display.disk_inner_radius_separation_units,
    outerRadius: display.disk_outer_radius_separation_units,
    starRadius: display.star_radius_separation_units,
    pressureIndex: flowModel.decretion_disk.pressure_radial_power_law_index,
    scaleHeightRatio: flowModel.decretion_disk.scale_height_ratio_at_stellar_surface,
    scaleHeightExponent: flowModel.decretion_disk.scale_height_exponent,
    angularSpeed: 0.035,
    size: 0.018,
  });
  scene.add(diskGas);
  layerObjects.diskGas = diskGas;

  addSystemLighting(starPosition, pulsarPosition);
  labelTargets.star = starPosition;
  labelTargets.pulsar = pulsarPosition;
  labelTargets.apex = apexPosition;
  labelTargets.barycenter = barycenterPosition;
  labelTargets.xAxis = axes.userData.labelPositions.x;
  labelTargets.yAxis = axes.userData.labelPositions.y;
  labelTargets.diskNormal = diskNormalArrow.userData.labelPosition;
  labelTargets.lineOfSight = lineOfSightArrow.userData.labelPosition;

  if (VIEW_PRESET === "paper") {
    createSceneLabel("Be star", starPosition, {
      color: "#f3dfc9",
      offset: new THREE.Vector3(0.18, -0.10, 0.10),
    });
    createSceneLabel("Pulsar", pulsarPosition, {
      color: "#d9e8f4",
      offset: new THREE.Vector3(-0.18, 0.03, 0.11),
    });
    createSceneLabel("Shock apex", apexPosition, {
      color: "#f0d46b",
      offset: new THREE.Vector3(-0.22, -0.08, -0.09),
      layer: "apex",
    });
    createSceneLabel("Barycenter", barycenterPosition, {
      color: "#e1e5eb",
      offset: new THREE.Vector3(-0.21, -0.17, -0.12),
      layer: "barycenter",
    });
    createSceneLabel("x", axes.userData.labelPositions.x, {
      color: "#ef7777",
      offset: new THREE.Vector3(0.07, 0, 0.055),
      height: 0.15,
      connector: false,
      layer: "coordinateAxes",
    });
    createSceneLabel("y", axes.userData.labelPositions.y, {
      color: "#71df88",
      offset: new THREE.Vector3(0, 0.07, 0.065),
      height: 0.15,
      connector: false,
      layer: "coordinateAxes",
    });
    createSceneLabel("n_disk", diskNormalArrow.userData.labelPosition, {
      color: "#ffbd61",
      offset: new THREE.Vector3(0.075, 0, 0.085),
      height: 0.17,
      connector: false,
      layer: "diskNormal",
    });
    createSceneLabel("LOS", lineOfSightArrow.userData.labelPosition, {
      color: "#79ddff",
      offset: new THREE.Vector3(0.08, 0, 0.085),
      height: 0.17,
      connector: false,
      layer: "lineOfSight",
    });
  }

  const targets = {
    star: starPosition,
    pulsar: pulsarPosition,
    shock: shockCenter,
    orbits: {
      center: orbitSphere.center,
      radius: orbitSphere.radius,
    },
  };
  bindControls(targets);
  applyViewPreset(VIEW_PRESET);
  setCameraView("system", targets);
  setStatus(
    VIEW_PRESET === "paper" ? "Loaded" : "GLB + JSON + texture loaded",
    "ready",
  );
}

layerObjects.backgroundStars = addBackgroundStars();
resize();
window.addEventListener("resize", resize);

const clock = new THREE.Clock();
renderer.setAnimationLoop(function renderFrame() {
  const deltaSeconds = Math.min(clock.getDelta(), 0.05);
  if (VIEW_PRESET !== "paper") {
    animatedFlows.forEach(function update(flow) {
      if (!flow.object.visible) return;
      if (flow.type === "radial") updateRadialFlow(flow.object, deltaSeconds);
      if (flow.type === "disk") updateDiskFlow(flow.object, deltaSeconds);
    });
  }
  controls.update();
  if (VIEW_PRESET !== "paper") {
    updateLabel("star-label", labelTargets.star);
    updateLabel("pulsar-label", labelTargets.pulsar);
    updateLabel("apex-label", labelTargets.apex, "apex");
    updateLabel("barycenter-label", labelTargets.barycenter, "barycenter");
    updateLabel("x-axis-label", labelTargets.xAxis, "coordinateAxes");
    updateLabel("y-axis-label", labelTargets.yAxis, "coordinateAxes");
    updateLabel("disk-normal-label", labelTargets.diskNormal, "diskNormal");
    updateLabel("los-label", labelTargets.lineOfSight, "lineOfSight");
  }
  renderer.render(scene, camera);
});

loadScene().catch(showError);
