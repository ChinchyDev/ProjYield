import React, { useState, useMemo } from 'react';
import { zoneHealth } from '../utils/labels';
import './Tasks.css';

function buildTasks(zones) {
  const tasks = [];
  const urgent = zones.filter(z => {
    const [st] = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
    return st === 'danger' || st === 'average';
  });

  for (const z of urgent.slice(0, 7)) { // Miller's Law: max 7
    const lbl = z.zone_label || z.zone_id;
    const [st] = zoneHealth(z.soil_moisture_20cm, z.nitrogen_ppm, z.ph_level);
    const m = z.soil_moisture_20cm, n = z.nitrogen_ppm, ph = z.ph_level;
    const priority = st === 'danger' ? 'high' : 'medium';
    const priorityIcon = st === 'danger' ? '🔴' : '🟡';

    if (m != null && m < 30) {
      tasks.push({ id: z.zone_id + '_water', priority, priorityIcon, verb: 'Water', zone: lbl, crop: z.soil_type || 'your crop', duration: '~20 mins', zone_data: z });
    } else if (n != null && n < 80) {
      tasks.push({ id: z.zone_id + '_fert',  priority, priorityIcon, verb: 'Fertilise', zone: lbl, crop: z.soil_type || 'your crop', duration: '~30 mins', zone_data: z });
    } else if (ph != null && (ph < 6.0 || ph > 7.8)) {
      tasks.push({ id: z.zone_id + '_ph',    priority, priorityIcon, verb: 'Fix soil acidity —', zone: lbl, crop: '', duration: '~15 mins', zone_data: z });
    }
  }
  return tasks;
}

export default function Tasks({ zones, goToZone }) {
  const tasks = useMemo(() => buildTasks(zones), [zones]);
  const [done, setDone] = useState({});
  const [celebrated, setCelebrated] = useState(false);

  const doneCount  = Object.values(done).filter(Boolean).length;
  const totalCount = tasks.length;
  const progress   = totalCount > 0 ? doneCount / totalCount : 0;

  const toggleDone = (id) => {
    setDone(prev => {
      const next = { ...prev, [id]: !prev[id] };
      const nowDone = Object.values(next).filter(Boolean).length;
      if (nowDone === totalCount && totalCount > 0 && !celebrated) {
        setCelebrated(true);
      }
      return next;
    });
  };

  return (
    <div className="screen tasks-screen">
      <div className="page-header">
        <h1>📋 Today's Tasks</h1>
        <p>{doneCount} of {totalCount} done</p>
      </div>

      {/* Progress bar */}
      <div className="tasks-progress">
        <div className="tasks-progress__bar-bg">
          <div className="tasks-progress__bar-fill"
               style={{ width: `${progress * 100}%` }} />
        </div>
        <span className="tasks-progress__label">{Math.round(progress * 100)}%</span>
      </div>

      {/* Celebration */}
      {celebrated && totalCount > 0 && (
        <div className="celebration-banner" role="status" aria-live="polite">
          🎉 You completed all {totalCount} tasks today! Your crops thank you.
        </div>
      )}

      {/* Task list */}
      {tasks.length === 0 && zones.length > 0 && (
        <div className="empty-state">
          <span className="empty-state-icon">🌾</span>
          <h3>No urgent tasks today!</h3>
          <p>All your zones look healthy. Great work!</p>
        </div>
      )}

      {zones.length === 0 && (
        <div className="loader">
          <span className="loader-icon">🌱</span>
          <p>Loading your farm data…</p>
        </div>
      )}

      <div className="task-list">
        {tasks.map((task) => (
          <div key={task.id}
               className={`task-card${done[task.id] ? ' task-card--done' : ''} task-card--${task.priority}`}>
            <label className="task-card__inner" htmlFor={`task-${task.id}`}>
              {/* Custom checkbox (large — Fitts's Law) */}
              <div className="task-checkbox-wrap">
                <input
                  type="checkbox"
                  id={`task-${task.id}`}
                  className="task-checkbox-input"
                  checked={!!done[task.id]}
                  onChange={() => toggleDone(task.id)}
                  aria-label={`${task.verb} Zone ${task.zone}`}
                />
                <div className={`task-checkbox${done[task.id] ? ' task-checkbox--checked' : ''}`}
                     aria-hidden="true">
                  {done[task.id] ? '✓' : ''}
                </div>
              </div>

              {/* Content */}
              <div className="task-content">
                <div className="task-title">
                  <span className="task-priority-icon">{task.priorityIcon}</span>
                  <span>{task.verb}</span>
                  <span className="task-zone"> Zone {task.zone}</span>
                </div>
                <div className="task-meta">
                  <span>⏱ {task.duration}</span>
                </div>
              </div>
            </label>

            {/* Details button */}
            <button
              className="task-details-btn"
              onClick={() => goToZone(task.zone_data)}
              aria-label={`See details for Zone ${task.zone}`}
            >
              Details →
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
