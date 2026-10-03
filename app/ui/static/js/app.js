/**
 * Nexus — Frontend Application Logic
 * 
 * Handles WebSocket communication with the backend,
 * UI updates, approval flow, and message rendering.
 */

// ── State ──
let ws = null;
let currentApprovalStepId = null;
let isProcessing = false;

// ── DOM References ──
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const btnSend = document.getElementById('btn-send');
const connectionDot = document.getElementById('connection-dot');
const connectionStatus = document.getElementById('connection-status');
const agentPhase = document.getElementById('agent-phase');
const planSteps = document.getElementById('plan-steps');
const contextVars = document.getElementById('context-vars');
const screenshots = document.getElementById('screenshots');
const approvalBanner = document.getElementById('approval-banner');

// ── WebSocket Connection ──
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        connectionDot.className = 'status-dot connected';
        connectionStatus.textContent = 'Connected';
        console.log('WebSocket connected');
    };
    
    ws.onclose = () => {
        connectionDot.className = 'status-dot disconnected';
        connectionStatus.textContent = 'Disconnected';
        console.log('WebSocket disconnected, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleAgentMessage(data);
    };
}

// ── Message Handlers ──
function handleAgentMessage(data) {
    console.log('Agent message:', data.type, data);
    
    switch (data.type) {
        case 'task_start':
            handleTaskStart(data);
            break;
        case 'phase':
            handlePhaseUpdate(data);
            break;
        case 'goal':
            handleGoalUpdate(data);
            break;
        case 'plan':
            handlePlanUpdate(data);
            break;
        case 'step_start':
            handleStepStart(data);
            break;
        case 'approval_check':
        case 'approval_request':
            handleApprovalRequest(data);
            break;
        case 'step_complete':
            handleStepComplete(data);
            break;
        case 'step_skipped':
            handleStepSkipped(data);
            break;
        case 'recovery':
            handleRecovery(data);
            break;
        case 'human_help_needed':
            handleHumanHelp(data);
            break;
        case 'task_complete':
            handleTaskComplete(data);
            break;
        case 'task_error':
            handleTaskError(data);
            break;
        case 'clarification_needed':
            handleClarification(data);
            break;
        default:
            console.log('Unknown message type:', data.type);
    }
}

function handleTaskStart(data) {
    isProcessing = true;
    btnSend.disabled = true;
    updatePhase('🚀', 'Starting task...');
}

function handlePhaseUpdate(data) {
    const icons = {
        'understanding': '🧠',
        'planning': '📋',
        'executing': '⚡',
        'replanning': '🔄',
        'verifying': '🔍',
    };
    const icon = icons[data.phase] || '⚙️';
    updatePhase(icon, data.message);
    addSystemMessage(data.message, 'phase-message');
}

function handleGoalUpdate(data) {
    let html = `<strong>Goal:</strong> ${escapeHtml(data.goal)}<br>`;
    if (data.sub_goals && data.sub_goals.length > 0) {
        html += '<strong>Sub-goals:</strong><ul>';
        data.sub_goals.forEach(sg => {
            html += `<li>${escapeHtml(sg)}</li>`;
        });
        html += '</ul>';
    }
    if (data.urgency) {
        const urgencyColors = { low: '#10b981', medium: '#f59e0b', high: '#ef4444' };
        html += `<strong>Urgency:</strong> <span style="color: ${urgencyColors[data.urgency] || '#f59e0b'}">${data.urgency.toUpperCase()}</span>`;
    }
    addSystemMessage(html, 'goal-message');
}

function handlePlanUpdate(data) {
    // Update sidebar plan
    planSteps.innerHTML = '';
    if (data.steps && data.steps.length > 0) {
        data.steps.forEach((step, i) => {
            const div = document.createElement('div');
            div.className = 'plan-step';
            div.id = `plan-step-${step.step_id || i}`;
            div.innerHTML = `
                <span class="plan-step-status">⬜</span>
                <span class="plan-step-text">${escapeHtml(step.description || `Step ${i + 1}`)}</span>
            `;
            planSteps.appendChild(div);
        });
    }
    
    // Add plan message to chat
    let html = `<strong>📋 Execution Plan (${data.total_steps} steps):</strong><br>`;
    if (data.reasoning) {
        html += `<em>${escapeHtml(data.reasoning)}</em><br><br>`;
    }
    html += '<ol>';
    data.steps.forEach(step => {
        const riskBadge = step.risk_level === 'high' ? ' 🔴' : step.risk_level === 'medium' ? ' 🟡' : '';
        html += `<li>${escapeHtml(step.description)}${riskBadge}</li>`;
    });
    html += '</ol>';
    addSystemMessage(html, 'plan-message');
}

function handleStepStart(data) {
    // Update sidebar - mark step as active
    const stepEl = document.getElementById(`plan-step-${data.step_id}`);
    if (stepEl) {
        stepEl.className = 'plan-step active';
        stepEl.querySelector('.plan-step-status').textContent = '🔄';
    }
    
    addSystemMessage(
        `<span class="spinner"></span> <strong>Step ${data.step_index}/${data.total_steps}:</strong> ${escapeHtml(data.description)} <em>[${data.tool}]</em>`,
        'step-message'
    );
}

function handleApprovalRequest(data) {
    currentApprovalStepId = data.step_id;
    
    document.getElementById('approval-description').textContent = data.description;
    document.getElementById('approval-risk').textContent = `${data.risk_level.toUpperCase()} RISK`;
    approvalBanner.style.display = 'block';
    
    addSystemMessage(
        `🔒 <strong>Approval Required:</strong> ${escapeHtml(data.description)}<br>` +
        `<span style="color: var(--accent-yellow)">Risk Level: ${data.risk_level.toUpperCase()}</span><br>` +
        `<em>Waiting for your decision...</em>`,
        'approval-message'
    );
}

function handleStepComplete(data) {
    // Update sidebar plan step
    const stepEl = document.getElementById(`plan-step-${data.step_id}`);
    if (stepEl) {
        stepEl.className = data.success ? 'plan-step completed' : 'plan-step failed';
        stepEl.querySelector('.plan-step-status').textContent = data.success ? '✅' : '❌';
    }
    
    // Update context variables
    if (data.extracted_data && Object.keys(data.extracted_data).length > 0) {
        updateContextVars(data.extracted_data);
    }
    
    // Add screenshot if available
    if (data.screenshot) {
        addScreenshot(data.screenshot);
    }
    
    // Add result message
    const status = data.success ? '✅' : '❌';
    let html = `${status} ${escapeHtml(data.observation || 'Step completed')}`;
    addSystemMessage(html, data.success ? 'step-message' : 'step-message failed');
}

function handleStepSkipped(data) {
    const stepEl = document.getElementById(`plan-step-${data.step_id}`);
    if (stepEl) {
        stepEl.className = 'plan-step';
        stepEl.querySelector('.plan-step-status').textContent = '⏭️';
    }
    addSystemMessage(`⏭️ Step skipped: ${escapeHtml(data.reason)}`, 'step-message');
}

function handleRecovery(data) {
    const icon = data.action === 'retry' ? '🔄' : data.action === 'alternative' ? '🔀' : '⚠️';
    addSystemMessage(`${icon} <strong>Recovery:</strong> ${escapeHtml(data.message)}`, 'recovery-message');
}

function handleHumanHelp(data) {
    addSystemMessage(
        `🆘 <strong>Human assistance needed:</strong><br>${escapeHtml(data.message)}`,
        'help-message'
    );
}

function handleTaskComplete(data) {
    isProcessing = false;
    btnSend.disabled = false;
    
    const verified = data.verified;
    updatePhase(verified ? '✅' : '⚠️', verified ? 'Task Complete — Verified' : 'Task Complete — Unverified');
    
    let html = `<strong>${verified ? '✅ Task Completed Successfully' : '⚠️ Task Completed (Unverified)'}</strong><br><br>`;
    html += `<strong>Summary:</strong> ${escapeHtml(data.summary || 'No summary')}<br><br>`;
    
    if (data.confidence !== undefined) {
        html += `<strong>Confidence:</strong> ${(data.confidence * 100).toFixed(0)}%<br>`;
    }
    
    html += `<strong>Steps Executed:</strong> ${data.steps_executed || 0} (${data.steps_failed || 0} failed)<br>`;
    
    if (data.evidence && data.evidence.completed_items) {
        html += '<br><strong>Completed:</strong><ul>';
        data.evidence.completed_items.forEach(item => {
            html += `<li>${escapeHtml(item)}</li>`;
        });
        html += '</ul>';
    }
    
    if (data.missing_items && data.missing_items.length > 0) {
        html += '<br><strong>Missing/Unverified:</strong><ul>';
        data.missing_items.forEach(item => {
            html += `<li>${escapeHtml(item)}</li>`;
        });
        html += '</ul>';
    }
    
    if (data.recommendations && data.recommendations.length > 0) {
        html += '<br><strong>Recommendations:</strong><ul>';
        data.recommendations.forEach(rec => {
            html += `<li>${escapeHtml(rec)}</li>`;
        });
        html += '</ul>';
    }
    
    addSystemMessage(html, verified ? 'verification-message' : 'verification-message failed');
}

function handleTaskError(data) {
    isProcessing = false;
    btnSend.disabled = false;
    updatePhase('❌', 'Task Failed');
    addSystemMessage(`❌ <strong>Error:</strong> ${escapeHtml(data.summary || data.error || 'Unknown error')}`, 'error-message');
}

function handleClarification(data) {
    addSystemMessage(`❓ <strong>Clarification needed:</strong> ${escapeHtml(data.question)}`, 'clarification-message');
}

// ── UI Update Helpers ──
function updatePhase(icon, text) {
    agentPhase.innerHTML = `
        <span class="phase-icon">${icon}</span>
        <span class="phase-text">${text}</span>
    `;
}

function updateContextVars(newVars) {
    // Get existing vars or start fresh
    if (contextVars.querySelector('.empty-text')) {
        contextVars.innerHTML = '';
    }
    
    Object.entries(newVars).forEach(([key, value]) => {
        let existing = document.getElementById(`ctx-${key}`);
        if (existing) {
            existing.querySelector('.context-value').textContent = String(value).substring(0, 200);
        } else {
            const div = document.createElement('div');
            div.className = 'context-item';
            div.id = `ctx-${key}`;
            div.innerHTML = `
                <span class="context-key">${escapeHtml(key)}</span>
                <span class="context-value">${escapeHtml(String(value).substring(0, 200))}</span>
            `;
            contextVars.appendChild(div);
        }
    });
}

function addScreenshot(path) {
    if (screenshots.querySelector('.empty-text')) {
        screenshots.innerHTML = '';
    }
    // We can't directly display local file screenshots in the browser,
    // so we show the path and use the API endpoint
    const filename = path.split(/[/\\]/).pop();
    const img = document.createElement('img');
    img.src = `/screenshots/${filename}`;
    img.className = 'screenshot-thumb';
    img.alt = filename;
    img.onerror = function() {
        this.style.display = 'none';
    };
    screenshots.appendChild(img);
}

function addSystemMessage(html, extraClass = '') {
    const div = document.createElement('div');
    div.className = `message system-message ${extraClass}`;
    div.innerHTML = `
        <div class="message-icon">⚡</div>
        <div class="message-body">
            <div class="message-sender">Nexus</div>
            <div class="message-text">${html}</div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message user-message';
    div.innerHTML = `
        <div class="message-icon">👤</div>
        <div class="message-body">
            <div class="message-sender">You</div>
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── User Actions ──
function sendMessage(event) {
    event.preventDefault();
    
    const text = userInput.value.trim();
    if (!text || isProcessing) return;
    
    addUserMessage(text);
    userInput.value = '';
    userInput.style.height = 'auto';
    
    // Reset sidebar
    planSteps.innerHTML = '<p class="empty-text">Creating plan...</p>';
    contextVars.innerHTML = '<p class="empty-text">No data yet</p>';
    screenshots.innerHTML = '<p class="empty-text">No screenshots</p>';
    
    // Send to backend
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'task',
            input: text,
        }));
    } else {
        addSystemMessage('❌ Not connected to server. Please wait...', 'error-message');
    }
}

function submitApproval(approved) {
    if (currentApprovalStepId === null) return;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'approval',
            step_id: currentApprovalStepId,
            approved: approved,
            reason: approved ? 'User approved' : 'User rejected',
        }));
    }
    
    approvalBanner.style.display = 'none';
    
    addSystemMessage(
        approved 
            ? '✅ <strong>Approved</strong> — proceeding with action' 
            : '❌ <strong>Rejected</strong> — skipping action',
        'approval-response'
    );
    
    currentApprovalStepId = null;
}

// ── Auto-resize textarea ──
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// Enter to send (Shift+Enter for newline)
userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('chat-form').dispatchEvent(new Event('submit'));
    }
});

// ── Utility ──
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Initialize ──
connectWebSocket();
