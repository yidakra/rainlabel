import React, { useState } from 'react';

function LabelsList({ labels, searchQuery, onSearchChange, onLabelClick, activeLabels }) {
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
      <input
        type="text"
        className="search-bar"
        placeholder="Search labels..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
      />
      
      <div className="labels-list">
        {labels.length === 0 ? (
          <p>No labels found</p>
        ) : (
          labels.map((label, index) => (
            <div key={label.id || `${label.description}-${index}`} className={`label-item ${isLabelActive(label) ? 'active' : ''}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => toggleExpand(index)}>
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
                <div style={{ marginTop: 6, paddingLeft: 8 }}>
                  {label.segments.map((seg, sidx) => (
                    <div key={sidx} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <button onClick={() => onLabelClick({ ...label, segments: [{ start: seg.start, end: seg.end }] })}>
                        {formatTime(seg.start)} - {formatTime(seg.end)}
                      </button>
                      {typeof seg.confidence === 'number' && (
                        <span style={{ color: '#666', fontSize: '12px' }}>{(seg.confidence * 100).toFixed(1)}%</span>
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


