import React from 'react';

function OCRPanel({ metadata, currentTime }) {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60) || 0;
    const secs = Math.floor(seconds % 60) || 0;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Build a local speech snippet around current time (±5s)
  const speechSnippet = (() => {
    if (!metadata?.speech || metadata.speech.length === 0) return null;
    const windowS = 5;
    const words = [];
    for (const altGroup of metadata.speech) {
      for (const w of altGroup.words || []) {
        const s = w.start ?? 0;
        const e = w.end ?? 0;
        if (s <= currentTime + windowS && e >= currentTime - windowS) {
          words.push({ t: w.word, s });
        }
      }
    }
    words.sort((a, b) => a.s - b.s);
    const snippet = words.map((w) => w.t).join(' ').trim();
    return snippet.length > 0 ? snippet : null;
  })();

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
    return items.slice(0, 8);
  })();

  return (
    <div className="ocr-panel">
      {/* Speech transcript (windowed snippet) */}
      {metadata?.speech && metadata.speech.length > 0 ? (
        speechSnippet ? (
          <div className="label-item">{speechSnippet}</div>
        ) : (
          <div style={{ color: '#666', fontSize: '14px' }}>No transcript near this time</div>
        )
      ) : (
        <div style={{ color: '#666', fontSize: '14px' }}>No speech transcription available for this video</div>
      )}

      {/* OCR texts */}
      <div style={{ fontWeight: 600, marginTop: 12, marginBottom: 6 }}>On-Screen Text (OCR)</div>
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
