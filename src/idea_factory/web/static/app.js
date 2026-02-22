/* Idea Factory — SSE client + provider setup + feedback form handler */

let currentRunId = null;
let evtSource = null;

/* --- Provider setup --- */
const btnSaveKey = document.getElementById('btn-save-key');
const btnChangeProvider = document.getElementById('btn-change-provider');
const providerStatus = document.getElementById('provider-status');
const providerConnected = document.getElementById('provider-connected');
const providerBadge = document.getElementById('provider-badge');
const keyError = document.getElementById('key-error');

if (btnSaveKey) {
    btnSaveKey.addEventListener('click', async () => {
        const selected = document.querySelector('input[name="provider"]:checked');
        const apiKeyInput = document.getElementById('api-key');
        if (!selected || !apiKeyInput) return;

        const provider = selected.value;
        const apiKey = apiKeyInput.value.trim();

        if (!apiKey) {
            if (keyError) { keyError.textContent = 'API key is required.'; keyError.style.display = ''; }
            return;
        }

        btnSaveKey.disabled = true;

        try {
            const res = await fetch('/api/provider', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, api_key: apiKey }),
            });
            const data = await res.json();

            if (data.has_key) {
                // Switch to connected view
                if (providerStatus) providerStatus.style.display = 'none';
                if (providerConnected) providerConnected.style.display = '';
                if (providerBadge) { providerBadge.textContent = 'CONNECTED'; providerBadge.className = 'badge badge-winner'; }

                const cp = document.getElementById('connected-provider');
                const cm = document.getElementById('connected-model');
                if (cp) cp.textContent = data.provider;
                if (cm) cm.textContent = data.model;

                // Enable start button
                if (btnStart) btnStart.disabled = false;

                if (keyError) keyError.style.display = 'none';
            } else {
                if (keyError) { keyError.textContent = 'Failed to save key.'; keyError.style.display = ''; }
            }
        } catch (err) {
            if (keyError) { keyError.textContent = 'Error: ' + err.message; keyError.style.display = ''; }
        } finally {
            btnSaveKey.disabled = false;
        }
    });
}

if (btnChangeProvider) {
    btnChangeProvider.addEventListener('click', () => {
        if (providerConnected) providerConnected.style.display = 'none';
        if (providerStatus) providerStatus.style.display = '';
    });
}

const startForm = document.getElementById('start-form');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const runStatus = document.getElementById('run-status');
const statusBadge = document.getElementById('run-status-badge');
const timeline = document.getElementById('event-timeline');
const feedbackForm = document.getElementById('feedback-form');
const fbForm = document.getElementById('fb-form');
const fbRunId = document.getElementById('fb-run-id');
const fbIdeaInfo = document.getElementById('feedback-idea-info');

/* --- Event descriptions --- */
const EVENT_MESSAGES = {
    loop_started: d => `Loop ${d.loop_num} starting`,
    agent_started: d => `${(d.agent || '').toUpperCase()} working on ${d.idea || 'batch'}...`,
    agent_completed: d => {
        let msg = `${(d.agent || '').toUpperCase()} done`;
        if (d.verdict) msg += ` — ${d.verdict}`;
        if (d.composite_score) msg += ` (${d.composite_score.toFixed(1)})`;
        if (d.count !== undefined) msg += ` — ${d.count} ideas`;
        return msg;
    },
    idea_created: d => `New idea: ${d.name}`,
    idea_survived: d => `SURVIVE: ${d.name}`,
    idea_killed: d => `KILL: ${d.name}`,
    feedback_needed: d => `Feedback needed for: ${d.name} (${d.verdict}, ${d.composite_score.toFixed(1)})`,
    run_completed: d => `Run complete! ${d.total_ideas} ideas, ${d.total_winners} winners`,
    run_error: d => `Error: ${d.error}`,
    log: d => d.message || '',
};

function addEvent(eventType, data) {
    if (!timeline) return;
    const div = document.createElement('div');
    div.className = `event-entry event-${eventType}`;
    const msgFn = EVENT_MESSAGES[eventType];
    const msg = msgFn ? msgFn(data) : JSON.stringify(data);
    div.innerHTML = `<span class="event-type">${eventType.replace(/_/g, ' ')}</span><span class="event-msg">${msg}</span>`;
    timeline.appendChild(div);
    timeline.scrollTop = timeline.scrollHeight;
}

/* --- Start run --- */
if (startForm) {
    startForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(startForm);
        const domains = fd.getAll('domains');
        const payload = {
            region: fd.get('region') || 'Global',
            domains: domains.length ? domains : ['Software engineering'],
            constraints: fd.get('constraints') || '',
            claude_check: !!fd.get('claude_check'),
        };

        btnStart.disabled = true;
        btnStart.setAttribute('aria-busy', 'true');

        try {
            const res = await fetch('/api/runs/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const json = await res.json();
            currentRunId = json.run_id;
            if (fbRunId) fbRunId.value = currentRunId;

            // Show status panel
            if (runStatus) runStatus.style.display = '';
            if (statusBadge) { statusBadge.textContent = 'RUNNING'; statusBadge.className = 'badge badge-contender'; }
            if (btnStop) btnStop.disabled = false;

            // Start SSE
            connectSSE(currentRunId);
        } catch (err) {
            alert('Failed to start run: ' + err.message);
        } finally {
            btnStart.disabled = false;
            btnStart.removeAttribute('aria-busy');
        }
    });
}

/* --- Stop run --- */
if (btnStop) {
    btnStop.addEventListener('click', async () => {
        if (!currentRunId) return;
        await fetch(`/api/runs/${currentRunId}/stop`, { method: 'POST' });
        if (statusBadge) { statusBadge.textContent = 'STOPPING'; statusBadge.className = 'badge badge-killed'; }
        btnStop.disabled = true;
    });
}

/* --- SSE --- */
function connectSSE(runId) {
    if (evtSource) evtSource.close();
    evtSource = new EventSource(`/sse/${runId}`);

    const eventTypes = [
        'loop_started', 'agent_started', 'agent_completed',
        'idea_created', 'idea_survived', 'idea_killed',
        'feedback_needed', 'run_completed', 'run_error', 'log', 'done'
    ];

    eventTypes.forEach(type => {
        evtSource.addEventListener(type, (e) => {
            const data = e.data ? JSON.parse(e.data) : {};

            if (type === 'done') {
                evtSource.close();
                if (statusBadge) { statusBadge.textContent = 'DONE'; statusBadge.className = 'badge badge-winner'; }
                if (feedbackForm) feedbackForm.style.display = 'none';
                return;
            }

            if (type === 'run_error') {
                if (statusBadge) { statusBadge.textContent = 'ERROR'; statusBadge.className = 'badge badge-pass'; }
            }

            if (type === 'feedback_needed') {
                showFeedbackForm(data);
            }

            addEvent(type, data);
        });
    });

    evtSource.onerror = () => {
        // SSE connection lost — don't auto-reconnect
    };
}

/* --- Feedback --- */
function showFeedbackForm(data) {
    if (!feedbackForm || !fbIdeaInfo) return;
    feedbackForm.style.display = '';
    fbIdeaInfo.innerHTML = `<strong>${data.name}</strong> — ${data.verdict} (${data.composite_score.toFixed(1)}/10)`;
    feedbackForm.scrollIntoView({ behavior: 'smooth' });
}

if (fbForm) {
    fbForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(fbForm);
        const payload = {
            decision: fd.get('decision') || 'like',
            rating: parseInt(fd.get('rating') || '5'),
            tags: (fd.get('tags') || '').split(',').map(s => s.trim()).filter(Boolean),
            note: fd.get('note') || '',
        };

        const runId = fbRunId ? fbRunId.value : currentRunId;
        await fetch(`/api/feedback/${runId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        feedbackForm.style.display = 'none';
        addEvent('log', { message: `Feedback submitted: ${payload.decision} (${payload.rating}/10)` });
    });
}
