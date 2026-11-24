// Upload page: picks a file, requests an upload URL, sends the file to Blob Storage.
import { requestUpload, uploadFile, getSessionUser } from './api.js';
import { bindThemeToggle } from './common.js';

const MAX_BYTES = 500 * 1024 * 1024;

const form = document.getElementById('upload-form');
const fileInput = document.getElementById('file');
const fileName = document.getElementById('file-name');
const titleInput = document.getElementById('title');
const captionInput = document.getElementById('caption');
const submit = document.getElementById('upload-submit');
const status = document.getElementById('upload-status');
const errorEl = document.getElementById('upload-error');
const bar = document.getElementById('progress-bar');

if (!getSessionUser()) {
  location.replace('index.html');
}

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  fileName.textContent = file ? file.name : 'Choose a video file';
});

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  errorEl.hidden = true;

  const file = fileInput.files[0];
  const title = titleInput.value.trim();
  if (!file) return showError('Choose a video file first.');
  if (!file.type.startsWith('video/')) return showError('That file is not a video.');
  if (file.size > MAX_BYTES) return showError('Videos must be 500 MB or smaller.');
  if (!title) return showError('Add a title for your video.');

  submit.disabled = true;
  try {
    status.textContent = 'Preparing upload…';
    const { videoId, uploadUrl } = await requestUpload({
      title,
      caption: captionInput.value.trim(),
      fileName: file.name,
      contentType: file.type,
      sizeBytes: file.size
    });

    status.textContent = 'Uploading…';
    await uploadFile(videoId, uploadUrl, file, pct => {
      bar.style.width = pct + '%';
      status.textContent = `Uploading… ${pct}%`;
    });

    status.textContent = 'Uploaded. Processing starts now, and the video appears in your feed once it is ready.';
    setTimeout(() => { location.href = 'feed.html'; }, 1500);
  } catch (err) {
    showError(err.message);
    status.textContent = '';
    submit.disabled = false;
  }
});

bindThemeToggle();
