import React from 'react';

function VideoList({ videos, onVideoSelect }) {
  if (videos.length === 0) {
    return (
      <div className="video-list">
        <div className="video-card">
          <h3>No videos found</h3>
          <p>Add some video files to the videos directory to get started.</p>
          <p>Supported formats: MP4, AVI, MOV, MKV, WebM</p>
        </div>
      </div>
    );
  }

  return (
    <div className="video-list">
      {videos.map((video) => (
        <div 
          key={video.name} 
          className="video-card"
          onClick={() => onVideoSelect(video)}
        >
          <h3>{video.name}</h3>
          <p><strong>File:</strong> {video.filename}</p>
          <p><strong>Size:</strong> {(video.size / (1024 * 1024)).toFixed(2)} MB</p>
          <p><strong>Analysis:</strong> {video.has_metadata ? '✓ Available' : '✗ Not analyzed'}</p>
        </div>
      ))}
    </div>
  );
}

export default VideoList;