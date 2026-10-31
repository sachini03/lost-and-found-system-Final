// Base URL of the backend. Change it in .env (VITE_API_URL) - no code edits needed.
const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:4000/api";
const FILE_HOST = API_URL.replace(/\/api\/?$/, "");
const TOKEN_KEY = "unifind_token";

// ---- login token (kept in the browser so the user stays logged in) ----
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage blocked - user just has to log in again next time */
  }
}

// Backend returns image paths like "/uploads/abc.jpg" - make them full URLs.
function withImageUrl(item) {
  if (item && item.image && item.image.startsWith("/")) {
    item = { ...item, image: FILE_HOST + item.image };
  }
  if (item && Array.isArray(item.images)) {
    item = {
      ...item,
      images: item.images.map((p) => (p.startsWith("/") ? FILE_HOST + p : p)),
    };
  }
  return item;
}

// One place for every request: adds the token, turns errors into readable messages.
async function request(path, { method = "GET", json, formData, auth = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token && (auth || token)) headers.Authorization = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : formData,
    });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }

  if (response.status === 204) return null;
  let body = null;
  try {
    body = await response.json();
  } catch {
    /* empty body */
  }
  if (!response.ok) {
    const detail = body && (body.detail || body.error);
    let message = "Something went wrong";
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail) && detail.length) {
      message = detail
        .map((d) => `${(d.loc || []).slice(-1)[0] ?? ""}: ${d.msg}`)
        .join(", ");
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return body;
}

// ---------------- items ----------------
export async function getItems(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => v && params.append(k, v));
  const data = await request(`/items?${params.toString()}`);
  return data.map(withImageUrl);
}

export async function createItem(item) {
  return withImageUrl(await request("/items", { method: "POST", json: item }));
}

export async function uploadImages(itemId, files) {
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
  return withImageUrl(
    await request(`/items/${itemId}/images`, { method: "POST", formData }),
  );
}

export async function updateItemStatus(itemId, status) {
  return withImageUrl(
    await request(`/items/${itemId}/status`, { method: "PATCH", json: { status } }),
  );
}

export async function getMyItems() {
  const data = await request("/items/mine");
  return data.map(withImageUrl);
}

// ---------------- accounts ----------------
export const register = (data) =>
  request("/auth/register", { method: "POST", json: data });
export const login = (data) =>
  request("/auth/login", { method: "POST", json: data });
export const fetchMe = () => request("/auth/me");

// ---------------- saved items ----------------
export async function getSavedItems() {
  const data = await request("/saved");
  return data.map(withImageUrl);
}
export const saveItem = (id) => request(`/saved/${id}`, { method: "PUT" });
export const unsaveItem = (id) => request(`/saved/${id}`, { method: "DELETE" });

export const checkBackend = () => request("/health");

// ---------------- chat ----------------
// A conversation carries a small copy of its item; fix the image path like we do for items.
function withConvImage(conv) {
  if (conv && conv.item && conv.item.image && conv.item.image.startsWith("/")) {
    return { ...conv, item: { ...conv.item, image: FILE_HOST + conv.item.image } };
  }
  return conv;
}

export async function startConversation(itemId) {
  return withConvImage(
    await request("/conversations", { method: "POST", json: { item_id: itemId } }),
  );
}
export async function getConversations() {
  const data = await request("/conversations");
  return data.map(withConvImage);
}
export const getMessages = (conversationId, afterId = 0) =>
  request(`/conversations/${conversationId}/messages?after_id=${afterId}`);
export const sendMessage = (conversationId, body) =>
  request(`/conversations/${conversationId}/messages`, { method: "POST", json: { body } });

// ---------------- notifications ----------------
export const getNotifications = () => request("/notifications");
export const getSummary = () => request("/notifications/summary");
export const markNotificationRead = (id) =>
  request(`/notifications/${id}/read`, { method: "POST" });
export const markAllNotificationsRead = () =>
  request("/notifications/read-all", { method: "POST" });
