/* ===================================================================
   UrbanAir — Main Application JavaScript
   ES6+ · Vanilla JS · No frameworks
   =================================================================== */

(() => {
  'use strict';

  // ───────────── State ─────────────
  let currentAqiData   = null;   // last fetched AQI payload
  let currentCategory  = null;   // last AQI category
  let selectedProfile  = null;   // e.g. "family_with_children"
  let pollutantCharts  = {};     // Chart.js instances, keyed by pollutant name
  let searchAbort      = null;   // AbortController for in-flight search

  // ───────────── DOM refs ─────────────
  const $  = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const cityInput        = $('#city-input');
  const autocompleteDD   = $('#autocomplete-dropdown');
  const searchSpinner    = $('#search-spinner');
  const btnGeo           = $('#btn-geolocation');
  const btnCheckAqi      = $('#btn-check-aqi');
  const aqiBtnSpinner    = $('#aqi-btn-spinner');
  const aqiDashboard     = $('#aqi-dashboard');
  const profileSection   = $('#profile-section');
  const recSection       = $('#recommendations-section');
  const recLoading       = $('#rec-loading');
  const recContent       = $('#rec-content');
  const btnGetRecs       = $('#btn-get-recs');
  const recBtnSpinner    = $('#rec-btn-spinner');

  // ───────────── Constants ─────────────
  const SAFE_LIMITS = {
    pm25: 25,   // WHO guideline μg/m³
    pm10: 50,
    o3:   100,
    no2:  40,
    so2:  40,
    co:   10
  };

  const POLLUTANT_LABELS = {
    pm25: 'PM2.5', pm10: 'PM10', o3: 'O₃',
    no2: 'NO₂', so2: 'SO₂', co: 'CO'
  };

  // ═══════════════════════════════════════════════════════════════════
  //  HELPERS
  // ═══════════════════════════════════════════════════════════════════

  /** Return AQI colour hex from value */
  function getAqiColor(aqi) {
    if (aqi <= 50)  return '#10b981'; // green
    if (aqi <= 100) return '#f59e0b'; // yellow
    if (aqi <= 150) return '#f97316'; // orange
    if (aqi <= 200) return '#ef4444'; // red
    if (aqi <= 300) return '#8b5cf6'; // purple
    return '#991b1b';                 // maroon
  }

  /** Return Tailwind-style badge class from colour hex */
  function getBadgeClass(hex) {
    const map = {
      '#10b981': 'badge-green',
      '#f59e0b': 'badge-yellow',
      '#f97316': 'badge-orange',
      '#ef4444': 'badge-red',
      '#8b5cf6': 'badge-purple',
      '#991b1b': 'badge-maroon'
    };
    return map[hex] || 'badge-green';
  }

  /** Format ISO date string to friendly local format */
  function formatDate(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        dateStyle: 'medium', timeStyle: 'short'
      });
    } catch { return iso; }
  }

  /** Count-up animation for a number */
  function animateNumber(el, target, duration = 1200) {
    const start = performance.now();
    const from  = 0;
    const step  = (ts) => {
      const progress = Math.min((ts - start) / duration, 1);
      const eased    = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      const val      = Math.round(from + (target - from) * eased);
      el.textContent = val;
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /** Debounce utility */
  function debounce(fn, ms) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  }

  // ═══════════════════════════════════════════════════════════════════
  //  TOAST NOTIFICATIONS
  // ═══════════════════════════════════════════════════════════════════

  function showToast(message, type = 'info', ms = 4000) {
    const container = $('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    toast.innerHTML = `<span class="text-lg">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'toastOut 0.3s ease forwards';
      toast.addEventListener('animationend', () => toast.remove());
    }, ms);
  }

  // ═══════════════════════════════════════════════════════════════════
  //  SECTION REVEAL (IntersectionObserver)
  // ═══════════════════════════════════════════════════════════════════

  function initSectionObserver() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    }, { threshold: 0.08 });
    $$('.fade-section').forEach(s => observer.observe(s));
  }

  /** Programmatically show & scroll to a section */
  function revealSection(el) {
    el.classList.remove('hidden');
    // small delay so the browser paints the element before we observe it
    requestAnimationFrame(() => {
      el.classList.add('visible');
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  //  AUTOCOMPLETE SEARCH
  // ═══════════════════════════════════════════════════════════════════

  async function searchStations(query) {
    if (searchAbort) searchAbort.abort();
    if (query.length < 2) {
      autocompleteDD.classList.add('hidden');
      cityInput.setAttribute('aria-expanded', 'false');
      return;
    }

    searchAbort = new AbortController();
    searchSpinner.classList.remove('hidden');

    try {
      const res  = await fetch(`/api/search-stations?q=${encodeURIComponent(query)}`, {
        signal: searchAbort.signal
      });
      const json = await res.json();
      searchSpinner.classList.add('hidden');

      if (json.status !== 'ok' || !json.data?.length) {
        autocompleteDD.classList.add('hidden');
        cityInput.setAttribute('aria-expanded', 'false');
        return;
      }

      autocompleteDD.innerHTML = json.data
        .slice(0, 8)
        .map((s, idx) => {
          const name = s.station_name || s.city || s.name || '';
          const aqi  = s.aqi ?? '';
          return `<div class="autocomplete-item" role="option" id="station-opt-${idx}" tabindex="0" data-name="${typeof name === 'string' ? name : ''}">${name}${aqi ? ` <span class="text-gray-400 text-xs ml-2">AQI ${aqi}</span>` : ''}</div>`;
        })
        .join('');

      autocompleteDD.classList.remove('hidden');
      cityInput.setAttribute('aria-expanded', 'true');

      // click handler per item
      autocompleteDD.querySelectorAll('.autocomplete-item').forEach(item => {
        item.addEventListener('click', () => {
          cityInput.value = item.dataset.name || item.textContent.trim();
          autocompleteDD.classList.add('hidden');
          cityInput.setAttribute('aria-expanded', 'false');
          cityInput.focus();
        });
      });
    } catch (err) {
      searchSpinner.classList.add('hidden');
      cityInput.setAttribute('aria-expanded', 'false');
      if (err.name !== 'AbortError') console.error(err);
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  GEOLOCATION
  // ═══════════════════════════════════════════════════════════════════

  function handleGeolocation() {
    if (!navigator.geolocation) {
      showToast('Geolocation is not supported by your browser.', 'error');
      return;
    }
    btnGeo.disabled = true;
    btnGeo.querySelector('span').textContent = 'Locating…';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        cityInput.value = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;
        cityInput.dataset.lat = pos.coords.latitude;
        cityInput.dataset.lng = pos.coords.longitude;
        btnGeo.disabled = false;
        btnGeo.querySelector('span').textContent = 'Use My Location';
        showToast('Location detected!', 'success');
        fetchAqi(); // auto-fetch
      },
      (err) => {
        btnGeo.disabled = false;
        btnGeo.querySelector('span').textContent = 'Use My Location';
        showToast('Could not get your location. Please allow permission.', 'error');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  //  FETCH AQI
  // ═══════════════════════════════════════════════════════════════════

  async function fetchAqi() {
    const val = cityInput.value.trim();
    if (!val) { showToast('Please enter a city or use your location.', 'error'); return; }

    // show loading state on button
    btnCheckAqi.disabled = true;
    aqiBtnSpinner.classList.remove('hidden');

    let body;
    if (cityInput.dataset.lat && cityInput.dataset.lng) {
      body = { lat: parseFloat(cityInput.dataset.lat), lng: parseFloat(cityInput.dataset.lng) };
      // clear coords so next manual text entry uses city
      delete cityInput.dataset.lat;
      delete cityInput.dataset.lng;
    } else {
      body = { city: val };
    }

    try {
      const res  = await fetch('/api/air-quality', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const json = await res.json();

      if (json.status !== 'ok') throw new Error(json.error || 'Failed to fetch air quality data.');

      currentAqiData  = json.data;
      currentCategory = json.data.category;
      renderDashboard(json.data, json.data.category);
      showToast(`Air quality loaded for ${json.data.city || json.data.station_name}`, 'success');
    } catch (err) {
      showToast(err.message || 'Network error. Please try again.', 'error');
    } finally {
      btnCheckAqi.disabled = false;
      aqiBtnSpinner.classList.add('hidden');
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  RENDER AQI DASHBOARD
  // ═══════════════════════════════════════════════════════════════════

  function renderDashboard(data, category) {
    // --- AQI Gauge ---
    const aqi       = data.aqi ?? 0;
    const color     = category?.color || getAqiColor(aqi);
    const circumf   = 2 * Math.PI * 85; // 534.07
    const fraction  = Math.min(aqi / 500, 1);
    const offset    = circumf * (1 - fraction);

    const ring = $('#aqi-ring');
    ring.setAttribute('stroke', color);
    ring.setAttribute('stroke-dashoffset', offset);

    const aqiValue = $('#aqi-value');
    aqiValue.setAttribute('fill', color);
    aqiValue.classList.add('aqi-pulse');
    animateNumber(aqiValue, aqi);

    // --- Badge ---
    const badge = $('#aqi-badge');
    badge.textContent = category?.level || '—';
    badge.className   = `inline-block px-4 py-1.5 rounded-full text-sm font-semibold mb-3 badge ${getBadgeClass(color)}`;

    // --- Station & time ---
    $('#station-name').textContent = data.station_name || data.city || '';
    $('#aqi-time').textContent     = data.time_updated ? `Updated ${formatDate(data.time_updated)}` : '';

    // --- Health message ---
    $('#health-message').textContent = category?.health_message || '';

    // --- Dominant pollutant ---
    $('#dominant-pollutant').textContent = POLLUTANT_LABELS[data.dominant_pollutant] || data.dominant_pollutant || '—';

    // --- Pollutant cards ---
    renderPollutants(data.pollutants, data.dominant_pollutant);

    // Show sections
    revealSection(aqiDashboard);
    setTimeout(() => revealSection(profileSection), 300);
  }

  // ═══════════════════════════════════════════════════════════════════
  //  POLLUTANT CHARTS (Chart.js)
  // ═══════════════════════════════════════════════════════════════════

  function renderPollutants(pollutants, dominant) {
    // Destroy previous chart instances
    Object.values(pollutantCharts).forEach(c => c.destroy());
    pollutantCharts = {};

    if (!pollutants) return;

    $$('.pollutant-card').forEach(card => {
      const key   = card.dataset.pollutant;
      const val   = pollutants[key] ?? 0;
      const safe  = SAFE_LIMITS[key] ?? 50;

      // Update value text
      card.querySelector('.pollutant-value').textContent = val === null || val === undefined ? '—' : val;

      // Dominant highlight
      card.classList.toggle('dominant', key === dominant);

      // Chart
      const canvas = card.querySelector('.pollutant-chart');
      const ctx    = canvas.getContext('2d');
      const ratio  = val / safe;
      const barColor = ratio <= 1 ? '#10b981' : ratio <= 2 ? '#f59e0b' : '#ef4444';

      pollutantCharts[key] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Value', 'Safe Limit'],
          datasets: [{
            data: [val, safe],
            backgroundColor: [barColor, 'rgba(255,255,255,0.08)'],
            borderRadius: 4,
            barThickness: 18
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: 0 },
          plugins: { legend: { display: false }, tooltip: { enabled: true } },
          scales: {
            x: {
              display: false,
              beginAtZero: true,
              max: Math.max(val, safe) * 1.2 || 1
            },
            y: {
              display: true,
              ticks: { color: '#6b7280', font: { size: 10 } },
              grid: { display: false }
            }
          }
        }
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  //  PROFILE SELECTION
  // ═══════════════════════════════════════════════════════════════════

  function initProfileSelection() {
    $$('.profile-card').forEach(card => {
      const selectCard = () => {
        // deselect others
        $$('.profile-card').forEach(c => {
          c.classList.remove('selected');
          c.setAttribute('aria-checked', 'false');
        });
        card.classList.add('selected');
        card.setAttribute('aria-checked', 'true');
        selectedProfile = card.dataset.profile;
        btnGetRecs.disabled = false;
      };

      card.addEventListener('click', selectCard);
      card.addEventListener('keydown', (e) => {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          selectCard();
        }
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  //  FETCH & RENDER RECOMMENDATIONS
  // ═══════════════════════════════════════════════════════════════════

  async function fetchRecommendations() {
    if (!selectedProfile || !currentAqiData) return;

    // Show section + loading
    recSection.classList.remove('hidden');
    recSection.classList.add('visible');
    recLoading.classList.remove('hidden');
    recContent.classList.add('hidden');
    btnGetRecs.disabled = true;
    recBtnSpinner.classList.remove('hidden');
    recSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    const body = {
      aqi_data: currentAqiData,
      user_profile: {
        type: selectedProfile,
        details: $('#user-details').value.trim()
      }
    };

    try {
      const res  = await fetch('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const json = await res.json();
      if (json.status !== 'ok') throw new Error(json.error || 'Failed to get recommendations.');

      renderRecommendations(json.data);
      showToast('Recommendations generated!', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to generate recommendations.', 'error');
    } finally {
      recLoading.classList.add('hidden');
      recContent.classList.remove('hidden');
      btnGetRecs.disabled = false;
      recBtnSpinner.classList.add('hidden');
    }
  }

  function renderRecommendations(rec) {
    // --- Summary + Risk Badge ---
    const riskColors = {
      low:       'badge-green',
      moderate:  'badge-yellow',
      high:      'badge-orange',
      very_high: 'badge-red',
      hazardous: 'badge-maroon'
    };
    const riskBadge = $('#rec-risk-badge');
    riskBadge.textContent = (rec.health_risk_level || 'unknown').replace(/_/g, ' ');
    riskBadge.className   = `inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider self-start badge ${riskColors[rec.health_risk_level] || 'badge-green'}`;
    $('#rec-aqi-summary').textContent = rec.aqi_summary || '';

    // --- Immediate Actions ---
    const actionsList = $('#rec-actions-list');
    actionsList.innerHTML = (rec.immediate_actions || [])
      .map(a => `<li class="flex items-start gap-2"><span class="text-amber-400 mt-0.5">▸</span><span>${a}</span></li>`)
      .join('');

    // --- Outdoor Windows ---
    $('#rec-outdoor-text').textContent = rec.outdoor_activity_windows || 'No data available.';

    // --- Tabbed Content ---
    renderRoutines(rec.low_emission_routines);
    renderIndoor(rec.indoor_air_quality_hacks);
    renderSustainable(rec.sustainable_alternatives);

    // --- Wellness Tips ---
    const tipsList = $('#wellness-tips-list');
    tipsList.innerHTML = (rec.weekly_wellness_tips || [])
      .map(t => `
        <div class="wellness-tip">
          <div class="wellness-tip-check">✓</div>
          <span class="text-sm text-gray-300">${t}</span>
        </div>
      `).join('');
  }

  function renderRoutines(items) {
    const grid = $('#routines-grid');
    grid.innerHTML = (items || []).map(item => {
      const timeColor = {
        morning: 'badge-yellow', afternoon: 'badge-orange',
        evening: 'badge-purple', all_day: 'badge-sky'
      };
      return `
        <div class="rec-card">
          <div class="flex items-start gap-3 mb-2">
            <span class="text-2xl">${item.icon || '🏃'}</span>
            <div class="flex-1">
              <h4 class="font-semibold text-sm">${item.title}</h4>
              <span class="badge ${timeColor[item.time_of_day] || 'badge-sky'} mt-1">${(item.time_of_day || '').replace(/_/g, ' ')}</span>
            </div>
          </div>
          <p class="text-xs text-gray-400 leading-relaxed mb-2">${item.description}</p>
          <p class="text-xs text-emerald-400/80"><strong>Impact:</strong> ${item.impact}</p>
        </div>`;
    }).join('');
  }

  function renderIndoor(items) {
    const grid = $('#indoor-grid');
    const effColor = { High: 'badge-green', Medium: 'badge-yellow', Low: 'badge-orange' };
    const costColor = { Free: 'badge-green', Low: 'badge-green', Medium: 'badge-yellow', High: 'badge-red' };

    grid.innerHTML = (items || []).map(item => `
      <div class="rec-card">
        <div class="flex items-start gap-3 mb-2">
          <span class="text-2xl">${item.icon || '🏠'}</span>
          <div class="flex-1">
            <h4 class="font-semibold text-sm">${item.title}</h4>
            <div class="flex gap-2 mt-1">
              <span class="badge ${effColor[item.effectiveness] || 'badge-green'}">${item.effectiveness}</span>
              <span class="badge ${costColor[item.cost] || 'badge-yellow'}">${item.cost}</span>
            </div>
          </div>
        </div>
        <p class="text-xs text-gray-400 leading-relaxed">${item.description}</p>
      </div>`
    ).join('');
  }

  function renderSustainable(items) {
    const grid = $('#sustainable-grid');
    grid.innerHTML = (items || []).map(item => `
      <div class="rec-card">
        <div class="flex items-start gap-3 mb-3">
          <span class="text-2xl">${item.icon || '🌱'}</span>
          <h4 class="font-semibold text-sm flex-1">${item.title}</h4>
        </div>
        <div class="flex items-center gap-2 text-xs mb-2">
          <span class="bg-red-500/10 text-red-400 px-2 py-0.5 rounded">${item.current_practice}</span>
          <span class="text-gray-500">→</span>
          <span class="bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded">${item.alternative}</span>
        </div>
        <p class="text-xs text-gray-400 leading-relaxed">${item.environmental_impact}</p>
      </div>`
    ).join('');
  }

  // ═══════════════════════════════════════════════════════════════════
  //  TAB SWITCHING
  // ═══════════════════════════════════════════════════════════════════

  function initTabs() {
    $$('.rec-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        $$('.rec-tab').forEach(t => {
          t.classList.remove('active');
          t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        $$('.tab-panel').forEach(p => p.classList.add('hidden'));
        $(`#tab-${tab.dataset.tab}`).classList.remove('hidden');
      });
    });
  }

  // ═══════════════════════════════════════════════════════════════════
  //  EVENT BINDINGS
  // ═══════════════════════════════════════════════════════════════════

  function init() {
    // Section reveal on scroll
    initSectionObserver();
    // Make the search section visible immediately
    $('#search-section').classList.add('visible');

    // Autocomplete (debounced 300ms)
    cityInput.addEventListener('input', debounce(() => {
      // clear lat/lng when user types manually
      delete cityInput.dataset.lat;
      delete cityInput.dataset.lng;
      searchStations(cityInput.value.trim());
    }, 300));

    // Hide dropdown on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#city-input') && !e.target.closest('#autocomplete-dropdown')) {
        autocompleteDD.classList.add('hidden');
      }
    });

    // Enter key on input
    cityInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { autocompleteDD.classList.add('hidden'); fetchAqi(); }
    });

    // Buttons
    btnGeo.addEventListener('click', handleGeolocation);
    btnCheckAqi.addEventListener('click', fetchAqi);
    btnGetRecs.addEventListener('click', fetchRecommendations);

    // Profile selection
    initProfileSelection();

    // Tabs
    initTabs();
  }

  // Boot
  document.addEventListener('DOMContentLoaded', init);
})();
