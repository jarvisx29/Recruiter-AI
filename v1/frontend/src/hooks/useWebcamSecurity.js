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

const DETECTOR_OPTS = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 })

export async function getDescriptor(source) {
  // source: HTMLImageElement | HTMLVideoElement | HTMLCanvasElement
  const result = await faceapi
    .detectSingleFace(source, DETECTOR_OPTS)
    .withFaceLandmarks(true)
    .withFaceDescriptor()
  return result?.descriptor ?? null
}

export function compareDescriptors(d1, d2) {
  if (!d1 || !d2) return { matched: false, distance: 1 }
  const distance = faceapi.euclideanDistance(d1, d2)
  return { matched: distance < 0.55, distance: +distance.toFixed(3) }
}

export async function captureFromVideo(videoEl) {
  const canvas = document.createElement('canvas')
  canvas.width = videoEl.videoWidth
  canvas.height = videoEl.videoHeight
  canvas.getContext('2d').drawImage(videoEl, 0, 0)
  return getDescriptor(canvas)
}
