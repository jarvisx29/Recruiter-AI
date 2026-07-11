import * as faceapi from 'face-api.js'

const MODEL_URL = '/models'
let modelsLoaded = false
let modelsLoading = false
const modelsReadyCallbacks = []

export async function loadFaceModels() {
  if (modelsLoaded) return true
  if (modelsLoading) {
    return new Promise(res => modelsReadyCallbacks.push(res))
  }
  modelsLoading = true
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
    faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_URL),
    faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
  ])
  modelsLoaded = true
  modelsLoading = false
  modelsReadyCallbacks.forEach(fn => fn(true))
  return true
}

const DETECTOR_OPTS = new faceapi.TinyFaceDetectorOptions({ inputSize: 160, scoreThreshold: 0.4 })

export async function getDescriptor(source) {
  const result = await faceapi
    .detectSingleFace(source, DETECTOR_OPTS)
    .withFaceLandmarks(true)
    .withFaceDescriptor()
  return result?.descriptor ?? null
}

// threshold param lets callers choose strictness:
// Apply verification uses default 0.55, Interview monitoring uses 0.6
export function compareDescriptors(d1, d2, threshold = 0.55) {
  if (!d1 || !d2) return { matched: false, distance: 1 }
  const distance = faceapi.euclideanDistance(d1, d2)
  return { matched: distance < threshold, distance: +distance.toFixed(3) }
}

export async function captureFromVideo(videoEl) {
  if (!videoEl || !videoEl.videoWidth || !videoEl.videoHeight || videoEl.readyState < 2) return null
  // Resize to 320px wide before inference — reduces pixel data 4-8x vs full webcam resolution
  const W = Math.min(videoEl.videoWidth, 320)
  const H = Math.round(W * videoEl.videoHeight / videoEl.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  canvas.getContext('2d').drawImage(videoEl, 0, 0, W, H)
  return getDescriptor(canvas)
}
