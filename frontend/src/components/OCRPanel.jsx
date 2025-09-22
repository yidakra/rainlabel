import React from 'react';

function OCRPanel({ metadata, currentTime }) {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60) || 0;
    const secs = Math.floor(seconds % 60) || 0;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const activeTexts = (() => {
    const items = [];
    for (const t of metadata?.text || []) {
      for (const seg of t.segments || []) {
        const s = seg.start ?? 0;
        const e = seg.end ?? 0;
        if (currentTime >= s && currentTime <= e) {
          items.push({ text: t.text, start: s, end: e, confidence: seg.confidence });
          break;
        }
      }
    }
    return items.slice(0, 8); // Show more items since this has its own panel
  })();

  return (
    <div className="ocr-panel">
      <h3>On-Screen Text (OCR)</h3>
      {activeTexts.length === 0 ? (
        <div style={{ color: '#666', fontSize: '14px' }}>No text detected at current time</div>
      ) : (
        <div className="ocr-texts">
          {activeTexts.map((t, i) => (
            <div key={i} className="ocr-item">
              <div className="ocr-text">"{t.text}"</div>
              <div className="ocr-time">{formatTime(t.start)} - {formatTime(t.end)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default OCRPanel;
