import React, { useState, useEffect } from 'react';
import axios from 'axios';
import VideoPlayer from './components/VideoPlayer';
import VideoList from './components/VideoList';

function App() {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchVideos();
  }, []);

  useEffect(() => {
    // Handle browser back/forward buttons
    const handlePopState = (event) => {
      const videoName = event.state?.videoName;
      if (videoName) {
        const video = videos.find(v => v.name === videoName);
        if (video) {
          setSelectedVideo(video);
        }
      } else {
        setSelectedVideo(null);
      }
    };

    window.addEventListener('popstate', handlePopState);
    
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [videos]);

  useEffect(() => {
    // Check if we're returning to a specific video from URL
    const urlParams = new URLSearchParams(window.location.search);
    const videoParam = urlParams.get('video');
    if (videoParam && videos.length > 0) {
      const video = videos.find(v => v.name === videoParam);
      if (video) {
        setSelectedVideo(video);
      }
    }
  }, [videos]);

  const fetchVideos = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/videos');
      setVideos(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch videos');
      console.error('Error fetching videos:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleVideoSelect = (video) => {
    setSelectedVideo(video);
    // Push to browser history
    window.history.pushState(
      { videoName: video.name }, 
      `RainLabel - ${video.name}`, 
      `?video=${encodeURIComponent(video.name)}`
    );
  };

  const handleBackToList = () => {
    setSelectedVideo(null);
    // Push to browser history
    window.history.pushState(
      {}, 
      'RainLabel - Video List', 
      window.location.pathname
    );
  };

  if (loading) {
    return (
      <div className="app">
        <div className="header">
          <h1>RainLabel</h1>
          <p>Loading videos...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <div className="header">
          <h1>RainLabel</h1>
          <p style={{ color: 'red' }}>{error}</p>
          <button onClick={fetchVideos}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="header">
        <h1>RainLabel</h1>
        <p>Video Analysis and Labeling Tool</p>
      </div>

      {selectedVideo ? (
        <VideoPlayer 
          video={selectedVideo} 
          onBack={handleBackToList}
        />
      ) : (
        <VideoList 
          videos={videos} 
          onVideoSelect={handleVideoSelect}
        />
      )}
    </div>
  );
}

export default App;


