const config = window.OPSPILOT_CONFIG;

const storageKeys = {
  accessToken: "opspilot_access_token",
  expiresAt: "opspilot_expires_at",
  oauthState: "opspilot_oauth_state",
  pkceVerifier: "opspilot_pkce_verifier"
};

const elements = Object.fromEntries(
  [
    "approval-action",
    "approval-copy",
    "approval-request-id",
    "approval-status",
    "auth-status",
    "outcome-reason",
    "outcome-result",
    "outcome-risk",
    "outcome-status",
    "outcome-tool",
    "panel-sign-in",
    "refresh-timeline",
    "request",
    "request-approval",
    "request-message",
    "run-read-only",
    "sign-in",
    "sign-out",
    "signed-out-panel",
    "timeline",
    "workspace"
  ].map((id) => [id, document.getElementById(id)])
);

let activeApprovalRequestId = "";
let approvalPoll = 0;

function requiredConfig() {
  const required = [
    "apiUrl",
    "clientId",
    "cognitoDomain",
    "logoutUri",
    "redirectUri",
    "scopes"
  ];
  const missing = required.filter((key) => !config || !config[key]);
  if (missing.length) {
    throw new Error(`Missing public web configuration: ${missing.join(", ")}`);
  }
}

function randomBase64Url(byteLength) {
  const bytes = crypto.getRandomValues(new Uint8Array(byteLength));
  return base64Url(bytes);
}

function base64Url(bytes) {
  const binary = Array.from(new Uint8Array(bytes), (byte) =>
    String.fromCharCode(byte)
  ).join("");
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

async function sha256Base64Url(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return base64Url(new Uint8Array(digest));
}

function getAccessToken() {
  const token = sessionStorage.getItem(storageKeys.accessToken);
  const expiresAt = Number(sessionStorage.getItem(storageKeys.expiresAt) || "0");
  if (!token || Date.now() >= expiresAt) {
    clearSession();
    return "";
  }
  return token;
}

function clearSession() {
  for (const key of Object.values(storageKeys)) {
    sessionStorage.removeItem(key);
  }
}

async function beginSignIn() {
  requiredConfig();
  const verifier = randomBase64Url(48);
  const state = randomBase64Url(24);
  sessionStorage.setItem(storageKeys.pkceVerifier, verifier);
  sessionStorage.setItem(storageKeys.oauthState, state);

  const query = new URLSearchParams({
    client_id: config.clientId,
    code_challenge: await sha256Base64Url(verifier),
    code_challenge_method: "S256",
    redirect_uri: config.redirectUri,
    response_type: "code",
    scope: config.scopes.join(" "),
    state
  });
  window.location.assign(`${config.cognitoDomain}/oauth2/authorize?${query}`);
}

async function completeSignIn() {
  const query = new URLSearchParams(window.location.search);
  const code = query.get("code");
  const returnedState = query.get("state");
  if (!code) {
    return;
  }

  const verifier = sessionStorage.getItem(storageKeys.pkceVerifier);
  const expectedState = sessionStorage.getItem(storageKeys.oauthState);
  if (!verifier || !expectedState || returnedState !== expectedState) {
    clearSession();
    throw new Error("Cognito sign-in state validation failed.");
  }

  const response = await fetch(`${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: config.clientId,
      code,
      code_verifier: verifier,
      grant_type: "authorization_code",
      redirect_uri: config.redirectUri
    })
  });
  if (!response.ok) {
    clearSession();
    throw new Error("Cognito token exchange failed.");
  }

  const tokens = await response.json();
  sessionStorage.setItem(storageKeys.accessToken, tokens.access_token);
  sessionStorage.setItem(
    storageKeys.expiresAt,
    String(Date.now() + Math.max(0, tokens.expires_in - 30) * 1000)
  );
  sessionStorage.removeItem(storageKeys.pkceVerifier);
  sessionStorage.removeItem(storageKeys.oauthState);
  history.replaceState({}, "", "/");
}

function signOut() {
  clearSession();
  const query = new URLSearchParams({
    client_id: config.clientId,
    logout_uri: config.logoutUri
  });
  window.location.assign(`${config.cognitoDomain}/logout?${query}`);
}

function renderSession() {
  const signedIn = Boolean(getAccessToken());
  elements["auth-status"].textContent = signedIn ? "Authenticated" : "Signed out";
  elements["auth-status"].classList.toggle("signed-in", signedIn);
  elements["sign-in"].hidden = signedIn;
  elements["sign-out"].hidden = !signedIn;
  elements["signed-out-panel"].hidden = signedIn;
  elements.workspace.hidden = !signedIn;
}

async function apiRequest(path, options = {}) {
  const token = getAccessToken();
  if (!token) {
    renderSession();
    throw new Error("Your session expired. Sign in again.");
  }
  const response = await fetch(`${config.apiUrl}${path}`, {
    ...options,
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      ...(Reflect.get(options, "headers") || {})
    }
  });
  const body = await response.json();
  return { ...body, http_status: response.status };
}

function requestText() {
  return requestInput().value.trim();
}

function requestInput() {
  const input = elements.request;
  if (!(input instanceof HTMLTextAreaElement)) {
    throw new Error("The request input is unavailable.");
  }
  return input;
}

function setButtonDisabled(id, disabled) {
  const button = elements[id];
  if (button instanceof HTMLButtonElement) {
    button.disabled = disabled;
  }
}

function setBusy(busy) {
  setButtonDisabled("run-read-only", busy);
  setButtonDisabled("request-approval", busy);
  elements["request-message"].textContent = busy ? "Evaluating request..." : "";
}

function statusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (["succeeded", "completed", "approved"].includes(normalized)) {
    return "status-good";
  }
  if (["awaiting_approval", "pending", "waiting_approval"].includes(normalized)) {
    return "status-warning";
  }
  if (["failed", "refused", "rejected", "expired"].includes(normalized)) {
    return "status-bad";
  }
  return "status-neutral";
}

function setStatusPill(element, status) {
  element.textContent = String(status || "Unknown").replaceAll("_", " ");
  element.className = `status-pill ${statusClass(status)}`;
}

function renderOutcome(outcome) {
  setStatusPill(elements["outcome-status"], outcome.status);
  elements["outcome-tool"].textContent = outcome.tool || "None";
  elements["outcome-risk"].textContent = outcome.risk || "Unknown";
  elements["outcome-reason"].textContent = outcome.reason || "No reason supplied";
  elements["outcome-result"].textContent = outcome.result
    ? JSON.stringify(outcome.result, null, 2)
    : "No tool result. Inspect the policy decision above.";
}

async function runReadOnly() {
  if (!requestText()) {
    elements["request-message"].textContent = "Enter a request first.";
    return;
  }
  setBusy(true);
  try {
    const outcome = await apiRequest("/requests", {
      method: "POST",
      body: JSON.stringify({ request: requestText() })
    });
    renderOutcome(outcome);
    await refreshTimeline();
  } catch (error) {
    elements["request-message"].textContent = error.message;
  } finally {
    setBusy(false);
  }
}

async function requestControlledApproval() {
  if (!requestText()) {
    elements["request-message"].textContent = "Enter the approved controlled request first.";
    return;
  }
  setBusy(true);
  try {
    const outcome = await apiRequest("/controlled-requests", {
      method: "POST",
      body: JSON.stringify({ request: requestText() })
    });
    renderOutcome(outcome);
    if (outcome.approval_status === "awaiting_approval" && outcome.request_id) {
      activeApprovalRequestId = outcome.request_id;
      renderApproval(outcome);
      scheduleApprovalPoll();
    }
    await refreshTimeline();
  } catch (error) {
    elements["request-message"].textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function renderApproval(approval) {
  const status = approval.approval_status || approval.status || "None";
  setStatusPill(elements["approval-status"], status);
  elements["approval-request-id"].textContent = approval.request_id || "None";
  elements["approval-action"].textContent = approval.action || approval.tool || "None";
  elements["approval-copy"].textContent =
    status === "awaiting_approval"
      ? "Step Functions is waiting for a human approval decision."
      : `The controlled request is ${String(status).replaceAll("_", " ")}.`;
}

async function refreshApproval() {
  if (!activeApprovalRequestId) {
    return;
  }
  const approval = await apiRequest(
    `/approvals/${encodeURIComponent(activeApprovalRequestId)}`
  );
  if (approval.http_status === 200) {
    renderApproval(approval);
    if (approval.approval_status !== "awaiting_approval") {
      window.clearInterval(approvalPoll);
      approvalPoll = 0;
      await refreshTimeline();
    }
  }
}

function scheduleApprovalPoll() {
  window.clearInterval(approvalPoll);
  approvalPoll = window.setInterval(() => {
    refreshApproval().catch((error) => {
      elements["request-message"].textContent = error.message;
    });
  }, 5000);
}

function timelineTitle(event) {
  if (event.type === "approval") {
    return `${event.action || "Controlled action"}: ${event.approval_status}`;
  }
  return event.request || event.tool || "Operations request";
}

function timelineDetail(event) {
  if (event.type === "approval") {
    return `Approval workflow · ${event.status || "pending"}`;
  }
  return `${event.tool || "no tool"} · ${event.risk || "unknown risk"} · ${
    event.reason || "no reason"
  }`;
}

function renderTimeline(events) {
  elements.timeline.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No audited requests for this reviewer yet.";
    elements.timeline.append(empty);
    return;
  }

  for (const event of events) {
    const item = document.createElement("li");
    item.className = "timeline-event";
    const marker = document.createElement("span");
    marker.className = "timeline-marker";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = timelineTitle(event);
    const detail = document.createElement("small");
    detail.textContent = timelineDetail(event);
    copy.append(title, detail);
    const time = document.createElement("time");
    time.className = "timeline-time";
    const timestamp = event.timestamp || event.updated_at || event.created_at;
    time.textContent = timestamp ? new Date(timestamp).toLocaleString() : "Pending";
    item.append(marker, copy, time);
    elements.timeline.append(item);
  }
}

async function refreshTimeline() {
  const timeline = await apiRequest("/timeline");
  renderTimeline(Array.isArray(timeline.events) ? timeline.events : []);
}

function wireEvents() {
  elements["sign-in"].addEventListener("click", () => beginSignIn());
  elements["panel-sign-in"].addEventListener("click", () => beginSignIn());
  elements["sign-out"].addEventListener("click", signOut);
  elements["run-read-only"].addEventListener("click", runReadOnly);
  elements["request-approval"].addEventListener("click", requestControlledApproval);
  elements["refresh-timeline"].addEventListener("click", () => {
    refreshTimeline().catch((error) => {
      elements["request-message"].textContent = error.message;
    });
  });
  for (const example of document.querySelectorAll(".example")) {
    example.addEventListener("click", () => {
      requestInput().value =
        example instanceof HTMLElement ? example.dataset.request || "" : "";
      requestInput().focus();
    });
  }
}

async function start() {
  try {
    requiredConfig();
    await completeSignIn();
    renderSession();
    wireEvents();
    if (getAccessToken()) {
      await refreshTimeline();
    }
  } catch (error) {
    renderSession();
    elements["request-message"].textContent = error.message;
    console.error(error);
  }
}

start();
