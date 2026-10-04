// Set this one value after deploying the backend to Render.
export const API_BASE_URL = 'https://reviewarudo.onrender.com';
const BACKEND_UNAVAILABLE_MESSAGE =
  'Unable to connect to the learning-material server. Check your internet connection or try again later. Render may need a minute to wake up.';
export function request(path, body, progress = () => {}) {
  return new Promise((resolve, reject) => {
    if (API_BASE_URL.includes('YOUR-RENDER')) return reject(new Error(
      'Backend not configured yet. Try the demo, or set API_BASE_URL in js/api.js after deploying Render.'
      ));
    const xhr = new XMLHttpRequest();
    xhr.open('POST', API_BASE_URL.replace(/\/$/, '') + path);
    xhr.timeout = 16 * 60 * 1000; // Slightly longer than the backend's 15-minute deadline.
    if (!(body instanceof FormData)) xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) progress(Math.round(e.loaded / e.total * 100));
    };
    xhr.onload = () => {
      try {
        const result = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300 && result.success) resolve(result.data);
        else reject(new Error(result.error?.message ||
          'The server could not complete this request.'));
      } catch {
        reject(new Error(BACKEND_UNAVAILABLE_MESSAGE));
      }
    };
    xhr.onerror = () => reject(new Error(BACKEND_UNAVAILABLE_MESSAGE));
    xhr.ontimeout = () => reject(new Error(
      'The request timed out. Try fewer documents or outputs.'));
    xhr.send(body instanceof FormData ? body : JSON.stringify(body));
  });
}
