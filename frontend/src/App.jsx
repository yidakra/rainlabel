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
  };

  const handleBackToList = () => {
    setSelectedVideo(null);
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


