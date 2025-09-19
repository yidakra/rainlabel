import React from 'react';

function ActiveLabelPanel({ activeLabels, currentTime }) {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getActiveSegment = (label) => {
    if (!label.segments) return null;
    return label.segments.find(segment => 
      currentTime >= segment.start && currentTime <= segment.end
    );
  };

  return (
    <div className="active-label-panel">
      <h3>Active Labels</h3>
      <div><strong>Time:</strong> {formatTime(currentTime)}</div>
      
      {activeLabels.length === 0 ? (
        <p>No labels active at current time</p>
      ) : (
        <div className="active-labels-list">
          {activeLabels.map((label, index) => {
            const activeSegment = getActiveSegment(label);
            return (
              <div key={index} className="label-item active">
                <div><strong>{label.description}</strong></div>
                <div>Confidence: {(label.confidence * 100).toFixed(1)}%</div>
                {activeSegment && (
                  <div>
                    Segment: {formatTime(activeSegment.start)} - {formatTime(activeSegment.end)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      
      <div style={{ marginTop: '15px', fontSize: '12px', color: '#666' }}>
        <div>Labels shown here are currently visible in the video</div>
        <div>Updates automatically as video plays</div>
      </div>
    </div>
  );
}

export default ActiveLabelPanel;