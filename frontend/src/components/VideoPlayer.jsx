import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import LabelsList from './LabelsList';
import Timeline from './Timeline';
import InsightsPanel from './InsightsPanel';
import OCRPanel from './OCRPanel';

function VideoPlayer({ video, onBack }) {
  const videoRef = useRef(null);
  const [metadata, setMetadata] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeLabels, setActiveLabels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMetadata();
  }, [video.name]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    updateActiveLabels();
  }, [currentTime, metadata]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchMetadata = async () => {
    try {
      setLoading(true);
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await axios.get(
        `${apiBase}/metadata/${encodeURIComponent(video.name)}`,
        {
          timeout: 10000,
          params: { t: Date.now() },
          headers: { 'Cache-Control': 'no-cache' }
        }
      );
      setMetadata(response.data);
    } catch (err) {
      console.error('Failed to fetch metadata:', err);
      setMetadata({
        video_name: video.name,
        labels: [],
        shots: [],
        objects: [],
        text: [],
        faces: [],
        error: 'Failed to load metadata'
      });
    } finally {
      setLoading(false);
    }
  };

  const updateActiveLabels = () => {
    if (!metadata || !metadata.labels) return;
    
    const active = metadata.labels.filter(label => 
      label.segments && label.segments.some(segment => 
        currentTime >= segment.start && currentTime <= segment.end
      )
    );
    setActiveLabels(active);
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleLabelClick = (label) => {
    if (label.segments && label.segments.length > 0 && videoRef.current) {
      videoRef.current.currentTime = label.segments[0].start;
    }
  };

  const handleTimelineClick = (time) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
  };


  if (loading) {
    return (
      <div>
        <button className="back-button" onClick={onBack}>
          ← Back to Videos
        </button>
        <div className="video-player-container">
          <p>Loading video analysis...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <button className="back-button" onClick={onBack}>
        ← Back to Videos
      </button>

      <div className="video-layout">
        <div className="video-section">
          <div className="video-player-container">
            <h2>{video.name}</h2>
            <video
              ref={videoRef}
              className="video-player"
              controls
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${video.path}`}
            >
              Your browser does not support the video tag.
            </video>
          </div>

          <OCRPanel 
            metadata={metadata}
            currentTime={currentTime}
          />

          {/* Timeline moved to sit below transcript/OCR and span full width */}
          <div className="timeline-wrapper">
            <Timeline 
              duration={duration}
              currentTime={currentTime}
              labels={metadata?.labels || []}
              onTimelineClick={handleTimelineClick}
            />
          </div>
        </div>
        
        <div className="insights-section">
          <InsightsPanel 
            metadata={metadata}
            currentTime={currentTime}
            duration={duration}
          />

          {/* Labels moved under insights panel */}
          <div style={{ marginTop: 15 }}>
            <LabelsList 
              labels={metadata?.labels || []}
              onLabelClick={handleLabelClick}
              activeLabels={activeLabels}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default VideoPlayer;


