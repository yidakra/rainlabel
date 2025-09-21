import os
import json
from pathlib import Path
from google.cloud import videointelligence_v1 as videointelligence

# Resolve project root and videos directory; allow env override
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEOS = (PROJECT_ROOT / "videos").as_posix()
VIDEO_DIR = os.environ.get("VIDEO_DIR", DEFAULT_VIDEOS)

client = videointelligence.VideoIntelligenceServiceClient()

FEATURES = [
    videointelligence.Feature.LABEL_DETECTION,
    videointelligence.Feature.SHOT_CHANGE_DETECTION,
    videointelligence.Feature.EXPLICIT_CONTENT_DETECTION,
    videointelligence.Feature.OBJECT_TRACKING,
    videointelligence.Feature.PERSON_DETECTION,
    videointelligence.Feature.FACE_DETECTION,
    videointelligence.Feature.TEXT_DETECTION,
    videointelligence.Feature.LOGO_RECOGNITION,
    videointelligence.Feature.SPEECH_TRANSCRIPTION,
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
        # Enrich results using detection configs; be compatible across library versions
        vc_kwargs = {}

        # Label detection config (prefer SHOT_AND_FRAME mode if enum is available)
        try:
            ld_kwargs = {"stationary_camera": False, "model": "builtin/latest"}
            try:
                # Enum may be generated at module level in some versions
                ld_kwargs["label_detection_mode"] = videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE
            except Exception:
                # Fallback: skip setting label_detection_mode if enum path not present
                pass
            vc_kwargs["label_detection_config"] = videointelligence.LabelDetectionConfig(**ld_kwargs)
        except Exception:
            pass

        # Person detection config (include detailed attributes where supported)
        try:
            vc_kwargs["person_detection_config"] = videointelligence.PersonDetectionConfig(
                include_bounding_boxes=True,
                include_pose_landmarks=True,
                include_attributes=True,
            )
        except Exception:
            pass

        # Text detection config (language hints; omit model if unsupported)
        try:
            vc_kwargs["text_detection_config"] = videointelligence.TextDetectionConfig(
                language_hints=["ru", "en"],
            )
        except Exception:
            pass

        # Speech transcription config (prefer Russian, allow English as alternative)
        try:
            vc_kwargs["speech_transcription_config"] = videointelligence.SpeechTranscriptionConfig(
                language_code="ru-RU",
                alternative_language_codes=["en-US"],
                enable_automatic_punctuation=True,
                enable_speaker_diarization=True,
                diarization_speaker_count=2,
                enable_word_time_offsets=True,
            )
        except Exception:
            pass

        request_payload = {
            "features": FEATURES,
            "input_content": input_content,
        }
        if vc_kwargs:
            request_payload["video_context"] = videointelligence.VideoContext(**vc_kwargs)

        operation = client.annotate_video(request=request_payload)
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
        "explicit_content": [],
        "text": [],
        "logos": [],
        "speech": [],
        "shots": [],
    }

    # Segment-level labels
    try:
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
    except Exception:
        pass

    # Object tracking
    try:
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
    except Exception:
        pass

    # Person detection
    try:
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
                        # Compatible extraction of landmark type across versions
                        landmark_type_name = None
                        try:
                            enum_val = getattr(landmark, "type_", None) or getattr(landmark, "type", None)
                            landmark_type_name = getattr(enum_val, "name", str(enum_val)) if enum_val is not None else None
                        except Exception:
                            landmark_type_name = None
                        item = {
                            "position": {
                                "x": landmark.point.x,
                                "y": landmark.point.y,
                            },
                            "confidence": getattr(landmark, "confidence", 0.0),
                        }
                        if landmark_type_name is not None:
                            item["type"] = landmark_type_name
                        lm.append(item)
                    track_data["landmarks"].append({
                        "time": time_offset_to_sec(timestamped_obj.time_offset),
                        "landmarks": lm
                    })
                person_data["tracks"].append(track_data)
            output["persons"].append(person_data)
    except Exception:
        pass

    # Explicit content
    try:
        for frame in annotations.explicit_annotation.frames:
            output["explicit_content"].append({
                "time": time_offset_to_sec(frame.time_offset),
                "pornography_likelihood": frame.pornography_likelihood.name
            })
    except Exception:
        pass

    # Shot change annotations
    try:
        for shot in annotations.shot_annotations:
            start = time_offset_to_sec(shot.start_time_offset)
            end = time_offset_to_sec(shot.end_time_offset)
            output["shots"].append({"start": start, "end": end})
    except Exception:
        pass

    # Text (OCR) annotations
    try:
        for text_ann in annotations.text_annotations:
            item = {
                "text": getattr(text_ann, "text", ""),
                "segments": []
            }
            for seg in text_ann.segments:
                start = time_offset_to_sec(seg.segment.start_time_offset)
                end = time_offset_to_sec(seg.segment.end_time_offset)
                item["segments"].append({
                    "start": start,
                    "end": end,
                    "confidence": getattr(seg, "confidence", 0.0),
                })
            output["text"].append(item)
    except Exception:
        pass

    # Logo recognition annotations
    try:
        for logo in annotations.logo_recognition_annotations:
            entry = {
                "entity": getattr(logo.entity, "description", ""),
                "tracks": []
            }
            for tr in logo.tracks:
                entry["tracks"].append({
                    "segment": {
                        "start": time_offset_to_sec(tr.segment.start_time_offset),
                        "end": time_offset_to_sec(tr.segment.end_time_offset),
                    },
                    "confidence": getattr(tr, "confidence", 0.0),
                })
            output["logos"].append(entry)
    except Exception:
        pass

    # Speech transcription annotations
    try:
        for st in annotations.speech_transcriptions:
            for alt in getattr(st, "alternatives", []):
                speech_item = {
                    "transcript": getattr(alt, "transcript", ""),
                    "confidence": getattr(alt, "confidence", 0.0),
                    "words": []
                }
                for w in getattr(alt, "words", []):
                    speech_item["words"].append({
                        "word": getattr(w, "word", ""),
                        "start": time_offset_to_sec(getattr(w, "start_time", 0)),
                        "end": time_offset_to_sec(getattr(w, "end_time", 0)),
                    })
                output["speech"].append(speech_item)
    except Exception:
        pass

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


