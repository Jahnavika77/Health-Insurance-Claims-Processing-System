const API_BASE = "http://localhost:8000";
let selectedFiles = [];
let pipelineInterval;

// Navigation
function showSection(sectionId) {
    document.querySelectorAll('main > section').forEach(s => s.style.display = 'none');
    document.querySelectorAll('nav li').forEach(l => l.classList.remove('active'));
    
    document.getElementById(`${sectionId}-section`).style.display = 'block';
    const links = document.querySelectorAll('nav li');
    if (sectionId === 'dashboard') links[0].classList.add('active');
    if (sectionId === 'new-claim') links[1].classList.add('active');
    if (sectionId === 'history') links[2].classList.add('active');

    if (sectionId === 'history' || sectionId === 'dashboard') fetchHistory();
}

// File Selection
function handleFiles(files) {
    selectedFiles = Array.from(files);
    document.getElementById('file-count').innerText = `${selectedFiles.length} file(s) selected`;
}

// History & Stats
async function fetchHistory() {
    try {
        const response = await fetch(`${API_BASE}/history`);
        const history = await response.json();
        updateStats(history);
        renderHistoryTable(history, 'history-container');
        renderHistoryTable(history.slice(0, 5), 'recent-claims-list');
    } catch (err) { console.error(err); }
}

function updateStats(history) {
    document.getElementById('total-claims').innerText = history.length;
    const approved = history.filter(h => h.verdict === 'APPROVED' || h.verdict === 'PARTIAL').length;
    document.getElementById('approval-rate').innerText = `${history.length > 0 ? Math.round((approved / history.length) * 100) : 0}%`;
    document.getElementById('auto-processed').innerText = history.filter(h => h.verdict !== 'MANUAL_REVIEW').length;
    const totalPayout = history.reduce((acc, c) => acc + (c.trace?.summary?.approved_amount || 0), 0);
    document.getElementById('total-payout').innerText = `₹${totalPayout.toLocaleString()}`;
}

function renderHistoryTable(data, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (data.length === 0) { container.innerHTML = "<p>No claims found.</p>"; return; }

    // Use containerId prefix to make IDs unique across dashboard and history tab
    const prefix = containerId.split('-')[0];

    let html = `<table class="history-table"><thead><tr><th>ID</th><th>Member</th><th>Verdict</th><th>Amount</th><th>Date</th><th>Action</th></tr></thead><tbody>`;
    data.forEach((item, index) => {
        const badgeClass = item.verdict.toLowerCase().replace('_', '-');
        const rowId = `${prefix}-trace-${index}`;
        html += `
            <tr>
                <td style="color:var(--primary);font-weight:600">${item.claim_id}</td>
                <td>${item.member_id}</td>
                <td><span class="badge badge-${badgeClass}">${item.verdict}</span></td>
                <td>₹${item.amount}</td>
                <td>${new Date(item.created_at).toLocaleDateString()}</td>
                <td><button class="btn" style="font-size:11px" onclick="toggleTrace('${rowId}')">Trace</button></td>
            </tr>
            <tr id="${rowId}" style="display:none;background:rgba(0,0,0,0.3)"><td colspan="6"><pre style="color:var(--success);padding:15px;overflow:auto">${JSON.stringify(item.trace, null, 2)}</pre></td></tr>`;
    });
    container.innerHTML = html + "</tbody></table>";
}

function toggleTrace(rowId) {
    const el = document.getElementById(rowId);
    el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
}

// Submission & Pipeline
async function submitClaim() {
    const memberId = document.getElementById('member-id').value;
    const category = document.getElementById('claim-category').value;
    const amount = document.getElementById('claimed-amount').value;
    const date = document.getElementById('treatment-date').value;

    if (!memberId || !amount || !date || selectedFiles.length === 0) {
        alert("Please fill all fields."); return;
    }

    // Prepare UI
    document.getElementById('claim-form').style.display = 'none';
    document.getElementById('pipeline-result').style.display = 'block';
    document.getElementById('final-verdict').style.display = 'none';

    const steps = [1,2,3,4,5].map(i => document.getElementById(`step-${i}`));
    steps.forEach(s => {
        s.classList.remove('completed', 'processing');
        s.style.opacity = '1';
        s.style.borderColor = 'var(--border)';
    });

    // Start simulation
    let current = 0;
    pipelineInterval = setInterval(() => {
        if (current < 5) {
            steps[current].classList.add('processing');
            if (current > 0) {
                steps[current-1].classList.remove('processing');
                steps[current-1].classList.add('completed');
            }
            current++;
        }
    }, 3000);

    const formData = new FormData();
    formData.append('member_id', memberId);
    formData.append('claim_category', category);
    formData.append('claimed_amount', amount);
    formData.append('treatment_date', date);
    selectedFiles.forEach(f => formData.append('files', f));

    try {
        const response = await fetch(`${API_BASE}/submit-claim`, { method: 'POST', body: formData });
        const result = await response.json();
        
        clearInterval(pipelineInterval);

        if (result.status === "VALIDATION_FAILED") {
            handleError(result.error_message, result.failed_step);
        } else {
            steps.forEach(s => { s.classList.remove('processing'); s.classList.add('completed'); });
            displayVerdict(result);
        }
    } catch (err) {
        clearInterval(pipelineInterval);
        handleError("Connection to AI Pipeline failed.", 0);
    }
}

function handleError(msg, failedStepIdx) {
    const originalTexts = [
        "1. OCR & Validation (Agent 1)",
        "2. Document Parsing (Agent 2)",
        "3. Policy Checking (Agent 3)",
        "4. Fraud Detection (Agent 4)",
        "5. Final Decision (Agent 5)"
    ];
    const steps = [1,2,3,4,5].map(i => document.getElementById(`step-${i}`));
    
    // Reset and process steps
    steps.forEach((s, idx) => {
        s.classList.remove('processing', 'completed');
        s.innerText = originalTexts[idx];
        
        if (idx < failedStepIdx) {
            s.classList.add('completed');
            s.innerText += " (Completed)";
        } else if (idx === failedStepIdx) {
            s.style.opacity = '1';
            s.style.borderColor = 'var(--danger)';
            s.innerText += " (FAILED)";
        } else {
            s.style.opacity = '0.3';
        }
    });

    const div = document.getElementById('final-verdict');
    div.style.display = 'block';
    div.style.background = 'rgba(249, 65, 68, 0.1)';
    div.style.border = '1px solid var(--danger)';
    
    document.getElementById('verdict-text').innerText = "Pipeline Halted";
    document.getElementById('verdict-reason').innerText = msg;
    document.getElementById('verdict-amount').innerText = "Action Required";
}

function displayVerdict(res) {
    const div = document.getElementById('final-verdict');
    div.style.display = 'block';
    div.style.background = 'rgba(131, 56, 236, 0.05)';
    div.style.border = '1px solid var(--primary)';
    
    document.getElementById('verdict-text').innerText = res.verdict;
    document.getElementById('verdict-reason').innerText = res.reason;
    document.getElementById('verdict-amount').innerText = `₹${res.approved_amount}`;
}

fetchHistory();
