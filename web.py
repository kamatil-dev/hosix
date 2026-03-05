from flask import Flask, render_template_string, request, jsonify
import threading
import json
import os
import re
import socket
from datetime import date, timedelta, datetime

import script as _script_mod
from script import MENU_CONFIG, parse_ddmmyyyy_strict, run_job, fetch_patients_without_bilans

app = Flask(__name__)

# ──────────────────────────────────────────────
# Job history (last 10 jobs, persisted to disk)
# ──────────────────────────────────────────────
_jobs = []
_jobs_lock = threading.Lock()
_JOB_HISTORY_FILE = "jobs.json"


def _load_jobs():
    global _jobs
    if os.path.exists(_JOB_HISTORY_FILE):
        try:
            with open(_JOB_HISTORY_FILE, "r", encoding="utf-8") as fh:
                _jobs = json.load(fh)
        except Exception as exc:
            print(f"[WARNING] Could not load job history: {exc}")
            _jobs = []


def _save_jobs():
    try:
        with open(_JOB_HISTORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(_jobs[-10:], fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"[WARNING] Could not save job history: {exc}")


def _add_job(job):
    with _jobs_lock:
        _jobs.append(job)
        if len(_jobs) > 10:
            _jobs.pop(0)
        _save_jobs()


def _update_job(job_id, status, error=None):
    with _jobs_lock:
        for job in _jobs:
            if job["id"] == job_id:
                job["status"] = status
                if error is not None:
                    job["error"] = error
                break
        _save_jobs()


# ──────────────────────────────────────────────
# HTML template
# ──────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HOSIX — Impression automatique</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #333; }
  header { background: #1a73e8; color: #fff; padding: 14px 24px; display: flex; align-items: center; gap: 12px; box-shadow: 0 2px 4px rgba(0,0,0,.2); }
  header h1 { font-size: 1.3rem; font-weight: 600; }
  .container { max-width: 960px; margin: 24px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.1); padding: 24px; margin-bottom: 24px; }
  .card h2 { font-size: 1.05rem; font-weight: 600; color: #1a73e8; border-bottom: 2px solid #e8f0fe; padding-bottom: 8px; margin-bottom: 16px; }
  label { display: block; font-weight: 500; margin-bottom: 4px; margin-top: 14px; }
  input[type=text], input[type=password], textarea { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: .95rem; }
  textarea { resize: vertical; min-height: 60px; }
  .row { display: flex; gap: 16px; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 220px; }
  .choice-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
  .choice-group label { font-weight: normal; display: flex; align-items: center; gap: 6px;
      cursor: pointer; background: #f8f9fa; border: 1px solid #ddd; border-radius: 4px;
      padding: 6px 12px; transition: background .15s, border-color .15s; }
  .choice-group label:hover { background: #e8f0fe; border-color: #1a73e8; }
  .choice-group input { margin: 0; }
  .hidden { display: none; }
  .btn { background: #1a73e8; color: #fff; border: none; padding: 10px 28px;
      border-radius: 4px; font-size: 1rem; cursor: pointer; font-weight: 500; transition: background .15s; }
  .btn:hover { background: #1557b0; }
  .btn:disabled { background: #aaa; cursor: not-allowed; }
  .link-btn { font-size: .82rem; color: #1a73e8; cursor: pointer; background: none;
      border: none; text-decoration: underline; padding: 0; margin-left: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  th { background: #f8f9fa; padding: 10px 8px; text-align: left; font-weight: 600; border-bottom: 2px solid #dee2e6; }
  td { padding: 9px 8px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px;
      border-radius: 12px; font-size: .78rem; font-weight: 600; }
  .badge-running  { background: #fff3cd; color: #856404; }
  .badge-completed{ background: #d1e7dd; color: #0f5132; }
  .badge-failed   { background: #f8d7da; color: #842029; }
  .err-text { color: #842029; font-size: .78rem; margin-top: 3px; }
  .spinner { width: 11px; height: 11px; border: 2px solid #856404; border-top-color: transparent;
      border-radius: 50%; animation: spin .7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }
  #toast { position: fixed; bottom: 24px; right: 24px; background: #333; color: #fff;
      padding: 12px 20px; border-radius: 6px; display: none; z-index: 999; max-width: 300px; }
  .ipp-cell { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .fetch-wrap { position: relative; display: inline-block; }
  .fetch-btn { background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 2px 6px;
      border-radius: 4px; vertical-align: middle; color: #1a73e8; transition: background .15s; }
  .fetch-btn:hover { background: #e8f0fe; }
  .fetch-btn:disabled { color: #aaa; cursor: not-allowed; }
  .fetch-btn .search-icon { display: inline; }
  .fetch-btn .fetch-spinner { display: none; width: 14px; height: 14px; border: 2px solid #1a73e8;
      border-top-color: transparent; border-radius: 50%; animation: spin .7s linear infinite; vertical-align: middle; }
  .fetch-btn.loading .search-icon { display: none; }
  .fetch-btn.loading .list-icon { display: none; }
  .fetch-btn.loading .fetch-spinner { display: inline-block; }
  .fetch-menu { display: none; position: absolute; left: 0; top: 100%; background: #fff; border: 1px solid #ddd;
      border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.15); z-index: 50; min-width: 260px; padding: 4px 0; }
  .fetch-menu.open { display: block; }
  .fetch-menu button { display: block; width: 100%; text-align: left; padding: 8px 14px; border: none;
      background: none; cursor: pointer; font-size: .88rem; color: #333; }
  .fetch-menu button:hover { background: #e8f0fe; }
  .run-wrap { position: relative; display: inline-block; }
  .headless-popover { display: none; position: absolute; bottom: calc(100% + 8px); left: 0;
      background: #fff; border: 1px solid #ddd; border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0,0,0,.15); z-index: 50; padding: 10px 14px; white-space: nowrap; }
  .headless-popover.open { display: block; }
  .headless-popover p { font-size: .82rem; color: #666; margin-bottom: 8px; }
  .headless-popover .headless-btn { background: #e8f0fe; color: #1a73e8; border: 1px solid #1a73e8;
      border-radius: 4px; padding: 6px 14px; cursor: pointer; font-size: .88rem; font-weight: 500; }
  .headless-popover .headless-btn:hover { background: #d2e3fc; }
  /* Patient modal */
  .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 200;
      align-items: center; justify-content: center; }
  .modal-overlay.open { display: flex; }
  .modal-box { background: #fff; border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,.2);
      max-width: 700px; width: 96%; max-height: 80vh; display: flex; flex-direction: column; }
  .modal-header { padding: 16px 20px; border-bottom: 1px solid #eee; display: flex;
      align-items: center; justify-content: space-between; }
  .modal-header h3 { font-size: 1rem; font-weight: 600; color: #1a73e8; }
  .modal-close { background: none; border: none; font-size: 1.4rem; cursor: pointer;
      color: #666; line-height: 1; padding: 0 4px; }
  .modal-close:hover { color: #333; }
  .modal-body { overflow-y: auto; flex: 1; padding: 8px 0; }
  .modal-body table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  .modal-body th { background: #f8f9fa; padding: 9px 10px; text-align: left; font-weight: 600;
      border-bottom: 2px solid #dee2e6; position: sticky; top: 0; }
  .modal-body td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
  .modal-body tr:last-child td { border-bottom: none; }
  .modal-body tr.has-bilan td { color: #aaa; }
  .modal-footer { padding: 12px 20px; border-top: 1px solid #eee; display: flex;
      align-items: center; justify-content: space-between; gap: 10px; }
  .modal-footer small { color: #666; font-size: .82rem; }
  .modal-sel-all { background: none; border: none; color: #1a73e8; font-size: .82rem;
      cursor: pointer; text-decoration: underline; padding: 0; }
</style>
</head>
<body>
<header>
  <svg width="26" height="26" viewBox="0 0 24 24" fill="white">
    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z"/>
  </svg>
  <h1>HOSIX — Système d'impression automatique</h1>
</header>

<div class="container">

  <!-- ── New Job Form ── -->
  <div class="card">
    <h2>Nouveau travail</h2>
    <form id="jobForm">

      <div class="row">
        <div>
          <label>Liste des IPP <small style="font-weight:normal;">(séparés par virgules)</small>
            <span class="fetch-wrap">
              <button type="button" class="fetch-btn" id="fetchToggle" title="Récupérer les patients sans bilans" aria-label="Récupérer les patients sans bilans"><svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span class="fetch-spinner"></span></button>
              <div class="fetch-menu" id="fetchMenu">
                <button type="button" onclick="fetchPatients('today')">Patients sans bilans aujourd'hui</button>
                <button type="button" onclick="fetchPatients('yesterday')">Patients sans bilans hier</button>
              </div>
            </span>
            <span class="fetch-wrap" style="margin-left:4px;">
              <button type="button" class="fetch-btn" id="listToggle" title="Lister tous les patients" aria-label="Lister tous les patients"><svg class="list-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg><span class="fetch-spinner"></span></button>
              <div class="fetch-menu" id="listMenu">
                <button type="button" onclick="listAllPatients('today')">Tous les patients aujourd'hui</button>
                <button type="button" onclick="listAllPatients('yesterday')">Tous les patients hier</button>
              </div>
            </span>
          </label>
          <textarea name="ipp_list" placeholder="ex : 123456, 789012, 345678" required></textarea>
        </div>
        <div>
          <label>Identifiants SIH</label>
          <input type="text"     name="username" placeholder="Nom d'utilisateur" value="{{ default_username }}">
          <input type="password" name="password" placeholder="Mot de passe" style="margin-top:8px">
        </div>
      </div>

      <div class="row">
        <div>
          <label>Date de rendez-vous</label>
          <div class="choice-group" id="dateGroup">
            <label><input type="radio" name="date_choice" value="today"    checked> Aujourd'hui ({{ today }})</label>
            <label><input type="radio" name="date_choice" value="tomorrow">         Demain ({{ tomorrow }})</label>
            <label><input type="radio" name="date_choice" value="custom">           Personnalisé</label>
          </div>
          <div id="customDateWrap" class="hidden" style="margin-top:8px;">
            <input type="text" name="custom_date" placeholder="jj/mm/aaaa">
          </div>
        </div>

        <div>
          <label>Heure de rendez-vous</label>
          <div class="choice-group" id="timeGroup">
            <label><input type="radio" name="time_choice" value="now"    checked> Maintenant</label>
            <label><input type="radio" name="time_choice" value="06:00">          06:00</label>
            <label><input type="radio" name="time_choice" value="08:00">          08:00</label>
            <label><input type="radio" name="time_choice" value="09:00">          09:00</label>
            <label><input type="radio" name="time_choice" value="custom">         Personnalisé</label>
          </div>
          <div id="customTimeWrap" class="hidden" style="margin-top:8px;">
            <input type="text" name="custom_time" placeholder="HH:MM">
          </div>
        </div>
      </div>

      <label>
        Analyses
        <button type="button" class="link-btn" id="toggleAll">Tout désélectionner</button>
      </label>
      <div class="choice-group" id="bookingGroup">
        {% for item in menu_items %}
        <label><input type="checkbox" name="bookings" value="{{ item }}" checked> {{ item }}</label>
        {% endfor %}
      </div>

      <div style="margin-top:20px;" class="run-wrap" id="runWrap">
        <button type="submit" class="btn" id="submitBtn">▶ Lancer le travail</button>
        <div class="headless-popover" id="headlessPopover">
          <p>Mode navigateur</p>
          <button type="button" class="headless-btn" id="headlessToggleBtn"></button>
        </div>
      </div>
    </form>
  </div>

  <!-- ── Job History ── -->
  <div class="card">
    <h2>
      Derniers travaux <small style="font-weight:normal; color:#666;">(10 derniers)</small>
      <button type="button" class="link-btn" style="float:right" onclick="loadJobs()">↻ Actualiser</button>
    </h2>
    <table>
      <thead>
        <tr><th>Horodatage</th><th>IPP(s)</th><th>Date RDV</th><th>Analyses</th><th>Utilisateur</th><th>Statut</th></tr>
      </thead>
      <tbody id="jobsBody">
        {% if not jobs %}
        <tr><td colspan="6" style="text-align:center;color:#999;padding:20px;">Aucun travail enregistré</td></tr>
        {% endif %}
        {% for job in jobs %}
        <tr>
          <td style="white-space:nowrap;">{{ job.timestamp }}</td>
          <td class="ipp-cell" title="{{ job.ipp_list | join(', ') }}">{{ job.ipp_list | join(', ') }}</td>
          <td style="white-space:nowrap;">{{ job.date }} {{ job.time[:5] }}</td>
          <td>{{ job.bookings | join(', ') }}</td>
          <td>{{ job.username }}</td>
          <td>
            {% if job.status == 'running' %}
              <span class="badge badge-running"><span class="spinner"></span>En cours</span>
            {% elif job.status == 'completed' %}
              <span class="badge badge-completed">✓ Terminé</span>
            {% else %}
              <span class="badge badge-failed">✗ Erreur</span>
              {% if job.error %}<div class="err-text">{{ job.error[:120] }}</div>{% endif %}
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

</div><!-- /container -->

<!-- ── Patient selection modal ── -->
<div class="modal-overlay" id="patientModal" role="dialog" aria-modal="true" aria-labelledby="patientModalTitle">
  <div class="modal-box">
    <div class="modal-header">
      <h3 id="patientModalTitle">Sélectionner les patients</h3>
      <button type="button" class="modal-close" id="patientModalClose" aria-label="Fermer">&times;</button>
    </div>
    <div class="modal-body">
      <table id="patientTable">
        <thead>
          <tr>
            <th style="width:36px;"><input type="checkbox" id="modalSelectAll" title="Tout sélectionner/désélectionner"></th>
            <th>IPP</th>
            <th>Nom complet</th>
            <th>Bilan existant</th>
          </tr>
        </thead>
        <tbody id="patientTableBody"></tbody>
      </table>
    </div>
    <div class="modal-footer">
      <small id="patientModalCount"></small>
      <button type="button" class="btn" id="patientModalConfirm">✓ Confirmer la sélection</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
// ── Custom date/time visibility ──
document.querySelectorAll('input[name="date_choice"]').forEach(r =>
  r.addEventListener('change', () => {
    document.getElementById('customDateWrap').classList.toggle('hidden', r.value !== 'custom' || !r.checked);
  })
);
document.querySelectorAll('input[name="time_choice"]').forEach(r =>
  r.addEventListener('change', () => {
    document.getElementById('customTimeWrap').classList.toggle('hidden', r.value !== 'custom' || !r.checked);
  })
);

// ── Toggle all bookings ──
let allOn = true;
document.getElementById('toggleAll').addEventListener('click', () => {
  allOn = !allOn;
  document.querySelectorAll('input[name="bookings"]').forEach(cb => cb.checked = allOn);
  document.getElementById('toggleAll').textContent = allOn ? 'Tout désélectionner' : 'Tout sélectionner';
});

// ── Toast helper ──
function showToast(msg, ms) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', ms || 3000);
}

// ── Render status badge ──
function renderBadge(job) {
  if (job.status === 'running')
    return '<span class="badge badge-running"><span class="spinner"></span>En cours</span>';
  if (job.status === 'completed')
    return '<span class="badge badge-completed">&#10003; Terminé</span>';
  let h = '<span class="badge badge-failed">&#10007; Erreur</span>';
  if (job.error) h += '<div class="err-text">' + job.error.substring(0, 120) + '</div>';
  return h;
}

// ── Load & render job list ──
function loadJobs() {
  fetch('/jobs')
    .then(r => r.json())
    .then(jobs => {
      const tbody = document.getElementById('jobsBody');
      if (!jobs.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;padding:20px;">Aucun travail enregistré</td></tr>';
        return;
      }
      tbody.innerHTML = jobs.map(j => `
        <tr>
          <td style="white-space:nowrap;">${j.timestamp}</td>
          <td class="ipp-cell" title="${j.ipp_list.join(', ')}">${j.ipp_list.join(', ')}</td>
          <td style="white-space:nowrap;">${j.date} ${j.time.substring(0,5)}</td>
          <td>${j.bookings.join(', ')}</td>
          <td>${j.username || ''}</td>
          <td>${renderBadge(j)}</td>
        </tr>`).join('');
    })
    .catch(() => {});
}

// ── Auto-refresh every 5 s ──
(function poll() { loadJobs(); setTimeout(poll, 5000); })();

// ── Form submission ──
document.getElementById('jobForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = 'Démarrage…';

  fetch('/run', { method: 'POST', body: new FormData(this) })
    .then(r => r.json())
    .then(res => {
      if (res.error) {
        showToast('Erreur : ' + res.error, 6000);
      } else {
        showToast('Travail démarré !');
        loadJobs();
      }
    })
    .catch(() => showToast('Erreur réseau', 5000))
    .finally(() => {
      btn.disabled = false;
      btn.textContent = '▶ Lancer le travail';
    });
});

// ── Fetch patients without bilans ──
const fetchToggle = document.getElementById('fetchToggle');
const fetchMenu = document.getElementById('fetchMenu');

fetchToggle.addEventListener('click', function(e) {
  e.preventDefault();
  listMenu.classList.remove('open');
  fetchMenu.classList.toggle('open');
});

document.addEventListener('click', function(e) {
  if (!fetchToggle.contains(e.target) && !fetchMenu.contains(e.target)) {
    fetchMenu.classList.remove('open');
  }
});

function fetchPatients(filter) {
  fetchMenu.classList.remove('open');
  const username = document.querySelector('input[name="username"]').value.trim();
  const password = document.querySelector('input[name="password"]').value;
  if (!username || !password) {
    showToast('Veuillez saisir vos identifiants SIH.', 4000);
    return;
  }
  const btn = fetchToggle;
  btn.disabled = true;
  btn.classList.add('loading');
  showToast('Récupération des patients en cours…', 5000);

  const fd = new FormData();
  fd.append('username', username);
  fd.append('password', password);
  fd.append('filter', filter);
  // Pass selected bookings so the server knows which bilan codes to check
  document.querySelectorAll('input[name="bookings"]:checked').forEach(cb => fd.append('bookings', cb.value));

  fetch('/fetch-patients', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(res => {
      if (res.error) {
        showToast('Erreur : ' + res.error, 6000);
      } else if (res.patients && res.patients.length) {
        showPatientModal(res.patients);
      } else {
        showToast('Aucun patient trouvé.', 4000);
      }
    })
    .catch(() => showToast('Impossible de contacter le serveur. Vérifiez votre connexion.', 5000))
    .finally(() => { btn.disabled = false; btn.classList.remove('loading'); });
}

// ── List all patients ──
const listToggle = document.getElementById('listToggle');
const listMenu = document.getElementById('listMenu');

listToggle.addEventListener('click', function(e) {
  e.preventDefault();
  fetchMenu.classList.remove('open');
  listMenu.classList.toggle('open');
});

document.addEventListener('click', function(e) {
  if (!listToggle.contains(e.target) && !listMenu.contains(e.target)) {
    listMenu.classList.remove('open');
  }
});

function listAllPatients(filter) {
  listMenu.classList.remove('open');
  const username = document.querySelector('input[name="username"]').value.trim();
  const password = document.querySelector('input[name="password"]').value;
  if (!username || !password) {
    showToast('Veuillez saisir vos identifiants SIH.', 4000);
    return;
  }
  const btn = listToggle;
  btn.disabled = true;
  btn.classList.add('loading');
  showToast('Récupération des patients en cours…', 5000);

  const fd = new FormData();
  fd.append('username', username);
  fd.append('password', password);
  fd.append('filter', filter);
  document.querySelectorAll('input[name="bookings"]:checked').forEach(cb => fd.append('bookings', cb.value));

  fetch('/fetch-patients', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(res => {
      if (res.error) {
        showToast('Erreur : ' + res.error, 6000);
      } else if (res.patients && res.patients.length) {
        showPatientModal(res.patients, true /* showAll: all patients selectable */);
      } else {
        showToast('Aucun patient trouvé.', 4000);
      }
    })
    .catch(() => showToast('Impossible de contacter le serveur. Vérifiez votre connexion.', 5000))
    .finally(() => { btn.disabled = false; btn.classList.remove('loading'); });
}

// ── Patient selection modal ──
(function() {
  const overlay = document.getElementById('patientModal');
  const closeBtn = document.getElementById('patientModalClose');
  const confirmBtn = document.getElementById('patientModalConfirm');
  const tbody = document.getElementById('patientTableBody');
  const countEl = document.getElementById('patientModalCount');
  const selectAllCb = document.getElementById('modalSelectAll');

  function updateCount() {
    const total = tbody.querySelectorAll('input[type="checkbox"]').length;
    const checked = tbody.querySelectorAll('input[type="checkbox"]:checked').length;
    countEl.textContent = checked + ' / ' + total + ' patient(s) sélectionné(s)';
    selectAllCb.checked = total > 0 && checked === total;
    selectAllCb.indeterminate = checked > 0 && checked < total;
  }

  window.showPatientModal = function(patients, showAll) {
    tbody.innerHTML = '';
    patients.forEach(function(p, idx) {
      const hasBilan = p.has_bilan;
      const checked = showAll ? false : !hasBilan;
      const tr = document.createElement('tr');
      tr.dataset.ip = p.ip;
      if (!showAll && hasBilan) tr.classList.add('has-bilan');
      tr.innerHTML =
        '<td><input type="checkbox" id="pmcb' + idx + '" aria-label="Sélectionner le patient ' + escHtml(p.ip) + '"' + (checked ? ' checked' : '') + '></td>' +
        '<td>' + escHtml(p.ip) + '</td>' +
        '<td>' + escHtml(p.name || '—') + '</td>' +
        '<td>' + (hasBilan
          ? '<span style="color:#856404;">✓ Bilan présent</span>'
          : '<span style="color:#0f5132;">✗ Pas de bilan</span>') + '</td>';
      tr.querySelector('input[type="checkbox"]').addEventListener('change', updateCount);
      tbody.appendChild(tr);
    });
    updateCount();
    overlay.classList.add('open');
  };

  selectAllCb.addEventListener('change', function() {
    tbody.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = selectAllCb.checked);
    updateCount();
  });

  function closeModal() { overlay.classList.remove('open'); }
  closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', function(e) { if (e.target === overlay) closeModal(); });
  document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeModal(); });

  confirmBtn.addEventListener('click', function() {
    const ips = [];
    tbody.querySelectorAll('tr').forEach(function(tr) {
      const cb = tr.querySelector('input[type="checkbox"]');
      if (cb && cb.checked && tr.dataset.ip) ips.push(tr.dataset.ip);
    });
    if (ips.length) {
      document.querySelector('textarea[name="ipp_list"]').value = ips.join(', ');
      showToast(ips.length + ' patient(s) ajouté(s).', 3000);
    } else {
      showToast('Aucun patient sélectionné.', 3000);
    }
    closeModal();
  });
})();

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Headless popover on long hover ──
(function() {
  const runWrap = document.getElementById('runWrap');
  const popover = document.getElementById('headlessPopover');
  const toggleBtn = document.getElementById('headlessToggleBtn');
  let hoverTimer = null;
  let closeTimer = null;
  let headless = {{ headless|tojson }};

  function updateBtn() {
    const label = headless ? '👁 Afficher le navigateur' : '🙈 Masquer le navigateur';
    toggleBtn.textContent = label;
    toggleBtn.setAttribute('aria-label', headless ? 'Afficher le navigateur (désactiver le mode headless)' : 'Masquer le navigateur (activer le mode headless)');
  }
  updateBtn();

  runWrap.addEventListener('mouseenter', function() {
    clearTimeout(closeTimer);
    hoverTimer = setTimeout(function() { popover.classList.add('open'); }, 1500);
  });
  runWrap.addEventListener('mouseleave', function() {
    clearTimeout(hoverTimer);
    closeTimer = setTimeout(function() { popover.classList.remove('open'); }, 200);
  });
  popover.addEventListener('mouseenter', function() { clearTimeout(closeTimer); });
  popover.addEventListener('mouseleave', function() {
    closeTimer = setTimeout(function() { popover.classList.remove('open'); }, 200);
  });

  document.addEventListener('click', function(e) {
    if (!runWrap.contains(e.target)) { popover.classList.remove('open'); }
  });

  toggleBtn.addEventListener('click', function() {
    fetch('/toggle-headless', { method: 'POST' })
      .then(r => r.json())
      .then(res => {
        headless = res.headless;
        updateBtn();
        showToast(res.headless ? 'Mode headless activé — navigateur masqué.' : 'Mode headless désactivé — le navigateur sera visible.');
        popover.classList.remove('open');
      })
      .catch(() => showToast('Erreur lors du changement de mode.', 4000));
  });
})();
</script>
</body>
</html>
"""


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@app.route("/")
def index():
    with _jobs_lock:
        recent = list(reversed(_jobs[-10:]))
    today = date.today()
    return render_template_string(
        _HTML,
        jobs=recent,
        menu_items=list(MENU_CONFIG.keys()),
        today=today.strftime("%d/%m/%Y"),
        tomorrow=(today + timedelta(days=1)).strftime("%d/%m/%Y"),
        default_username="",
        headless=_script_mod.HEADLESS,
    )


@app.route("/run", methods=["POST"])
def run_endpoint():
    # ── Collect form values ──
    ipp_raw        = request.form.get("ipp_list", "").strip()
    date_choice    = request.form.get("date_choice", "today")
    custom_date    = request.form.get("custom_date", "").strip()
    time_choice    = request.form.get("time_choice", "now")
    custom_time    = request.form.get("custom_time", "").strip()
    username       = request.form.get("username", "").strip()
    password       = request.form.get("password", "")
    sel_bookings   = request.form.getlist("bookings")

    if not username:
        return jsonify({"error": "Nom d'utilisateur requis."}), 400
    if not password:
        return jsonify({"error": "Mot de passe requis."}), 400

    # ── Resolve date ──
    today = date.today()
    if date_choice == "today":
        selected_date = today.strftime("%d/%m/%Y")
    elif date_choice == "tomorrow":
        selected_date = (today + timedelta(days=1)).strftime("%d/%m/%Y")
    else:
        try:
            parse_ddmmyyyy_strict(custom_date)
            selected_date = custom_date
        except Exception:
            return jsonify({"error": "Format de date invalide. Utilisez jj/mm/aaaa."}), 400

    # ── Resolve time ──
    if time_choice == "now":
        selected_time = datetime.now().strftime("%H:%M:%S")
    elif time_choice == "custom":
        try:
            parsed = datetime.strptime(custom_time, "%H:%M")
            selected_time = parsed.strftime("%H:%M:%S")
        except ValueError:
            return jsonify({"error": "Format d'heure invalide. Utilisez HH:MM."}), 400
    else:
        selected_time = time_choice + ":00"

    # ── Parse & validate IPP list ──
    cleaned = re.sub(r"\s+", "", ipp_raw)
    ipp_list = [i for i in cleaned.split(",") if i]
    if not ipp_list:
        return jsonify({"error": "Aucun IPP fourni."}), 400
    _IPP_RE = re.compile(r"^\d{1,20}$")
    invalid = [i for i in ipp_list if not _IPP_RE.match(i)]
    if invalid:
        return jsonify({"error": f"IPP invalide(s) : {', '.join(invalid[:5])}. Seuls les chiffres sont acceptés."}), 400

    if not sel_bookings:
        sel_bookings = list(MENU_CONFIG.keys())

    # ── Create job record ──
    job_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    job = {
        "id":        job_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ipp_list":  ipp_list,
        "date":      selected_date,
        "time":      selected_time,
        "bookings":  sel_bookings,
        "username":  username,
        "status":    "running",
        "error":     None,
    }
    _add_job(job)

    # ── Run automation in a background thread ──
    def _bg():
        try:
            run_job(ipp_list, selected_date, selected_time, sel_bookings, username, password)
            _update_job(job_id, "completed")
        except Exception as exc:
            _update_job(job_id, "failed", str(exc))

    threading.Thread(target=_bg, daemon=True).start()

    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/jobs")
def jobs_endpoint():
    with _jobs_lock:
        recent = list(reversed(_jobs[-10:]))
    return jsonify(recent)


@app.route("/toggle-headless", methods=["POST"])
def toggle_headless_endpoint():
    _script_mod.HEADLESS = not _script_mod.HEADLESS
    return jsonify({"headless": _script_mod.HEADLESS})


@app.route("/fetch-patients", methods=["POST"])
def fetch_patients_endpoint():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    filter_option = request.form.get("filter", "today")
    sel_bookings = request.form.getlist("bookings")

    if not username:
        return jsonify({"error": "Nom d'utilisateur requis."}), 400
    if not password:
        return jsonify({"error": "Mot de passe requis."}), 400
    if filter_option not in ("today", "yesterday"):
        return jsonify({"error": "Option de filtre invalide."}), 400

    # Derive booking codes from selected analyses
    booking_codes = list({MENU_CONFIG[b]["code"] for b in sel_bookings if b in MENU_CONFIG})
    if not booking_codes:
        booking_codes = ["CYTO"]

    try:
        patients = fetch_patients_without_bilans(username, password, filter_option, booking_codes)
        return jsonify({"patients": patients})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ──────────────────────────────────────────────
# Entry-point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    _load_jobs()

    # Try to determine a LAN IP for convenience
    lan_ip = "localhost"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
    except Exception:
        pass

    print()
    print("=" * 55)
    print("  HOSIX Web Interface démarré !")
    print("  Accédez depuis n'importe quel appareil :")
    print(f"    → http://{lan_ip}:5000")
    print(f"    → http://localhost:5000")
    print("  Appuyez sur Ctrl+C pour arrêter le serveur.")
    print("=" * 55)
    print()

    app.run(host="0.0.0.0", port=5000, debug=False)
