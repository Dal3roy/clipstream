// Feed page: video player, likes, captions, comments and sentiment.
import { getVideos, getComments, postComment, toggleLike, summarise, getSessionUser, logout } from './api.js';
import { bindThemeToggle, esc, formatCount, timeAgo } from './common.js';

const user = getSessionUser();
if (!user) {
  location.replace('index.html');
}

const el = id => document.getElementById(id);

const state = {
  videos: [],
  index: 0,
  comments: [],
  likedIds: new Set(),
  captionsOn: false
};

// ---------- rendering ----------

function avatarHtml(person, sizeClass = '') {
  return `<span class="avatar ${sizeClass}" style="background:${esc(person.color)}" aria-hidden="true">${esc(person.initials)}</span>`;
}


function renderVideo() {
  const video = state.videos[state.index];
  if (!video) return;

  // Player
  el('player').style.background = video.tone;
  el('player-title').textContent = video.title;
  el('player-sound').textContent = video.sound;
  el('player-note').textContent = video.status === 'ready' ? 'Video' : 'Processing';

  const pill = el('status-pill');
  pill.textContent = video.status === 'ready' ? 'Ready' : 'Processing…';
  pill.hidden = video.status === 'ready';

  // Captions (advanced feature 1: transcription)
  const hasTranscript = video.transcript && video.transcript.length > 0;
  el('captions-toggle').disabled = !hasTranscript;
  el('captions').hidden = !(state.captionsOn && hasTranscript);
  el('captions-text').innerHTML = hasTranscript
    ? video.transcript.map(line => `<p>${esc(line)}</p>`).join('')
    : '';

  // Likes: remembered per video in this session
  const liked = state.likedIds.has(video.id);
  el('like').setAttribute('aria-pressed', String(liked));
  el('like').style.color = liked ? 'var(--accent)' : '';
  el('heart').setAttribute('fill', liked ? 'currentColor' : 'none');
  el('like-count').textContent = formatCount(video.likeCount);

  // Creator
  const avatar = el('creator-avatar');
  avatar.textContent = video.creator.initials;
  avatar.style.background = video.creator.color;
  el('creator-name').textContent = video.creator.displayName;
  el('creator-handle').textContent = '@' + video.creator.username;
  el('creator-caption').textContent = video.caption;
  el('creator-tags').innerHTML = video.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('');

  // Position
  el('position').textContent = `${state.index + 1} / ${state.videos.length}`;
  el('prev').disabled = state.index === 0;
  el('next').disabled = state.index === state.videos.length - 1;
}

function renderComments() {
  const list = el('comment-list');
  if (state.comments.length === 0) {
    list.innerHTML = '<p class="empty">No comments yet. Be the first.</p>';
  } else {
    list.innerHTML = state.comments.map(c => {
      const label = c.sentiment ? c.sentiment.label : 'neutral';
      return `
        <div class="comment">
          ${avatarHtml({ color: c.color, initials: c.initials }, 'avatar-sm')}
          <div class="comment-body">
            <div class="comment-meta">
              <span class="name">${esc(c.username)}</span>
              <span class="time">${timeAgo(c.createdAt)}</span>
              <span class="sentiment-badge sentiment-${label}" title="Comment sentiment, detected automatically">${esc(label)}</span>
            </div>
            <span class="comment-text">${esc(c.text)}</span>
          </div>
        </div>`;
    }).join('');
  }
  renderSummary();
}

function renderSummary() {
  const counts = summarise(state.comments);
  const total = counts.positive + counts.neutral + counts.negative;
  const pct = n => (total ? Math.round((n / total) * 100) : 0);

  const bar = el('sentiment-bar');
  const [pos, neu, neg] = bar.children;
  pos.style.width = pct(counts.positive) + '%';
  neu.style.width = pct(counts.neutral) + '%';
  neg.style.width = pct(counts.negative) + '%';
  bar.setAttribute('aria-label', `Comment mood: ${pct(counts.positive)}% positive, ${pct(counts.neutral)}% neutral, ${pct(counts.negative)}% negative`);

  el('sentiment-legend').innerHTML = total
    ? `<span>${pct(counts.positive)}% positive</span><span>${pct(counts.neutral)}% neutral</span><span>${pct(counts.negative)}% negative</span>`
    : '<span>Mood appears once there are comments</span>';

  el('comment-count').textContent = formatCount(state.comments.length);
  el('comments-total').textContent = `${state.comments.length} total`;
}

// ---------- data ----------

async function loadCurrent() {
  const video = state.videos[state.index];
  state.comments = await getComments(video.id);
  renderVideo();
  renderComments();
}

async function move(delta) {
  const next = Math.min(state.videos.length - 1, Math.max(0, state.index + delta));
  if (next === state.index) return;
  state.index = next;
  state.captionsOn = false;
  el('captions-toggle').setAttribute('aria-pressed', 'false');
  await loadCurrent();
}

// ---------- events ----------

el('prev').addEventListener('click', () => move(-1));
el('next').addEventListener('click', () => move(1));

document.addEventListener('keydown', event => {
  if (event.target.matches('input, textarea')) return;
  if (event.key === 'ArrowUp') move(-1);
  if (event.key === 'ArrowDown') move(1);
});

el('like').addEventListener('click', async () => {
  const video = state.videos[state.index];
  const result = await toggleLike(video.id, state.likedIds.has(video.id));
  if (result.liked) state.likedIds.add(video.id);
  else state.likedIds.delete(video.id);
  video.likeCount = result.likeCount;
  renderVideo();
});

el('captions-toggle').addEventListener('click', () => {
  state.captionsOn = !state.captionsOn;
  el('captions-toggle').setAttribute('aria-pressed', String(state.captionsOn));
  renderVideo();
});

el('comments-jump').addEventListener('click', () => el('comment-input').focus());

el('comment-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = el('comment-input');
  const text = input.value;
  if (!text.trim()) return;

  const button = el('comment-submit');
  button.disabled = true;
  try {
    const comment = await postComment(state.videos[state.index].id, text);
    state.comments.push(comment);
    input.value = '';
    renderComments();
  } catch (err) {
    alert(err.message);
  } finally {
    button.disabled = false;
    input.focus();
  }
});

el('logout').addEventListener('click', async () => {
  await logout();
  location.href = 'index.html';
});

// ---------- start ----------

async function init() {
  if (!user) return;
  el('user-avatar').textContent = user.initials || '??';
  el('user-avatar').style.background = '#3b5bdb';
  el('user-name').textContent = user.displayName || user.username;
  el('user-handle').textContent = '@' + user.username;

  bindThemeToggle();
  state.videos = await getVideos();
  if (state.videos.length === 0) {
    el('player').innerHTML = '<p style="padding:24px">No videos yet. Upload one to get started.</p>';
    return;
  }
  await loadCurrent();
}

init();
