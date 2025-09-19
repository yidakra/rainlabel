import React from 'react';

function LabelsList({ labels, searchQuery, onSearchChange, onLabelClick, activeLabels }) {
  const isLabelActive = (label) => {
    return activeLabels.some(activeLabel => activeLabel.description === label.description);
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
            <div
              key={index}
              className={`label-item ${isLabelActive(label) ? 'active' : ''}`}
              onClick={() => onLabelClick(label)}
            >
              <div><strong>{label.description}</strong></div>
              <div>Confidence: {(label.confidence * 100).toFixed(1)}%</div>
              <div>
                Segments: {label.segments ? label.segments.length : 0}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default LabelsList;