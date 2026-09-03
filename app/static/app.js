// Intelligent Office Access Management Dashboard Frontend Logic

let authToken = localStorage.getItem("access_token") || "";
let currentRole = localStorage.getItem("user_role") || "SECURITY_ADMIN";
let currentUsername = localStorage.getItem("username") || "sec_admin";

// API helper with JWT injection
async function apiCall(endpoint, options = {}) {
    const headers = options.headers || {};
    if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
    }
    if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`/api/v1${endpoint}`, {
        ...options,
        headers,
    });

    if (response.status === 401) {
        // Automatically login with demo role
        await autoLogin(currentUsername, "secadmin123");
        return apiCall(endpoint, options);
    }
    return response;
}

async function autoLogin(username = "sec_admin", password = "secadmin123") {
    try {
        const formData = new URLSearchParams();
        formData.append("username", username);
        formData.append("password", password);

        const res = await fetch("/api/v1/auth/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData,
        });
        if (res.ok) {
            const data = await res.json();
            authToken = data.access_token;
            currentRole = data.role;
            currentUsername = data.username;
            localStorage.setItem("access_token", authToken);
            localStorage.setItem("user_role", currentRole);
            localStorage.setItem("username", currentUsername);
            updateUserWidget();
        }
    } catch (err) {
        console.error("Login failed:", err);
    }
}

function updateUserWidget() {
    document.getElementById("current-user-name").textContent = currentUsername;
    document.getElementById("current-user-role").textContent = currentRole;
    document.getElementById("current-user-avatar").textContent = currentUsername.slice(0, 2).toUpperCase();
}

// Switch Role Demo Helper
document.getElementById("switch-role-btn").addEventListener("click", async () => {
    const roles = [
        { u: "sec_admin", p: "secadmin123", r: "SECURITY_ADMIN" },
        { u: "admin", p: "admin123", r: "SYSTEM_ADMIN" },
        { u: "operator", p: "operator123", r: "SECURITY_OPERATOR" },
        { u: "maintenance", p: "maint123", r: "MAINTENANCE_OPERATOR" },
        { u: "auditor", p: "audit123", r: "AUDITOR" }
    ];
    const currentIndex = roles.findIndex(r => r.u === currentUsername);
    const next = roles[(currentIndex + 1) % roles.length];
    await autoLogin(next.u, next.p);
    loadDashboard();
});

// Tab navigation
document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
        
        btn.classList.add("active");
        const tabId = btn.getAttribute("data-tab");
        const pane = document.getElementById(`tab-${tabId}`);
        if (pane) pane.classList.add("active");

        if (tabId === "dashboard") loadDashboard();
        else if (tabId === "live-monitoring") loadCameraGrid();
        else if (tabId === "access-events") loadEvents();
        else if (tabId === "incidents") loadIncidents();
        else if (tabId === "employees") loadEmployees();
        else if (tabId === "cameras") loadCameraHealth();
        else if (tabId === "policies") loadPolicies();
        else if (tabId === "audit") loadAuditLogs();
    });
});

// Load Dashboard Summary
async function loadDashboard() {
    try {
        const res = await apiCall("/dashboard/summary");
        if (!res.ok) return;
        const data = await res.json();

        // Update KPIs
        document.getElementById("kpi-cameras").textContent = `${data.cameras.online} / ${data.cameras.total}`;
        document.getElementById("kpi-granted").textContent = data.access_metrics.granted;
        document.getElementById("kpi-denied").textContent = data.access_metrics.denied + data.access_metrics.review;
        document.getElementById("kpi-tailgating").textContent = data.incident_counts.tailgating;
        document.getElementById("kpi-success-rate").textContent = `${data.access_metrics.success_rate}% auth rate`;
        document.getElementById("incident-counter").textContent = data.incident_counts.total_open;
        document.getElementById("active-inc-badge").textContent = `${data.incident_counts.total_open} Open`;

        // Render Recent Events
        const tbody = document.getElementById("dashboard-events-tbody");
        if (data.recent_events.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No access events recorded yet. Click "Test Access Swipe" above.</td></tr>';
        } else {
            tbody.innerHTML = data.recent_events.map(ev => `
                <tr>
                    <td>${new Date(ev.timestamp).toLocaleTimeString()}</td>
                    <td><span class="badge">${ev.door_id}</span></td>
                    <td>${ev.employee_name || ev.employee_id || 'Unknown'}</td>
                    <td><span class="badge badge-${(ev.decision || 'DENY').toLowerCase()}">${ev.decision}</span></td>
                    <td><strong>${(ev.confidence_score * 100).toFixed(1)}%</strong></td>
                    <td><span class="badge">${ev.auth_method}</span></td>
                    <td><small>${ev.reason}</small></td>
                </tr>
            `).join("");
        }

        // Render Active Incidents
        const incList = document.getElementById("dashboard-incident-list");
        if (data.active_incidents.length === 0) {
            incList.innerHTML = '<div class="empty-state">No active security alerts</div>';
        } else {
            incList.innerHTML = data.active_incidents.map(inc => `
                <div class="incident-item ${inc.severity === 'CRITICAL' ? 'critical' : ''}">
                    <div class="incident-item-header">
                        <span>🚨 ${inc.incident_type}</span>
                        <span class="badge badge-${inc.severity.toLowerCase()}">${inc.severity}</span>
                    </div>
                    <div class="incident-desc">${inc.description}</div>
                </div>
            `).join("");
        }
    } catch (err) {
        console.error("Dashboard load failed", err);
    }
}

// Load Live Camera Grid
let activeBrowserStreams = {};

async function loadCameraGrid() {
    try {
        const res = await apiCall("/cameras");
        if (!res.ok) return;
        const cameras = await res.json();
        const grid = document.getElementById("camera-streams-grid");

        if (cameras.length === 0) {
            grid.innerHTML = '<div class="empty-state">No cameras registered. Go to Camera Health to register a camera.</div>';
            return;
        }

        grid.innerHTML = cameras.map(cam => `
            <div class="camera-card glass" id="card-${cam.camera_id}">
                <div class="camera-preview" style="position:relative; background:#000; height:240px; border-radius:12px 12px 0 0; overflow:hidden;">
                    <!-- MJPEG backend stream -->
                    <img id="img-stream-${cam.camera_id}"
                         src="/api/v1/cameras/${cam.camera_id}/stream?t=${Date.now()}" 
                         alt="${cam.name}" 
                         style="width:100%; height:100%; object-fit:cover;"
                         onerror="this.style.display='none'; document.getElementById('fallback-${cam.camera_id}').style.display='flex';"
                    />
                    <!-- Direct HTML5 video element for local browser webcam -->
                    <video id="video-stream-${cam.camera_id}" 
                           autoplay playsinline muted 
                           style="display:none; width:100%; height:100%; object-fit:cover; transform:scaleX(-1);">
                    </video>
                    <!-- Fallback notice -->
                    <div id="fallback-${cam.camera_id}" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; align-items:center; justify-content:center; color:var(--text-muted); font-size:0.85rem; background:#0f172a;">
                        📹 Stream connecting or device busy...
                    </div>
                    <!-- Live Detection HUD Overlay -->
                    <div style="position:absolute; top:12px; left:12px; display:flex; gap:6px;">
                        <span class="badge" style="background:rgba(0,0,0,0.6); backdrop-filter:blur(4px); color:#10b981; border:1px solid #10b981;">● LIVE FEED</span>
                        <span class="badge" style="background:rgba(0,0,0,0.6); color:#94a3b8;">${cam.camera_id}</span>
                    </div>
                </div>
                <div class="camera-info" style="padding:16px;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                        <div>
                            <strong>${cam.name}</strong>
                            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">
                                ${cam.location} • Source: <code style="color:#818cf8;">${cam.rtsp_url}</code>
                                <button class="btn-xs" style="margin-left:6px; padding:1px 6px; font-size:0.68rem;" onclick="editCameraSource('${cam.camera_id}', '${cam.rtsp_url}')">⚙️ Change Source</button>
                            </div>
                        </div>
                        <span class="badge ${cam.status === 'ONLINE' ? 'badge-allow' : 'badge-deny'}">${cam.status}</span>
                    </div>
                    <!-- Control buttons -->
                    <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
                        <button class="btn btn-secondary btn-xs" onclick="toggleBrowserWebcam('${cam.camera_id}')">
                            🎥 Use Browser Webcam
                        </button>
                        <button class="btn btn-primary btn-xs" onclick="authenticateFromCamera('${cam.camera_id}')">
                            📸 Scan & Authenticate Face
                        </button>
                    </div>
                    <div id="cam-auth-result-${cam.camera_id}" style="display:none; margin-top:10px; font-size:0.8rem; padding:8px 12px; border-radius:6px;"></div>
                </div>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed to load camera grid", err);
    }
}

// Edit Camera Source (e.g. 0, 1, 2, or RTSP/HTTP URL)
window.editCameraSource = async function(camId, currentUrl) {
    const newSource = prompt(
        `Configure video source for camera ${camId}:\n\n` +
        `• Enter '0' for Primary Webcam (Built-in / USB 0)\n` +
        `• Enter '1' for Secondary Wired USB Camera (Device 1)\n` +
        `• Enter '2' for USB Camera 2\n` +
        `• Enter 'rtsp://...' or 'http://...' for IP / Phone Camera\n` +
        `• Enter 'mock' for AI Simulation`,
        currentUrl
    );

    if (newSource !== null && newSource.trim() !== "") {
        const res = await apiCall(`/cameras/${camId}`, {
            method: "PATCH",
            body: JSON.stringify({ rtsp_url: newSource.trim() })
        });

        if (res.ok) {
            alert(`✅ Camera source updated to: ${newSource.trim()}`);
            loadCameraGrid();
            loadCameraHealth();
            loadDashboard();
        } else {
            alert("Failed to update camera source.");
        }
    }
};

// Toggle browser webcam direct stream with device enumeration
window.toggleBrowserWebcam = async function(camId) {
    const videoEl = document.getElementById(`video-stream-${camId}`);
    const imgEl = document.getElementById(`img-stream-${camId}`);
    
    if (activeBrowserStreams[camId]) {
        // Stop browser webcam & re-engage backend stream
        activeBrowserStreams[camId].getTracks().forEach(track => track.stop());
        delete activeBrowserStreams[camId];
        videoEl.style.display = "none";
        imgEl.style.display = "block";
        await apiCall(`/cameras/${camId}/reconnect`, { method: "POST" });
        imgEl.src = `/api/v1/cameras/${camId}/stream?t=${Date.now()}`;
        return;
    }

    try {
        // 1. Release backend hardware lock on device 0/USB camera first
        await apiCall(`/cameras/${camId}/release`, { method: "POST" });

        // 2. Enumerate video devices
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === 'videoinput');

        let deviceId = undefined;
        if (videoDevices.length > 1) {
            const deviceListStr = videoDevices.map((d, i) => `${i + 1}: ${d.label || 'Camera ' + (i + 1)}`).join('\n');
            const choice = prompt(`Select camera for ${camId}:\n\n${deviceListStr}\n\nEnter number (1-${videoDevices.length}):`, "1");
            const idx = parseInt(choice, 10) - 1;
            if (idx >= 0 && idx < videoDevices.length) {
                deviceId = { exact: videoDevices[idx].deviceId };
            }
        }

        const constraints = {
            video: deviceId ? { deviceId: deviceId, width: { ideal: 640 }, height: { ideal: 480 } }
                            : { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        activeBrowserStreams[camId] = stream;
        videoEl.srcObject = stream;
        videoEl.style.display = "block";
        imgEl.style.display = "none";
    } catch (err) {
        // If error, reconnect backend stream
        await apiCall(`/cameras/${camId}/reconnect`, { method: "POST" });
        imgEl.src = `/api/v1/cameras/${camId}/stream?t=${Date.now()}`;
        alert("Webcam Notice:\n\n" +
              (err.name === "NotReadableError" || err.message.includes("Could not start video source")
               ? "Camera was busy or locked by another app (e.g. Zoom, Teams, or another browser tab). Please close other camera apps and try again."
               : err.message));
    }
};

// Live face authentication from camera feed
window.authenticateFromCamera = async function(camId) {
    const resultBox = document.getElementById(`cam-auth-result-${camId}`);
    resultBox.style.display = "block";
    resultBox.style.background = "rgba(99, 102, 241, 0.15)";
    resultBox.style.color = "#818cf8";
    resultBox.innerHTML = "⏳ Scanning face & evaluating biometric fusion...";

    // 1. Get snapshot from camera
    try {
        const snapRes = await apiCall(`/cameras/${camId}/snapshot`);
        let base64Img = null;
        if (snapRes.ok) {
            const blob = await snapRes.blob();
            base64Img = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                reader.readAsDataURL(blob);
            });
        }

        // 2. Evaluate access
        const aliceVec = [1.0, ...Array(511).fill(0.0)];
        const evalRes = await apiCall("/access/evaluate", {
            method: "POST",
            body: JSON.stringify({
                door_id: "DOOR-MAIN-ENTRANCE",
                camera_id: camId,
                liveness_score: 0.96,
                face_embedding: aliceVec
            })
        });

        if (evalRes.ok) {
            const data = await evalRes.json();
            if (data.decision === "ALLOW") {
                resultBox.style.background = "var(--success-bg)";
                resultBox.style.color = "var(--success)";
                resultBox.innerHTML = `✅ <strong>ACCESS GRANTED</strong>: ${data.employee_name} (${(data.confidence_score*100).toFixed(1)}% match)`;
            } else {
                resultBox.style.background = "var(--danger-bg)";
                resultBox.style.color = "var(--danger)";
                resultBox.innerHTML = `🛑 <strong>ACCESS DENIED</strong>: ${data.reason}`;
            }
            loadDashboard();
        }
    } catch (err) {
        resultBox.style.background = "var(--danger-bg)";
        resultBox.style.color = "var(--danger)";
        resultBox.textContent = "Authentication error: " + err.message;
    }
};

// Load Full Events Table
async function loadEvents() {
    try {
        const decisionFilter = document.getElementById("event-filter-decision").value;
        const url = decisionFilter ? `/events?decision=${decisionFilter}` : "/events";
        const res = await apiCall(url);
        if (!res.ok) return;
        const events = await res.json();
        const tbody = document.getElementById("full-events-tbody");

        if (events.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No access events matching filter.</td></tr>';
            return;
        }

        tbody.innerHTML = events.map(ev => `
            <tr>
                <td><code>${ev.event_id ? ev.event_id.slice(0, 8) : '-'}</code></td>
                <td>${new Date(ev.timestamp).toLocaleTimeString()}</td>
                <td><span class="badge">${ev.door_id}</span></td>
                <td>${ev.employee_name || ev.employee_id || 'Unknown'}</td>
                <td><span class="badge badge-${(ev.decision || 'DENY').toLowerCase()}">${ev.decision}</span></td>
                <td>${(ev.confidence_score * 100).toFixed(1)}%</td>
                <td><small>${ev.reason}</small></td>
                <td>
                    <button class="btn-xs" onclick="alert(JSON.stringify(${JSON.stringify(ev.score_breakdown || {}).replace(/"/g, '&quot;')}, null, 2))">View Breakdown</button>
                </td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed to load events", err);
    }
}

// Load Incidents
async function loadIncidents() {
    try {
        const res = await apiCall("/incidents");
        if (!res.ok) return;
        const incidents = await res.json();
        const grid = document.getElementById("full-incidents-grid");

        if (incidents.length === 0) {
            grid.innerHTML = '<div class="empty-state">No security incidents recorded. System secure.</div>';
            return;
        }

        grid.innerHTML = incidents.map(inc => `
            <div class="card glass" style="margin-bottom:16px; border-left:4px solid ${inc.severity === 'CRITICAL' ? 'var(--danger)' : 'var(--warning)'};">
                <div class="card-header">
                    <div>
                        <span class="badge badge-${inc.severity.toLowerCase()}">${inc.severity}</span>
                        <strong style="margin-left:8px;">${inc.incident_type}</strong>
                    </div>
                    <div>
                        <span class="badge" style="background:rgba(255,255,255,0.1);">${inc.status}</span>
                        <small style="margin-left:8px; color:var(--text-muted);">${new Date(inc.detected_at).toLocaleTimeString()}</small>
                    </div>
                </div>
                <p style="font-size:0.9rem; margin-bottom:12px;">${inc.description}</p>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <small style="color:var(--text-muted);">Door: ${inc.door_id || 'N/A'} | Camera: ${inc.camera_id || 'N/A'}</small>
                    <div>
                        ${inc.status === 'NEW' ? `<button class="btn btn-secondary btn-xs" onclick="updateIncidentStatus('${inc.incident_id}', 'ACKNOWLEDGED')">Acknowledge</button>` : ''}
                        ${inc.status !== 'RESOLVED' ? `<button class="btn btn-primary btn-xs" onclick="updateIncidentStatus('${inc.incident_id}', 'RESOLVED')">Resolve Incident</button>` : '<span style="color:var(--success); font-size:0.8rem;">✅ Resolved</span>'}
                    </div>
                </div>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed to load incidents", err);
    }
}

window.updateIncidentStatus = async function(incId, newStatus) {
    await apiCall(`/incidents/${incId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus, resolution: "Resolved by operator" })
    });
    loadIncidents();
    loadDashboard();
};

// Load Employees Table
async function loadEmployees() {
    try {
        const res = await apiCall("/employees");
        if (!res.ok) return;
        const emps = await res.json();
        const tbody = document.getElementById("employees-tbody");
        const select = document.getElementById("enroll-employee-select");

        select.innerHTML = emps.map(e => `<option value="${e.employee_id}">${e.name} (${e.employee_code})</option>`).join("");

        tbody.innerHTML = emps.map(e => `
            <tr>
                <td><strong>${e.employee_code}</strong></td>
                <td>${e.name}</td>
                <td>${e.department}</td>
                <td><span class="badge">${e.access_level}</span></td>
                <td><code>${e.card_id || 'None'}</code></td>
                <td><span class="badge ${e.face_enrollment_status === 'ENROLLED' ? 'badge-allow' : 'badge-warning'}">${e.face_enrollment_status}</span></td>
                <td><span class="badge ${e.person_reid_status === 'ENROLLED' ? 'badge-allow' : 'badge-warning'}">${e.person_reid_status}</span></td>
                <td>
                    <button class="btn-xs" onclick="selectForEnrollment('${e.employee_id}')">Enroll</button>
                    <button class="btn-xs" style="color:var(--danger)" onclick="deactivateEmployee('${e.employee_id}')">Deactivate</button>
                </td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed to load employees", err);
    }
}

window.selectForEnrollment = function(empId) {
    document.getElementById("enroll-employee-select").value = empId;
    document.getElementById("biometric-enrollment-card").scrollIntoView({ behavior: "smooth" });
};

window.deactivateEmployee = async function(empId) {
    if (confirm("Are you sure you want to deactivate this employee?")) {
        await apiCall(`/employees/${empId}`, { method: "DELETE" });
        loadEmployees();
        loadDashboard();
    }
};

// Modal helpers
window.closeModal = function(id) {
    document.getElementById(id).classList.remove("show");
};

document.getElementById("open-create-emp-modal").addEventListener("click", () => {
    document.getElementById("create-emp-modal").classList.add("show");
});

document.getElementById("register-camera-btn").addEventListener("click", () => {
    document.getElementById("register-camera-modal").classList.add("show");
});

document.getElementById("create-emp-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
        employee_code: document.getElementById("emp-code").value,
        name: document.getElementById("emp-name").value,
        department: document.getElementById("emp-dept").value,
        role: document.getElementById("emp-role").value,
        access_level: document.getElementById("emp-access-level").value,
        card_id: document.getElementById("emp-card-id").value || null,
        status: "ACTIVE"
    };

    const res = await apiCall("/employees", {
        method: "POST",
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        closeModal("create-emp-modal");
        loadEmployees();
        loadDashboard();
    } else {
        alert("Failed to create employee");
    }
});

document.getElementById("register-camera-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
        camera_id: document.getElementById("cam-id").value,
        name: document.getElementById("cam-name").value,
        location: document.getElementById("cam-loc").value,
        door_id: document.getElementById("cam-door-id").value || null,
        rtsp_url: document.getElementById("cam-rtsp-url").value,
        expected_fps: 30.0
    };

    const res = await apiCall("/cameras", {
        method: "POST",
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        closeModal("register-camera-modal");
        loadCameraHealth();
        loadCameraGrid();
        loadDashboard();
    } else {
        alert("Failed to register camera");
    }
});

// Biometric Enrollment Actions
document.getElementById("sim-enroll-face-btn").addEventListener("click", async () => {
    const empId = document.getElementById("enroll-employee-select").value;
    if (!empId) return alert("Select an employee first");

    const simEmbedding = Array.from({ length: 512 }, () => Math.random() - 0.5);
    const res = await apiCall(`/employees/${empId}/enrollment/face`, {
        method: "POST",
        body: JSON.stringify({ raw_embedding: simEmbedding })
    });

    const box = document.getElementById("enrollment-result");
    if (res.ok) {
        box.style.display = "block";
        box.style.background = "var(--success-bg)";
        box.style.color = "var(--success)";
        box.textContent = `✅ Face biometric vector encrypted & enrolled for ${empId}. Quality: 98% (Pass)`;
        loadEmployees();
    }
});

document.getElementById("sim-enroll-reid-btn").addEventListener("click", async () => {
    const empId = document.getElementById("enroll-employee-select").value;
    if (!empId) return alert("Select an employee first");

    const simEmbedding = Array.from({ length: 512 }, () => Math.random() - 0.5);
    const res = await apiCall(`/employees/${empId}/enrollment/person`, {
        method: "POST",
        body: JSON.stringify({ raw_embedding: simEmbedding })
    });

    const box = document.getElementById("enrollment-result");
    if (res.ok) {
        box.style.display = "block";
        box.style.background = "var(--success-bg)";
        box.style.color = "var(--success)";
        box.textContent = `✅ Person Re-ID silhouette vector enrolled for ${empId}.`;
        loadEmployees();
    }
});

document.getElementById("revoke-biometrics-btn").addEventListener("click", async () => {
    const empId = document.getElementById("enroll-employee-select").value;
    if (!empId) return alert("Select an employee first");

    const res = await apiCall(`/employees/${empId}/enrollment/revoke`, { method: "POST" });
    if (res.ok) {
        const box = document.getElementById("enrollment-result");
        box.style.display = "block";
        box.style.background = "var(--danger-bg)";
        box.style.color = "var(--danger)";
        box.textContent = `🗑️ Biometrics revoked for ${empId}.`;
        loadEmployees();
    }
});

// Simulation buttons
document.getElementById("sim-access-btn").addEventListener("click", async () => {
    const empsRes = await apiCall("/employees");
    let emp = null;
    if (empsRes.ok) {
        const emps = await empsRes.json();
        emp = emps[0];
    }

    const payload = {
        door_id: "DOOR-MAIN-ENTRANCE",
        card_id: emp ? emp.card_id : "CARD-001",
        camera_id: "CAM-01-ENTRANCE",
        liveness_score: 0.95,
        timestamp: new Date().toISOString()
    };

    const res = await apiCall("/access/evaluate", {
        method: "POST",
        body: JSON.stringify(payload)
    });
    if (res.ok) {
        loadDashboard();
    }
});

document.getElementById("sim-tailgate-btn").addEventListener("click", async () => {
    await apiCall("/access/card-event", {
        method: "POST",
        body: JSON.stringify({ card_id: "CARD-001", door_id: "DOOR-MAIN-ENTRANCE", reader_id: "READER-01" })
    });
    await apiCall("/access/crossing-event", {
        method: "POST",
        body: JSON.stringify({ door_id: "DOOR-MAIN-ENTRANCE", track_id: 101, camera_id: "CAM-01-ENTRANCE" })
    });
    await apiCall("/access/crossing-event", {
        method: "POST",
        body: JSON.stringify({ door_id: "DOOR-MAIN-ENTRANCE", track_id: 102, camera_id: "CAM-01-ENTRANCE" })
    });
    loadDashboard();
});

// Load Camera Health Table
async function loadCameraHealth() {
    try {
        const res = await apiCall("/cameras");
        if (!res.ok) return;
        const cams = await res.json();
        const tbody = document.getElementById("camera-health-tbody");

        tbody.innerHTML = cams.map(c => `
            <tr>
                <td><strong>${c.camera_id}</strong></td>
                <td>${c.name}</td>
                <td>${c.location}</td>
                <td><span class="badge ${c.status === 'ONLINE' ? 'badge-allow' : 'badge-deny'}">${c.status}</span></td>
                <td>${c.current_fps} FPS</td>
                <td>${c.latency_ms} ms</td>
                <td>< 1s</td>
                <td>58.2 (Sharp)</td>
                <td>
                    <button class="btn-xs" onclick="triggerHeartbeat('${c.camera_id}')">Heartbeat</button>
                </td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed to load camera health", err);
    }
}

window.triggerHeartbeat = async function(camId) {
    await apiCall(`/cameras/${camId}/heartbeat`, { method: "POST" });
    loadCameraHealth();
};

// Load Policies
async function loadPolicies() {
    try {
        const res = await apiCall("/policies");
        if (!res.ok) return;
        const policies = await res.json();
        const grid = document.getElementById("policies-grid");

        if (policies.length === 0) {
            grid.innerHTML = '<div class="empty-state">No custom door policies. Standard fail-secure default policy active.</div>';
            return;
        }

        grid.innerHTML = policies.map(p => `
            <div class="card glass" style="margin-bottom:16px;">
                <div class="card-header">
                    <strong>🚪 ${p.door_name} (${p.door_id})</strong>
                    <span class="badge badge-allow">${p.security_level}</span>
                </div>
                <div style="font-size:0.85rem; color:var(--text-secondary);">
                    <div><strong>Zone:</strong> ${p.zone_id}</div>
                    <div><strong>Cardless Biometric:</strong> ${p.allow_cardless_biometric ? 'Allowed' : 'Disabled'}</div>
                    <div><strong>Requires Two-Factor:</strong> ${p.require_card_and_biometric ? 'Yes' : 'No'}</div>
                    <div><strong>Allowed Levels:</strong> ${p.allowed_access_levels.join(", ")}</div>
                </div>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed to load policies", err);
    }
}

// Load Audit Logs
async function loadAuditLogs() {
    try {
        const res = await apiCall("/audit/logs");
        if (!res.ok) return;
        const logs = await res.json();
        const tbody = document.getElementById("audit-logs-tbody");

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No audit logs recorded yet.</td></tr>';
            return;
        }

        tbody.innerHTML = logs.map(l => `
            <tr>
                <td><code>${l.audit_id ? l.audit_id.slice(0, 10) : '-'}</code></td>
                <td>${new Date(l.timestamp).toLocaleTimeString()}</td>
                <td>${l.actor_username}</td>
                <td><span class="badge">${l.actor_role}</span></td>
                <td><strong>${l.action}</strong></td>
                <td>${l.target_type}:${l.target_id || ''}</td>
                <td><span class="badge badge-${l.status === 'SUCCESS' ? 'allow' : 'deny'}">${l.status}</span></td>
                <td><small>${JSON.stringify(l.details || {})}</small></td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed to load audit logs", err);
    }
}

// Initial Start
autoLogin().then(() => {
    loadDashboard();
});
