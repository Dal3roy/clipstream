// Central settings for the frontend.
// useMock: true  -> reads data/videos.json and keeps changes in memory (no backend needed)
// useMock: false -> calls the real API at apiBase (set this once the backend is deployed)
export const CONFIG = {
  useMock: true,
  apiBase: 'https://YOUR-APP-NAME.azurewebsites.net/api'
};
