// Login and sign-up page. Switches between the two modes on one form.
import { login, signup, getSessionUser } from './api.js';
import { bindThemeToggle } from './common.js';

const form = document.getElementById('auth-form');
const title = document.getElementById('auth-title');
const subtitle = document.getElementById('auth-subtitle');
const nameField = document.getElementById('name-field');
const submit = document.getElementById('auth-submit');
const error = document.getElementById('auth-error');
const switchText = document.getElementById('auth-switch-text');
const switchLink = document.getElementById('auth-switch-link');
const passwordInput = document.getElementById('password');

let mode = 'login';

// Already logged in? Go straight to the feed.
if (getSessionUser()) {
  location.replace('feed.html');
}

function setMode(next) {
  mode = next;
  const signingUp = mode === 'signup';
  title.textContent = signingUp ? 'Create your account' : 'Welcome back';
  subtitle.textContent = signingUp ? 'It takes less than a minute.' : 'Log in to see what people are posting.';
  nameField.hidden = !signingUp;
  submit.textContent = signingUp ? 'Sign up' : 'Log in';
  switchText.textContent = signingUp ? 'Already have an account?' : 'New to Clipstream?';
  switchLink.textContent = signingUp ? 'Log in' : 'Create an account';
  passwordInput.autocomplete = signingUp ? 'new-password' : 'current-password';
  error.hidden = true;
}

switchLink.addEventListener('click', event => {
  event.preventDefault();
  setMode(mode === 'login' ? 'signup' : 'login');
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  error.hidden = true;

  const data = new FormData(form);
  const email = String(data.get('email') || '').trim();
  const password = String(data.get('password') || '');
  const name = String(data.get('name') || '').trim();

  if (!email.includes('@')) return showError('Enter a valid email address.');
  if (mode === 'signup' && password.length < 8) return showError('Passwords need at least 8 characters.');
  if (!password) return showError('Enter your password.');

  submit.disabled = true;
  try {
    if (mode === 'signup') {
      await signup(name, email, password);
    } else {
      await login(email, password);
    }
    location.href = 'feed.html';
  } catch (err) {
    showError(err.message);
  } finally {
    submit.disabled = false;
  }
});

function showError(message) {
  error.textContent = message;
  error.hidden = false;
}

bindThemeToggle();
setMode('login');
