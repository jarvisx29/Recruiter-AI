import * as faceapi from 'face-api.js'

const MODEL_URL = '/models'
let modelsLoaded = false
let modelsLoading = false
const modelsReadyCallbacks = []

export async function loadFaceModels() {
  if (modelsLoaded) return true
  if (modelsLoading) return new Promise(res => modelsReadyCallbacks.push(res))
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

export function compareDescriptors(d1, d2, threshold = 0.55) {
  if (!d1 || !d2) return { matched: false, distance: 1 }
  const distance = faceapi.euclideanDistance(d1, d2)
  return { matched: distance < threshold, distance: +distance.toFixed(3) }
}

// Pass video element directly to face-api — avoids manual canvas overhead.
// face-api reads the current frame internally at its inputSize (160px).
export async function captureFromVideo(videoEl) {
  if (!videoEl || !videoEl.videoWidth || !videoEl.videoHeight || videoEl.readyState < 2) return null
  return getDescriptor(videoEl)
}
