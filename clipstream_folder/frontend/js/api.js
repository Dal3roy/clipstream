// All data access goes through this file. Pages never call fetch() directly,
// so switching from mock data to the real API only changes this module.
import { CONFIG } from './config.js';

const SESSION_KEY = 'clipstream.user';
let mockDb = null;

// ---------- helpers ----------

async function request(path, options = {}) {
  const user = getSessionUser();
  const headers = { 'Content-Type': 'application/json' };
  if (user && user.token) headers.Authorization = `Bearer ${user.token}`;

  const res = await fetch(CONFIG.apiBase + path, {
    credentials: 'include',
    ...options,
    headers: { ...headers, ...(options.headers || {}) }
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

async function loadMock() {
  if (!mockDb) {
    const res = await fetch('data/videos.json');
    mockDb = await res.json();
    mockDb.likedVideoIds = new Set();
    mockDb.commentCounter = 100;
  }
  return mockDb;
}

// Placeholder sentiment for mock mode only. The real app calls Azure AI Language.
const POSITIVE = ['love', 'great', 'amazing', 'good', 'clean', 'worked', 'best', 'favourite', 'nice', 'perfect', 'thanks', 'awesome', 'brilliant', 'saving', 'satisfying'];
const NEGATIVE = ['bad', 'hate', 'worst', 'boring', 'awful', 'terrible', 'wrong', 'fail', 'broken', 'annoying', 'disappointed', 'blurry'];

export function mockSentiment(text) {
  const words = text.toLowerCase().match(/[a-z']+/g) || [];
  const pos = words.filter(w => POSITIVE.includes(w)).length;
  const neg = words.filter(w => NEGATIVE.includes(w)).length;
  const label = pos > neg ? 'positive' : neg > pos ? 'negative' : 'neutral';
  const total = pos + neg + 2;
  return {
    label,
    scores: {
      positive: +((pos + 1) / total).toFixed(2),
      neutral: +(1 / total).toFixed(2),
      negative: +((neg + 1) / total).toFixed(2)
    }
  };
}

// ---------- session ----------

export function getSessionUser() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY));
  } catch {
    return null;
  }
}

function saveSessionUser(user) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
  } catch {
    /* storage blocked: the page still works, the user just isn't remembered */
  }
}

export async function login(email, password) {
  if (CONFIG.useMock) {
    if (!email || !password) throw new Error('Enter your email and password.');
    const username = email.split('@')[0];
    const user = { username, displayName: username, initials: username.slice(0, 2).toUpperCase() };
    saveSessionUser(user);
    return user;
  }
  const user = await request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  saveSessionUser(user);
  return user;
}

export async function signup(name, email, password) {
  if (CONFIG.useMock) {
    if (!name || !email || !password) throw new Error('Fill in every field to sign up.');
    return login(email, password);
  }
  const user = await request('/auth/signup', { method: 'POST', body: JSON.stringify({ name, email, password }) });
  saveSessionUser(user);
  return user;
}

export async function logout() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
  if (!CONFIG.useMock) {
    await request('/auth/logout', { method: 'POST' }).catch(() => {});
  }
}

// ---------- videos ----------

export async function getVideos() {
  if (CONFIG.useMock) {
    const db = await loadMock();
    return db.videos.map(v => ({ ...v }));
  }
  return request('/videos');
}

export async function getVideo(id) {
  if (CONFIG.useMock) {
    const db = await loadMock();
    const v = db.videos.find(x => x.id === id);
    if (!v) throw new Error('Video not found');
    return { ...v };
  }
  return request(`/videos/${encodeURIComponent(id)}`);
}

// ---------- comments ----------

export async function getComments(videoId) {
  if (CONFIG.useMock) {
    const db = await loadMock();
    return db.comments
      .filter(c => c.videoId === videoId)
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }
  return request(`/videos/${encodeURIComponent(videoId)}/comments`);
}

export async function postComment(videoId, text) {
  const trimmed = text.trim();
  if (!trimmed) throw new Error('Comment cannot be empty.');
  if (CONFIG.useMock) {
    const db = await loadMock();
    const user = getSessionUser() || { username: 'guest', initials: 'G', color: '#3b5bdb' };
    db.commentCounter += 1;
    const comment = {
      id: 'c_' + db.commentCounter,
      videoId,
      username: user.username,
      initials: user.initials,
      color: '#3b5bdb',
      text: trimmed,
      createdAt: new Date().toISOString(),
      sentiment: mockSentiment(trimmed)
    };
    db.comments.push(comment);
    return comment;
  }
  return request(`/videos/${encodeURIComponent(videoId)}/comments`, {
    method: 'POST',
    body: JSON.stringify({ text: trimmed })
  });
}

// Sentiment counts for one video's comments, used by the summary bar.
export function summarise(comments) {
  const counts = { positive: 0, neutral: 0, negative: 0 };
  comments.forEach(c => {
    if (c.sentiment && counts[c.sentiment.label] !== undefined) counts[c.sentiment.label] += 1;
  });
  return counts;
}

// ---------- likes ----------

// currentlyLiked is the state the page shows now. The new state is the opposite.
export async function toggleLike(videoId, currentlyLiked) {
  if (CONFIG.useMock) {
    const db = await loadMock();
    const video = db.videos.find(v => v.id === videoId);
    const liked = !currentlyLiked;
    if (liked && !db.likedVideoIds.has(videoId)) {
      db.likedVideoIds.add(videoId);
      video.likeCount += 1;
    } else if (!liked && db.likedVideoIds.has(videoId)) {
      db.likedVideoIds.delete(videoId);
      video.likeCount -= 1;
    }
    return { liked, likeCount: video.likeCount };
  }
  return request(`/videos/${encodeURIComponent(videoId)}/like`, {
    method: currentlyLiked ? 'DELETE' : 'POST'
  });
}

// ---------- upload ----------

export async function requestUpload(meta) {
  if (CONFIG.useMock) {
    const db = await loadMock();
    const user = getSessionUser() || { username: 'guest', displayName: 'Guest', initials: 'G', color: '#3b5bdb' };
    const id = 'v_' + (2000 + db.videos.length);
    const video = {
      id,
      title: meta.title,
      caption: meta.caption,
      creator: { username: user.username, displayName: user.displayName || user.username, initials: user.initials, color: '#3b5bdb' },
      tone: '#27272a',
      sound: 'Original sound',
      tags: [],
      status: 'processing',
      likeCount: 0,
      createdAt: new Date().toISOString(),
      transcript: []
    };
    db.videos.unshift(video);
    return { videoId: id, uploadUrl: null };
  }
  return request('/videos/upload-url', { method: 'POST', body: JSON.stringify(meta) });
}

// Uploads the file. Mock mode simulates progress, then marks the video ready after a delay
// to stand in for conversion and transcription running in Azure Functions.
export function uploadFile(videoId, uploadUrl, file, onProgress) {
  if (CONFIG.useMock) {
    return new Promise(resolve => {
      let pct = 0;
      const timer = setInterval(async () => {
        pct = Math.min(100, pct + 20);
        onProgress(pct);
        if (pct === 100) {
          clearInterval(timer);
          const db = await loadMock();
          setTimeout(() => {
            const v = db.videos.find(x => x.id === videoId);
            if (v) {
              v.status = 'ready';
              v.tone = '#1f2a37';
              v.transcript = ['Mock transcript: the real one comes from Azure AI Speech.'];
            }
          }, 4000);
          resolve();
        }
      }, 300);
    });
  }
  // Real mode: PUT the file straight to Blob Storage using the SAS URL. The API never sees the bytes.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', uploadUrl);
    xhr.setRequestHeader('x-ms-blob-type', 'BlockBlob');
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error('Upload failed')));
    xhr.onerror = () => reject(new Error('Upload failed. Check your connection.'));
    xhr.send(file);
  });
}
