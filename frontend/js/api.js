const API_BASE = "http://127.0.0.1:8000/api";

async function apiFetch(path, options = {}) {
  const access = localStorage.getItem("access");

  const headers = {
    ...(options.headers || {}),
  };

  // set JSON header only if body exists and not already set
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  if (access) headers["Authorization"] = `Bearer ${access}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // ✅ auto-handle expired tokens (401)
  if (res.status === 401) {
    console.warn("401 Unauthorized -> logging out");
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("user");
    window.location.href = "login.html";
    return res;
  }

  return res;
}
