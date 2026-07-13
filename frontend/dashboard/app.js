const API_BASE = "http://localhost:8003";

const DOM = {
    statusIndicator: document.getElementById('global-status'),
    statusText: document.getElementById('status-text'),
    servicesList: document.getElementById('active-services-list'),
    statAwake: document.getElementById('stat-awake'),
    statDrowsy: document.getElementById('stat-drowsy'),
    statDangerous: document.getElementById('stat-dangerous'),
    statTotal: document.getElementById('stat-total'),
    eventFeed: document.getElementById('event-feed')
};

let lastEventCount = -1;

function updateStatusUI(overall) {
    DOM.statusIndicator.className = 'status-indicator';
    if (overall === 'DANGEROUS') {
        DOM.statusIndicator.classList.add('danger');
        DOM.statusText.textContent = 'CRITICAL ALERT';
    } else if (overall === 'DROWSY' || overall === 'TIRED') {
        DOM.statusIndicator.classList.add('warning');
        DOM.statusText.textContent = 'WARNING DETECTED';
    } else {
        DOM.statusIndicator.classList.add('safe');
        DOM.statusText.textContent = 'SYSTEM SECURE';
    }
}

function formatTime(isoString) {
    if (!isoString) return new Date().toLocaleTimeString();
    let d = new Date(isoString);
    if (isNaN(d.getTime())) {
        d = new Date(isoString * 1000); // handle unix timestamp if provided
    }
    return d.toLocaleTimeString();
}

function createEventElement(event) {
    const el = document.createElement('div');
    el.className = 'event-item';
    
    if (event.alert_level === 'DANGEROUS') el.classList.add('danger');
    else if (event.alert_level === 'DROWSY' || event.alert_level === 'TIRED') el.classList.add('warning');

    let message = event.alert_level;
    if (event.data && event.data.message) {
        message = event.data.message;
    } else if (event.message) {
        message = event.message;
    }

    el.innerHTML = `
        <div class="event-meta">
            <span class="event-source">${event.source || 'system'}</span>
            <span class="event-time">${formatTime(event.timestamp || event.received_at)}</span>
        </div>
        <div class="event-message">${message}</div>
    `;
    return el;
}

async function fetchStats() {
    try {
        const res = await fetch(`${API_BASE}/stats`);
        if (!res.ok) return;
        const data = await res.json();
        
        DOM.statAwake.textContent = data.alert_counts.AWAKE || 0;
        DOM.statDrowsy.textContent = (data.alert_counts.DROWSY || 0) + (data.alert_counts.TIRED || 0);
        DOM.statDangerous.textContent = data.alert_counts.DANGEROUS || 0;
        DOM.statTotal.textContent = data.total;

    } catch (e) {
        console.error("Failed to fetch stats", e);
    }
}

async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/status`);
        if (!res.ok) return;
        const data = await res.json();

        updateStatusUI(data.overall_alert);

        // Update active services
        if (data.active_services.length === 0) {
            DOM.servicesList.innerHTML = '<li>No active services detected</li>';
        } else {
            DOM.servicesList.innerHTML = data.active_services.map(s => `<li>${s}</li>`).join('');
        }

        // Only fetch events if the count has changed
        if (data.event_count !== lastEventCount) {
            fetchEvents();
            fetchStats();
            lastEventCount = data.event_count;
        }

    } catch (e) {
        console.error("Failed to fetch status", e);
        DOM.statusIndicator.className = 'status-indicator danger';
        DOM.statusText.textContent = 'OFFLINE';
    }
}

async function fetchEvents() {
    try {
        const res = await fetch(`${API_BASE}/events?limit=20`);
        if (!res.ok) return;
        const events = await res.json();
        
        DOM.eventFeed.innerHTML = '';
        if (events.length === 0) {
            DOM.eventFeed.innerHTML = '<div class="empty-state">No events detected yet.</div>';
            return;
        }

        events.forEach(ev => {
            DOM.eventFeed.appendChild(createEventElement(ev));
        });

    } catch (e) {
        console.error("Failed to fetch events", e);
    }
}

// Initial fetch and poll
fetchStatus();
fetchEvents();
setInterval(fetchStatus, 1000);
