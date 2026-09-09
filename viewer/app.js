import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const MODEL_URL = "../public/models/binary-shock-v0.1.glb";
const METADATA_URL = "../public/models/binary-shock-v0.1.metadata.json";
const PULSAR_TEXTURE_URL = "../public/textures/neutron-star-thermal-v0.3.png";

const canvas = document.getElementById("scene-canvas");
const statusElement = document.getElementById("load-status");
const errorPanel = document.getElementById("error-panel");
const errorMessage = document.getElementById("error-message");

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
const animatedFlows = [];
const labelTargets = {};

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
  scene.add(new THREE.Points(geometry, material));
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
        material.opacity = 0.68;
        material.depthWrite = false;
        material.side = THREE.DoubleSide;
        material.vertexColors = true;
        if (material.emissive) material.emissive.multiplyScalar(1.35);
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
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      depthTest: true,
    });
    const sprite = new THREE.Sprite(material);
    sprite.scale.setScalar(layer.radius * 2);
    group.add(sprite);
  });
  return group;
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
  const geometry = new THREE.PlaneGeometry(
    options.outerRadius * 2,
    options.outerRadius * 2,
  );
  const vertexShader = `
    varying vec2 vDiskPosition;
    void main() {
      vDiskPosition = position.xy;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
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
    uniform float uSliceHeight;
    uniform float uSliceOpacity;
    varying vec2 vDiskPosition;

    void main() {
      float radius = length(vDiskPosition);
      if (radius < uInnerRadius || radius > uOuterRadius) discard;
      float scaleHeight = uScaleHeightRatio * radius
        * pow(radius / uStarRadius, uScaleHeightExponent);
      float vertical = exp(-0.5 * pow(uSliceHeight / scaleHeight, 2.0));
      float pressure = uPressureNormalization
        * pow(uStarRadius / radius, uPressureIndex) * vertical;
      float normalizedPressure = clamp(pressure / uDisplayPressureMax, 1e-10, 1.0);
      float pressureLight = 0.14 + 0.86 * pow(normalizedPressure, 0.12);
      float innerFade = smoothstep(uInnerRadius, uInnerRadius * 1.16, radius);
      float edgeFade = 1.0 - smoothstep(uOuterRadius * 0.70, uOuterRadius, radius);
      float alpha = uSliceOpacity * innerFade * edgeFade * pow(vertical, 0.56);
      gl_FragColor = vec4(uColor * pressureLight, alpha);
    }
  `;

  for (let index = 0; index < options.slices; index += 1) {
    const fraction = options.slices === 1 ? 0.5 : index / (options.slices - 1);
    const height = THREE.MathUtils.lerp(-extent, extent, fraction);
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
        uSliceHeight: { value: height },
        uSliceOpacity: { value: options.opacity },
      },
      vertexShader,
      fragmentShader,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const slice = new THREE.Mesh(geometry, material);
    slice.position.z = height;
    slice.frustumCulled = false;
    group.add(slice);
  }
  return group;
}

function createOrbitPath(pathCoordinates, options) {
  const points = pathCoordinates.map(function toVector(point) {
    return new THREE.Vector3().fromArray(point);
  });
  // The metadata closes the orbit by repeating the first point. TubeGeometry
  // closes the curve itself, so omit that duplicate when constructing it.
  const curvePoints = points.slice(0, -1);
  const curve = new THREE.CatmullRomCurve3(curvePoints, true, "centripetal");
  const group = new THREE.Group();

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

function setCameraView(name, targets) {
  const views = {
    system: {
      position: new THREE.Vector3(3.3, -2.7, 2.25),
      target: new THREE.Vector3(0, 0.92, 0),
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
    });
  });
}

function updateLabel(elementId, point) {
  const element = document.getElementById(elementId);
  if (!point) {
    element.hidden = true;
    return;
  }
  const projected = point.clone().project(camera);
  const visible = projected.z > -1 && projected.z < 1;
  element.hidden = !visible;
  if (!visible) return;
  element.style.left = ((projected.x + 1) * 0.5 * window.innerWidth) + "px";
  element.style.top = ((1 - projected.y) * 0.5 * window.innerHeight) + "px";
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
  scene.add(stellarPressure);
  layerObjects.stellarPressure = stellarPressure;

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
  scene.add(pulsarPressure);
  layerObjects.pulsarPressure = pulsarPressure;

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
    slices: 46,
    opacity: 0.028,
    color: 0xff4a28,
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
  setCameraView("system", targets);
  setStatus("GLB + JSON + texture loaded", "ready");
}

addBackgroundStars();
resize();
window.addEventListener("resize", resize);

const clock = new THREE.Clock();
renderer.setAnimationLoop(function renderFrame() {
  const deltaSeconds = Math.min(clock.getDelta(), 0.05);
  animatedFlows.forEach(function update(flow) {
    if (!flow.object.visible) return;
    if (flow.type === "radial") updateRadialFlow(flow.object, deltaSeconds);
    if (flow.type === "disk") updateDiskFlow(flow.object, deltaSeconds);
  });
  controls.update();
  updateLabel("star-label", labelTargets.star);
  updateLabel("pulsar-label", labelTargets.pulsar);
  renderer.render(scene, camera);
});

loadScene().catch(showError);
