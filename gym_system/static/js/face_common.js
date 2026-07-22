/**
 * face_common.js
 * -----------------------------------------------------------------------
 * Utilidades compartidas para reconocimiento facial con face-api.js.
 * Usado tanto en la pantalla de registro (clients) como en check-in
 * (attendance/facial).
 *
 * IMPORTANTE — modelos:
 * Por defecto los modelos se cargan desde un CDN (jsdelivr) para que todo
 * funcione sin pasos extra. Para producción se recomienda descargarlos y
 * servirlos desde /static/face_models/ (más rápido y no depende de un
 * tercero). Los archivos necesarios son:
 *   tiny_face_detector_model-*
 *   face_landmark_68_model-*
 *   face_recognition_model-*
 * Se consiguen en: https://github.com/justadudewhohacks/face-api.js/tree/master/weights
 * Si los copias a static/face_models/, cambia MODEL_URL abajo por:
 *   '/static/face_models'
 */

const FACE_MODEL_URL = 'https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@master/weights';

let _modelsLoaded = false;

async function loadFaceModels() {
    if (_modelsLoaded) return;
    await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(FACE_MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL),
    ]);
    _modelsLoaded = true;
}

async function startCamera(videoEl, facingMode = 'environment') {
    let stream;
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 480, height: 360, facingMode: { exact: facingMode } },
            audio: false,
        });
    } catch (err) {
        // Si el celular no tiene esa cámara exacta (ej. no tiene trasera separada),
        // reintenta sin "exact" para que el navegador use la que tenga disponible.
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 480, height: 360, facingMode },
            audio: false,
        });
    }
    videoEl.srcObject = stream;
    await videoEl.play();
    return stream;
}

function stopCamera(stream) {
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
    }
}

/**
 * Detecta un rostro en el video y devuelve su embedding (Array de 128 floats),
 * o null si no se detectó ningún rostro con suficiente confianza.
 */
async function getFaceEmbedding(videoEl) {
    const detection = await faceapi
        .detectSingleFace(videoEl, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

    if (!detection) return null;
    return Array.from(detection.descriptor);
}
