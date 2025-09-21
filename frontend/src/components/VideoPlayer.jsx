import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import LabelsList from './LabelsList';
import Timeline from './Timeline';
import ActiveLabelPanel from './ActiveLabelPanel';

function VideoPlayer({ video, onBack }) {
  const videoRef = useRef(null);
  const [metadata, setMetadata] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeLabels, setActiveLabels] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
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
      const response = await axios.get(`/metadata/${encodeURIComponent(video.name)}`, {
        timeout: 10000
      });
      setMetadata(response.data);
    } catch (err) {
      console.warn('Failed to fetch metadata, using sample data');
      // Create sample metadata for demo purposes
      setMetadata({
        video_name: video.name,
        labels: [
          {
            description: "Person",
            confidence: 0.95,
            segments: [
              { start: 0, end: 30 },
              { start: 45, end: 120 }
            ]
          },
          {
            description: "Car",
            confidence: 0.88,
            segments: [
              { start: 15, end: 60 }
            ]
          },
          {
            description: "Building",
            confidence: 0.92,
            segments: [
              { start: 0, end: 180 }
            ]
          }
        ],
        shots: [],
        objects: [],
        text: [],
        faces: []
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

  const filteredLabels = metadata?.labels?.filter(label =>
    label.description.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

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

      <div className="video-controls">
        <LabelsList 
          labels={filteredLabels}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onLabelClick={handleLabelClick}
          activeLabels={activeLabels}
        />
        
        <Timeline 
          duration={duration}
          currentTime={currentTime}
          labels={metadata?.labels || []}
          onTimelineClick={handleTimelineClick}
        />
        
        <ActiveLabelPanel 
          activeLabels={activeLabels}
          currentTime={currentTime}
        />
      </div>
    </div>
  );
}

export default VideoPlayer;


