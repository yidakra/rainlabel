import React from 'react';

function InsightsPanel({ metadata, currentTime, duration }) {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60) || 0;
    const secs = Math.floor(seconds % 60) || 0;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  const activeLabels = (metadata?.labels || []).filter((label) =>
    (label.segments || []).some((s) => currentTime >= s.start && currentTime <= s.end)
  );

  const activeLogos = (metadata?.logos || []).filter((logo) =>
    (logo.tracks || []).some((t) => currentTime >= (t.segment?.start ?? 0) && currentTime <= (t.segment?.end ?? 0))
  );

  const currentShot = (() => {
    for (const shot of metadata?.shots || []) {
      const s = clamp(shot.start ?? 0, 0, duration || Infinity);
      const e = clamp(shot.end ?? 0, 0, duration || Infinity);
      if (currentTime >= s && currentTime <= e) return { start: s, end: e };
    }
    return null;
  })();


  const activeObjects = (() => {
    const items = [];
    for (const obj of metadata?.objects || []) {
      // Find the closest frame to current time
      let closestFrame = null;
      let minTimeDiff = Infinity;
      
      for (const frame of obj.frames || []) {
        const frameTime = frame.time ?? 0;
        const timeDiff = Math.abs(currentTime - frameTime);
        
        // Only consider frames within 0.5 seconds of current time
        if (timeDiff <= 0.5 && timeDiff < minTimeDiff) {
          minTimeDiff = timeDiff;
          closestFrame = frame;
        }
      }
      
      if (closestFrame) {
        items.push({
          entity: obj.entity,
          confidence: obj.confidence,
          time: closestFrame.time,
          bbox: closestFrame.bbox
        });
      }
    }
    return items.slice(0, 6);
  })();

  const speechSnippet = (() => {
    // Check if speech data exists at all
    if (!metadata?.speech || metadata.speech.length === 0) {
      return null; // No speech data available
    }
    
    // Collect words within ±5s around current time
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

  const hasSpeechData = metadata?.speech && metadata.speech.length > 0;

  const explicitAtTime = (() => {
    // Show last explicit frame before time
    const frames = metadata?.explicit_content || [];
    let last = null;
    for (const f of frames) {
      if ((f.time ?? 0) <= currentTime) last = f;
    }
    return last;
  })();

  return (
    <div className="active-label-panel">
      <h3>Insights</h3>
      <div><strong>Time:</strong> {formatTime(currentTime)}</div>


      <section style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Detected Objects</div>
        {activeObjects.length === 0 ? (
          <div style={{ color: '#666' }}>None</div>
        ) : (
          activeObjects.map((obj, i) => (
            <div key={i} className="label-item">
              <div><strong>{obj.entity}</strong></div>
              <div style={{ fontSize: 12, color: '#666' }}>
                Confidence: {(obj.confidence * 100).toFixed(1)}% @ {formatTime(obj.time)}
              </div>
            </div>
          ))
        )}
      </section>


      <section style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Speech</div>
        {!hasSpeechData ? (
          <div style={{ color: '#666' }}>No speech transcription available for this video</div>
        ) : speechSnippet ? (
          <div className="label-item">{speechSnippet}</div>
        ) : (
          <div style={{ color: '#666' }}>No transcript near this time</div>
        )}
      </section>

      <section style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Logos</div>
        {activeLogos.length === 0 ? (
          <div style={{ color: '#666' }}>None</div>
        ) : (
          activeLogos.map((lg, i) => (
            <div key={i} className="label-item"><strong>{lg.entity}</strong></div>
          ))
        )}
      </section>

      <section style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Shot</div>
        {currentShot ? (
          <div className="label-item">{formatTime(currentShot.start)} - {formatTime(currentShot.end)}</div>
        ) : (
          <div style={{ color: '#666' }}>Unknown</div>
        )}
      </section>

      {explicitAtTime && (
        <section style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Explicit Content</div>
          <div className="label-item" style={{ fontSize: 12 }}>
            Likelihood: {explicitAtTime.pornography_likelihood}
          </div>
        </section>
      )}

      <div style={{ marginTop: '15px', fontSize: '12px', color: '#666' }}>
        Updates automatically as video plays
      </div>
    </div>
  );
}

export default InsightsPanel;


