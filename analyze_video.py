#!/usr/bin/env python3
"""
Google Cloud Video Intelligence API integration script.
This script analyzes videos and saves the results as JSON metadata.

Requirements:
- Google Cloud Video Intelligence API credentials
- Video files in the videos/ directory

Usage:
    python analyze_video.py <video_filename>
"""

import os
import json
import sys
from pathlib import Path
from google.cloud import videointelligence

def analyze_video(video_path, output_path):
    """Analyze video using Google Cloud Video Intelligence API."""
    
    # Initialize the client
    client = videointelligence.VideoIntelligenceServiceClient()
    
    # Read the video file
    with open(video_path, "rb") as f:
        video_content = f.read()
    
    # Configure the request
    features = [
        videointelligence.Feature.LABEL_DETECTION,
        videointelligence.Feature.SHOT_CHANGE_DETECTION,
        videointelligence.Feature.OBJECT_TRACKING,
        videointelligence.Feature.TEXT_DETECTION,
        videointelligence.Feature.FACE_DETECTION,
    ]
    
    # Submit the request
    operation = client.annotate_video(
        request={
            "features": features,
            "input_content": video_content,
        }
    )
    
    print(f"Processing video: {video_path}")
    result = operation.result(timeout=600)  # Wait up to 10 minutes
    
    # Process the results
    metadata = {
        "video_name": Path(video_path).stem,
        "analysis_timestamp": result.annotation_results[0].input_uri or "local_analysis",
        "labels": [],
        "shots": [],
        "objects": [],
        "text": [],
        "faces": []
    }
    
    # Extract label annotations
    for annotation in result.annotation_results:
        # Label detection
        for label in annotation.segment_label_annotations:
            label_data = {
                "description": label.entity.description,
                "confidence": label.segments[0].confidence if label.segments else 0.0,
                "segments": []
            }
            
            for segment in label.segments:
                start_time = segment.segment.start_time_offset.total_seconds()
                end_time = segment.segment.end_time_offset.total_seconds()
                label_data["segments"].append({
                    "start": start_time,
                    "end": end_time
                })
            
            metadata["labels"].append(label_data)
        
        # Shot change detection
        for shot in annotation.shot_annotations:
            start_time = shot.start_time_offset.total_seconds()
            end_time = shot.end_time_offset.total_seconds()
            metadata["shots"].append({
                "start": start_time,
                "end": end_time
            })
        
        # Object tracking
        for obj in annotation.object_annotations:
            obj_data = {
                "name": obj.entity.description,
                "confidence": obj.confidence,
                "bounding_boxes": []
            }
            
            for frame in obj.frames:
                time_offset = frame.time_offset.total_seconds()
                bbox = frame.normalized_bounding_box
                obj_data["bounding_boxes"].append({
                    "time": time_offset,
                    "left": bbox.left,
                    "top": bbox.top,
                    "right": bbox.right,
                    "bottom": bbox.bottom
                })
            
            metadata["objects"].append(obj_data)
        
        # Text detection
        for text in annotation.text_annotations:
            text_data = {
                "text": text.text,
                "confidence": text.confidence,
                "time_range": {
                    "start": text.segments[0].segment.start_time_offset.total_seconds(),
                    "end": text.segments[0].segment.end_time_offset.total_seconds()
                }
            }
            metadata["text"].append(text_data)
        
        # Face detection
        for face in annotation.face_detection_annotations:
            for track in face.tracks:
                face_data = {
                    "confidence": track.confidence,
                    "time_range": {
                        "start": track.segment.start_time_offset.total_seconds(),
                        "end": track.segment.end_time_offset.total_seconds()
                    }
                }
                metadata["faces"].append(face_data)
    
    # Save the metadata
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Analysis complete. Metadata saved to: {output_path}")
    return metadata

def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze_video.py <video_filename>")
        sys.exit(1)
    
    video_filename = sys.argv[1]
    video_path = Path("videos") / video_filename
    
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    # Create output path
    output_path = Path("metadata") / f"{video_path.stem}.json"
    output_path.parent.mkdir(exist_ok=True)
    
    try:
        analyze_video(str(video_path), str(output_path))
    except Exception as e:
        print(f"Error analyzing video: {e}")
        print("Make sure you have:")
        print("1. Google Cloud credentials configured")
        print("2. Video Intelligence API enabled")
        print("3. Sufficient API quota")
        sys.exit(1)

if __name__ == "__main__":
    main()