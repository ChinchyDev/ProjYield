import React, { useState, useEffect } from 'react';
import { getZoneDecisions } from '../api';
import { confWord, confColour } from '../utils/labels';
import './RecommendationModal.css';

export default function RecommendationModal({ zone, onClose }) {
  const [state, setState] = useState('loading'); // loading | ready | error
  const [actions, setActions] = useState([]);
  const [view, setView]   = useState('top'); // top | others

  const zlbl = zone.zone_label || zone.zone_id;

  useEffect(() => {
    getZoneDecisions(zone.zone_id)
      .then(({ data }) => {
        setActions(data.top_actions || []);
        setState('ready');
      })
      .catch(() => setState('error'));
  }, [zone.zone_id]);

  const top  = actions[0];
  const rest = actions.slice(1, 5); // max 4 others (Miller's Law)

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true"
         aria-label={`Recommendation for Zone ${zlbl}`}>
      <div className="modal-sheet">
        {/* Header */}
        <div className="modal-header">
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
          <h2>💡 Zone {zlbl}</h2>
          <p>YieldVision Recommendation</p>
        </div>

        <div className="modal-body">
          {/* Loading */}
          {state === 'loading' && (
            <div className="loader">
              <span className="loader-icon">🌱</span>
              <p>Analysing your farm data…</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--slate)' }}>This takes about 10–15 seconds</p>
            </div>
          )}

          {/* Error — plain language (Nielsen: error messages) */}
          {state === 'error' && (
            <div className="empty-state">
              <span className="empty-state-icon">📡</span>
              <h3>We couldn't load the recommendation</h3>
              <p>Check your internet connection and try again.</p>
              <button className="btn btn--primary" style={{ marginTop: 16 }}
                      onClick={() => { setState('loading'); getZoneDecisions(zone.zone_id).then(({ data }) => { setActions(data.top_actions || []); setState('ready'); }).catch(() => setState('error')); }}>
                Try Again
              </button>
            </div>
          )}

          {/* Ready — top recommendation */}
          {state === 'ready' && !actions.length && (
            <div className="empty-state">
              <span className="empty-state-icon">🌾</span>
              <p>No recommendations available yet.</p>
            </div>
          )}

          {state === 'ready' && actions.length > 0 && view === 'top' && top && (
            <TopRecommendation
              action={top}
              rest={rest}
              onShowOthers={() => setView('others')}
              onAccept={onClose}
              onDecline={onClose}
            />
          )}

          {state === 'ready' && view === 'others' && (
            <OtherOptions
              actions={rest}
              onBack={() => setView('top')}
              onChoose={onClose}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function TopRecommendation({ action, rest, onShowOthers, onAccept, onDecline }) {
  const [showDetails, setShowDetails] = useState(false);

  const actionLbl = action.action_label || 'No action';
  const benefit   = action.net_benefit_usd || 0;
  const conf      = action.confidence || 0;
  const risk      = action.risk || 'unknown';
  const rec       = action.recommendation || {};
  const recText   = typeof rec === 'string' ? rec : rec.text || '';
  const riskColour = { low: 'var(--green-lt)', medium: 'var(--amber)', high: 'var(--red)' }[risk] || 'var(--slate)';

  return (
    <>
      {/* Main recommendation card — conversational, plain language */}
      <div className="rec-card">
        <div className="rec-card__label">💡 Recommendation</div>
        <h3 className="rec-card__title">{actionLbl}</h3>
        {recText && <p className="rec-card__reason">{recText}</p>}
      </div>

      {/* Expected result — summary first, details behind toggle */}
      <div className="expected-results">
        <div className="expected-row">
          <span>📈 Estimated benefit</span>
          <span className="expected-value">~KSh {(benefit * 130).toFixed(0)}</span>
        </div>

        <div className="expected-row">
          <span>📊 Confidence</span>
          <div className="conf-bar-wrap">
            <div className="conf-bar-bg">
              <div className="conf-bar-fill"
                   style={{ width: `${conf * 100}%`, background: confColour(conf) }} />
            </div>
            <span className="conf-label" style={{ color: confColour(conf) }}>
              {confWord(conf)}
            </span>
          </div>
        </div>

        <div className="expected-row">
          <span>⚠️ Risk level</span>
          <span className="expected-value" style={{ color: riskColour }}>
            {risk.toUpperCase()}
          </span>
        </div>

        {/* Progressive disclosure — technical details */}
        <button className="toggle-numbers-btn" onClick={() => setShowDetails(v => !v)}>
          {showDetails ? '▲ Hide technical details' : '▼ Show technical details'}
        </button>

        {showDetails && (
          <div className="tech-details">
            <p>Expected yield: <strong>{action.expected_yield_kg?.toFixed(2)} kg</strong></p>
            <p>Net benefit: <strong>${benefit.toFixed(2)} USD</strong></p>
            <p>ROI: <strong>{action.roi?.toFixed(2)}×</strong></p>
            <p style={{ fontSize: '0.78rem', color: 'var(--slate)', marginTop: 8 }}>
              Based on Monte Carlo simulation (10,000 runs) with your zone's sensor data.
            </p>
          </div>
        )}
      </div>

      {/* Three choices — User Agency (Norman) */}
      <div className="rec-choices">
        <button className="btn btn--primary" onClick={onAccept}>
          ✅ Yes, I will do this
        </button>

        {rest.length > 0 && (
          <button className="btn btn--secondary" onClick={onShowOthers}>
            🔄 Show me other options
          </button>
        )}

        <button className="btn btn--ghost" onClick={onDecline}>
          ❌ I can't do this today
        </button>
      </div>
    </>
  );
}

function OtherOptions({ actions, onBack, onChoose }) {
  return (
    <>
      <button className="back-btn" onClick={onBack}>← Back to top recommendation</button>
      <p className="section-label">Other options for this zone</p>

      {actions.map((action, i) => {
        const benefit = action.net_benefit_usd || 0;
        const risk    = action.risk || 'unknown';
        const riskColour = { low: 'var(--green-lt)', medium: 'var(--amber)', high: 'var(--red)' }[risk] || 'var(--slate)';
        return (
          <div key={i} className="other-option-card card">
            <div className="card-body">
              <h3>{action.action_label}</h3>
              <div className="other-option-meta">
                <span>Benefit: ~KSh {(benefit * 130).toFixed(0)}</span>
                <span style={{ color: riskColour }}>Risk: {risk.toUpperCase()}</span>
              </div>
              <button className="btn btn--primary" style={{ marginTop: 10 }}
                      onClick={onChoose}>
                Choose this →
              </button>
            </div>
          </div>
        );
      })}
    </>
  );
}
