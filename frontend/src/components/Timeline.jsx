import React from 'react';

function Timeline({ duration, currentTime, labels, onTimelineClick }) {
  const handleTimelineClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const timelineWidth = rect.width;
    const clickedTime = (clickX / timelineWidth) * duration;
    onTimelineClick(clickedTime);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="timeline-panel">
      <h3>Timeline</h3>
      <div>
        <strong>Current Time:</strong> {formatTime(currentTime)} / {formatTime(duration)}
      </div>
      
      <div 
        className="timeline"
        onClick={handleTimelineClick}
        style={{ cursor: 'pointer' }}
      >
        {/* Current time indicator */}
        <div
          style={{
            position: 'absolute',
            left: `${duration > 0 ? (currentTime / duration) * 100 : 0}%`,
            top: 0,
            width: '2px',
            height: '100%',
            backgroundColor: 'red',
            zIndex: 10
          }}
        />
        
        {/* Label segments */}
        {labels.map((label, labelIndex) => (
          label.segments && label.segments.map((segment, segmentIndex) => {
            const start = Math.max(0, Math.min(duration, segment.start || 0));
            const end = Math.max(0, Math.min(duration, segment.end || 0));
            const widthPct = duration > 0 ? ((end - start) / duration) * 100 : 0;
            if (widthPct <= 0) return null;
            return (
            <div
              key={`${labelIndex}-${segmentIndex}`}
              className="timeline-highlight"
              style={{
                left: `${duration > 0 ? (start / duration) * 100 : 0}%`,
                width: `${widthPct}%`,
                backgroundColor: `hsl(${labelIndex * 137.5 % 360}, 70%, 70%)`,
                opacity: 0.7
              }}
              title={`${label.description} ${(typeof segment.confidence === 'number') ? `(${(segment.confidence * 100).toFixed(0)}%)` : ''}: ${formatTime(start)} - ${formatTime(end)}`}
            />
            );
          })
        ))}
      </div>
      
      <div style={{ marginTop: '10px', fontSize: '12px' }}>
        <div>Click timeline to jump to specific time</div>
        <div>Colored bars represent label segments</div>
      </div>
    </div>
  );
}

export default Timeline;


