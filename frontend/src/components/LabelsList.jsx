import React, { useState } from 'react';

function LabelsList({ labels, onLabelClick, activeLabels }) {
  const [expanded, setExpanded] = useState({});

  const isLabelActive = (label) => {
    return activeLabels.some(activeLabel => activeLabel.description === label.description);
  };

  const toggleExpand = (key) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="labels-panel">
      <h3>Labels</h3>
      <div className="labels-list">
        {labels.length === 0 ? (
          <p>No labels found</p>
        ) : (
          labels.map((label, index) => (
            <div key={`${label.description}-${index}`} className={`label-item${isLabelActive(label) ? ' active' : ''}`}>
              <div
                style={{ display: 'flex', justifyContent: 'space-between', cursor: 'pointer' }}
                onClick={() => toggleExpand(index)}
                onKeyDown={(e) => e.key === 'Enter' && toggleExpand(index)}
                tabIndex={0}
                role="button"
                aria-expanded={expanded[index] || false}
                aria-controls={`label-segments-${index}`}
              >
                <div>
                  <strong>{label.description}</strong>
                  {label.categories && label.categories.length > 0 && (
                    <span style={{ marginLeft: 8, color: '#666', fontSize: '12px' }}>
                      [{label.categories.join(', ')}]
                    </span>
                  )}
                </div>
                <div>Conf: {(label.confidence * 100).toFixed(1)}%</div>
              </div>
              {expanded[index] && label.segments && label.segments.length > 0 && (
                <div id={`label-segments-${index}`} style={{ marginTop: 6, paddingLeft: 8 }}>
                  {label.segments.map((seg, segIdx) => (
                    <div key={segIdx} style={{ marginBottom: 4 }}>
                      <button
                        onClick={() => onLabelClick({ ...label, segments: [{ start: seg.start, end: seg.end }] })}
                        aria-label={`Play segment from ${formatTime(seg.start)} to ${formatTime(seg.end)} for ${label.description}`}
                      >
                        {formatTime(seg.start)} - {formatTime(seg.end)}
                      </button>
                      {typeof seg.confidence === 'number' && (
                        <span style={{ marginLeft: 8, color: '#666', fontSize: '12px' }}>
                          {(seg.confidence * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default LabelsList;


