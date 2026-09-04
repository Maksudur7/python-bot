document.addEventListener('DOMContentLoaded', () => {
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const btnClearConsole = document.getElementById('btn-clear-console');
    const watchLiveToggle = document.getElementById('watch-live-toggle');
    const statusBadge = document.getElementById('bot-status-badge');
    const statusText = document.getElementById('bot-status-text');
    
    const metricChecked = document.getElementById('metric-checked');
    const metricSaved = document.getElementById('metric-saved');
    const metricCancelled = document.getElementById('metric-cancelled');
    const metricLiveStatus = document.getElementById('metric-live-status');
    
    const consoleBody = document.getElementById('terminal-console');
    const recordsTableBody = document.getElementById('records-table-body');

    let pollInterval = null;

    // Start Bot Handler
    btnStart.addEventListener('click', async () => {
        const watchLive = watchLiveToggle.checked;
        try {
            const res = await fetch('/api/bot/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ headless: !watchLive })
            });
            const data = await res.json();
            if (data.status === 'ok') {
                updateUIState(true);
            }
        } catch (e) {
            console.error('Error starting bot:', e);
        }
    });

    // Stop Bot Handler
    btnStop.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/bot/stop', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'ok') {
                updateUIState(false);
            }
        } catch (e) {
            console.error('Error stopping bot:', e);
        }
    });

    // Clear Console Handler
    btnClearConsole.addEventListener('click', () => {
        consoleBody.innerHTML = '<div class="log-line system">[System] Console logs cleared.</div>';
    });

    function updateUIState(isRunning) {
        btnStart.disabled = isRunning;
        btnStop.disabled = !isRunning;
        watchLiveToggle.disabled = isRunning;

        if (isRunning) {
            statusBadge.className = 'status-badge running';
            statusText.textContent = 'RUNNING';
        } else {
            statusBadge.className = 'status-badge idle';
            statusText.textContent = 'IDLE';
        }
    }

    async function fetchState() {
        try {
            const res = await fetch('/api/state');
            if (!res.ok) return;
            const data = await res.json();

            // Update status & metrics
            const isRunning = data.is_running;
            updateUIState(isRunning);

            metricChecked.textContent = data.metrics.numbers_checked || 0;
            metricSaved.textContent = data.metrics.records_saved || 0;
            metricCancelled.textContent = data.metrics.cancelled_cost || 0;
            metricLiveStatus.textContent = data.metrics.current_status || 'IDLE';

            // Update Console Logs
            if (data.logs && data.logs.length > 0) {
                consoleBody.innerHTML = data.logs.map(log => `<div class="log-line">${escapeHtml(log)}</div>`).join('');
                consoleBody.scrollTop = consoleBody.scrollHeight;
            }

            // Update Records Table
            if (data.records && data.records.length > 0) {
                recordsTableBody.innerHTML = data.records.map(rec => `
                    <tr>
                        <td>${rec.timestamp || '-'}</td>
                        <td><strong>${rec.phone || '-'}</strong></td>
                        <td>${rec.order_id || '-'}</td>
                        <td>${rec.name || '-'}</td>
                        <td>${rec.age || '-'}</td>
                        <td>${rec.location || '-'}</td>
                        <td>${rec.relatives || '-'}</td>
                        <td><span class="badge-verify">${rec.google_status || 'Verified'}</span></td>
                    </tr>
                `).join('');
            } else {
                recordsTableBody.innerHTML = `
                    <tr>
                        <td colspan="8" class="empty-state">No saved record matches yet. Bot will populate valid FamilyTreeNow results here.</td>
                    </tr>
                `;
            }
        } catch (e) {
            console.error('Error fetching state:', e);
        }
    }

    function escapeHtml(text) {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Start Polling every 1 second
    fetchState();
    pollInterval = setInterval(fetchState, 1000);
});
