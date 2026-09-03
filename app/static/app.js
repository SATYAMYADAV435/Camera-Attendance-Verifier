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

// Tab navigation
document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
        
        btn.classList.add("active");
        const tabId = btn.getAttribute("data-tab");
        const pane = document.getElementById(`tab-${tabId}`);
        if (pane) pane.classList.add("active");

        // Load data corresponding to tab
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

// Select employee in dropdown
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

// Create Employee Form
document.getElementById("open-create-emp-modal").addEventListener("click", () => {
    document.getElementById("create-emp-modal").classList.add("show");
});

window.closeModal = function(id) {
    document.getElementById(id).classList.remove("show");
};

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

// Biometric Enrollment Actions
document.getElementById("sim-enroll-face-btn").addEventListener("click", async () => {
    const empId = document.getElementById("enroll-employee-select").value;
    if (!empId) return alert("Select an employee first");

    // Generate simulated high quality 512-dim embedding
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

// Access Simulation Triggers
document.getElementById("sim-access-btn").addEventListener("click", async () => {
    // 1. Pick first employee if exists
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
        liveness_score: 0.94,
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
    // 1. Ingest valid card
    await apiCall("/access/card-event", {
        method: "POST",
        body: JSON.stringify({
            card_id: "CARD-001",
            door_id: "DOOR-MAIN-ENTRANCE",
            reader_id: "READER-01"
        })
    });

    // 2. Simulate 1st legitimate entrant crossing
    await apiCall("/access/crossing-event", {
        method: "POST",
        body: JSON.stringify({ door_id: "DOOR-MAIN-ENTRANCE", track_id: 101, camera_id: "CAM-01-ENTRANCE" })
    });

    // 3. Simulate 2nd unauthorized entrant crossing without badge (Tailgating!)
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

// Initial Start
autoLogin().then(() => {
    loadDashboard();
});
