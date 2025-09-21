import os
import json
from pathlib import Path
from google.cloud import videointelligence_v1 as videointelligence

# Resolve videos directory relative to repository root, allow env override
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_VIDEOS = (BASE_DIR / "videos").as_posix()
VIDEO_DIR = os.environ.get("VIDEO_DIR", DEFAULT_VIDEOS)

client = videointelligence.VideoIntelligenceServiceClient()

FEATURES = [
    videointelligence.Feature.LABEL_DETECTION,
    videointelligence.Feature.SHOT_CHANGE_DETECTION,
    videointelligence.Feature.EXPLICIT_CONTENT_DETECTION,
    videointelligence.Feature.OBJECT_TRACKING,
    videointelligence.Feature.PERSON_DETECTION
]

MAX_UPLOAD_BYTES = 524288000  # 500 MB API limit

def time_offset_to_sec(time_offset):
    # Handle protobuf Duration (seconds+nanos) and potential datetime.timedelta
    if hasattr(time_offset, "seconds") and hasattr(time_offset, "nanos"):
        return float(time_offset.seconds) + float(time_offset.nanos) / 1e9
    if hasattr(time_offset, "total_seconds"):
        return float(time_offset.total_seconds())
    if hasattr(time_offset, "seconds") and hasattr(time_offset, "microseconds"):
        return float(time_offset.seconds) + float(time_offset.microseconds) / 1e6
    return 0.0

def analyze_video(file_path):
    with open(file_path, "rb") as f:
        input_content = f.read()

    try:
        operation = client.annotate_video(
            request={
                "features": FEATURES,
                "input_content": input_content
            }
        )
        print(f"Processing {file_path}...")
        result = operation.result(timeout=600)
    except Exception as e:
        print(f"API error processing {file_path}: {e}")
        raise

    annotations = result.annotation_results[0]

    output = {
        "video_file": os.path.basename(file_path),
        "labels": [],
        "objects": [],
        "persons": [],
        "explicit_content": []
    }

    # Segment-level labels
    for label in annotations.segment_label_annotations:
        for seg in label.segments:
            start = time_offset_to_sec(seg.segment.start_time_offset)
            end = time_offset_to_sec(seg.segment.end_time_offset)
            output["labels"].append({
                "description": label.entity.description,
                "category": [cat.description for cat in label.category_entities],
                "confidence": seg.confidence,
                "start_time": start,
                "end_time": end
            })

    # Object tracking
    for obj in annotations.object_annotations:
        track = {
            "entity": obj.entity.description,
            "confidence": obj.confidence,
            "frames": []
        }
        for frame in obj.frames:
            frame_data = {
                "time": time_offset_to_sec(frame.time_offset),
                "bbox": {
                    "left": frame.normalized_bounding_box.left,
                    "top": frame.normalized_bounding_box.top,
                    "right": frame.normalized_bounding_box.right,
                    "bottom": frame.normalized_bounding_box.bottom,
                }
            }
            track["frames"].append(frame_data)
        output["objects"].append(track)

    # Person detection
    for person in annotations.person_detection_annotations:
        person_data = {"tracks": []}
        for track in person.tracks:
            track_data = {
                "segment": {
                    "start_time": time_offset_to_sec(track.segment.start_time_offset),
                    "end_time": time_offset_to_sec(track.segment.end_time_offset),
                },
                "landmarks": []
            }
            for timestamped_obj in track.timestamped_objects:
                lm = []
                for landmark in timestamped_obj.landmarks:
                    lm.append({
                        "type": landmark.type_.name,
                        "position": {
                            "x": landmark.point.x,
                            "y": landmark.point.y,
                        },
                        "confidence": landmark.confidence,
                    })
                track_data["landmarks"].append({
                    "time": time_offset_to_sec(timestamped_obj.time_offset),
                    "landmarks": lm
                })
            person_data["tracks"].append(track_data)
        output["persons"].append(person_data)

    # Explicit content
    for frame in annotations.explicit_annotation.frames:
        output["explicit_content"].append({
            "time": time_offset_to_sec(frame.time_offset),
            "pornography_likelihood": frame.pornography_likelihood.name
        })

    # Save to JSON
    json_file = file_path + ".json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved annotations to {json_file}")

if __name__ == "__main__":
    for fname in os.listdir(VIDEO_DIR):
        if fname.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            file_path = os.path.join(VIDEO_DIR, fname)
            try:
                try:
                    size_bytes = os.path.getsize(file_path)
                    if size_bytes > MAX_UPLOAD_BYTES:
                        print(f"Skipping {fname}: size {size_bytes} exceeds 500MB limit")
                        continue
                except OSError:
                    pass
                analyze_video(file_path)
            except Exception as e:
                print(f"Error with {fname}: {e}")